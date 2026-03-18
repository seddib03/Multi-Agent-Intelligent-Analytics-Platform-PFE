import httpx
import os
from dotenv import load_dotenv
from app.graph.state import OrchestratorState

load_dotenv()
INSIGHT_API_URL = os.getenv("INSIGHT_API_URL", "http://127.0.0.1:8002")


def _build_sector_context(state: OrchestratorState) -> dict:
    """
    Construit le sector_context attendu par le Collègue 3
    à partir du state de l'orchestrateur.

    Collègue 3 attend :
    {
      "sector": "Insurance",
      "context": "Customer and premium analytics",
      "recommended_kpis": ["Total Premium Amount", ...],
      "recommended_charts": ["line", "bar"],
      "dashboard_focus": "Insurance Analytics Dashboard"
    }
    """
    # KPIs recommandés — extraits du kpi_mapping du Collègue 1
    recommended_kpis = [
        kpi.get("name", kpi) if isinstance(kpi, dict) else kpi
        for kpi in state.kpi_mapping
    ]

    # Types de graphiques — extraits du data_profile si disponible
    recommended_charts = ["line", "bar"]  # défaut

    # Contexte métier
    dashboard_focus = f"{state.sector.value} Analytics Dashboard"

    return {
        "sector":              state.sector.value,
        "context":             state.query_raw,
        "recommended_kpis":    recommended_kpis,
        "recommended_charts":  recommended_charts,
        "dashboard_focus":     dashboard_focus,
    }


async def call_generate_dashboard(
    state: OrchestratorState
) -> OrchestratorState:
    """
    Appelle POST /generate-dashboard (Collègue 3 — Insight Agent).

    Envoie :
    - sector_context  : secteur + KPIs + contexte métier (depuis state)
    - dataset_path    : chemin du CSV fourni par l'UI (state.csv_path)
    - metadata_path   : chemin du fichier metadata (depuis state.metadata)
    - user_query      : requête originale de l'utilisateur

    Reçoit :
    - kpis, charts, insights, template, title
    """
    try:
        sector_context = _build_sector_context(state)

        # metadata_path — si metadata est un dict on le sérialise en fichier temp
        # sinon on suppose que c'est déjà un chemin
        metadata_path = state.metadata.get("metadata_path", "") \
            if isinstance(state.metadata, dict) else ""

        payload = {
            "sector_context": sector_context,
            "dataset_path":   state.csv_path,
            "metadata_path":  metadata_path,
            "user_query":     state.query_raw or None,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{INSIGHT_API_URL}/generate-dashboard",
                json=payload
            )
            result = response.json()

        if result.get("status") == "success":
            # Stocker la réponse complète dans agent_response
            state.agent_response = result

            # Construire la final_response lisible
            kpis = result.get("kpis", [])
            insights = result.get("insights", [])

            kpi_lines = "\n".join(
                f"- {k.get('name', '')}: {k.get('value', '')}"
                for k in kpis
            )
            insight_lines = "\n".join(
                f"- {i}" for i in insights
            )

            state.final_response = (
                f"**Dashboard généré** — {result.get('title', '')}\n\n"
                f"**KPIs**\n{kpi_lines}\n\n"
                f"**Insights**\n{insight_lines}"
            )

            state.response_format = "kpi"

            state.processing_steps.append(
                f"insight_agent → template={result.get('template', 'N/A')} | "
                f"kpis={len(kpis)} | "
                f"charts={len(result.get('charts', []))} | "
                f"mode={result.get('dashboard_mode', 'general')}"
            )
        else:
            state.errors.append(
                f"Insight Agent error: {result.get('detail', 'Unknown error')}"
            )

    except httpx.ConnectError:
        state.errors.append("❌ Insight Agent API non disponible")
        state.processing_steps.append("insight_agent → ERREUR connexion")

    except Exception as e:
        state.errors.append(f"❌ Insight Agent exception: {str(e)}")
        state.processing_steps.append(f"insight_agent → ERREUR: {str(e)}")

    return state