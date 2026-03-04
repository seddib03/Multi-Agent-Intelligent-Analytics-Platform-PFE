from app.graph.state import OrchestratorState


def response_node(state: OrchestratorState) -> OrchestratorState:
    """
    Format the final response to return to the UI.
    Sprint 5: to be replaced by the real Response Agent.
    """
    agent_resp = state.agent_response

    if state.agent_error:
        state.final_response = (
            f"An error occurred: {state.agent_error}. "
            "Please rephrase your question."
        )
    elif state.needs_clarification:
        state.final_response = state.clarification_question
    else:
        state.final_response = agent_resp.get("response", "No response generated.")
        state.response_format = agent_resp.get("response_format", "text")

    state.processing_steps.append("response_node → response formatted ✅")
    return state