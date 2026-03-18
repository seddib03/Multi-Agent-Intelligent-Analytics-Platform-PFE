"""
API FastAPI — Intelligence Analytics Platform
=============================================
PFE — DXC Technology | Sprint 1 → Sprint 2

Expose les 2 agents via 4 endpoints REST.

Endpoints
---------
GET  /health          → status API + modèle + sessions actives
POST /detect-sector   → Sector Detection Agent → SectorContext
POST /chat            → NLQ Layer → réponse analytique ou routing
POST /chat/reset      → réinitialiser la conversation d'un user

Changements Sprint 2
--------------------
AJOUT — adapt_data_profile() : convertit le JSON du Data Prep Agent
        vers le format interne attendu par NLQAgent.

        Le Data Prep Agent produit un JSON ydata-profiling :
            { "summary": { "dataset": {...}, "columns": { col: {type, mean, ...} } } }

        NLQAgent.chat() attend un dict plat :
            { "columns": [...], "numeric_columns": [...], "column_stats": {...}, ... }

        Sans cette conversion, data_profile est ignoré → SQL sans noms de colonnes réels.

MODIF — /chat : data_profile DataProfileRequest → adapt_data_profile()
        avant passage à NLQAgent.

Consommateurs
-------------
- UI (Frontend)       → /detect-sector puis /chat (chatbot)
- Orchestrateur       → /detect-sector (routing_target) + /chat (avec data_profile)
- Data Prep Agent     → fournit data_profile dans /chat via DataProfileRequest

Flux data_profile
-----------------
    Data Prep Agent (:8001)
        GET /jobs/{job_id}/profiling-json  →  { summary: { columns: {...} } }
                │
                │  l'Orchestrateur stocke ce JSON
                ▼
    Orchestrateur (:8002)
        POST /chat  body: { ..., data_profile: { summary: {...} } }
                │
                ▼
    Ton API (:8000)  ← adapt_data_profile() convertit ici
        NLQAgent.chat(data_profile=adapted)
        → SQL avec vrais noms de colonnes ✅

Démarrer
--------
    uvicorn api.main:app --reload --port 8000
    http://localhost:8000/docs   ← Swagger interactif
    http://localhost:8000/health ← Status JSON
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents.context_sector_agent import ContextSectorAgent as SectorDetectionAgent, ColumnMetadata, AVAILABLE_SECTORS
from agents.nlq_agent import NLQAgent
from api.schemas import (
    DetectSectorRequest, DetectSectorResponse,
    SectorOverrideRequest,
    ChatRequest, ChatResponse,
    ResetRequest, ResetResponse,
    HealthResponse,
)

# ══════════════════════════════════════════════════════════
# INITIALISATION
# ══════════════════════════════════════════════════════════

load_dotenv()

app = FastAPI(
    title       = "DXC Intelligence Analytics Platform — Sprint 2",
    description = (
        "API exposant le Sector Detection Agent et la NLQ Layer.\n\n"
        "**Flux recommandé :**\n"
        "1. `POST /detect-sector` → obtenir le SectorContext\n"
        "2. `POST /chat` → poser des questions analytiques (chatbot)\n"
        "3. `POST /chat/reset` → réinitialiser la session\n\n"
        "**Note :** Si `requires_orchestrator=true` dans la réponse de `/chat`, "
        "l'UI doit appeler l'Orchestrateur (Sprint 2) avec `routing_target` + `sub_agent`.\n\n"
        "**data_profile :** Fournir le JSON du Data Prep Agent dans `data_profile.summary` "
        "pour que le SQL généré utilise les vrais noms de colonnes du dataset."
    ),
    version = "2.0.0",
)

# CORS — autorise l'UI à appeler l'API depuis un autre port
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Agents — None au niveau module pour permettre le patch dans les tests ────
sector_agent = None
nlq_agent    = None


def _get_agents():
    """
    Retourne les agents (singletons). Les instancie au premier appel.

    Design pour les tests :
    -----------------------
    Les tests patchent api.main.sector_agent / api.main.nlq_agent AVANT
    tout appel d'endpoint. Quand patch() remplace la variable, elle n'est
    plus None — cette fonction retourne simplement le mock sans rien créer.
    """
    import api.main as _self
    sa = _self.sector_agent
    na = _self.nlq_agent
    if sa is None or na is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not found. "
                "Create a .env file with: OPENROUTER_API_KEY=sk-or-v1-..."
            )
        sa = SectorDetectionAgent(openrouter_api_key=api_key, verbose=True)
        na = NLQAgent(openrouter_api_key=api_key, verbose=True)
        _self.sector_agent = sa
        _self.nlq_agent    = na
    return sa, na


# ══════════════════════════════════════════════════════════
# ADAPTATEUR — Data Prep Agent → NLQ Agent
# ══════════════════════════════════════════════════════════

# Types ydata-profiling → catégorie NLQ
_YDATA_NUMERIC     = {"Numeric"}
_YDATA_CATEGORICAL = {"Categorical", "Boolean"}
_YDATA_DATETIME    = {"DateTime"}


def adapt_data_profile(profiling_json) -> dict:
    """
    Convertit le JSON du Data Prep Agent vers le format interne NLQAgent.

    Pourquoi cette fonction existe
    --------------------------------
    Le Data Prep Agent (ydata-profiling) retourne :
        {
            "summary": {
                "dataset": { "total_rows": 1000, "missing_pct": 2.5 },
                "columns": {
                    "delay_minutes": { "type": "Numeric", "mean": 34.5,
                                       "min": 0.0, "max": 180.0, "missing_pct": 1.2 },
                    "gate":          { "type": "Categorical", "n_unique": 25 },
                    "departure_dt":  { "type": "DateTime" }
                }
            }
        }

    Le NLQAgent attend un dict plat :
        {
            "row_count"          : 1000,
            "columns"            : ["delay_minutes", "gate", "departure_dt"],
            "numeric_columns"    : ["delay_minutes"],
            "categorical_columns": ["gate"],
            "datetime_columns"   : ["departure_dt"],
            "missing_summary"    : {"delay_minutes": 1.2},
            "quality_score"      : None,
            "column_stats"       : {
                "delay_minutes": {"mean": 34.5, "min": 0.0, "max": 180.0}
            }
        }

    Sans cette conversion, NLQAgent reçoit None → SQL générique sans noms réels.

    Format alternatif supporté — liste [{name, type, sample_values}]
    ----------------------------------------------------------------
    L'Orchestrateur peut envoyer data_profile comme une liste :
        [ {"name": "delay_minutes", "type": "Numeric"}, ... ]
    Dans ce cas, un summary synthétique est construit avant de continuer.
    """
    # Détecter le format liste envoyé parfois par l'Orchestrateur
    if isinstance(profiling_json, list):
        cols_synthetic = {}
        for col in profiling_json:
            name = col.get("name", "")
            if not name:
                continue
            cols_synthetic[name] = {
                "type"       : col.get("type", "Unsupported"),
                "missing_pct": col.get("missing_pct", 0.0) or 0.0,
            }
        profiling_json = {
            "summary": {
                "dataset": {"total_rows": 0},
                "columns": cols_synthetic,
            }
        }

    summary  = profiling_json.get("summary", {})
    dataset  = summary.get("dataset", {})
    cols_raw = summary.get("columns", {})

    numeric_cols     = []
    categorical_cols = []
    datetime_cols    = []
    missing_summary  = {}
    column_stats     = {}

    for col_name, col_info in cols_raw.items():
        ydata_type  = col_info.get("type", "Unsupported")
        missing_pct = col_info.get("missing_pct", 0.0) or 0.0

        if ydata_type in _YDATA_NUMERIC:
            numeric_cols.append(col_name)
            stats = {}
            for stat in ("mean", "std", "min", "max"):
                if col_info.get(stat) is not None:
                    stats[stat] = col_info[stat]
            if stats:
                column_stats[col_name] = stats

        elif ydata_type in _YDATA_CATEGORICAL:
            categorical_cols.append(col_name)
            if col_info.get("n_unique") is not None:
                column_stats[col_name] = {"n_unique": col_info["n_unique"]}

        elif ydata_type in _YDATA_DATETIME:
            datetime_cols.append(col_name)

        # Text / Unsupported → ignoré

        if missing_pct > 0:
            missing_summary[col_name] = missing_pct

    # quality_score : pas dans profiling-json, vient de POST /prepare
    # On le lit quand même si présent (injection optionnelle par l'Orchestrateur)
    raw_quality = dataset.get("quality_score")
    if raw_quality is None:
        raw_quality = dataset.get("global_scores", {}).get("global")
    quality_score = (
        round(raw_quality * 100, 1) if raw_quality and raw_quality <= 1
        else raw_quality
    )

    return {
        "row_count"          : dataset.get("total_rows", 0),
        "columns"            : list(cols_raw.keys()),
        "numeric_columns"    : numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns"   : datetime_cols,
        "missing_summary"    : missing_summary,
        "quality_score"      : quality_score,
        "column_stats"       : column_stats,
    }


# ══════════════════════════════════════════════════════════
# ENDPOINT 1 — HEALTH CHECK
# ══════════════════════════════════════════════════════════

@app.get(
    "/health",
    response_model = HealthResponse,
    summary        = "Status de l'API",
    tags           = ["System"],
)
def health_check() -> HealthResponse:
    """Vérifie que l'API est opérationnelle."""
    sa, na = _get_agents()
    return HealthResponse(
        status          = "ok",
        model           = sa.MODEL,
        active_sessions = na.active_sessions,
    )


