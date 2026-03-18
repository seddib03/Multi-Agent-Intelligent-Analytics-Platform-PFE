from app.graph.state import OrchestratorState, RouteEnum
from app.graph.nodes.insight_node import insight_node


def dispatch_node(state: OrchestratorState) -> OrchestratorState:

    route = state.route
    state.processing_steps.append(f"dispatch_node → route={route.value if route else 'None'}")

    # ── Insight Agent ────────────────────────────────────────────────────
    if route == RouteEnum.INSIGHT_AGENT:
        state = insight_node(state)
        return state

    # ── Agents sectoriels → Insight Agent (génère KPIs + dashboard) ─────
    if route in [
        RouteEnum.TRANSPORT_AGENT,
        RouteEnum.FINANCE_AGENT,
        RouteEnum.RETAIL_AGENT,
        RouteEnum.MANUFACTURING_AGENT,
        RouteEnum.PUBLIC_AGENT,
        RouteEnum.GENERIC_ML_AGENT,
    ]:
        # Si NLQ a déjà répondu → utiliser sa réponse
        if state.final_response and state.final_response != "No response generated.":
            state.processing_steps.append(
                f"dispatch_node → NLQ direct answer (route={route.value})"
            )
            return state

        # Sinon → Insight Agent génère le dashboard sectoriel
        state.processing_steps.append(
            f"dispatch_node → redirecting {route.value} to insight_node"
        )
        state = insight_node(state)
        return state

    # ── Clarification ────────────────────────────────────────────────────
    if route == RouteEnum.CLARIFICATION:
        state.final_response = state.clarification_question or (
            "Pourriez-vous préciser votre demande ?"
        )
        state.processing_steps.append("dispatch_node → clarification response")
        return state

    # ── Défaut ───────────────────────────────────────────────────────────
    state.final_response = "Une erreur inattendue s'est produite dans le routing."
    state.errors.append(f"dispatch_node → unknown route: {route}")
    return state