import httpx
import os
from dotenv import load_dotenv
from app.graph.state import (
    OrchestratorState, SectorEnum, RouteEnum
)

load_dotenv()
NLQ_API_URL = os.getenv("NLQ_API_URL", "http://127.0.0.1:8000")

# Mapping routing_target → RouteEnum
ROUTING_TARGET_MAP = {
    "transport_agent":     RouteEnum.TRANSPORT_AGENT,
    "finance_agent":       RouteEnum.FINANCE_AGENT,
    "retail_agent":        RouteEnum.RETAIL_AGENT,
    "manufacturing_agent": RouteEnum.MANUFACTURING_AGENT,
    "public_agent":        RouteEnum.PUBLIC_AGENT,
}


# ✅ Fonction 1 — au niveau racine (pas d'indentation)
async def call_detect_sector(state: OrchestratorState):
    """
    Appelle POST /detect-sector
    Retourne (state, suggested_route)
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{NLQ_API_URL}/detect-sector",
            json={"user_query": state.query_raw}
        )
        sector_context = response.json()

    # Remplir le state
    try:
        state.sector = SectorEnum(
            sector_context.get("sector", "unknown").capitalize()
        )
    except ValueError:
        state.sector = SectorEnum.UNKNOWN

    state.sector_confidence = sector_context.get("confidence", 0.0)
    state.kpi_mapping       = sector_context.get("kpis", [])

    routing_target  = sector_context.get("routing_target", "")
    suggested_route = ROUTING_TARGET_MAP.get(routing_target)

    # Stocker le SectorContext complet pour le NLQ
    state.query_structured = sector_context

    state.processing_steps.append(
        f"detect_sector → sector={state.sector.value} "
        f"({state.sector_confidence:.0%}) | "
        f"routing_target={routing_target}"
    )

    return state, suggested_route


# ✅ Fonction 2 — au niveau racine (pas d'indentation)
async def call_nlq_chat(
    state: OrchestratorState,
    question: str,
    data_profile: dict = None
) -> OrchestratorState:
    """
    Appelle POST /chat
    Activé après le dashboard pour les questions spécifiques.
    """
    payload = {
        "user_id":        state.user_id,
        "question":       question,
        "sector_context": state.query_structured,
    }

    if data_profile:
        payload["data_profile"] = data_profile

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{NLQ_API_URL}/chat",
            json=payload
        )
        chat_result = response.json()

    # Remplir le state
    state.agent_response   = chat_result
    state.final_response   = chat_result.get("answer", "")
    state.canonical_metric = chat_result.get("kpi_referenced", "")

    suggested_chart = chat_result.get("suggested_chart", "")
    state.response_format = "chart" if suggested_chart else "text"

    state.processing_steps.append(
        f"nlq_chat → kpi={state.canonical_metric} | "
        f"chart={suggested_chart}"
    )

    return state