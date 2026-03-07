from typing import Optional
from pydantic import BaseModel
from app.graph.state import RouteEnum
# This module defines the output schema for the orchestrator app, including the response format and metadata for debugging and analysis.
#The response of the Orchestrator
class OrchestratorResponse(BaseModel):
    # what Orchestrator return to UI
    user_id: str
    session_id: str
    query_raw: str

    # the final response
    response: str
    response_format: str    # "text", "kpi", "chart", "table"

    # Metadata  debug (use for demo Sprint 1)
    route_taken: Optional[RouteEnum] = None
    route_reason: str = ""
    sector_detected: str = ""
    intent_detected: str = ""
    needs_clarification: bool = False
    clarification_question: str = ""

    # for KPI dashboard
    data_payload: dict = {}

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "u_001",
                "session_id": "sess_abc123",
                "query_raw": "Show me the transport KPIs in the last mouth",
                "response": "Here are the transport KPIs for the mouth February 2026..",
                "response_format": "kpi",
                "route_taken": "Transport_Sector_Agent",
                "route_reason": "Transport sector detected with 92% of confidence + intent KPI",
                "sector_detected": "Transport",
                "intent_detected": "kpi_request",
                "needs_clarification": False,
                "data_payload": {
                    "kpis": [
                        {"name": "Taux de livraison", "value": 94.2, "unit": "%"},
                        {"name": "Coût moyen/km", "value": 1.8, "unit": "€"}
                    ]
                }
            }
        }
