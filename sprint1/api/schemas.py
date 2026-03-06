"""
API Schemas — Request & Response Models
=========================================
PFE — DXC Technology | Intelligence Analytics Platform

Ce fichier définit tous les modèles Pydantic utilisés par l'API FastAPI.
Ils servent à :
  - Valider automatiquement les données entrantes (Request)
  - Documenter l'API via Swagger/OpenAPI (auto-généré par FastAPI)
  - Garantir la structure des réponses (Response)

Séparation des responsabilités :
  schemas.py  → modèles HTTP (ce que l'API expose)
  agents/     → modèles métier internes (SectorContext, NLQResponse)
"""

from typing import Optional
from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════
# REQUÊTES ENTRANTES (Request Bodies)
# ══════════════════════════════════════════════════════════

class ColumnMetadataSchema(BaseModel):
    """
    Décrit une colonne du dataset de l'utilisateur.
    Optionnel : fourni pour lever l'ambiguïté sectorielle.
    """
    name: str = Field(..., description="Nom exact de la colonne", example="delay_minutes")
    description: Optional[str] = Field(
        None,
        description="Description lisible de la colonne",
        example="Retard du vol en minutes"
    )
    sample_values: Optional[list[str]] = Field(
        None,
        description="Exemples de valeurs",
        example=["0", "15", "45", "120"]
    )


class DetectSectorRequest(BaseModel):
    """
    Corps de la requête POST /detect-sector.

    Envoyé par :
    - L'interface utilisateur quand l'user soumet son objectif global
    - L'orchestrateur pour router vers le bon agent sectoriel

    Le champ `column_metadata` est optionnel mais recommandé
    si la query est générique (ex: 'améliorer l'expérience client').
    """
    user_query: str = Field(
        ...,
        description="Objectif global de l'utilisateur en langage naturel",
        example="améliorer l'expérience des passagers de l'aéroport"
    )
    column_metadata: Optional[list[ColumnMetadataSchema]] = Field(
        None,
        description="Colonnes du dataset (optionnel, aide à lever l'ambiguïté sectorielle)"
    )

    class Config:
        json_schema_extra = {
            "examples": {
                "query_only": {
                    "summary": "Query précise sans metadata",
                    "value": {
                        "user_query": "améliorer l'expérience des passagers de l'aéroport"
                    }
                },
                "with_metadata": {
                    "summary": "Query ambiguë avec metadata colonnes",
                    "value": {
                        "user_query": "améliorer l'expérience client",
                        "column_metadata": [
                            {"name": "flight_id", "description": "identifiant unique du vol"},
                            {"name": "delay_minutes", "description": "retard en minutes"},
                            {"name": "gate", "description": "porte d'embarquement"}
                        ]
                    }
                }
            }
        }


class ChatRequest(BaseModel):
    """
    Corps de la requête POST /chat.

    Envoyé par :
    - L'interface utilisateur (chatbot analytique)

    Le `sector_context` est le SectorContext retourné par POST /detect-sector.
    Le `user_id` permet de maintenir l'historique de conversation côté serveur.
    Le `data_profile` est optionnel — fourni par le Data Prep Agent si disponible.
    """
    user_id: str = Field(
        ...,
        description="Identifiant unique de l'utilisateur pour maintenir la session",
        example="user_123"
    )
    question: str = Field(
        ...,
        description="Question spécifique de l'utilisateur",
        example="Quel est le taux de retard moyen ce mois ?"
    )
    sector_context: dict = Field(
        ...,
        description="SectorContext retourné par POST /detect-sector (objet JSON complet)"
    )
    data_profile: Optional[dict] = Field(
        None,
        description="Profil du dataset produit par le Data Prep Agent (optionnel)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "question": "Quel est le taux de retard moyen ce mois ?",
                "sector_context": {
                    "sector": "transport",
                    "confidence": 0.95,
                    "use_case": "Améliorer l'expérience des passagers",
                    "metadata_used": False,
                    "kpis": [
                        {"name": "Average Delay", "description": "Mean delay",
                         "unit": "minutes", "priority": "high"}
                    ],
                    "dashboard_focus": "Passenger Experience",
                    "recommended_charts": ["histogram"],
                    "routing_target": "transport_agent",
                    "explanation": "Airport keywords detected."
                },
                "data_profile": None
            }
        }


class ResetChatRequest(BaseModel):
    """Corps de la requête POST /chat/reset."""
    user_id: str = Field(
        ...,
        description="Identifiant de l'utilisateur dont on réinitialise la session",
        example="user_123"
    )


# ══════════════════════════════════════════════════════════
# RÉPONSES SORTANTES (Response Bodies)
# ══════════════════════════════════════════════════════════

class KPISchema(BaseModel):
    """KPI dans la réponse de détection sectorielle."""
    name: str
    description: str
    unit: str
    priority: str


class DetectSectorResponse(BaseModel):
    """
    Réponse de POST /detect-sector.

    Retournée à :
    - L'interface utilisateur (pour afficher le dashboard global)
    - L'orchestrateur (pour router vers l'agent sectoriel via routing_target)
    """
    sector: str = Field(..., example="transport")
    confidence: float = Field(..., example=0.95)
    use_case: str = Field(..., example="Améliorer l'expérience des passagers de l'aéroport")
    metadata_used: bool = Field(..., example=False)
    kpis: list[KPISchema]
    dashboard_focus: str = Field(..., example="Passenger Experience & Operational Efficiency")
    recommended_charts: list[str]
    routing_target: str = Field(
        ...,
        description="Agent sectoriel cible pour l'orchestrateur",
        example="transport_agent"
    )
    explanation: str


class ChatResponse(BaseModel):
    """
    Réponse de POST /chat.

    Retournée à l'interface utilisateur pour afficher dans le chatbot.
    """
    user_id: str
    answer: str = Field(..., example="Le taux de retard moyen ce mois est de 12.4 minutes.")
    query_type: str = Field(..., example="aggregation")
    generated_query: Optional[str] = Field(
        None,
        example="SELECT AVG(delay_minutes) FROM flights WHERE MONTH(date) = MONTH(NOW())"
    )
    kpi_referenced: Optional[str] = Field(None, example="Average Delay")
    suggested_chart: Optional[str] = Field(None, example="KPI card with monthly trend")
    needs_more_data: bool = Field(False)
    history_length: int = Field(..., description="Nombre de tours dans la session courante")


class ResetChatResponse(BaseModel):
    """Réponse de POST /chat/reset."""
    user_id: str
    message: str
    history_cleared: bool


class HealthResponse(BaseModel):
    """Réponse de GET /health."""
    status: str = Field(..., example="ok")
    model: str = Field(..., example="meta-llama/llama-3.1-8b-instruct")
    active_sessions: int = Field(..., description="Nombre de sessions NLQ actives en mémoire")


class ErrorResponse(BaseModel):
    """Réponse d'erreur standard."""
    error: str
    detail: Optional[str] = None