from app.graph.state import (
    ExecutionTypeEnum, OrchestratorState, RouteEnum, SectorEnum, IntentEnum
)
from app.utils.logger import log_routing_decision
from app.clients.nlq_client import ROUTING_TARGET_MAP

# Confidence thresholds
CONFIDENCE_MIN_SECTOR = 0.60
CONFIDENCE_MIN_INTENT = 0.50

# Sector → Route mapping
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
    sector         = state.sector
    intent         = state.intent
    sector_conf    = state.sector_confidence
    intent_conf    = state.intent_confidence
    execution_type = state.execution_type
    routing_target = state.routing_target

    # ✅ NOUVEAU — passer requires_orchestrator + sub_agent à _decide_route
    route, reason = _decide_route(
        sector, intent, sector_conf, intent_conf,
        execution_type, routing_target,
        requires_orchestrator=state.requires_orchestrator,
        sub_agent=state.sub_agent,
    )

    # Fallback route
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
    state.route        = route
    state.route_reason = reason
    state.fallback_route = fallback
    state.needs_clarification = (route == RouteEnum.CLARIFICATION)
    state.processing_steps.append(f"routing_node → {route.value}")

    return state


def _decide_route(
    sector: SectorEnum,
    intent: IntentEnum,
    sector_conf: float,
    intent_conf: float,
    execution_type: ExecutionTypeEnum,
    routing_target: str = "",
    requires_orchestrator: bool = False,  # ✅ NOUVEAU
    sub_agent: str = "",                  # ✅ NOUVEAU
) -> tuple[RouteEnum, str]:
    """
    Routing logic with 7 priority levels.
    Returns (route, reason).
    """

    # ── Niveau 0 — routing_target de /detect-sector ───────────────
    # Signal direct du Sector Detection Agent, haute confiance
    if routing_target and sector_conf >= 0.80:
        route = ROUTING_TARGET_MAP.get(routing_target)
        if route:
            return (
                route,
                f"Niveau 0 — routing_target='{routing_target}' fourni par "
                f"Context Agent ({sector_conf:.0%} confiance) → route directe."
            )

    # ── Niveau 0 bis — requires_orchestrator=True depuis /chat ────
    # ✅ NOUVEAU — le NLQ Agent a classifié l'intent ET désigné un agent cible
    # Plus précis que le Niveau 0 car il tient compte de l'INTENT réel
    # Exemples :
    #   intent=dashboard   → routing_target=insight_agent
    #   intent=prediction  → routing_target=transport_agent, sub_agent=sector_prediction
    #   intent=anomaly     → routing_target=generic_predictive_agent
    if requires_orchestrator and routing_target:
        route = ROUTING_TARGET_MAP.get(routing_target)
        if route:
            sub_info = f" | sub_agent={sub_agent}" if sub_agent else ""
            return (
                route,
                f"Niveau 0bis — NLQ routing: '{routing_target}'"
                f"{sub_info} | intent={intent.value}."
            )

    # ── Niveau 1 — Confiance trop faible → Clarification ─────────
    if sector_conf < CONFIDENCE_MIN_SECTOR and sector == SectorEnum.UNKNOWN:
        return (
            RouteEnum.CLARIFICATION,
            f"Niveau 1 — Secteur inconnu et confiance trop faible "
            f"({sector_conf:.0%}). Clarification requise."
        )
    if intent_conf < CONFIDENCE_MIN_INTENT and intent == IntentEnum.UNKNOWN:
        return (
            RouteEnum.CLARIFICATION,
            f"Niveau 1 — Intent non reconnu et confiance trop faible "
            f"({intent_conf:.0%}). Clarification requise."
        )

    # ── Niveau 2 — execution_type = insight → Insight Agent ──────
    if execution_type == ExecutionTypeEnum.INSIGHT:
        return (
            RouteEnum.INSIGHT_AGENT,
            "Niveau 2 — execution_type='insight' → Insight Agent prioritized."
        )

    # ── Niveau 3 — execution_type = prediction ────────────────────
    if execution_type == ExecutionTypeEnum.PREDICTION:
        if sector in KNOWN_SECTORS:
            return (
                sector_to_route[sector],
                f"Niveau 3 — Sectorial prediction → agent '{sector.value}'."
            )
        return (
            RouteEnum.GENERIC_ML_AGENT,
            "Niveau 3 — Prediction with unknown sector → Generic ML Agent."
        )

    # ── Niveau 4 — execution_type = sql ───────────────────────────
    if execution_type == ExecutionTypeEnum.SQL:
        if sector in sector_to_route:
            return (
                sector_to_route[sector],
                f"Niveau 4 — SQL query with known sector → agent '{sector.value}'."
            )
        return (
            RouteEnum.GENERIC_ML_AGENT,
            "Niveau 4 — SQL query with unknown sector → Generic ML Agent."
        )

    # ── Niveau 5 — Intent connu ───────────────────────────────────
    if intent in [IntentEnum.DASHBOARD, IntentEnum.COMPARISON,
                  IntentEnum.KPI_CHART, IntentEnum.INSIGHT]:
        return (
            RouteEnum.INSIGHT_AGENT,
            f"Niveau 5 — Intent '{intent.value}' → Insight Agent."
        )

    if intent in [IntentEnum.KPI_REQUEST, IntentEnum.PREDICTION,
                  IntentEnum.SECTOR_ANALYSIS, IntentEnum.ANOMALY]:
        if sector in KNOWN_SECTORS:
            return (
                sector_to_route[sector],
                f"Niveau 5 — Intent '{intent.value}' + secteur connu "
                f"→ agent '{sector.value}'."
            )
        return (
            RouteEnum.GENERIC_ML_AGENT,
            f"Niveau 5 — Intent '{intent.value}' + secteur inconnu "
            "→ Generic ML Agent."
        )

    # ── Niveau 6 — Secteur connu malgré intent inconnu ────────────
    # ✅ NOUVEAU — évite de tomber en Clarification quand le secteur
    # est bien identifié mais l'intent n'est pas encore classifié
    if sector in KNOWN_SECTORS and sector_conf >= CONFIDENCE_MIN_SECTOR:
        return (
            sector_to_route[sector],
            f"Niveau 6 — Secteur connu '{sector.value}' "
            f"({sector_conf:.0%}), intent inconnu → agent sectoriel."
        )

    # ── Défaut — Clarification ─────────────────────────────────────
    return (
        RouteEnum.CLARIFICATION,
        "Défaut — Aucune règle de routing satisfaite → Clarification requise."
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
        return RouteEnum.GENERIC_ML_AGENT

    return RouteEnum.CLARIFICATION