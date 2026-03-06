def detect_sector(use_case: str) -> str:
    """Best-effort sector detection placeholder used by project routes."""
    text = (use_case or "").lower()
    keywords = {
        "finance": ["bank", "financ", "assurance", "credit", "loan"],
        "healthcare": ["health", "hospital", "patient", "medical", "clinic"],
        "retail": ["retail", "ecommerce", "shop", "customer", "sales"],
        "manufacturing": ["factory", "production", "supply", "manufacturing"],
        "telecom": ["telecom", "network", "subscriber", "5g", "broadband"],
    }

    for sector, terms in keywords.items():
        if any(term in text for term in terms):
            return sector

    return "general"
