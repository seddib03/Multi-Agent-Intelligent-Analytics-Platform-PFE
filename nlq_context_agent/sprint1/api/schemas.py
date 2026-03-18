"""
API Schemas — Request / Response models
========================================
PFE — DXC Technology | Intelligence Analytics Platform
Sprint 1

Définit les modèles Pydantic pour l'API FastAPI.
Compatible Pydantic V2 (model_config, json_schema_extra).
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict
from agents.context_sector_agent import KPI, SectorContext


# ══════════════════════════════════════════════════════════
# REQUÊTES
# ══════════════════════════════════════════════════════════

class ColumnMetadataRequest(BaseModel):
    """Colonne du dataset fournie en option à /detect-sector."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "delay_minutes",
                "description": "Retard en minutes",
                "sample_values": ["0", "15", "45"],
            }
        }
    )
    name          : str
    description   : Optional[str]       = None
    sample_values : Optional[list[str]] = None


class DetectSectorRequest(BaseModel):
    """Corps de requête pour POST /detect-sector."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_query": "améliorer l'expérience des passagers de l'aéroport",
                "column_metadata": [
                    {"name": "flight_id", "description": "ID du vol"},
                    {"name": "delay_minutes", "sample_values": ["0", "15", "45"]},
                ],
            }
        }
    )
    user_query      : str
    column_metadata : Optional[list[ColumnMetadataRequest]] = None


class ChatRequest(BaseModel):
    """Corps de requête pour POST /chat."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_001",
                "question": "Quel est le taux de retard moyen ce mois ?",
                "sector_context": {
                    "sector": "transport",
                    "confidence": 0.95,
                    "routing_target": "transport_agent",
                },
            }
        }
    )
    user_id        : str
    question       : str
    sector_context : SectorContext
    data_profile   : Optional[dict] = None


class ResetRequest(BaseModel):
    """Corps de requête pour POST /chat/reset."""
    model_config = ConfigDict(
        json_schema_extra={"example": {"user_id": "user_001"}}
    )
    user_id: str


# ══════════════════════════════════════════════════════════
# RÉPONSES
# ══════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    """Réponse de GET /health."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "model": "meta-llama/llama-3.1-8b-instruct",
                "active_sessions": 0,
            }
        }
    )
    status         : str
    model          : str
    active_sessions: int


class DetectSectorResponse(BaseModel):
    """Réponse de POST /detect-sector."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sector": "transport",
                "confidence": 0.95,
                "use_case": "Améliorer l'expérience des passagers",
                "metadata_used": False,
                "kpis": [],
                "dashboard_focus": "Passenger Experience & Operational Efficiency",
                "recommended_charts": ["line chart", "bar chart"],
                "routing_target": "transport_agent",
                "explanation": "Secteur transport détecté.",
            }
        }
    )
    sector             : str
    confidence         : float
    use_case           : str
    metadata_used      : bool
    kpis               : list[KPI]
    dashboard_focus    : str
    recommended_charts : list[str]
    routing_target     : str
    explanation        : str


class ChatResponse(BaseModel):
    """Réponse de POST /chat."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_001",
                "answer": "Le taux de retard moyen ce mois est de 12.4 minutes.",
                "intent": "aggregation",
                "query_type": "aggregation",
                "generated_query": "SELECT AVG(delay_minutes) FROM flights",
                "kpi_referenced": "Average Delay",
                "suggested_chart": "KPI card",
                "requires_orchestrator": False,
                "routing_target": None,
                "sub_agent": None,
                "orchestrator_payload": None,
                "needs_more_data": False,
                "history_length": 1,
            }
        }
    )
    user_id               : str
    answer                : str
    intent                : str
    query_type            : str
    generated_query       : Optional[str]  = None
    kpi_referenced        : Optional[str]  = None
    suggested_chart       : Optional[str]  = None
    requires_orchestrator : bool           = False
    routing_target        : Optional[str]  = None
    sub_agent             : Optional[str]  = None
    orchestrator_payload  : Optional[dict] = None
    needs_more_data       : bool           = False
    history_length        : int


class ResetResponse(BaseModel):
    """Réponse de POST /chat/reset."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_001",
                "history_cleared": True,
                "message": "Conversation history cleared for user 'user_001'.",
            }
        }
    )
    user_id        : str
    history_cleared: bool
    message        : str
