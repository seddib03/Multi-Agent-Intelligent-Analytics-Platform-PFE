from app.graph.state import(
    OrchestratorState, RouteEnum, SectorEnum, IntentEnum
)
from app.utils.logger import log_routing_decision

#confidence rate
CONFIDENCE_MIN_SECTOR = 0.60
CONFIDENCE_MIN_INTENT =0.50


def routing_node(state: OrchestratorState) -> OrchestratorState:
    """
    Core of the orchestrator.
    Decides which route to take based on sector + intent.
    """
    sector = state.sector
    intent = state.intent
    sector_conf = state.sector_confidence
    intent_conf = state.intent_confidence

    route, reason = _decide_route(sector, intent, sector_conf, intent_conf)

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

def _decide_route(
        sector: SectorEnum,
        intent: IntentEnum,
        sector_conf: float,
        intent_conf: float
) -> tuple[RouteEnum, str]:
    """
    Routing logic with 4 priority levels.
    Returns (route, reason).
    """

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
    
    #Level 2: Dashboard/Chart intent → Insight Agent
    # Regardless of sector, dashboards always go to Insight

    if intent in [IntentEnum.DASHBOARD, IntentEnum.COMPARISON]:
        return (
            RouteEnum.INSIGHT_AGENT,
            f"Intent '{intent.value}' requires the Insight Agent "
            "(KPI routing + Power BI)."
        )
    
    #Level 3: Known sector → Sector Agent

    sector_to_route = {
        SectorEnum.TRANSPORT:     RouteEnum.TRANSPORT_AGENT,
        SectorEnum.FINANCE:       RouteEnum.FINANCE_AGENT,
        SectorEnum.RETAIL:        RouteEnum.RETAIL_AGENT,
        SectorEnum.MANUFACTURING: RouteEnum.MANUFACTURING_AGENT,
        SectorEnum.PUBLIC:        RouteEnum.PUBLIC_AGENT,
    }

    if sector in sector_to_route:
        route = sector_to_route[sector]
        return (
            route,
            f"Sector '{sector.value}' detected ({sector_conf:.0%} confidence) "
            f"+ Intent '{intent.value}' → Sector-specific agent."
        )
    
    #Level 4: Unknown sector but clear intent → Generic ML

    if intent in [IntentEnum.PREDICTION, IntentEnum.KPI_REQUEST]:
        return (
            RouteEnum.GENERIC_ML_AGENT,
            f"Unknown sector but clear intent '{intent.value}' → "
            "Generic Predictive Agent (AutoML)."
        )
    
    #Level 5: Default case

    return (
        RouteEnum.CLARIFICATION,
        "No route could be determined with sufficient confidence. Clarification requested."
    )


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

