import pytest
from app.graph.state import (
    OrchestratorState, SectorEnum, IntentEnum, RouteEnum
)
from app.graph.nodes.routing_node import routing_node


# ── Helpers ───────────────────────────────────────────────────────
def make_state(sector, intent, sector_conf=0.9, intent_conf=0.9, query="test"):
    return OrchestratorState(
        user_id="u_test",
        query_raw=query,
        sector=sector,
        sector_confidence=sector_conf,
        intent=intent,
        intent_confidence=intent_conf,
    )


# ── Tests Routing Sectoriel ────────────────────────────────────────
class TestSectorRouting:

    def test_transport_kpi(self):
        state = make_state(SectorEnum.TRANSPORT, IntentEnum.KPI_REQUEST)
        result = routing_node(state)
        assert result.route == RouteEnum.TRANSPORT_AGENT
        assert "Transport" in result.route_reason

    def test_finance_prediction(self):
        state = make_state(SectorEnum.FINANCE, IntentEnum.PREDICTION)
        result = routing_node(state)
        assert result.route == RouteEnum.FINANCE_AGENT

    def test_retail_explanation(self):
        state = make_state(SectorEnum.RETAIL, IntentEnum.EXPLANATION)
        result = routing_node(state)
        assert result.route == RouteEnum.RETAIL_AGENT

    def test_manufacturing(self):
        state = make_state(SectorEnum.MANUFACTURING, IntentEnum.KPI_REQUEST)
        result = routing_node(state)
        assert result.route == RouteEnum.MANUFACTURING_AGENT

    def test_public(self):
        state = make_state(SectorEnum.PUBLIC, IntentEnum.KPI_REQUEST)
        result = routing_node(state)
        assert result.route == RouteEnum.PUBLIC_AGENT


# ── Tests Routing Intent Spécial ──────────────────────────────────
class TestIntentRouting:

    def test_dashboard_always_insight(self):
        """Peu importe le secteur, dashboard → Insight Agent"""
        state = make_state(SectorEnum.TRANSPORT, IntentEnum.DASHBOARD)
        result = routing_node(state)
        assert result.route == RouteEnum.INSIGHT_AGENT

    def test_comparison_always_insight(self):
        state = make_state(SectorEnum.FINANCE, IntentEnum.COMPARISON)
        result = routing_node(state)
        assert result.route == RouteEnum.INSIGHT_AGENT

    def test_unknown_sector_prediction_goes_generic(self):
        """Secteur inconnu mais intent clair → Generic ML"""
        state = make_state(
            SectorEnum.UNKNOWN, IntentEnum.PREDICTION,
            sector_conf=0.3
        )
        result = routing_node(state)
        assert result.route == RouteEnum.GENERIC_ML_AGENT


# ── Tests Clarification ───────────────────────────────────────────
class TestClarification:

    def test_low_confidence_sector_triggers_clarification(self):
        state = make_state(
            SectorEnum.UNKNOWN, IntentEnum.UNKNOWN,
            sector_conf=0.1, intent_conf=0.1
        )
        result = routing_node(state)
        assert result.route == RouteEnum.CLARIFICATION

    def test_unknown_intent_low_confidence(self):
        state = make_state(
            SectorEnum.TRANSPORT, IntentEnum.UNKNOWN,
            sector_conf=0.9, intent_conf=0.2
        )
        result = routing_node(state)
        assert result.route == RouteEnum.CLARIFICATION


# ── Tests Fallback ────────────────────────────────────────────────
class TestFallback:

    def test_sector_agent_fallback_is_generic(self):
        """Si agent sectoriel échoue → fallback Generic ML"""
        state = make_state(SectorEnum.TRANSPORT, IntentEnum.KPI_REQUEST)
        result = routing_node(state)
        assert result.fallback_route == RouteEnum.GENERIC_ML_AGENT

    def test_generic_agent_fallback_is_clarification(self):
        state = make_state(
            SectorEnum.UNKNOWN, IntentEnum.PREDICTION,
            sector_conf=0.3
        )
        result = routing_node(state)
        assert result.fallback_route == RouteEnum.CLARIFICATION


# ── Tests Processing Steps ────────────────────────────────────────
class TestProcessingSteps:

    def test_routing_step_logged(self):
        """Vérifie que chaque décision est tracée"""
        state = make_state(SectorEnum.TRANSPORT, IntentEnum.KPI_REQUEST)
        result = routing_node(state)
        assert any("routing_node" in step for step in result.processing_steps)