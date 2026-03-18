from app.graph.state import OrchestratorState


def mock_finance_agent(state: OrchestratorState) -> dict:
    intent = state.intent.value

    if intent == "kpi_request":
        return {
            "response": "Here are the Finance KPIs for March 2026.",
            "response_format": "kpi",
            "data_payload": {
                "kpis": [
                    {"name": "Revenue",              "value": 4_250_000, "unit": "€", "trend": "+12%"},
                    {"name": "Gross Margin",         "value": 38.4,      "unit": "%", "trend": "+1.5%"},
                    {"name": "EBITDA",               "value": 820_000,   "unit": "€", "trend": "+9%"},
                    {"name": "DSO (Days Sales Outstanding)", "value": 42, "unit": "days", "trend": "-3d"},
                ]
            }
        }
    elif intent == "prediction":
        return {
            "response": "Prediction: Q2 revenue estimated at €4.8M with an 85% confidence interval.",
            "response_format": "text",
            "data_payload": {
                "prediction": {
                    "metric": "revenue_Q2",
                    "value": 4_800_000,
                    "unit": "€",
                    "confidence": 0.85
                }
            }
        }

    else:
        return {
            "response": "Finance Agent: request received and processed.",
            "response_format": "text",
            "data_payload": {}
        }