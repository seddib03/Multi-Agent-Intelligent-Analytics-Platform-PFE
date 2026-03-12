from app.graph.state import OrchestratorState, RouteEnum
from app.clients.nlq_client import call_detect_sector
from app.utils.async_utils import run_async

ROUTING_TARGET_MAP = {
    "transport_agent":     RouteEnum.TRANSPORT_AGENT,
    "finance_agent":       RouteEnum.FINANCE_AGENT,
    "retail_agent":        RouteEnum.RETAIL_AGENT,
    "manufacturing_agent": RouteEnum.MANUFACTURING_AGENT,
    "public_agent":        RouteEnum.PUBLIC_AGENT,
}

def sector_detection_node(state: OrchestratorState) -> OrchestratorState:
    state, suggested_route = run_async(call_detect_sector(state))
    return state