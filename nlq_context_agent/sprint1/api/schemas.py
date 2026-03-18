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
    """
    Corps de requête pour POST /detect-sector.

    Remarque encadrant R2 : column_metadata est OBLIGATOIRE.
    L'upload des métadonnées du dataset est essentiel pour une détection
    fiable du secteur. Sans métadonnées, la détection ne s'appuie que sur
    la query textuelle, ce qui génère des erreurs sur des queries ambiguës.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_query": "améliorer l'expérience des passagers de l'aéroport",
                "column_metadata": [
                    {"name": "flight_id", "description": "ID du vol"},
                    {"name": "delay_minutes", "sample_values": ["0", "15", "45"]},
                    {"name": "route", "description": "Route de vol (ex: CMN-CDG)"},
                ],
            }
        }
    )
    user_query      : str
    column_metadata : list[ColumnMetadataRequest]
    # R2 — Obligatoire : les métadonnées sont essentielles pour la détection secteur
    # → FastAPI retourne 422 si absent


class ColumnProfile(BaseModel):
    """
    Profil d'une colonne — format retourné par Data Prep Agent
    (ydata-profiling via GET /jobs/{job_id}/profiling-json).

    Types ydata-profiling reconnus :
      Numeric     → colonnes numériques (int, float)
      Categorical → colonnes catégorielles (string, enum)
      Boolean     → colonnes booléennes
      DateTime    → colonnes de dates/timestamps
      Text        → colonnes texte libre (haute cardinalité)
      Unsupported → type non reconnu par ydata-profiling
    """
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "Numeric",
            "mean": 34.5,
            "std": 12.1,
            "min": 0.0,
            "max": 100.0,
            "missing_pct": 2.5,
            "n_unique": None,
        }
    })
    # Type ydata-profiling — valeurs exactes du rapport
    type        : str                   # "Numeric" | "Categorical" | "Boolean" | "DateTime" | "Text" | "Unsupported"
    mean        : Optional[float] = None  # Numeric uniquement
    std         : Optional[float] = None  # Numeric uniquement
    min         : Optional[float] = None  # Numeric uniquement
    max         : Optional[float] = None  # Numeric uniquement
    missing_pct : Optional[float] = None  # % valeurs manquantes (ex: 3.1 = 3.1%)
    n_unique    : Optional[int]   = None  # Categorical / Text


class DataProfileRequest(BaseModel):
    """
    Profil du dataset produit par le Data Prep Agent.
    Format : réponse de GET /jobs/{job_id}/profiling-json du Data Prep Agent.

    Le NLQ Agent utilise ce profil pour :
    - Générer du SQL avec les vrais noms de colonnes
    - Mentionner les stats pertinentes dans la réponse
    - Éviter les colonnes avec trop de valeurs manquantes
    """
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "summary": {
                "dataset": {
                    "total_rows": 1000,
                    "missing_pct": 2.5,
                    "quality_score": 85.0
                },
                "columns": {
                    "flight_id":     {"type": "Numeric",     "missing_pct": 0.0},
                    "delay_minutes": {"type": "Numeric",     "mean": 12.4, "min": 0.0, "max": 180.0, "missing_pct": 1.2},
                    "gate":          {"type": "Categorical", "n_unique": 25, "missing_pct": 3.1},
                    "route":         {"type": "Categorical", "n_unique": 42, "missing_pct": 0.0},
                    "departure_dt":  {"type": "DateTime",    "missing_pct": 0.5},
                }
            }
        }
    })
    summary: dict   # structure complète du JSON ydata-profiling


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
    data_profile   : Optional[DataProfileRequest] = None


class ChatWithProfileRequest(BaseModel):
    """
    Corps de requête pour POST /chat-with-profile.

    Variante de /chat qui accepte directement le job_id du Data Prep Agent
    au lieu du data_profile complet. L'API récupère et adapte le profil
    automatiquement depuis le Data Prep Agent.

    Flux :
        UI → POST /chat-with-profile { job_id, question, ... }
             → GET data_prep_api/jobs/{job_id}/profiling-json
             → adapt_data_profile()
             → NLQAgent.chat(data_profile=adapted)
    """
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_id": "user_001",
            "question": "Quel est le retard moyen sur la route CMN-CDG ?",
            "sector_context": {
                "sector": "transport",
                "confidence": 0.95,
                "routing_target": "transport_agent",
            },
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
        }
    })
    user_id        : str
    question       : str
    sector_context : SectorContext
    job_id         : str     # job_id retourné par POST /prepare du Data Prep Agent


class SectorOverrideRequest(BaseModel):
    """
    Corps de requête pour POST /sector/override.

    Remarque encadrant R1 : permet à l'utilisateur de corriger
    la détection automatique du secteur.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_query": "améliorer l'expérience client",
                "sector": "retail",
                "column_metadata": [
                    {"name": "product_id", "description": "ID produit"},
                    {"name": "sales_amount", "description": "Montant des ventes"},
                ],
            }
        }
    )
    user_query      : str
    sector          : str
    # Secteur choisi manuellement — doit être dans AVAILABLE_SECTORS
    # ["transport", "finance", "retail", "manufacturing", "public"]
    column_metadata : Optional[list[ColumnMetadataRequest]] = None


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
    is_overridden      : bool = False
    available_sectors  : list[str] = []
    # R1 — Liste des secteurs disponibles retournée dans la réponse
    # → L'UI peut afficher "Ce n'est pas votre secteur ? Choisissez ici"


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


class NLQInternalResponse(BaseModel):
    """
    Réponse de POST /nlq — endpoint interne pour l'Orchestrateur.

    Contrairement à ChatResponse (qui est pour l'UI),
    ce modèle retourne le NLQResponse COMPLET avec orchestrator_payload.

    Utilisé par l'Orchestrateur pour :
    1. Lire requires_orchestrator → savoir si routing nécessaire
    2. Lire routing_target        → savoir quel agent appeler
    3. Lire sub_agent             → savoir quel sous-composant appeler
    4. Lire orchestrator_payload  → avoir toutes les données pour l'agent cible
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer"               : "Prédiction sectorielle détectée. Routing vers transport_agent.",
                "intent"               : "prediction",
                "query_type"           : "prediction",
                "generated_query"      : None,
                "kpi_referenced"       : None,
                "suggested_chart"      : None,
                "requires_orchestrator": True,
                "routing_target"       : "transport_agent",
                "sub_agent"            : "sector_prediction",
                "orchestrator_payload" : {
                    "task_type"          : "sector_prediction",
                    "target_kpi"         : "Average Delay",
                    "prediction_horizon" : "next_month",
                    "sector"             : "transport",
                    "routing_target"     : "transport_agent",
                    "sub_agent"          : "sector_prediction",
                    "original_question"  : "Prédis le retard moyen du mois prochain",
                    "kpis"               : ["On-Time Performance", "Average Delay"],
                    "extracted_entities" : {"time_period": "next_month"},
                },
                "needs_more_data": False,
            }
        }
    )

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