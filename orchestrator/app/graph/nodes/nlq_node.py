from app.graph.state import OrchestratorState, IntentEnum


# Keywords per intent (includes French and English variants)
INTENT_KEYWORDS = {
    IntentEnum.KPI_REQUEST:  ["kpi","indicateur","indicator","metric","metrics","métrique","performance","rate","taux","chiffre",],
    IntentEnum.PREDICTION:   ["prediction","prédiction","prévoir","forecast","forecasting","next","prochaine","anticipate","anticiper","future","futur",],
    IntentEnum.EXPLANATION:  ["why","pourquoi","explain","expliquer","cause","raison","reason","analysis","analyse","understand","comprendre",],
    IntentEnum.COMPARISON:   ["compare","comparer","versus","vs","difference","différence","between","entre","comparison","comparaison",],
    IntentEnum.DASHBOARD:    ["dashboard","tableau de bord","view","vue","report","rapport","summary","synthèse",],
}


def nlq_node(state: OrchestratorState) -> OrchestratorState:
    """
    Mock Sprint 1: intent detection using keyword matching.
    Sprint 2: to be replaced by the real NLQ Agent + LLM.
    """
    query_lower = state.query_raw.lower()
    best_intent = IntentEnum.UNKNOWN
    best_score = 0.0

    for intent, keywords in INTENT_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in query_lower)
        score = min(matches / 2, 1.0)
        if score > best_score:
            best_score = score
            best_intent = intent

    if best_score == 0:
        best_intent = IntentEnum.UNKNOWN
        best_score = 0.1

    state.intent = best_intent
    state.intent_confidence = round(best_score, 2)
    state.query_structured = {
        "original": state.query_raw,
        "intent": best_intent.value,
        "sector": state.sector.value,
    }
    state.processing_steps.append(
        f"nlq_node → {best_intent.value} ({best_score:.0%})"
    )

    return state