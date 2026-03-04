from app.graph.state import OrchestratorState


def mock_clarification_agent(state: OrchestratorState) -> dict:
    """
    Used when the orchestrator does not know where to route the request.
    Generates a clarification question.
    """
    return {
        "response": (
            f"I did not fully understand your request: '{state.query_raw}'. "
            "Could you please specify the concerned sector? "
            "(Transport, Finance, Retail, Manufacturing, Public)"
        ),
        "response_format": "text",
        "data_payload": {
            "options": ["Transport", "Finance", "Retail", "Manufacturing", "Public"]
        }
    }