"""
Tests Sprint 1 — LangGraph
============================
PFE — DXC Technology | Intelligence Analytics Platform

Teste les deux agents LangGraph :
  - ContextSectorAgent  (Sector Detection Graph)
  - NLQAgent            (NLQ Layer Graph)

Stratégie :
  - Les nœuds LangGraph sont testés unitairement (sans appel LLM)
  - Les graphs complets sont testés avec le LLM mocké
  - La table de routing est testée de façon déterministe

Lancer :
    pytest tests/test_sprint1.py -v
    pytest tests/test_sprint1.py -v -k "TestRoutingTable"
"""

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage

from agents.context_sector_agent import (
    ContextSectorAgent, SectorDetectionAgent,
    SectorContext, KPI, ColumnMetadata,
    node_load_context, node_map_kpis,
    SectorAgentState,
)
from agents.nlq_agent import (
    NLQAgent, NLQResponse, IntentClassification,
    ROUTING_TABLE, ORCHESTRATOR_INTENTS, NLQ_DIRECT_INTENTS,
    SECTOR_DYNAMIC_INTENTS, resolve_routing_target,
    node_prepare_routing, NLQAgentState,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════

TRANSPORT_CTX = SectorContext(
    sector="transport", confidence=0.95,
    use_case="Améliorer l'expérience des passagers de l'aéroport",
    metadata_used=False,
    kpis=[
        KPI(name="On-Time Performance",  description="% vols à l'heure", unit="%",       priority="high"),
        KPI(name="Average Delay",         description="Retard moyen",     unit="minutes", priority="high"),
        KPI(name="Passenger Satisfaction",description="Score satisfaction",unit="score/5",priority="medium"),
    ],
    dashboard_focus="Passenger Experience & Flight Operations",
    recommended_charts=["line chart", "bar chart", "KPI card"],
    routing_target="transport_agent",
    explanation="Transport sector detected from airport context.",
)

FINANCE_CTX = SectorContext(
    sector="finance", confidence=0.92, use_case="Analyse financière",
    metadata_used=False,
    kpis=[KPI(name="Revenue Growth", description="Croissance", unit="%", priority="high")],
    dashboard_focus="Financial Performance",
    recommended_charts=["bar chart"],
    routing_target="finance_agent",
    explanation="Finance context.",
)

RETAIL_CTX = SectorContext(
    sector="retail", confidence=0.88, use_case="Performance ventes",
    metadata_used=False,
    kpis=[KPI(name="Conversion Rate", description="Taux conversion", unit="%", priority="high")],
    dashboard_focus="Sales Performance",
    recommended_charts=["bar chart"],
    routing_target="retail_agent",
    explanation="Retail context.",
)

KPI_CONFIG = {
    "sectors": {
        "transport": {
            "dashboard_focus": "Passenger Experience",
            "kpis": [
                {"name": "On-Time Performance",  "description": "% vols à l'heure", "unit": "%"},
                {"name": "Average Delay",         "description": "Retard moyen",     "unit": "minutes"},
                {"name": "Passenger Satisfaction","description": "Score satisfaction","unit": "score/5"},
            ]
        }
    }
}


def _make_sector_llm_mock(sector_data: dict) -> MagicMock:
    """Crée un mock LLM qui retourne sector_data en JSON."""
    import json
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(content=json.dumps(sector_data))
    return mock


def _make_intent_llm_mock(intent: str, confidence: float = 0.9) -> MagicMock:
    """Crée un mock LLM qui retourne une classification d'intent."""
    import json
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(content=json.dumps({
        "intent": intent,
        "confidence": confidence,
        "is_follow_up": False,
        "extracted_entities": {},
    }))
    return mock


def _make_nlq_llm_mock(answer: str = "Réponse test.") -> MagicMock:
    """Crée un mock LLM pour la génération de réponse NLQ directe."""
    import json
    mock = MagicMock()
    mock.invoke.return_value = AIMessage(content=json.dumps({
        "answer"         : answer,
        "intent"         : "aggregation",
        "query_type"     : "aggregation",
        "generated_query": "SELECT AVG(delay_minutes) FROM flights",
        "kpi_referenced" : "Average Delay",
        "suggested_chart": "KPI card",
        "needs_more_data": False,
    }))
    return mock


# ══════════════════════════════════════════════════════════════════
# 1. ROUTING TABLE
# ══════════════════════════════════════════════════════════════════

class TestRoutingTable:
    """La table de routing est la source de vérité du système."""

    def test_all_intents_present(self):
        expected = {"sql", "aggregation", "comparison", "explanation",
                    "prediction", "anomaly", "sector_analysis",
                    "dashboard", "kpi_chart", "insight"}
        assert expected == set(ROUTING_TABLE.keys())

    def test_nlq_direct_intents(self):
        assert NLQ_DIRECT_INTENTS == {"sql", "aggregation", "comparison", "explanation"}

    def test_orchestrator_intents(self):
        assert ORCHESTRATOR_INTENTS == {
            "prediction", "anomaly", "sector_analysis",
            "dashboard", "kpi_chart", "insight"
        }

    def test_sector_dynamic_intents(self):
        assert SECTOR_DYNAMIC_INTENTS == {"prediction", "sector_analysis"}

    def test_prediction_uses_sector_context_marker(self):
        assert ROUTING_TABLE["prediction"]["routing_target"] == "USE_SECTOR_CONTEXT"

    def test_sector_analysis_uses_sector_context_marker(self):
        assert ROUTING_TABLE["sector_analysis"]["routing_target"] == "USE_SECTOR_CONTEXT"

    def test_anomaly_static_routing(self):
        assert ROUTING_TABLE["anomaly"]["routing_target"] == "generic_predictive_agent"

    def test_insight_intents_route_to_insight_agent(self):
        for intent in ["dashboard", "kpi_chart", "insight"]:
            assert ROUTING_TABLE[intent]["routing_target"] == "insight_agent"

    def test_prediction_sub_agent(self):
        assert ROUTING_TABLE["prediction"]["sub_agent"] == "sector_prediction"

    def test_sector_analysis_sub_agent(self):
        assert ROUTING_TABLE["sector_analysis"]["sub_agent"] == "sector_explanation"

    def test_nlq_intents_no_sub_agent(self):
        for intent in NLQ_DIRECT_INTENTS:
            assert ROUTING_TABLE[intent]["sub_agent"] is None

    def test_every_entry_has_required_keys(self):
        required = {"requires_orchestrator", "routing_target", "sub_agent", "description"}
        for intent, config in ROUTING_TABLE.items():
            assert required.issubset(config.keys()), f"Missing keys in '{intent}'"


# ══════════════════════════════════════════════════════════════════
# 2. RESOLVE ROUTING TARGET
# ══════════════════════════════════════════════════════════════════

class TestResolveRoutingTarget:

    def test_prediction_transport(self):
        assert resolve_routing_target("prediction", TRANSPORT_CTX) == "transport_agent"

    def test_prediction_finance(self):
        assert resolve_routing_target("prediction", FINANCE_CTX) == "finance_agent"

    def test_prediction_retail(self):
        assert resolve_routing_target("prediction", RETAIL_CTX) == "retail_agent"

    def test_sector_analysis_transport(self):
        assert resolve_routing_target("sector_analysis", TRANSPORT_CTX) == "transport_agent"

    def test_anomaly_always_generic(self):
        for ctx in [TRANSPORT_CTX, FINANCE_CTX, RETAIL_CTX]:
            assert resolve_routing_target("anomaly", ctx) == "generic_predictive_agent"

    def test_insight_intents_always_insight_agent(self):
        for intent in ["dashboard", "kpi_chart", "insight"]:
            assert resolve_routing_target(intent, TRANSPORT_CTX) == "insight_agent"

    def test_same_intent_different_sectors(self):
        t = resolve_routing_target("prediction", TRANSPORT_CTX)
        f = resolve_routing_target("prediction", FINANCE_CTX)
        assert t != f
        assert t == "transport_agent"
        assert f == "finance_agent"

    def test_nlq_direct_intents_return_none(self):
        for intent in NLQ_DIRECT_INTENTS:
            assert resolve_routing_target(intent, TRANSPORT_CTX) is None


# ══════════════════════════════════════════════════════════════════
# 3. NŒUDS SECTOR DETECTION GRAPH
# ══════════════════════════════════════════════════════════════════

class TestSectorGraphNodes:
    """Tests unitaires des nœuds LangGraph du Sector Detection Graph."""

    def _base_state(self, user_query="test", columns=None) -> SectorAgentState:
        return {
            "user_query"     : user_query,
            "columns"        : columns,
            "prompt"         : "",
            "llm_raw"        : "",
            "llm_data"       : {},
            "kpi_config_text": "SECTOR: TRANSPORT\n  - On-Time Performance (%): Flights on time",
            "kpi_config_dict": KPI_CONFIG,
            "sector_context" : None,
            "error"          : None,
            "verbose"        : False,
        }

    def test_node_load_context_builds_prompt(self):
        state = self._base_state("améliorer l'expérience passagers")
        result = node_load_context(state)
        assert len(result["prompt"]) > 100
        assert "améliorer l'expérience passagers" in result["prompt"]

    def test_node_load_context_includes_columns(self):
        cols  = [ColumnMetadata(name="flight_id"), ColumnMetadata(name="delay_minutes")]
        state = self._base_state("expérience client", columns=cols)
        result = node_load_context(state)
        assert "flight_id" in result["prompt"]
        assert "delay_minutes" in result["prompt"]

    def test_node_load_context_no_columns_section(self):
        state  = self._base_state("transport query")
        result = node_load_context(state)
        assert "USER DATASET COLUMNS" not in result["prompt"]

    def test_node_map_kpis_validates_against_yaml(self):
        state = {
            **self._base_state(),
            "llm_data": {
                "sector"            : "transport",
                "confidence"        : 0.95,
                "use_case"          : "Test",
                "metadata_used"     : False,
                "kpis"              : [{"name": "On-Time Performance", "description": "test",
                                        "unit": "%", "priority": "high"}],
                "dashboard_focus"   : "Test Dashboard",
                "recommended_charts": ["bar chart"],
                "routing_target"    : "transport_agent",
                "explanation"       : "Test.",
            },
        }
        result = node_map_kpis(state)
        assert result["error"] is None
        ctx = result["sector_context"]
        assert ctx is not None
        assert ctx.sector == "transport"
        assert len(ctx.kpis) == 1
        assert ctx.kpis[0].name == "On-Time Performance"

    def test_node_map_kpis_skips_on_error(self):
        state = {**self._base_state(), "error": "previous error", "llm_data": {}}
        result = node_map_kpis(state)
        assert result["error"] == "previous error"
        assert result["sector_context"] is None


# ══════════════════════════════════════════════════════════════════
# 4. CONTEXT SECTOR AGENT (GRAPH COMPLET)
# ══════════════════════════════════════════════════════════════════

class TestContextSectorAgent:

    def _mock_agent(self, sector_data: dict) -> ContextSectorAgent:
        """Crée un ContextSectorAgent avec LLM mocké."""
        with patch("agents.context_sector_agent.load_kpi_config", return_value=KPI_CONFIG):
            agent = ContextSectorAgent.__new__(ContextSectorAgent)
            agent.verbose     = False
            agent.config      = KPI_CONFIG
            agent.config_text = "mock config text"
            agent.llm         = _make_sector_llm_mock(sector_data)
            agent.graph       = agent._build_graph()
        return agent

    def test_detect_returns_sector_context(self):
        agent = self._mock_agent({
            "sector": "transport", "confidence": 0.95,
            "use_case": "Test", "metadata_used": False,
            "kpis": [{"name": "Average Delay", "description": "Retard moyen",
                      "unit": "minutes", "priority": "high"}],
            "dashboard_focus": "Transport Dashboard",
            "recommended_charts": ["line chart"],
            "routing_target": "transport_agent",
            "explanation": "Transport.",
        })
        ctx = agent.detect("améliorer l'expérience passagers")
        assert isinstance(ctx, SectorContext)
        assert ctx.sector == "transport"
        assert ctx.routing_target == "transport_agent"

    def test_detect_routing_target_format(self):
        for sector in ["transport", "finance", "retail", "manufacturing", "public"]:
            agent = self._mock_agent({
                "sector": sector, "confidence": 0.9,
                "use_case": "Test", "metadata_used": False,
                "kpis": [], "dashboard_focus": "D",
                "recommended_charts": [],
                "routing_target": f"{sector}_agent",
                "explanation": "ok",
            })
            ctx = agent.detect("test")
            assert ctx.routing_target == f"{sector}_agent"

    def test_alias_sector_detection_agent(self):
        assert SectorDetectionAgent is ContextSectorAgent


# ══════════════════════════════════════════════════════════════════
# 5. NŒUDS NLQ LAYER GRAPH
# ══════════════════════════════════════════════════════════════════

class TestNLQGraphNodes:
    """Tests unitaires du nœud prepare_routing."""

    def _base_nlq_state(self, intent_str: str, routing_target: str,
                        sub_agent=None) -> NLQAgentState:
        intent = IntentClassification(
            intent=intent_str, confidence=0.9,
            requires_orchestrator=True,
            routing_target=routing_target,
            sub_agent=sub_agent,
            is_follow_up=False,
        )
        return {
            "user_id"       : "u1",
            "question"      : "Prédis le retard moyen",
            "sector_context": TRANSPORT_CTX,
            "data_profile"  : None,
            "history"       : [],
            "intent_result" : intent,
            "nlq_response"  : None,
            "verbose"       : False,
        }

    def test_prepare_routing_prediction(self):
        state  = self._base_nlq_state("prediction", "transport_agent", "sector_prediction")
        result = node_prepare_routing(state)
        r = result["nlq_response"]
        assert r.requires_orchestrator is True
        assert r.routing_target == "transport_agent"
        assert r.sub_agent == "sector_prediction"
        assert r.orchestrator_payload["task_type"] == "sector_prediction"

    def test_prepare_routing_anomaly(self):
        state  = self._base_nlq_state("anomaly", "generic_predictive_agent")
        result = node_prepare_routing(state)
        r = result["nlq_response"]
        assert r.routing_target == "generic_predictive_agent"
        assert r.orchestrator_payload["task_type"] == "anomaly_detection"

    def test_prepare_routing_sector_analysis(self):
        state  = self._base_nlq_state("sector_analysis", "transport_agent", "sector_explanation")
        result = node_prepare_routing(state)
        r = result["nlq_response"]
        assert r.sub_agent == "sector_explanation"
        assert r.orchestrator_payload["task_type"] == "sector_explanation"

    def test_prepare_routing_insight_agent(self):
        for intent in ["dashboard", "kpi_chart", "insight"]:
            state  = self._base_nlq_state(intent, "insight_agent")
            result = node_prepare_routing(state)
            r = result["nlq_response"]
            assert r.routing_target == "insight_agent"
            assert r.orchestrator_payload["output_type"] == intent


# ══════════════════════════════════════════════════════════════════
# 6. NLQ AGENT (GRAPH COMPLET)
# ══════════════════════════════════════════════════════════════════

class TestNLQAgentRouting:
    """Tests du graph NLQ complet avec LLM mocké."""

    def _mock_nlq_agent(self, intent: str) -> NLQAgent:
        """Crée un NLQAgent dont le LLM retourne toujours l'intent donné."""
        import json

        # Le LLM est appelé 2 fois : 1 pour classify_intent, 1 pour generate_answer
        # Pour les intents orchestrateur, seulement classify_intent est appelé
        mock_llm = MagicMock()

        classify_response = AIMessage(content=json.dumps({
            "intent": intent, "confidence": 0.9,
            "is_follow_up": False, "extracted_entities": {},
        }))
        answer_response = AIMessage(content=json.dumps({
            "answer": "Réponse test.", "intent": intent, "query_type": intent,
            "generated_query": None, "kpi_referenced": None,
            "suggested_chart": None, "needs_more_data": False,
        }))
        mock_llm.invoke.side_effect = [classify_response, answer_response]

        agent = NLQAgent.__new__(NLQAgent)
        agent.verbose    = False
        agent._histories = {}
        agent.llm        = mock_llm
        agent.graph      = agent._build_graph()
        return agent

    def test_prediction_routes_to_transport_agent(self):
        agent  = self._mock_nlq_agent("prediction")
        result = agent.chat("u1", "Prédis le retard", TRANSPORT_CTX)
        assert result.requires_orchestrator is True
        assert result.routing_target == "transport_agent"
        assert result.sub_agent == "sector_prediction"

    def test_prediction_not_generic_predictive(self):
        agent  = self._mock_nlq_agent("prediction")
        result = agent.chat("u1", "Prédis le retard", TRANSPORT_CTX)
        assert result.routing_target != "generic_predictive_agent"

    def test_prediction_finance_context(self):
        agent  = self._mock_nlq_agent("prediction")
        result = agent.chat("u1", "Forecast revenue", FINANCE_CTX)
        assert result.routing_target == "finance_agent"

    def test_anomaly_routes_to_generic_predictive(self):
        agent  = self._mock_nlq_agent("anomaly")
        result = agent.chat("u1", "Détecte les anomalies", TRANSPORT_CTX)
        assert result.routing_target == "generic_predictive_agent"
        assert result.sub_agent is None

    def test_sector_analysis_routes_correctly(self):
        agent  = self._mock_nlq_agent("sector_analysis")
        result = agent.chat("u1", "Analyse complète transport", TRANSPORT_CTX)
        assert result.routing_target == "transport_agent"
        assert result.sub_agent == "sector_explanation"

    def test_aggregation_nlq_direct(self):
        agent  = self._mock_nlq_agent("aggregation")
        result = agent.chat("u1", "Retard moyen ?", TRANSPORT_CTX)
        assert result.requires_orchestrator is False
        assert result.routing_target is None

    def test_direct_answer_saves_history(self):
        agent  = self._mock_nlq_agent("aggregation")
        agent.chat("u1", "Retard moyen ?", TRANSPORT_CTX)
        assert agent.history_length("u1") == 1

    def test_orchestrator_routing_doesnt_save_history(self):
        agent  = self._mock_nlq_agent("prediction")
        agent.chat("u1", "Prédis le retard", TRANSPORT_CTX)
        assert agent.history_length("u1") == 0

    def test_reset_conversation(self):
        agent  = self._mock_nlq_agent("aggregation")
        agent.chat("u1", "question", TRANSPORT_CTX)
        assert agent.reset_conversation("u1") is True
        assert agent.history_length("u1") == 0

    def test_reset_nonexistent_session(self):
        agent = self._mock_nlq_agent("aggregation")
        assert agent.reset_conversation("unknown") is False

    def test_active_sessions(self):
        agent = self._mock_nlq_agent("aggregation")
        assert agent.active_sessions == 0


# ══════════════════════════════════════════════════════════════════
# 7. PIPELINE COMPLET (INTÉGRATION)
# ══════════════════════════════════════════════════════════════════

class TestPipeline:
    """Tests d'intégration : Sector Detection → NLQ Layer."""

    def test_sector_then_prediction_routing(self):
        """Transport context → prediction → transport_agent."""
        assert resolve_routing_target("prediction", TRANSPORT_CTX) == "transport_agent"

    def test_sector_then_anomaly_routing(self):
        """Finance context + anomaly → toujours generic_predictive_agent."""
        assert resolve_routing_target("anomaly", FINANCE_CTX) == "generic_predictive_agent"

    def test_sector_then_sector_analysis(self):
        """Retail context → sector_analysis → retail_agent."""
        assert resolve_routing_target("sector_analysis", RETAIL_CTX) == "retail_agent"

    def test_nlq_direct_intents_dont_need_orchestrator(self):
        for intent in NLQ_DIRECT_INTENTS:
            assert ROUTING_TABLE[intent]["requires_orchestrator"] is False

    def test_routing_targets_valid_format(self):
        """Tous les routing_targets (sauf None/USE_SECTOR_CONTEXT) finissent par _agent."""
        for intent, config in ROUTING_TABLE.items():
            rt = config["routing_target"]
            if rt and rt != "USE_SECTOR_CONTEXT":
                assert rt.endswith("_agent"), f"'{intent}' routing_target='{rt}' should end with _agent"
