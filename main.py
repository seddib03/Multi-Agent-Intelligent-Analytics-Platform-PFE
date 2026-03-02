# main.py

# Standard library
from __future__ import annotations

import logging
import os
import shutil
import uuid
from datetime import datetime

# Third-party
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

# Local
from agent.graph import agent_graph
from agent.state import AgentState, STATUS_FAILED, STATUS_SUCCESS
from core.storage_manager import StorageManager


# ─── Configuration du logging ────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Application FastAPI ─────────────────────────────────────────────────────

app = FastAPI(
    title="Data Preparation Agent",
    version="1.0.0",
    description=(
        "Agent de préparation de données multi-secteur. "
        "Accepte un dataset + metadata et retourne les données "
        "nettoyées avec un rapport de qualité complet."
    ),
)

# ─── Dossiers temporaires ────────────────────────────────────────────────────

TMP_DIR = "storage/tmp"
os.makedirs(TMP_DIR, exist_ok=True)


# ─── Événement démarrage ─────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup() -> None:
    """Initialise le Gold layer au démarrage de l'application.

    Crée les tables DuckDB si elles n'existent pas encore.
    Idempotent — sans effet si tables déjà présentes.
    """
    manager = StorageManager()
    manager.initialize_gold_layer()
    logger.info("Application démarrée — Gold layer initialisé")


# ─── Endpoints ───────────────────────────────────────────────────────────────


@app.get("/health")
def health_check() -> dict:
    """Vérifie que l'API est opérationnelle.

    Returns:
        Dictionnaire avec statut et version.
    """
    return {
        "status":  "ok",
        "agent":   "data_preparation_agent",
        "version": "1.0.0",
    }


@app.post("/prepare")
async def prepare_dataset(
    dataset:  UploadFile = File(..., description="Dataset CSV/Excel/JSON"),
    metadata: UploadFile = File(..., description="Metadata JSON"),
) -> JSONResponse:
    """Lance le pipeline complet de préparation de données.

    Reçoit un dataset et son metadata, déclenche le graph
    LangGraph avec les 4 nodes, et retourne le résultat
    structuré avec le rapport de qualité.

    Args:
        dataset:  Fichier dataset uploadé.
        metadata: Fichier metadata JSON uploadé.

    Returns:
        JSONResponse avec job_id, status, quality_score,
        chemins de stockage et cleaning_log.

    Raises:
        HTTPException 500: Si le pipeline échoue de façon inattendue.
    """
    job_id = str(uuid.uuid4())
    logger.info("Job démarré — id : %s", job_id)

    # ── Sauvegarder les fichiers uploadés ────────────────────────────
    dataset_ext   = os.path.splitext(dataset.filename)[1]
    dataset_path  = os.path.join(
        TMP_DIR, f"{job_id}_dataset{dataset_ext}"
    )
    metadata_path = os.path.join(
        TMP_DIR, f"{job_id}_metadata.json"
    )

    with open(dataset_path, "wb") as file_buffer:
        shutil.copyfileobj(dataset.file, file_buffer)

    with open(metadata_path, "wb") as file_buffer:
        shutil.copyfileobj(metadata.file, file_buffer)

    # ── Construire l'état initial ────────────────────────────────────
    initial_state: AgentState = {
        "dataset_path":   dataset_path,
        "metadata_path":  metadata_path,
        "metadata":       None,
        "action_plan":    None,
        "raw_df":         None,
        "clean_df":       None,
        "final_df":       None,
        "cleaning_log":   [],
        "quality_report": None,
        "quality_score":  None,
        "bronze_path":    None,
        "silver_path":    None,
        "status":         "RUNNING",
        "errors":         [],
        "started_at":     datetime.now().isoformat(),
        "completed_at":   None,
        "profile_before": None,   
        "profile_after":  None,
    }

    try:
        # ── Invoquer le graph ────────────────────────────────────────
        final_state = agent_graph.invoke(initial_state)
        final_state["completed_at"] = datetime.now().isoformat()

        if final_state["status"] not in (STATUS_FAILED,):
            final_state["status"] = STATUS_SUCCESS

        logger.info(
            "Job terminé — id : %s | status : %s | score : %s",
            job_id,
            final_state["status"],
            final_state.get("quality_score"),
        )

        # ── Construire la réponse ────────────────────────────────────
        # On ne retourne pas les DataFrames — trop lourds
        # On retourne les informations utiles pour l'Orchestrateur
        return JSONResponse(content={
            "job_id":         job_id,
            "status":         final_state["status"],
            "sector":         final_state.get(
                "action_plan", {}
            ).get("sector", "unknown"),
            "quality_score":  final_state.get("quality_score"),
            "quality_report": final_state.get("quality_report"),
            "bronze_path":    final_state.get("bronze_path"),
            "silver_path":    final_state.get("silver_path"),
            "cleaning_log":   final_state.get("cleaning_log", []),
            "errors":         final_state.get("errors", []),
            "started_at":     final_state.get("started_at"),
            "completed_at":   final_state.get("completed_at"),
        })

    except Exception as error:
        logger.error(
            "Job échoué — id : %s | erreur : %s", job_id, error
        )
        raise HTTPException(
            status_code=500, detail=str(error)
        ) from error


@app.get("/history/{sector}")
def get_sector_history(sector: str) -> JSONResponse:
    """Retourne l'historique des runs pour un secteur.

    Utile pour l'Orchestrateur et les agents en aval
    qui veulent connaître la qualité historique des données.

    Args:
        sector: Secteur dont on veut l'historique.

    Returns:
        JSONResponse avec la liste des 50 derniers runs.
    """
    manager = StorageManager()
    history = manager.get_sector_history(sector)

    return JSONResponse(content={
        "sector":  sector,
        "history": history,
        "count":   len(history),
    })


@app.get("/health/detailed")
def health_check_detailed() -> JSONResponse:
    """Vérifie l'état de tous les composants du pipeline.

    Returns:
        JSONResponse avec l'état de chaque composant.
    """
    components = {}

    # Vérifier DuckDB
    try:
        import duckdb
        conn = duckdb.connect(
            os.getenv("GOLD_DB_PATH", "storage/gold/analytics.duckdb")
        )
        conn.execute("SELECT 1").fetchone()
        conn.close()
        components["duckdb"] = "ok"
    except Exception as error:
        components["duckdb"] = f"error: {error}"

    # Vérifier les dossiers de stockage
    for layer in ("storage/bronze", "storage/silver", "storage/gold"):
        components[layer] = "ok" if os.path.exists(layer) else "missing"

    # Vérifier dbt
    try:
        import subprocess
        result = subprocess.run(
            ["dbt", "--version"],
            capture_output=True,
            text=True,
            cwd="DataQuality",
        )
        components["dbt"] = (
            "ok" if result.returncode == 0 else "error"
        )
    except Exception:
        components["dbt"] = "not_found"

    overall = (
        "ok"
        if all(v == "ok" for v in components.values())
        else "degraded"
    )

    return JSONResponse(content={
        "status":     overall,
        "components": components,
        "timestamp":  datetime.now().isoformat(),
    })