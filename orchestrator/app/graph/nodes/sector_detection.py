from app.graph.state import OrchestratorState, SectorEnum

# Keywords per sector to simulate detection
SECTOR_KEYWORDS = {
    SectorEnum.TRANSPORT:     ["transport", "delivery", "trip", "fleet", "logistics", "km", "driver"],
    SectorEnum.FINANCE:       ["finance", "revenue", "figure", "income", "margin", "budget", "cash", "ebitda"],
    SectorEnum.RETAIL:        ["retail", "sales", "store", "inventory", "product", "customer", "basket"],
    SectorEnum.MANUFACTURING: ["production", "factory", "manufacture", "quality", "defect", "yield"],
    SectorEnum.PUBLIC:        ["public", "citizen", "public service", "town hall", "community"],
}

def sector_detection_node(state: OrchestratorState) -> OrchestratorState:
    """
    Mock Sprint 1: keyword-based detection.
    Sprint 2: replaced by the real ML Sector Detection Agent.
    """
    query_lower = state.query_raw.lower()
    best_sector = SectorEnum.UNKNOWN
    best_score = 0.0

    for sector, keywords in SECTOR_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in query_lower)
        score = min(matches / 3, 1.0)  # Normalize between 0 and 1
        if score > best_score:
            best_score = score
            best_sector = sector
            
    # If no match → low confidence
    if best_score == 0:
        best_sector = SectorEnum.UNKNOWN
        best_score = 0.1

    state.sector = best_sector
    state.sector_confidence = round(best_score, 2)
    state.processing_steps.append(
        f"sector_detection → {best_sector.value} ({best_score:.0%})"
    )

    return state
        