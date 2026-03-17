import httpx
import io
import os
import json
from dotenv import load_dotenv
from app.graph.state import OrchestratorState, DataPrepStatusEnum

load_dotenv()
DATA_PREP_API_URL = os.getenv("DATA_PREP_API_URL", "http://localhost:8001")


async def call_import(state: OrchestratorState) -> OrchestratorState:
    """
    Étape 1 — POST /import
    Envoie uniquement le CSV.
    L'agent génère le profiling et rend le dataset disponible
    pour tous les agents (NLQ, Insight) immédiatement.
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(state.csv_path, "rb") as f:
                response = await client.post(
                    f"{DATA_PREP_API_URL}/import",
                    files={"dataset": ("dataset.csv", f, "text/csv")}
                )
            print(f"[import] HTTP {response.status_code} — {response.text[:300]}")
            result = response.json()
            state.data_prep_job_id = result.get("job_id", "")
            state.data_prep_status = DataPrepStatusEnum(
                result.get("status", "not_started")
            )
            state.processing_steps.append(
                f"data_prep → import | job_id={state.data_prep_job_id} | "
                f"status={state.data_prep_status.value}"
            )
    except httpx.ConnectError:
        state.data_prep_status = DataPrepStatusEnum.FAILED
        state.errors.append("Data Prep /import unavailable")
        state.processing_steps.append("data_prep → /import ERREUR connexion")
    return state


async def call_prepare_v2(state: OrchestratorState) -> OrchestratorState:
    """
    Étape 2 — POST /prepare/{job_id}
    Envoie la metadata + règles métier.
    L'agent lance l'analyse qualité, détecte les anomalies
    et génère le plan de nettoyage avec analyse d'impact LLM.
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            metadata_bytes = json.dumps(state.metadata).encode("utf-8")
            response = await client.post(
                f"{DATA_PREP_API_URL}/prepare/{state.data_prep_job_id}",
                files={
                    "metadata": (
                        "metadata.json",
                        io.BytesIO(metadata_bytes),
                        "application/json"
                    )
                }
            )
            print(f"[prepare] HTTP {response.status_code} — {response.text[:300]}")
            result = response.json()
            state.data_prep_status = DataPrepStatusEnum(
                result.get("status", "not_started")
            )
            state.data_prep_quality = result.get(
                "quality_before", {}
            ).get("global_scores", {})
            state.processing_steps.append(
                f"data_prep → prepare | status={state.data_prep_status.value} | "
                f"quality={state.data_prep_quality.get('global', 0):.0%}"
            )
    except httpx.ConnectError:
        state.data_prep_status = DataPrepStatusEnum.FAILED
        state.errors.append("Data Prep /prepare unavailable")
        state.processing_steps.append("data_prep → /prepare ERREUR connexion")
    return state


async def call_get_status(job_id: str) -> dict:
    """
    GET /jobs/{job_id}/status
    Vérifie si le pipeline est completed ou waiting_validation.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{DATA_PREP_API_URL}/jobs/{job_id}/status"
        )
        return response.json()


async def call_validate(job_id: str, decisions: dict) -> dict:
    """
    POST /validate
    Soumet les décisions de l'utilisateur sur le plan de nettoyage.
    L'agent applique les corrections et livre en Silver MinIO.

    decisions : {"anomaly_id": "action_chosen", ...}
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{DATA_PREP_API_URL}/validate",
            json={"job_id": job_id, "decisions": decisions}
        )
        return response.json()


async def call_get_data_profile(state: OrchestratorState) -> OrchestratorState:
    """
    GET /jobs/{job_id}/profiling-json
    Récupère le profil statistique du dataset nettoyé.
    Passé au NLQ Agent via POST /chat pour générer du SQL précis.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{DATA_PREP_API_URL}/jobs/"
                f"{state.data_prep_job_id}/profiling-json"
            )
            profiling = response.json()

        summary      = profiling.get("summary", {})
        columns_info = summary.get("columns", {})

        state.data_profile = {
            "row_count": summary.get("dataset", {}).get("total_rows", 0),
            "columns": list(columns_info.keys()),
            "numeric_columns": [
                col for col, info in columns_info.items()
                if info.get("type") == "Numeric"
            ],
            "categorical_columns": [
                col for col, info in columns_info.items()
                if info.get("type") == "Categorical"
            ],
            "missing_summary": {
                col: info.get("missing_pct", 0)
                for col, info in columns_info.items()
                if info.get("missing_pct", 0) > 0
            },
            "quality_score": state.data_prep_quality.get("global", 0)
        }

        state.processing_steps.append(
            f"data_profile → {state.data_profile['row_count']} rows | "
            f"{len(state.data_profile['columns'])} columns"
        )

    except Exception as e:
        state.errors.append(f"Profiling error: {str(e)}")

    return state