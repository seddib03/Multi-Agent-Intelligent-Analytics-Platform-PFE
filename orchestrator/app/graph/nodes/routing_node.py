from app.graph.state import(
    ExecutionTypeEnum, OrchestratorState, RouteEnum, SectorEnum, IntentEnum
)
from app.utils.logger import log_routing_decision
from app.clients.nlq_client import ROUTING_TARGET_MAP
#confidence rate
CONFIDENCE_MIN_SECTOR = 0.60
CONFIDENCE_MIN_INTENT =0.50

# Define known sectors and mapping to routes
sector_to_route = {
    SectorEnum.TRANSPORT:     RouteEnum.TRANSPORT_AGENT,
    SectorEnum.FINANCE:       RouteEnum.FINANCE_AGENT,
    SectorEnum.RETAIL:        RouteEnum.RETAIL_AGENT,
    SectorEnum.MANUFACTURING: RouteEnum.MANUFACTURING_AGENT,
    SectorEnum.PUBLIC:        RouteEnum.PUBLIC_AGENT,
}

KNOWN_SECTORS = set(sector_to_route.keys())

def routing_node(state: OrchestratorState) -> OrchestratorState:
    """
    Core of the orchestrator.
    Decides which route to take based on sector + intent.
    """
    sector = state.sector
    intent = state.intent
    sector_conf = state.sector_confidence
    intent_conf = state.intent_confidence
    execution_type = state.execution_type
    routing_target = state.routing_target

    route, reason = _decide_route(sector, intent, sector_conf, intent_conf, execution_type, routing_target)

    #Define fallback route
    fallback = _decide_fallback(sector, route)

    # Log decision
    log_routing_decision(
        query=state.query_raw,
        sector=sector.value,
        sector_confidence=sector_conf,
        intent=intent.value,
        route=route.value,
        reason=reason
    )

    # Update state
    state.route = route
    state.route_reason = reason
    state.fallback_route = fallback
    state.processing_steps.append(f"routing_node → {route.value}")

    return state

def _decide_route(sector: SectorEnum,intent: IntentEnum,sector_conf: float,intent_conf: float, execution_type: ExecutionTypeEnum, routing_target: str = "") -> tuple[RouteEnum, str]:
    """
    Routing logic with 4 priority levels.
    Returns (route, reason).
    """
    # Level 0 routing target from SectorContext Agent (if provided, it has the highest priority as it's a direct signal from the sector detection step)

    if routing_target and sector_conf >= 0.80:
        route = ROUTING_TARGET_MAP.get(routing_target)
        if route:
            return (
                route,
                f"routing_target='{routing_target}' fourni par Context Agent "
                f"({sector_conf:.0%} confiance) → route directe."
            )

    #Level 1: Confidence too low → Clarification

    if sector_conf < CONFIDENCE_MIN_SECTOR and sector == SectorEnum.UNKNOWN:
        return (
            RouteEnum.CLARIFICATION,
            f"Unknown sector and confidence too low ({sector_conf:.0%}). "
            "Clarification required."
        )
    if intent_conf < CONFIDENCE_MIN_INTENT and intent == IntentEnum.UNKNOWN:
        return (
            RouteEnum.CLARIFICATION,
            f"Intent not recognized and confidence too low ({intent_conf:.0%}). "
            "Clarification required."
        )
    
    # Level 2: execution type is insight → Insight Agent (even if sector is known, we want to prioritize insights)
    if execution_type == ExecutionTypeEnum.INSIGHT:
        return (
            RouteEnum.INSIGHT_AGENT,
            f"Execution type is 'insight' → Insight Agent prioritized."
        )
    
    # Level 3 : execution type is prediction → Generic ML Agent (even if sector is known, we want to prioritize predictive insights)
    if execution_type == ExecutionTypeEnum.PREDICTION:
        if sector in KNOWN_SECTORS:
            return (
                sector_to_route[sector],
                f"Secorial prediction request → Sector-specific agent for '{sector.value}'."
            )
        return RouteEnum.GENERIC_ML_AGENT, "Prediction request with unknown sector → Generic ML Agent."
    
    # Level 4: execution type is SQL → route to sector agent if sector is known, otherwise clarification (we want to prioritize SQL queries to get faster answers, but if sector is unknown we need clarification to avoid wrong answers)
    if execution_type == ExecutionTypeEnum.SQL:
        if sector in sector_to_route:
            return (
                sector_to_route[sector],
                f"SQL query with known sector → Sector-specific agent for '{sector.value}'."
            )
        return RouteEnum.GENERIC_ML_AGENT, "SQL query with unknown sector → Generic ML Agent (fallback to clarification if it fails)."

    
    
    #Level 5: Dashboard/Chart intent → Insight Agent
    # Regardless of sector, dashboards always go to Insight

    if intent in [IntentEnum.DASHBOARD, IntentEnum.COMPARISON]:
        return (
            RouteEnum.INSIGHT_AGENT,
            f"Intent '{intent.value}' requires the Insight Agent "
            "(KPI routing + Power BI)."
        )
    
    if intent in [IntentEnum.KPI_REQUEST, IntentEnum.PREDICTION]:
        if sector in KNOWN_SECTORS:
            return (
                sector_to_route[sector],
                f"Intent '{intent.value}' with known sector → '{sector.value}' agent."
            )
        return (
            RouteEnum.GENERIC_ML_AGENT,
            f"Intent '{intent.value}' with unknown sector → Generic ML Agent."
        )
    
    # Default: Clarification (we don't have a clear rule to route, we need clarification to avoid wrong answers)
    return RouteEnum.CLARIFICATION, "No clear routing rule matched → Clarification required."


def _decide_fallback(sector: SectorEnum, primary_route: RouteEnum) -> RouteEnum:
    """
    Defines the fallback route if the primary agent fails.
    """
    if primary_route == RouteEnum.GENERIC_ML_AGENT:
        return RouteEnum.CLARIFICATION

    if primary_route in [
        RouteEnum.TRANSPORT_AGENT,
        RouteEnum.FINANCE_AGENT,
        RouteEnum.RETAIL_AGENT,
        RouteEnum.MANUFACTURING_AGENT,
        RouteEnum.PUBLIC_AGENT,
    ]:
        # If sector agent fails → fallback to Generic ML
        return RouteEnum.GENERIC_ML_AGENT

    return RouteEnum.CLARIFICATION