# ══════════════════════════════════════════════════════════
# ENDPOINT 2 — DETECT SECTOR
# ══════════════════════════════════════════════════════════

@app.post(
    "/detect-sector",
    response_model = DetectSectorResponse,
    summary        = "Détecte le secteur et mappe les KPIs",
    tags           = ["Sector Detection Agent"],
)
def detect_sector(body: DetectSectorRequest) -> DetectSectorResponse:
    """
    **Sector Detection Agent** — point d'entrée du pipeline.

    Analyse la query globale de l'utilisateur et produit le SectorContext.
    Appeler en premier, avant tout appel à /chat.

    **Champs clés de la réponse :**
    - `routing_target` → utilisé par l'Orchestrateur pour router vers l'agent sectoriel
    - `kpis`           → KPIs à afficher sur le dashboard global
    - `confidence`     → si < 0.7, suggérer à l'utilisateur de fournir des colonnes
    """
    columns = None
    if body.column_metadata:
        columns = [
            ColumnMetadata(
                name          = c.name,
                description   = c.description,
                sample_values = c.sample_values,
            )
            for c in body.column_metadata
        ]

    sa, _ = _get_agents()
    try:
        ctx = sa.detect(body.user_query, columns=columns)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return DetectSectorResponse(
        sector             = ctx.sector,
        confidence         = ctx.confidence,
        use_case           = ctx.use_case,
        metadata_used      = ctx.metadata_used,
        kpis               = ctx.kpis,
        dashboard_focus    = ctx.dashboard_focus,
        recommended_charts = ctx.recommended_charts,
        routing_target     = ctx.routing_target,
        explanation        = ctx.explanation,
    )




