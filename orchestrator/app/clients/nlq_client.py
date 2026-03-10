import httpx
import os
from dotenv import load_dotenv
from app.graph.state import (
    OrchestratorState, SectorEnum, IntentEnum, RouteEnum
)

load_dotenv()
NLQ_API_URL = os.getenv("NLQ_API_URL", "http://127.0.0.1:8000")

# Mapping routing_target → RouteEnum
ROUTING_TARGET_MAP = {
    "transport_agent":          RouteEnum.TRANSPORT_AGENT,
    "finance_agent":            RouteEnum.FINANCE_AGENT,
    "retail_agent":             RouteEnum.RETAIL_AGENT,
    "manufacturing_agent":      RouteEnum.MANUFACTURING_AGENT,
    "public_agent":             RouteEnum.PUBLIC_AGENT,
    "generic_predictive_agent": RouteEnum.GENERIC_ML_AGENT,
    "insight_agent":            RouteEnum.INSIGHT_AGENT,
}


def _format_data_profile_for_nlq(state: OrchestratorState) -> dict | None:
    """
    Convertit le data_profile produit par le Collègue 2
    au format attendu par le Collègue 1 dans /chat.

    Collègue 2 produit :              Collègue 1 attend :
    {                                 {
      "columns": ["flight_id", ...],    "columns": [
      "row_count": 500,                   {"name": "flight_id",
      "numeric_columns": [...],            "type": "float",
      ...                                  "sample_values": []}
    }                                   ],
                                        "row_count": 500
                                      }
    """
    if not state.data_profile:
        return None

    columns_formatted = []

    for col in state.data_profile.get("numeric_columns", []):
        columns_formatted.append({
            "name": col, "type": "float", "sample_values": []
        })

    for col in state.data_profile.get("categorical_columns", []):
        columns_formatted.append({
            "name": col, "type": "string", "sample_values": []
        })

    already_added = (
        state.data_profile.get("numeric_columns", []) +
        state.data_profile.get("categorical_columns", [])
    )
    for col in state.data_profile.get("columns", []):
        if col not in already_added:
            columns_formatted.append({
                "name": col, "type": "unknown", "sample_values": []
            })

    return {
        "columns":   columns_formatted,
        "row_count": state.data_profile.get("row_count", 0)
    }


async def call_detect_sector(state: OrchestratorState):
    """
    Appelle POST /detect-sector (Collègue 1).
    Retourne (state, suggested_route)
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{NLQ_API_URL}/detect-sector",
                json={"user_query": state.query_raw}
            )
            sector_context = response.json()

        try:
            state.sector = SectorEnum(
                sector_context.get("sector", "unknown").capitalize()
            )
        except ValueError:
            state.sector = SectorEnum.UNKNOWN

        state.sector_confidence = float(sector_context.get("confidence", 0.0))
        state.kpi_mapping       = sector_context.get("kpis", [])

        # ✅ FIX 1 — routing_target stocké dans state (nécessaire pour routing_node Niveau 0)
        routing_target       = sector_context.get("routing_target", "")
        state.routing_target = routing_target

        # SectorContext complet gardé pour /chat
        state.query_structured = sector_context

        suggested_route = ROUTING_TARGET_MAP.get(routing_target)

        state.processing_steps.append(
            f"detect_sector → sector={state.sector.value} "
            f"({state.sector_confidence:.0%}) | "
            f"routing_target={routing_target}"
        )

        return state, suggested_route

    except httpx.ConnectError:
        state.errors.append("❌ NLQ API /detect-sector non disponible")
        state.processing_steps.append("detect_sector → ERREUR connexion")
        return state, None


async def call_nlq_chat(
    state: OrchestratorState,
    question: str,
    data_profile: dict = None
) -> OrchestratorState:
    """
    Appelle POST /chat (Collègue 1).
    Sprint 2 : classifie l'intent et route si nécessaire.
    """
    try:
        payload = {
            "user_id":        state.user_id,
            "question":       question,
            "sector_context": state.query_structured,
        }

        # ✅ FIX 2 — utiliser _format_data_profile_for_nlq
        # Convertit format Collègue 2 → format attendu par Collègue 1
        nlq_profile = data_profile or _format_data_profile_for_nlq(state)
        if nlq_profile:
            payload["data_profile"] = nlq_profile

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{NLQ_API_URL}/chat",
                json=payload
            )
            chat_result = response.json()

        state.agent_response   = chat_result
        state.final_response   = chat_result.get("answer", "")
        state.canonical_metric = chat_result.get("kpi_referenced", "")

        # ✅ FIX 3 — remplir state.intent (nécessaire pour routing_node Niveaux 5 et 6)
        intent_raw = chat_result.get("intent", "unknown")
        try:
            state.intent = IntentEnum(intent_raw.lower())
        except ValueError:
            state.intent = IntentEnum.UNKNOWN
        state.intent_confidence = float(chat_result.get("confidence", 0.0))

        # requires_orchestrator + sub_agent
        state.requires_orchestrator = chat_result.get("requires_orchestrator", False)
        state.sub_agent             = chat_result.get("sub_agent", "")

        # routing_target depuis /chat (prioritaire si présent)
        if chat_result.get("routing_target"):
            state.routing_target = chat_result["routing_target"]

        suggested_chart       = chat_result.get("suggested_chart", "")
        state.response_format = "chart" if suggested_chart else "text"

        state.processing_steps.append(
            f"nlq_chat → intent={state.intent.value} | "
            f"requires_orchestrator={state.requires_orchestrator} | "
            f"sub_agent={state.sub_agent or 'none'} | "
            f"kpi={state.canonical_metric}"
        )

    except httpx.ConnectError:
        state.errors.append("❌ NLQ API /chat non disponible")
        state.processing_steps.append("nlq_chat → ERREUR connexion")

    return state


async def reset_nlq_session(user_id: str) -> dict:
    """
    Appelle POST /chat/reset (Collègue 1).
    Nettoie l'historique de conversation de l'utilisateur.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{NLQ_API_URL}/chat/reset",
            json={"user_id": user_id}
        )
        return response.json()