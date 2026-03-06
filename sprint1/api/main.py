"""
FastAPI Application — Intelligence Analytics Platform
======================================================
PFE — DXC Technology | Sprint 1
Author: [Votre Nom]

Endpoints exposés
-----------------
  POST /detect-sector   → Context/Sector Agent
  POST /chat            → NLQ Agent (chatbot)
  POST /chat/reset      → Réinitialiser session NLQ
  GET  /health          → Status de l'API

Consumers de cette API
----------------------
  - User Interface (UI) : envoie la query globale, affiche dashboard et chatbot
  - Orchestrateur       : reçoit le SectorContext pour router vers l'agent sectoriel

Lancer l'API
------------
  uvicorn api.main:app --reload --port 8000

Accès Swagger (documentation interactive)
------------------------------------------
  http://localhost:8000/docs

Accès ReDoc
-----------
  http://localhost:8000/redoc
"""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from agents.context_sector_agent import (
    ContextSectorAgent,
    ColumnMetadata,
    SectorContext,
    KPI,
)
from agents.nlq_agent import NLQAgent
from api.schemas import (
    DetectSectorRequest,
    DetectSectorResponse,
    ChatRequest,
    ChatResponse,
    ResetChatRequest,
    ResetChatResponse,
    HealthResponse,
    KPISchema,
)

load_dotenv()


# ══════════════════════════════════════════════════════════
# ÉTAT GLOBAL DE L'APPLICATION
# ══════════════════════════════════════════════════════════

class AppState:
    """
    État partagé de l'application FastAPI.

    Contient :
    - sector_agent : instance unique du ContextSectorAgent (réutilisée)
    - nlq_sessions : dict {user_id → NLQAgent} pour maintenir les sessions
      de conversation par utilisateur

    Pourquoi un dict de sessions ?
    --------------------------------
    Le NLQ Agent maintient un historique de conversation en mémoire.
    Pour que chaque utilisateur ait son propre historique indépendant,
    on crée et stocke une instance NLQAgent par user_id.

    Limitation Sprint 1 : stockage en mémoire Python.
    Sprint suivant : migrer vers Redis pour la persistence.
    """
    sector_agent: Optional[ContextSectorAgent] = None
    nlq_sessions: dict[str, NLQAgent] = {}


app_state = AppState()


# ══════════════════════════════════════════════════════════
# LIFECYCLE — Initialisation au démarrage
# ══════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialise les agents au démarrage de l'application.
    Libère les ressources à l'arrêt.

    Le ContextSectorAgent est instancié une seule fois et réutilisé
    pour toutes les requêtes (chargement du LLM et config KPI).
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY manquante dans les variables d'environnement.\n"
            "Créer un fichier .env avec : OPENROUTER_API_KEY=sk-or-v1-..."
        )

    print("[Startup] Initializing Context/Sector Agent...")
    app_state.sector_agent = ContextSectorAgent(
        openrouter_api_key=api_key,
        config_path="config/kpi_config.yaml",
        verbose=False
    )
    print("[Startup] ✅ API ready — model: meta-llama/llama-3.1-8b-instruct")

    yield  # L'application tourne ici

    # Nettoyage à l'arrêt
    print("[Shutdown] Clearing NLQ sessions...")
    app_state.nlq_sessions.clear()


# ══════════════════════════════════════════════════════════
# APPLICATION FASTAPI
# ══════════════════════════════════════════════════════════

