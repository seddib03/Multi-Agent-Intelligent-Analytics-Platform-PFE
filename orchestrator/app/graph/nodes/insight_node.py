from app.graph.state import OrchestratorState
from app.clients.insight_client import call_generate_dashboard
from app.utils.async_utils import run_async

def insight_node(state: OrchestratorState) -> OrchestratorState:
    if not state.csv_path:
        state.final_response = (
            "Je peux generer un dashboard, mais j'ai besoin "
            "d'un dataset. Veuillez fournir un fichier CSV."
        )
        state.needs_clarification = True
        state.clarification_question = (
            "Veuillez uploader un fichier CSV pour generer le dashboard."
        )
        state.processing_steps.append("insight_node -> skipped (no CSV provided)")
        return state

    state = run_async(call_generate_dashboard(state))
    return state