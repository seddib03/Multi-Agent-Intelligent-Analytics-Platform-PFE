import pytest
from app.graph.state import (
    OrchestratorState, SectorEnum, IntentEnum, RouteEnum, ExecutionTypeEnum
)
from app.graph.nodes.routing_node import routing_node


# ── Helpers ───────────────────────────────────────────────────────
def make_state(
    sector=SectorEnum.UNKNOWN,
    intent=IntentEnum.UNKNOWN,
    sector_conf=0.9,
    intent_conf=0.9,
    query="test",
    routing_target="",
    requires_orchestrator=False,
    sub_agent="",
    execution_type=ExecutionTypeEnum.UNKNOWN,
):
    return OrchestratorState(
        user_id="u_test",
        query_raw=query,
        sector=sector,
        sector_confidence=sector_conf,
        intent=intent,
        intent_confidence=intent_conf,
        routing_target=routing_target,
        requires_orchestrator=requires_orchestrator,
        sub_agent=sub_agent,
        execution_type=execution_type,
    )


# ── Tests Niveau 0 — routing_target direct /detect-sector ─────────
class TestNiveau0:

    def test_transport_direct_routing_target(self):
        """routing_target=transport_agent + confiance >= 80% → route directe."""
        state = make_state(
            sector=SectorEnum.TRANSPORT,
            sector_conf=0.95,
            routing_target="transport_agent",
        )
        result = routing_node(state)
        assert result.route == RouteEnum.TRANSPORT_AGENT
        assert "Niveau 0" in result.route_reason

    def test_insight_direct_routing_target(self):
        state = make_state(
            sector_conf=0.90,
            routing_target="insight_agent",
        )
        result = routing_node(state)
        assert result.route == RouteEnum.INSIGHT_AGENT
        assert "Niveau 0" in result.route_reason

    def test_low_confidence_skips_niveau0(self):
        """Confiance < 80% → Niveau 0 ignoré, continue vers les autres niveaux."""
        state = make_state(
            sector=SectorEnum.TRANSPORT,
            intent=IntentEnum.KPI_REQUEST,
            sector_conf=0.75,
            intent_conf=0.90,
            routing_target="transport_agent",
        )
        result = routing_node(state)
        # Niveau 0 skippé → Niveau 5 → TRANSPORT_AGENT quand même
        assert result.route == RouteEnum.TRANSPORT_AGENT
        assert "Niveau 0" not in result.route_reason


# ── Tests Niveau 0 bis — requires_orchestrator depuis /chat ───────
class TestNiveau0Bis:

    def test_requires_orchestrator_dashboard_to_insight(self):
        """
        NLQ classe intent=dashboard → requires_orchestrator=True
        → routing_target=insight_agent → INSIGHT_AGENT
        """
        state = make_state(
            sector=SectorEnum.FINANCE,
            sector_conf=0.60,   # < 80% → Niveau 0 skippé
            intent=IntentEnum.DASHBOARD,
            intent_conf=0.90,
            routing_target="insight_agent",
            requires_orchestrator=True,
        )
        result = routing_node(state)
        assert result.route == RouteEnum.INSIGHT_AGENT
        assert "Niveau 0bis" in result.route_reason

    def test_requires_orchestrator_prediction_with_sub_agent(self):
        """
        NLQ classe intent=prediction → routing_target=transport_agent
        sub_agent=sector_prediction → TRANSPORT_AGENT
        """
        state = make_state(
            sector=SectorEnum.TRANSPORT,
            sector_conf=0.60,
            intent=IntentEnum.PREDICTION,
            routing_target="transport_agent",
            requires_orchestrator=True,
            sub_agent="sector_prediction",
        )
        result = routing_node(state)
        assert result.route == RouteEnum.TRANSPORT_AGENT
        assert "Niveau 0bis" in result.route_reason
        assert "sector_prediction" in result.route_reason

    def test_requires_orchestrator_anomaly_to_generic(self):
        """intent=anomaly → generic_predictive_agent → GENERIC_ML_AGENT"""
        state = make_state(
            sector=SectorEnum.UNKNOWN,
            sector_conf=0.30,
            intent=IntentEnum.ANOMALY,
            routing_target="generic_predictive_agent",
            requires_orchestrator=True,
        )
        result = routing_node(state)
        assert result.route == RouteEnum.GENERIC_ML_AGENT
        assert "Niveau 0bis" in result.route_reason

    def test_requires_orchestrator_false_ignored(self):
        """requires_orchestrator=False → Niveau 0bis ignoré."""
        state = make_state(
            sector=SectorEnum.TRANSPORT,
            sector_conf=0.60,
            intent=IntentEnum.KPI_REQUEST,
            intent_conf=0.90,
            routing_target="insight_agent",
            requires_orchestrator=False,  # ← False → ignoré
        )
        result = routing_node(state)
        assert "Niveau 0bis" not in result.route_reason

    def test_requires_orchestrator_no_routing_target_ignored(self):
        """requires_orchestrator=True mais routing_target vide → Niveau 0bis ignoré."""
        state = make_state(
            sector=SectorEnum.UNKNOWN,
            sector_conf=0.30,
            intent=IntentEnum.UNKNOWN,
            intent_conf=0.20,
            routing_target="",             # ← vide → ignoré
            requires_orchestrator=True,
        )
        result = routing_node(state)
        assert result.route == RouteEnum.CLARIFICATION
        assert "Niveau 0bis" not in result.route_reason


