from app.graph.state import OrchestratorState, RouteEnum

def response_node(state: OrchestratorState) -> OrchestratorState:
    agent_resp = state.agent_response

    if state.route == RouteEnum.CLARIFICATION:
        state.needs_clarification = True
        state.clarification_question = agent_resp.get(
            "question", "Pouvez-vous preciser votre demande ?"
        )

    if state.agent_error:
        state.final_response = (
            f"An error occurred: {state.agent_error}. "
            "Please rephrase your question."
        )
    elif state.needs_clarification:
        state.final_response = state.clarification_question
    elif state.final_response and state.final_response != "No response generated.":
        # final_response deja rempli par insight_node ou dispatch_node -> conserver
        pass
    else:
        state.final_response = agent_resp.get("response", "No response generated.")
        state.response_format = agent_resp.get("response_format", "text")

    state.processing_steps.append("response_node -> response formatted OK")
    return state