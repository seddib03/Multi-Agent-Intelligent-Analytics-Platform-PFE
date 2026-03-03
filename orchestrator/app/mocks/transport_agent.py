from app.graph.state import OrchestratorState


def mock_transport_agent(state: OrchestratorState) -> dict:
    """
    Simulate the response of the transport agent.
    Sprint 1 : fictitious but realistic data.
    """
    intent = state.intent.value

    if intent == "kpi_request":
        return {
            "response": "Here are the Transport KPIs for March 2026.",
            "response_format": "kpi",
            "data_payload": {
                "kpis": [
                    {"name": "On-time delivery rate", "value": 94.2, "unit": "%", "trend": "+2.1%"},
                    {"name": "Average cost per km",         "value": 1.83, "unit": "€", "trend": "-0.3%"},
                    {"name": "Number of trips",         "value": 12450, "unit": "",  "trend": "+5%"},
                    {"name": "Fleet utilization rate",  "value": 87.5, "unit": "%", "trend": "+1.2%"},
                ]
            }
        }

    elif intent == "prediction":
        return {
            "response": "Transport prediction: an 8% traffic increase is expected next week.",
            "response_format": "text",
            "data_payload": {
                "prediction": {"metric": "traffic_volume", "value": "+8%", "horizon": "7 jours", "confidence": 0.84}
            }
        }

    elif intent == "explanation":
        return {
            "response": "The observed delivery peak is due to weekend e-commerce promotions.",
            "response_format": "text",
            "data_payload": {}
        }

    else:
        return {
            "response": "Transport Agent: request received and processed.",
            "response_format": "text",
            "data_payload": {}
        }