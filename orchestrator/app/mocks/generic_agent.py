from app.graph.state import OrchestratorState


def mock_generic_agent(state: OrchestratorState) -> dict:
    """
    Used when the sector is unknown.
    Simulates an AutoML system that analyzes and predicts.
    """
    return {
        "response": (
            f"Unknown sector ('{state.sector.value}'). "
            "The Generic ML Agent has analyzed your request. "
            "An AutoML model was automatically selected "
            "with an estimated accuracy of 79%."
        ),
        "response_format": "text",
        "data_payload": {
            "model_selected": "GradientBoosting",
            "accuracy": 0.79,
            "features_used": 12,
            "training_time_sec": 45
        }
    }