# ── Tests Routing Sectoriel (ton fichier original — inchangé) ──────
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
        """
        EXPLANATION → pas dans les intents spéciaux
        → Niveau 6 → secteur connu → RETAIL_AGENT
        """
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


# ── Tests Routing Intent Spécial (ton fichier original — inchangé) ─
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

    def test_kpi_chart_to_insight(self):
        """kpi_chart → Insight Agent (nouveau intent du Collègue 1)"""
        state = make_state(
            sector=SectorEnum.TRANSPORT,
            intent=IntentEnum.KPI_CHART,
            intent_conf=0.85,
            sector_conf=0.60,
        )
        result = routing_node(state)
        assert result.route == RouteEnum.INSIGHT_AGENT

    def test_sector_analysis_to_sector_agent(self):
        """sector_analysis → agent sectoriel (nouveau intent du Collègue 1)"""
        state = make_state(
            sector=SectorEnum.FINANCE,
            intent=IntentEnum.SECTOR_ANALYSIS,
            intent_conf=0.85,
            sector_conf=0.60,
        )
        result = routing_node(state)
        assert result.route == RouteEnum.FINANCE_AGENT


# ── Tests Niveau 6 — secteur connu + intent inconnu ───────────────
class TestNiveau6:

    def test_sector_known_intent_unknown_routes_to_sector(self):
        """
        Secteur connu >= seuil + intent inconnu
        → agent sectoriel (pas Clarification)
        """
        state = make_state(
            sector=SectorEnum.PUBLIC,
            sector_conf=0.80,
            intent=IntentEnum.UNKNOWN,
            intent_conf=0.20,
        )
        result = routing_node(state)
        assert result.route == RouteEnum.PUBLIC_AGENT
        assert "Niveau 6" in result.route_reason

    def test_sector_known_low_confidence_falls_to_clarification(self):
        """Secteur connu mais confiance < seuil → Clarification."""
        state = make_state(
            sector=SectorEnum.TRANSPORT,
            sector_conf=0.50,   # < CONFIDENCE_MIN_SECTOR (0.60)
            intent=IntentEnum.UNKNOWN,
            intent_conf=0.20,
        )
        result = routing_node(state)
        assert result.route == RouteEnum.CLARIFICATION


# ── Tests Clarification (ton fichier original — inchangé) ─────────
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

    def test_needs_clarification_flag_set(self):
        """needs_clarification doit être True quand route=CLARIFICATION."""
        state = make_state(
            SectorEnum.UNKNOWN, IntentEnum.UNKNOWN,
            sector_conf=0.1, intent_conf=0.1
        )
        result = routing_node(state)
        assert result.needs_clarification is True


# ── Tests Fallback (ton fichier original — inchangé) ──────────────
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


# ── Tests Processing Steps (ton fichier original — inchangé) ──────
class TestProcessingSteps:

    def test_routing_step_logged(self):
        """Vérifie que chaque décision est tracée."""
        state = make_state(SectorEnum.TRANSPORT, IntentEnum.KPI_REQUEST)
        result = routing_node(state)
        assert any("routing_node" in step for step in result.processing_steps)