# ══════════════════════════════════════════════════════════
# ENDPOINT 2b — SECTOR OVERRIDE (Remarque encadrant R1)
# ══════════════════════════════════════════════════════════

@app.post(
    "/sector/override",
    response_model = DetectSectorResponse,
    summary        = "Corrige manuellement le secteur détecté",
    tags           = ["Sector Detection Agent"],
)
def override_sector(body: SectorOverrideRequest) -> DetectSectorResponse:
    """
    **Sector Override** — correction manuelle par l'utilisateur.

    Flux UI :
    1. POST /detect-sector → retourne sector + available_sectors
    2. UI affiche : "Secteur détecté : Transport. Ce n'est pas le bon ?"
    3. UI propose un dropdown avec available_sectors
    4. Utilisateur choisit → POST /sector/override
    5. Nouvelle réponse remplace l'ancien SectorContext dans l'UI

    is_overridden=true confirme le choix manuel. confidence=1.0.
    """
    cols = None
    if body.column_metadata:
        cols = [
            ColumnMetadata(
                name          = col.name,
                description   = col.description,
                sample_values = col.sample_values,
            )
            for col in body.column_metadata
        ]

    sa, _ = _get_agents()
    try:
        ctx = sa.override_sector(
            user_query = body.user_query,
            sector     = body.sector,
            columns    = cols,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return DetectSectorResponse(
        sector             = ctx.sector,
        confidence         = ctx.confidence,
        use_case           = ctx.use_case,
        metadata_used      = ctx.metadata_used,
        kpis               = ctx.kpis,
        dashboard_focus    = ctx.dashboard_focus,
        recommended_charts = ctx.recommended_charts,
        routing_target     = ctx.routing_target,
        explanation        = ctx.explanation,
        is_overridden      = ctx.is_overridden,
        available_sectors  = AVAILABLE_SECTORS,
    )

# ══════════════════════════════════════════════════════════
# ENDPOINT 3 — NLQ CHAT
# ══════════════════════════════════════════════════════════

@app.post(
    "/chat",
    response_model = ChatResponse,
    summary        = "Pose une question analytique au chatbot",
    tags           = ["NLQ Layer"],
)
def chat(body: ChatRequest) -> ChatResponse:
    """
    **NLQ Layer** — chatbot analytique avec support du data_profile.

    **Pré-requis :** Avoir appelé `/detect-sector` et conserver le `sector_context`.

    **Avec data_profile (Sprint 2) :**

    Fournir le JSON du Data Prep Agent pour un SQL précis avec les vrais noms de colonnes :
    ```json
    {
      "user_id"       : "user_001",
      "question"      : "Quel est le retard moyen ?",
      "sector_context": { ... },
      "data_profile"  : {
        "summary": {
          "dataset": { "total_rows": 1000 },
          "columns": {
            "delay_minutes": { "type": "Numeric", "mean": 34.5, "min": 0.0, "max": 180.0 },
            "gate":          { "type": "Categorical", "n_unique": 25 }
          }
        }
      }
    }
    ```
    Sans `data_profile` → SQL générique. Avec `data_profile` → `SELECT AVG(delay_minutes) FROM flights`.

    **Champs clés à surveiller dans la réponse :**
    - `requires_orchestrator` → si `true`, appeler l'Orchestrateur avec `routing_target`
    - `generated_query`       → SQL à exécuter sur les données
    - `history_length`        → nombre de tours dans la session (doit croître)
    """
    _, na = _get_agents()

    # ── Sprint 2 — adapter data_profile avant de passer au NLQAgent ──────
    # body.data_profile est un DataProfileRequest { summary: {...} }
    # NLQAgent.chat() attend un dict plat { columns, numeric_columns, ... }
    # adapt_data_profile() fait la conversion
    adapted_profile = None
    if body.data_profile:
        try:
            adapted_profile = adapt_data_profile(body.data_profile.summary)
        except Exception:
            # data_profile malformé → continuer sans lui
            # NLQAgent répondra avec SQL générique
            adapted_profile = None

    try:
        result = na.chat(
            user_id        = body.user_id,
            question       = body.question,
            sector_context = body.sector_context,
            data_profile   = adapted_profile,   # ← converti ou None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        user_id               = body.user_id,
        answer                = result.answer,
        intent                = result.intent,
        query_type            = result.query_type,
        generated_query       = result.generated_query,
        kpi_referenced        = result.kpi_referenced,
        suggested_chart       = result.suggested_chart,
        requires_orchestrator = result.requires_orchestrator,
        routing_target        = result.routing_target,
        sub_agent             = result.sub_agent,
        orchestrator_payload  = result.orchestrator_payload,
        needs_more_data       = result.needs_more_data,
        history_length        = na.history_length(body.user_id),
    )


# ══════════════════════════════════════════════════════════
# ENDPOINT 4 — RESET SESSION
# ══════════════════════════════════════════════════════════

@app.post(
    "/chat/reset",
    response_model = ResetResponse,
    summary        = "Réinitialise la conversation d'un utilisateur",
    tags           = ["NLQ Layer"],
)
def reset_chat(body: ResetRequest) -> ResetResponse:
    """
    Réinitialise l'historique de conversation d'un utilisateur.

    Si `user_id` n'a pas de session active → `history_cleared=false` (pas d'erreur).
    """
    _, na = _get_agents()
    cleared = na.reset_conversation(body.user_id)
    return ResetResponse(
        user_id         = body.user_id,
        history_cleared = cleared,
        message         = (
            f"Conversation history cleared for user '{body.user_id}'."
            if cleared
            else f"No active session found for user '{body.user_id}'."
        ),
    )