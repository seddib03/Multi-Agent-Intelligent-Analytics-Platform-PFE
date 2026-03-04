from app.graph.state import OrchestratorState
from app.mocks import dispatch


def dispatch_node(state: OrchestratorState) -> OrchestratorState:
    """
    Calls the appropriate agent (mock for Sprint 1) based on the chosen route.
    Sprint 2+: replace mocks with the real agents.
    """
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

    return state