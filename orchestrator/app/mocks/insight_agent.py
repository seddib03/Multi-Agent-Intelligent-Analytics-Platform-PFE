from app.graph.state import OrchestratorState


def mock_insight_agent(state: OrchestratorState) -> dict:
    """
    Used for cross-sector dashboard/chart/KPI requests.
    """
    return {
        "response": "Dashboard generated with 4 key KPIs and 2 charts.",
        "response_format": "chart",
        "data_payload": {
            "charts": [
                {"type": "line", "title": "Monthly Revenue Trend", "data_points": 12},
                {"type": "bar",  "title": "Sector Comparison",     "data_points": 5},
            ],
            "kpis": [
                {"name": "Overall Performance", "value": 91.3, "unit": "%"},
                {"name": "Active Alerts",       "value": 3,    "unit": ""},
            ]
        }
    }