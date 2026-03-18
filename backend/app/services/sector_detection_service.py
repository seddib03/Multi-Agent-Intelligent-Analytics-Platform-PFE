from __future__ import annotations

SECTOR_META: dict[str, dict] = {
    "finance": {
        "keywords": ["bank", "financ", "assurance", "credit", "loan", "fraud", "transaction", "investissement", "bours", "trading", "fraude", "bancaire", "paiement", "risque"],
        "kpis": [
            {"name": "Taux de fraude", "description": "Pourcentage de transactions frauduleuses", "unit": "%", "priority": "high"},
            {"name": "Score de crédit moyen", "description": "Score moyen du portefeuille", "unit": "pts", "priority": "high"},
            {"name": "Valeur à risque (VaR)", "description": "Perte potentielle maximale", "unit": "€", "priority": "medium"},
        ],
        "dashboard_focus": "risk_monitoring",
        "recommended_charts": ["line", "bar", "heatmap"],
        "routing_target": "fraud_detection_agent",
        "explanation": "Secteur finance détecté — focus sur la gestion du risque et la détection de fraude.",
    },
    "healthcare": {
        "keywords": ["health", "hospital", "patient", "medical", "clinic", "santé", "hôpital", "médical", "soin", "diagnostic"],
        "kpis": [
            {"name": "Durée moyenne de séjour", "description": "Jours moyens par patient", "unit": "jours", "priority": "high"},
            {"name": "Taux de réadmission", "description": "Patients réadmis dans les 30 jours", "unit": "%", "priority": "high"},
            {"name": "Occupation des lits", "description": "Taux d'utilisation des lits", "unit": "%", "priority": "medium"},
        ],
        "dashboard_focus": "patient_outcomes",
        "recommended_charts": ["line", "bar", "area"],
        "routing_target": "healthcare_agent",
        "explanation": "Secteur santé détecté — focus sur les résultats patients et la gestion des ressources.",
    },
    "retail": {
        "keywords": ["retail", "ecommerce", "shop", "customer", "sales", "vente", "client", "produit", "panier", "recommandation", "stock"],
        "kpis": [
            {"name": "Chiffre d'affaires", "description": "Revenus totaux", "unit": "€", "priority": "high"},
            {"name": "Panier moyen", "description": "Valeur moyenne par commande", "unit": "€", "priority": "high"},
            {"name": "Taux de rétention client", "description": "Clients fidèles sur 12 mois", "unit": "%", "priority": "medium"},
        ],
        "dashboard_focus": "sales_performance",
        "recommended_charts": ["bar", "pie", "line"],
        "routing_target": "retail_agent",
        "explanation": "Secteur retail détecté — focus sur la performance des ventes et la fidélisation client.",
    },
    "manufacturing": {
        "keywords": ["factory", "production", "supply", "manufacturing", "usine", "défaut", "qualité", "ligne", "machine", "maintenance"],
        "kpis": [
            {"name": "Taux de défauts", "description": "Produits défectueux / total", "unit": "%", "priority": "high"},
            {"name": "OEE (Efficacité globale)", "description": "Disponibilité × performance × qualité", "unit": "%", "priority": "high"},
            {"name": "MTBF", "description": "Temps moyen entre pannes", "unit": "heures", "priority": "medium"},
        ],
        "dashboard_focus": "quality_control",
        "recommended_charts": ["line", "heatmap", "bar"],
        "routing_target": "manufacturing_agent",
        "explanation": "Secteur industrie détecté — focus sur la qualité et la maintenance prédictive.",
    },
    "telecom": {
        "keywords": ["telecom", "network", "subscriber", "5g", "broadband", "réseau", "abonné", "churn", "opérateur"],
        "kpis": [
            {"name": "Taux de churn", "description": "Clients perdus par mois", "unit": "%", "priority": "high"},
            {"name": "ARPU", "description": "Revenu moyen par utilisateur", "unit": "€", "priority": "high"},
            {"name": "Qualité réseau (QoS)", "description": "Score de qualité de service", "unit": "pts", "priority": "medium"},
        ],
        "dashboard_focus": "churn_prevention",
        "recommended_charts": ["line", "bar", "area"],
        "routing_target": "telecom_agent",
        "explanation": "Secteur telecom détecté — focus sur la rétention abonnés et la qualité réseau.",
    },
    "transport": {
        "keywords": [
            "transport", "logistic", "fleet", "delivery", "itinéraire", "livraison", "flotte", "véhicule", "route", "conducteur",
            "aéroport", "aeroport", "passager", "vol", "airline", "terminal", "embarquement",
        ],
        "kpis": [
            {"name": "Taux de livraison à temps", "description": "Livraisons dans les délais", "unit": "%", "priority": "high"},
            {"name": "Coût par km", "description": "Coût moyen par kilomètre parcouru", "unit": "€/km", "priority": "high"},
            {"name": "Taux d'utilisation flotte", "description": "Véhicules actifs / total", "unit": "%", "priority": "medium"},
        ],
        "dashboard_focus": "fleet_optimization",
        "recommended_charts": ["line", "bar", "heatmap"],
        "routing_target": "transport_agent",
        "explanation": "Secteur transport détecté — focus sur l'optimisation de la flotte et des livraisons.",
    },
    "public": {
        "keywords": ["public", "gouvernement", "citoyen", "service public", "administration", "collectivité"],
        "kpis": [
            {"name": "Satisfaction citoyens", "description": "Score de satisfaction des services", "unit": "pts", "priority": "high"},
            {"name": "Délai de traitement", "description": "Temps moyen de traitement des demandes", "unit": "jours", "priority": "high"},
            {"name": "Taux de digitalisation", "description": "Services disponibles en ligne", "unit": "%", "priority": "medium"},
        ],
        "dashboard_focus": "service_quality",
        "recommended_charts": ["bar", "pie", "line"],
        "routing_target": "public_agent",
        "explanation": "Secteur public détecté — focus sur la qualité de service et la satisfaction citoyens.",
    },
}

DEFAULT_SECTOR = "general"

def detect_sector(use_case: str) -> str:
    """Best-effort sector detection — returns sector key string."""
    text = (use_case or "").lower()
    for sector, meta in SECTOR_META.items():
        if any(term in text for term in meta["keywords"]):
            return sector
    return DEFAULT_SECTOR


def detect_sector_full(use_case: str) -> dict:
    """Returns full sector context matching DetectSectorResponse frontend interface."""
    text = (use_case or "").lower()

    detected = DEFAULT_SECTOR
    confidence = 0.55

    for sector, meta in SECTOR_META.items():
        matched = sum(1 for term in meta["keywords"] if term in text)
        if matched > 0:
            score = min(0.95, 0.60 + matched * 0.08)
            if score > confidence:
                confidence = score
                detected = sector

    meta = SECTOR_META[detected]

    return {
        "sector": detected,
        "confidence": round(confidence, 2),
        "use_case": use_case,
        "metadata_used": False,
        "kpis": meta["kpis"],
        "dashboard_focus": meta["dashboard_focus"],
        "recommended_charts": meta["recommended_charts"],
        "routing_target": meta["routing_target"],
        "explanation": meta["explanation"],
    }