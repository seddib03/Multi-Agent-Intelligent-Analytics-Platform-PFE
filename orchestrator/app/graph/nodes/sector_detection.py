from app.graph.state import OrchestratorState, SectorEnum, RouteEnum
from app.clients.nlq_client import call_detect_sector
import asyncio

# Mapping routing_target → RouteEnum
ROUTING_TARGET_MAP = {
    "transport_agent":     RouteEnum.TRANSPORT_AGENT,
    "finance_agent":       RouteEnum.FINANCE_AGENT,
    "retail_agent":        RouteEnum.RETAIL_AGENT,
    "manufacturing_agent": RouteEnum.MANUFACTURING_AGENT,
    "public_agent":        RouteEnum.PUBLIC_AGENT,
}

def sector_detection_node(state: OrchestratorState) -> OrchestratorState:
    """
    Sprint 1 mock (mots-clés) → remplacé par l'API réelle de la collègue.
    Appelle POST /detect-sector et remplit le state avec le SectorContext.
    """
    # Appel à l'API de ta collègue
    state, suggested_route = asyncio.run(call_detect_sector(state))

    # Si elle suggère une route → on la stocke dans le state
    if suggested_route:
        state.routing_target = suggested_route.value

    return state