"""
API FastAPI — Intelligence Analytics Platform
=============================================
PFE — DXC Technology | Sprint 1

Expose les 2 agents du Sprint 1 via 4 endpoints REST.

Endpoints
---------
GET  /health          → status API + modèle + sessions actives
POST /detect-sector   → Sector Detection Agent → SectorContext
POST /chat            → NLQ Layer → réponse analytique ou routing
POST /chat/reset      → réinitialiser la conversation d'un user

Consommateurs
-------------
- UI (Frontend)       → /detect-sector puis /chat (chatbot)
- Orchestrateur       → /detect-sector (routing_target)
- Data Prep Agent     → fournit data_profile dans /chat

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

from agents.context_sector_agent import ContextSectorAgent as SectorDetectionAgent, ColumnMetadata
from agents.nlq_agent import NLQAgent
from api.schemas import (
    DetectSectorRequest, DetectSectorResponse,
    ChatRequest, ChatResponse,
    ResetRequest, ResetResponse,
    HealthResponse,
)

# ══════════════════════════════════════════════════════════
# INITIALISATION
# ══════════════════════════════════════════════════════════

load_dotenv()

app = FastAPI(
    title       = "DXC Intelligence Analytics Platform — Sprint 1",
    description = (
        "API exposant le Sector Detection Agent et la NLQ Layer.\n\n"
        "**Flux recommandé :**\n"
        "1. `POST /detect-sector` → obtenir le SectorContext\n"
        "2. `POST /chat` → poser des questions analytiques (chatbot)\n"
        "3. `POST /chat/reset` → réinitialiser la session\n\n"
        "**Note :** Si `requires_orchestrator=true` dans la réponse de `/chat`, "
        "l'UI doit appeler l'Orchestrateur (Sprint 2) avec `routing_target` + `sub_agent`."
    ),
    version = "1.0.0",
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
# En production, instanciés au premier appel d'endpoint via _get_agents().
# Les tests font : patch("api.main.sector_agent") / patch("api.main.nlq_agent")
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

    En production, sector_agent et nlq_agent sont None au démarrage,
    donc on instancie avec la vraie clé API au premier appel.
    """
    import api.main as _self          # référence au module courant
    sa = _self.sector_agent
    na = _self.nlq_agent
    if sa is None or na is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not found. "
                "Create a .env file with: OPENROUTER_API_KEY=sk-or-v1-..."
            )
        sa = SectorDetectionAgent(openrouter_api_key=api_key, verbose=False)
        na = NLQAgent(openrouter_api_key=api_key, verbose=False)
        _self.sector_agent = sa
        _self.nlq_agent    = na
    return sa, na


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
    """
    Vérifie que l'API est opérationnelle.

    Retourne le modèle LLM utilisé et le nombre de sessions NLQ actives.

    **Utilisé par :**
    - L'Orchestrateur pour vérifier la disponibilité avant d'appeler /detect-sector
    - Les tests de démarrage
    """
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

    **Appeler en premier** — avant tout appel à `/chat`.
    La réponse contient le `sector_context` à passer dans chaque appel `/chat`.

    **Cas d'usage :**

    **1. Query précise (sans colonnes)**
    ```json
    {"user_query": "améliorer l'expérience des passagers de l'aéroport"}
    ```
    → secteur `transport` détecté avec haute confiance (>0.85)

    **2. Query ambiguë avec colonnes**
    ```json
    {
      "user_query": "améliorer l'expérience client",
      "column_metadata": [
        {"name": "flight_id", "description": "identifiant du vol"},
        {"name": "delay_minutes", "sample_values": ["0", "15", "45"]}
      ]
    }
    ```
    → colonnes `flight_id`, `delay_minutes` → secteur `transport` confirmé,
    `metadata_used=true`, confidence ≥ 0.90

    **Champs clés de la réponse :**
    - `routing_target` → utilisé par l'Orchestrateur pour router vers l'agent sectoriel
    - `kpis` → KPIs à afficher sur le dashboard global
    - `confidence` → si < 0.7, suggérer à l'utilisateur de fournir des colonnes
    """
    # Conversion des colonnes si fournies
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
    **NLQ Layer (NLQ Agent + Intent Classifier)** — chatbot analytique.

    Traite une question spécifique dans le contexte sectoriel détecté.

    **Pré-requis :** Avoir appelé `/detect-sector` et conserver la réponse complète
    comme `sector_context` dans chaque appel `/chat`.

    **Exemples de questions :**

    **Agrégation** → SQL généré, KPI référencé
    ```json
    {
      "user_id": "user_001",
      "question": "Quel est le taux de retard moyen ce mois ?",
      "sector_context": { ...réponse de /detect-sector... }
    }
    ```

    **Question de suivi** → l'historique est injecté automatiquement
    ```json
    {
      "user_id": "user_001",
      "question": "Et pour la route CMN-CDG spécifiquement ?",
      "sector_context": { ...même contexte... }
    }
    ```

    **Prédiction** → routée vers l'Orchestrateur
    ```json
    {
      "user_id": "user_001",
      "question": "Prédis le taux de retard le mois prochain",
      "sector_context": { ... }
    }
    ```
    → `requires_orchestrator=true`, `routing_hint="predictive_agent"`

    **Avec data_profile** (fourni par le Data Prep Agent)
    → SQL utilise les vrais noms de colonnes du dataset

    **Champs clés à surveiller dans la réponse :**
    - `requires_orchestrator` → si `true`, appeler l'Orchestrateur avec `routing_hint`
    - `generated_query` → SQL à exécuter sur les données
    - `history_length` → nombre de tours dans la session (doit croître)
    """
    _, na = _get_agents()
    try:
        result = na.chat(
            user_id        = body.user_id,
            question       = body.question,
            sector_context = body.sector_context,
            data_profile   = body.data_profile,
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
    **Réinitialise l'historique de conversation** d'un utilisateur.

    À appeler quand :
    - L'utilisateur change de sujet ou démarre un nouveau workflow
    - L'UI détecte une déconnexion ou fin de session

    Si `user_id` n'a pas de session active → `history_cleared=false` (pas d'erreur).

    **Note :** L'appel à `/detect-sector` n'est pas nécessaire après un reset
    si l'utilisateur garde le même objectif.
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
