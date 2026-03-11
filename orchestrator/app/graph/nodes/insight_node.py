import asyncio
from app.graph.state import OrchestratorState, RouteEnum
from app.clients.insight_client import call_generate_dashboard


def insight_node(state: OrchestratorState) -> OrchestratorState:
    """
    Node du graph LangGraph — Insight Agent (Collègue 3).

    Appelé par dispatch_node quand route = INSIGHT_AGENT.

    Rôle :
    - Envoie le dataset + sector_context au Collègue 3
    - Reçoit le dashboard généré (KPIs + graphiques + insights)
    - Remplit state.agent_response + state.final_response

    Prérequis :
    - state.csv_path         : chemin du CSV fourni par l'UI
    - state.sector           : secteur détecté par Collègue 1
    - state.kpi_mapping      : KPIs recommandés par Collègue 1
    - state.query_raw        : requête originale de l'utilisateur
    """

    # ── Vérification — CSV requis ──────────────────────────────────
    # L'Insight Agent a besoin du dataset pour calculer les KPIs
    # Si pas de CSV → réponse de fallback
    if not state.csv_path:
        state.final_response = (
            "Je peux générer un dashboard, mais j'ai besoin "
            "d'un dataset. Veuillez fournir un fichier CSV."
        )
        state.needs_clarification = True
        state.clarification_question = (
            "Veuillez uploader un fichier CSV pour générer le dashboard."
        )
        state.processing_steps.append(
            "insight_node → skipped (no CSV provided)"
        )
        return state

    # ── Appel Insight Agent ────────────────────────────────────────
    state = asyncio.run(call_generate_dashboard(state))

    return state