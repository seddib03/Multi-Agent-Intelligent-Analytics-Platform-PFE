import asyncio
from app.graph.state import OrchestratorState, RouteEnum
from app.graph.nodes.insight_node import insight_node


def dispatch_node(state: OrchestratorState) -> OrchestratorState:
    """
    Node 5 du graph — Dispatche vers l'agent cible.

    Lit state.route et appelle le bon agent.
    Pour Sprint 2 : Insight Agent branché.
    Autres agents (sector, generic ML) : à brancher en Sprint 2/3.
    """

    route = state.route

    state.processing_steps.append(f"dispatch_node → route={route.value if route else 'None'}")

    # ── Insight Agent ──────────────────────────────────────────────
    if route == RouteEnum.INSIGHT_AGENT:
        state = insight_node(state)
        return state

    # ── Clarification ──────────────────────────────────────────────
    if route == RouteEnum.CLARIFICATION:
        if not state.final_response:
            state.final_response = state.clarification_question or (
                "Pourriez-vous préciser votre demande ?"
            )
        state.processing_steps.append("dispatch_node → clarification response")
        return state

    # ── Agents sectoriels (à brancher Sprint 3) ───────────────────
    # Pour l'instant → réponse NLQ déjà dans state.final_response
    # si requires_orchestrator=False, sinon message d'attente
    if route in [
        RouteEnum.TRANSPORT_AGENT,
        RouteEnum.FINANCE_AGENT,
        RouteEnum.RETAIL_AGENT,
        RouteEnum.MANUFACTURING_AGENT,
        RouteEnum.PUBLIC_AGENT,
        RouteEnum.GENERIC_ML_AGENT,
    ]:
        # Si le NLQ a déjà répondu (requires_orchestrator=False)
        # → final_response est déjà rempli
        if state.final_response:
            state.processing_steps.append(
                f"dispatch_node → using NLQ direct answer "
                f"(route={route.value})"
            )
            return state

        # Sinon → agent sectoriel non encore branché
        state.final_response = (
            f"Requête routée vers {route.value}. "
            f"Intégration en cours (Sprint 3)."
        )
        state.processing_steps.append(
            f"dispatch_node → {route.value} (not yet integrated)"
        )
        return state

    # ── Défaut ─────────────────────────────────────────────────────
    state.final_response = (
        "Une erreur inattendue s'est produite dans le routing."
    )
    state.errors.append(f"dispatch_node → unknown route: {route}")
    return state

"""from app.graph.state import OrchestratorState
from app.mocks import dispatch


def dispatch_node(state: OrchestratorState) -> OrchestratorState:
    
   # Calls the appropriate agent (mock for Sprint 1) based on the chosen route.
    #Sprint 2+: replace mocks with the real agents.
    
    try:
        result = dispatch(state)

        state.agent_response = result
        state.processing_steps.append(
            f"dispatch_node → agent called: {state.route.value}"
        )

    except Exception as e:
        # Fallback if the agent fails
        state.agent_error = str(e)
        state.route = state.fallback_route
        state.processing_steps.append(
            f"dispatch_node → ERROR, fallback to {state.fallback_route}"
        )

    return state"""