app = FastAPI(
    title="Intelligence Analytics Platform — Sprint 1 API",
    description="""
## DXC Technology | PFE | Multi-Sector AI Analytics

### Agents disponibles
- **Context/Sector Agent** : détecte le secteur business et mappe les KPIs
- **NLQ Agent** : chatbot analytique contextuel (questions spécifiques)

### Flux typique
1. `POST /detect-sector` → obtenir le SectorContext
2. Afficher le dashboard global (côté UI ou Orchestrateur)
3. `POST /chat` → poser des questions spécifiques
4. `POST /chat/reset` → nouvelle session si besoin
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS — permet à l'UI (React/Vue) d'appeler l'API depuis un autre port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # En prod : restreindre aux domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def get_or_create_nlq_session(user_id: str) -> NLQAgent:
    """
    Retourne la session NLQ existante ou en crée une nouvelle.

    Chaque utilisateur a sa propre instance NLQAgent avec
    son historique de conversation isolé.

    Parameters
    ----------
    user_id : str
        Identifiant unique de l'utilisateur

    Returns
    -------
    NLQAgent
        Instance dédiée à cet utilisateur
    """
    if user_id not in app_state.nlq_sessions:
        api_key = os.getenv("OPENROUTER_API_KEY")
        app_state.nlq_sessions[user_id] = NLQAgent(
            openrouter_api_key=api_key,
            verbose=False
        )
    return app_state.nlq_sessions[user_id]


def sector_context_from_dict(data: dict) -> SectorContext:
    """
    Reconstruit un SectorContext depuis le dict JSON de la requête.

    Nécessaire car le SectorContext est retourné par /detect-sector
    puis renvoyé dans le corps de /chat — on doit le reconstruire.

    Parameters
    ----------
    data : dict
        Dict JSON correspondant à un SectorContext sérialisé

    Returns
    -------
    SectorContext

    Raises
    ------
    HTTPException 422
        Si le dict ne correspond pas au schéma SectorContext
    """
    try:
        kpis = [KPI(**k) for k in data.get("kpis", [])]
        return SectorContext(
            sector=data["sector"],
            confidence=data["confidence"],
            use_case=data["use_case"],
            metadata_used=data.get("metadata_used", False),
            kpis=kpis,
            dashboard_focus=data["dashboard_focus"],
            recommended_charts=data.get("recommended_charts", []),
            routing_target=data["routing_target"],
            explanation=data.get("explanation", "")
        )
    except (KeyError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sector_context format: {str(e)}. "
                   f"Make sure you pass the full response from POST /detect-sector."
        )


def sector_context_to_response(ctx: SectorContext) -> DetectSectorResponse:
    """Convertit un SectorContext métier en réponse API."""
    return DetectSectorResponse(
        sector=ctx.sector,
        confidence=ctx.confidence,
        use_case=ctx.use_case,
        metadata_used=ctx.metadata_used,
        kpis=[KPISchema(**k.__dict__) for k in ctx.kpis],
        dashboard_focus=ctx.dashboard_focus,
        recommended_charts=ctx.recommended_charts,
        routing_target=ctx.routing_target,
        explanation=ctx.explanation
    )


# ══════════════════════════════════════════════════════════
# ENDPOINT 1 — GET /health
# ══════════════════════════════════════════════════════════

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Status de l'API",
    tags=["Monitoring"]
)
async def health_check():
    """
    Vérifie que l'API est opérationnelle.

    Retourne le statut, le modèle LLM utilisé, et le nombre
    de sessions NLQ actives en mémoire.

    **Utilisé par :**
    - L'orchestrateur pour vérifier la disponibilité avant d'envoyer des requêtes
    - Les outils de monitoring (healthcheck Docker, etc.)
    """
    return HealthResponse(
        status="ok",
        model=ContextSectorAgent.MODEL,
        active_sessions=len(app_state.nlq_sessions)
    )


# ══════════════════════════════════════════════════════════
# ENDPOINT 2 — POST /detect-sector
# ══════════════════════════════════════════════════════════

@app.post(
    "/detect-sector",
    response_model=DetectSectorResponse,
    status_code=status.HTTP_200_OK,
    summary="Détecter le secteur et mapper les KPIs",
    tags=["Context/Sector Agent"]
)
async def detect_sector(request: DetectSectorRequest):
    """
    **Context/Sector Agent** — Analyse l'objectif de l'utilisateur et retourne
    un contexte enrichi avec secteur, KPIs et informations de routing.

    ### Quand appeler cet endpoint ?
    - Dès que l'utilisateur soumet son objectif global
    - Avant d'afficher le dashboard global
    - L'orchestrateur l'appelle pour obtenir le `routing_target`

    ### Avec ou sans metadata ?
    - **Sans metadata** : suffit si la query est précise
      (`"améliorer l'expérience des passagers de l'aéroport"`)
    - **Avec metadata** : recommandé si la query est générique
      (`"améliorer l'expérience client"` + colonnes dataset)

    ### Réponse
    Le champ `routing_target` indique à l'orchestrateur vers quel agent sectoriel
    router : `"transport_agent"`, `"finance_agent"`, etc.

    **Conserver la réponse complète** — elle doit être passée telle quelle
    au champ `sector_context` de `POST /chat`.
    """
    # Convertir les metadata du schéma API vers le modèle agent
    column_metadata = None
    if request.column_metadata:
        column_metadata = [
            ColumnMetadata(
                name=col.name,
                description=col.description,
                sample_values=col.sample_values
            )
            for col in request.column_metadata
        ]

    try:
        sector_ctx = app_state.sector_agent.detect(
            user_query=request.user_query,
            column_metadata=column_metadata
        )
        return sector_context_to_response(sector_ctx)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM returned an unparseable response: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sector detection failed: {str(e)}"
        )


# ══════════════════════════════════════════════════════════
# ENDPOINT 3 — POST /chat
# ══════════════════════════════════════════════════════════

@app.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Poser une question analytique (NLQ chatbot)",
    tags=["NLQ Agent"]
)
async def chat(request: ChatRequest):
    """
    **NLQ Agent** — Répond à une question spécifique de l'utilisateur
    dans le contexte du secteur détecté.

    ### Quand appeler cet endpoint ?
    Après que l'utilisateur a vu le dashboard global et veut approfondir.
    Exemples de questions :
    - `"Quel est le taux de retard moyen ce mois ?"`
    - `"Compare la satisfaction entre les routes"`
    - `"Quels vols ont les pires scores ?"`

    ### Gestion de la conversation
    L'historique est maintenu **côté serveur** par `user_id`.
    Les questions de suivi fonctionnent naturellement :
    - Tour 1 : `"Quel est le retard moyen ?"` → `"12.4 minutes en moyenne"`
    - Tour 2 : `"Et pour la route CMN-CDG ?"` → le bot sait que "ça" = retard

    ### sector_context
    Passer **exactement** la réponse JSON complète de `POST /detect-sector`.

    ### data_profile (optionnel)
    Si fourni (par le Data Prep Agent), le SQL généré utilisera
    les vrais noms de colonnes du dataset.
    """
    # Récupérer ou créer la session NLQ pour cet utilisateur
    nlq_agent = get_or_create_nlq_session(request.user_id)

    # Reconstruire le SectorContext depuis le dict JSON
    sector_ctx = sector_context_from_dict(request.sector_context)

    try:
        nlq_response = nlq_agent.chat(
            user_question=request.question,
            sector_context=sector_ctx,
            data_profile=request.data_profile
        )

        return ChatResponse(
            user_id=request.user_id,
            answer=nlq_response.answer,
            query_type=nlq_response.query_type,
            generated_query=nlq_response.generated_query,
            kpi_referenced=nlq_response.kpi_referenced,
            suggested_chart=nlq_response.suggested_chart,
            needs_more_data=nlq_response.needs_more_data,
            history_length=nlq_agent.history_length
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"NLQ Agent failed: {str(e)}"
        )


# ══════════════════════════════════════════════════════════
# ENDPOINT 4 — POST /chat/reset
# ══════════════════════════════════════════════════════════

@app.post(
    "/chat/reset",
    response_model=ResetChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Réinitialiser la session de conversation",
    tags=["NLQ Agent"]
)
async def reset_chat(request: ResetChatRequest):
    """
    **Réinitialise l'historique de conversation** d'un utilisateur.

    ### Quand appeler cet endpoint ?
    - Quand l'utilisateur change de sujet ou de secteur
    - Quand l'utilisateur clique "Nouvelle conversation" dans l'UI
    - Quand l'orchestrateur démarre un nouveau workflow

    Après un reset, le prochain appel à `POST /chat` repart
    d'une conversation vide pour cet `user_id`.
    """
    if request.user_id in app_state.nlq_sessions:
        app_state.nlq_sessions[request.user_id].reset_conversation()
        return ResetChatResponse(
            user_id=request.user_id,
            message=f"Conversation history cleared for user '{request.user_id}'.",
            history_cleared=True
        )
    else:
        # Pas de session existante — c'est ok, on considère ça comme un succès
        return ResetChatResponse(
            user_id=request.user_id,
            message=f"No active session found for user '{request.user_id}'.",
            history_cleared=False
        )