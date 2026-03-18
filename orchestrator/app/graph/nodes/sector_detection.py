from app.graph.state import OrchestratorState, SectorEnum, RouteEnum
from app.clients.nlq_client import call_detect_sector
from app.utils.async_utils import run_async

SECTOR_ROUTE_MAP = {
    "finance":       "finance_agent",
    "healthcare":    "insight_agent",
    "retail":        "retail_agent",
    "manufacturing": "manufacturing_agent",
    "telecom":       "insight_agent",
    "transport":     "transport_agent",
    "public":        "public_agent",
    "general":       "generic_predictive_agent",
}

def sector_detection_node(state: OrchestratorState) -> OrchestratorState:
    # ── Utiliser le secteur déjà détecté dans les metadata ──────────────
    sector_from_meta = state.metadata.get("sector", "").lower()
    if sector_from_meta and sector_from_meta != "unknown":
        try:
            state.sector = SectorEnum(sector_from_meta.capitalize())
        except ValueError:
            state.sector = SectorEnum.UNKNOWN

        state.sector_confidence = 0.90
        state.routing_target    = SECTOR_ROUTE_MAP.get(sector_from_meta, "generic_predictive_agent")
        state.processing_steps.append(
            f"sector_detection → from_metadata: {sector_from_meta} "
            f"| routing_target={state.routing_target}"
        )
        return state

    # ── Fallback : appel NLQ /detect-sector ─────────────────────────────
    try:
        state, _ = run_async(call_detect_sector(state))
    except Exception as e:
        state.errors.append(f"sector_detection → erreur: {e}")
        state.processing_steps.append("sector_detection → ERREUR")
    return state