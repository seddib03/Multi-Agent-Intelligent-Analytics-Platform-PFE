from app.graph.state import OrchestratorState


def mock_transport_agent(state: OrchestratorState) -> dict:
    """
    Simule la réponse de l'Agent Transport.
    Sprint 1 : données fictives mais réalistes.
    """
    intent = state.intent.value

    if intent == "kpi_request":
        return {
            "response": "Voici les KPIs Transport pour le mois de Mars 2026.",
            "response_format": "kpi",
            "data_payload": {
                "kpis": [
                    {"name": "Taux de livraison à temps", "value": 94.2, "unit": "%", "trend": "+2.1%"},
                    {"name": "Coût moyen par km",         "value": 1.83, "unit": "€", "trend": "-0.3%"},
                    {"name": "Nombre de trajets",         "value": 12450, "unit": "",  "trend": "+5%"},
                    {"name": "Taux d'occupation fleet",  "value": 87.5, "unit": "%", "trend": "+1.2%"},
                ]
            }
        }

    elif intent == "prediction":
        return {
            "response": "Prédiction Transport : hausse de 8% du trafic attendue semaine prochaine.",
            "response_format": "text",
            "data_payload": {
                "prediction": {"metric": "traffic_volume", "value": "+8%", "horizon": "7 jours", "confidence": 0.84}
            }
        }

    elif intent == "explanation":
        return {
            "response": "Le pic de livraisons observé est dû aux promotions e-commerce du weekend.",
            "response_format": "text",
            "data_payload": {}
        }

    else:
        return {
            "response": "Agent Transport : requête reçue et traitée.",
            "response_format": "text",
            "data_payload": {}
        }