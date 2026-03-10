"""
Tests API — Sprint 1
=====================
PFE — DXC Technology | Intelligence Analytics Platform

Couvre tous les endpoints + les 3 routing targets :
  GET  /health
  POST /detect-sector
  POST /chat → NLQ direct
  POST /chat → routing_target = generic_predictive_agent
  POST /chat → routing_target = {sector}_agent (ex: transport_agent)
  POST /chat → routing_target = insight_agent
  POST /chat/reset

Lancer :
    pytest tests/test_api.py -v
    pytest tests/test_api.py -v -k "TestChatRouting"
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from agents.context_sector_agent import KPI, SectorContext
from agents.nlq_agent import NLQResponse

# Import api.main au niveau module — OBLIGATOIRE pour que patch("api.main.xxx") fonctionne.
# patch() résout "api.main" via sys.modules ; si le module n'a pas encore été importé,
# il échoue avec "module 'api' has no attribute 'main'".
import api.main  # noqa: F401  — effet de bord voulu : enregistre api.main dans sys.modules


# ══════════════════════════════════════════════════════════
# DONNÉES DE TEST
# ══════════════════════════════════════════════════════════

TRANSPORT_CTX = SectorContext(
    sector="transport", confidence=0.95,
    use_case="Améliorer l'expérience des passagers",
    metadata_used=False,
    kpis=[
        KPI(name="On-Time Performance",        description="% on time", unit="%",       priority="high"),
        KPI(name="Average Delay",               description="Mean delay",unit="minutes", priority="high"),
        KPI(name="Passenger Satisfaction Score",description="Avg score", unit="score/5", priority="medium"),
    ],
    dashboard_focus="Passenger Experience & Flight Operations",
    recommended_charts=["line chart", "bar chart", "KPI card"],
    routing_target="transport_agent",
    explanation="Transport sector detected.",
)

FINANCE_CTX = SectorContext(
    sector="finance", confidence=0.92, use_case="Analyse financière",
    metadata_used=False,
    kpis=[KPI(name="Revenue Growth", description="YoY", unit="%", priority="high")],
    dashboard_focus="Financial Performance",
    recommended_charts=["bar chart"],
    routing_target="finance_agent",
    explanation="Finance context.",
)


def make_nlq_response(
    intent: str = "aggregation",
    requires_orchestrator: bool = False,
    routing_target: str = None,
    orchestrator_payload: dict = None,
) -> NLQResponse:
    return NLQResponse(
        answer                = f"Réponse pour {intent}.",
        intent                = intent,
        query_type            = intent,
        generated_query       = "SELECT AVG(delay_minutes) FROM flights" if not requires_orchestrator else None,
        kpi_referenced        = "Average Delay" if not requires_orchestrator else None,
        suggested_chart       = "KPI card" if not requires_orchestrator else None,
        requires_orchestrator = requires_orchestrator,
        routing_target        = routing_target,
        orchestrator_payload  = orchestrator_payload,
        needs_more_data       = False,
    )


# ══════════════════════════════════════════════════════════
# FIXTURE CLIENT
# ══════════════════════════════════════════════════════════

@pytest.fixture
def client():
    with (
        patch("api.main.sector_agent") as mock_sector,
        patch("api.main.nlq_agent")    as mock_nlq,
    ):
        mock_sector.MODEL = "meta-llama/llama-3.1-8b-instruct"
        mock_sector.detect.return_value = TRANSPORT_CTX

        mock_nlq.active_sessions = 0
        mock_nlq.chat.return_value    = make_nlq_response()
        mock_nlq.history_length.return_value = 1
        mock_nlq.reset_conversation.return_value = True

        from api.main import app
        with TestClient(app) as c:
            c._mock_sector = mock_sector
            c._mock_nlq    = mock_nlq
            yield c


def _base_chat_body(user_id: str = "u1", question: str = "Retard moyen ?") -> dict:
    return {
        "user_id"       : user_id,
        "question"      : question,
        "sector_context": TRANSPORT_CTX.model_dump(),
    }


# ══════════════════════════════════════════════════════════
# 1. HEALTH
# ══════════════════════════════════════════════════════════

class TestHealth:

    def test_200(self, client):
        assert client.get("/health").status_code == 200

    def test_status_ok(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_model_in_response(self, client):
        assert "llama" in client.get("/health").json()["model"]

    def test_active_sessions_present(self, client):
        assert "active_sessions" in client.get("/health").json()


# ══════════════════════════════════════════════════════════
# 2. DETECT SECTOR
# ══════════════════════════════════════════════════════════

class TestDetectSector:

    def test_200(self, client):
        r = client.post("/detect-sector", json={"user_query": "expérience passagers"})
        assert r.status_code == 200

    def test_sector_transport(self, client):
        r = client.post("/detect-sector", json={"user_query": "expérience passagers"})
        assert r.json()["sector"]         == "transport"
        assert r.json()["routing_target"] == "transport_agent"

    def test_kpis_present(self, client):
        r = client.post("/detect-sector", json={"user_query": "test"})
        assert len(r.json()["kpis"]) >= 1

    def test_confidence_valid_range(self, client):
        r = client.post("/detect-sector", json={"user_query": "test"})
        assert 0.0 <= r.json()["confidence"] <= 1.0

    def test_with_column_metadata(self, client):
        r = client.post("/detect-sector", json={
            "user_query": "expérience client",
            "column_metadata": [
                {"name": "flight_id",     "description": "ID du vol"},
                {"name": "delay_minutes", "sample_values": ["0", "15", "45"]},
            ],
        })
        assert r.status_code == 200

    def test_missing_user_query_422(self, client):
        assert client.post("/detect-sector", json={}).status_code == 422

    def test_recommended_charts_is_list(self, client):
        r = client.post("/detect-sector", json={"user_query": "test"})
        assert isinstance(r.json()["recommended_charts"], list)


# ══════════════════════════════════════════════════════════
# 3. CHAT — NLQ direct
# ══════════════════════════════════════════════════════════

class TestChatDirect:

    def test_200(self, client):
        assert client.post("/chat", json=_base_chat_body()).status_code == 200

    def test_answer_present(self, client):
        r = client.post("/chat", json=_base_chat_body())
        assert r.json()["answer"] != ""

    def test_requires_orchestrator_false(self, client):
        assert client.post("/chat", json=_base_chat_body()).json()["requires_orchestrator"] is False

    def test_routing_target_null(self, client):
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="aggregation", requires_orchestrator=False, routing_target=None
        )
        r = client.post("/chat", json=_base_chat_body())
        assert r.json()["routing_target"] is None

    def test_user_id_in_response(self, client):
        r = client.post("/chat", json=_base_chat_body("user_test"))
        assert r.json()["user_id"] == "user_test"

    def test_history_length_present(self, client):
        r = client.post("/chat", json=_base_chat_body())
        assert r.json()["history_length"] >= 1

    def test_missing_user_id_422(self, client):
        body = {"question": "test", "sector_context": TRANSPORT_CTX.model_dump()}
        assert client.post("/chat", json=body).status_code == 422

    def test_missing_question_422(self, client):
        body = {"user_id": "u1", "sector_context": TRANSPORT_CTX.model_dump()}
        assert client.post("/chat", json=body).status_code == 422

    def test_incomplete_context_422(self, client):
        body = {"user_id": "u1", "question": "test", "sector_context": {"sector": "transport"}}
        assert client.post("/chat", json=body).status_code == 422

    def test_with_data_profile(self, client):
        body = {
            **_base_chat_body(),
            "data_profile": {
                "row_count": 500,
                "columns": ["flight_id", "delay_minutes", "route"],
                "numeric_columns": ["delay_minutes"],
                "categorical_columns": ["route"],
                "datetime_columns": [],
                "missing_summary": {},
                "quality_score": 85.0,
            },
        }
        assert client.post("/chat", json=body).status_code == 200


# ══════════════════════════════════════════════════════════
# 4. CHAT — routing vers les 3 agents
# ══════════════════════════════════════════════════════════

class TestChatRouting:

    # ── Prédiction → Agent Spécifique du secteur (Sector Predictive Model) ──

    def test_prediction_routes_to_sector_agent(self, client):
        """prediction + transport → transport_agent [sector_prediction]."""
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="prediction",
            requires_orchestrator=True,
            routing_target="transport_agent",        # résolu depuis SectorContext
            orchestrator_payload={"task_type": "sector_prediction",
                                  "sub_agent": "sector_prediction",
                                  "target_kpi": "Average Delay",
                                  "prediction_horizon": "next_month"},
        )
        r = client.post("/chat", json=_base_chat_body(question="Prédis le retard"))
        assert r.json()["requires_orchestrator"] is True
        assert r.json()["routing_target"]        == "transport_agent"
        assert r.json()["intent"]                == "prediction"

    def test_prediction_sector_specific_not_generic(self, client):
        """prediction ne doit PAS router vers generic_predictive_agent."""
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="prediction", requires_orchestrator=True,
            routing_target="transport_agent",
        )
        r = client.post("/chat", json=_base_chat_body(question="Prédis le retard"))
        assert r.json()["routing_target"] != "generic_predictive_agent"
        assert r.json()["routing_target"] == "transport_agent"

    # ── Anomalie → Generic Predictive Agent ──────────────────────────────────

    def test_anomaly_routes_to_generic_predictive(self, client):
        """anomaly → toujours generic_predictive_agent (pas un agent sectoriel)."""
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="anomaly",
            requires_orchestrator=True,
            routing_target="generic_predictive_agent",
            orchestrator_payload={"task_type": "anomaly_detection"},
        )
        r = client.post("/chat", json=_base_chat_body(question="Détecte anomalies"))
        assert r.json()["requires_orchestrator"] is True
        assert r.json()["routing_target"]        == "generic_predictive_agent"
        assert r.json()["intent"]                == "anomaly"

    def test_prediction_anomaly_different_routing(self, client):
        """prediction et anomaly routent vers des agents différents."""
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="prediction", requires_orchestrator=True, routing_target="transport_agent"
        )
        r_pred = client.post("/chat", json=_base_chat_body())

        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="anomaly", requires_orchestrator=True, routing_target="generic_predictive_agent"
        )
        r_anom = client.post("/chat", json=_base_chat_body())
        assert r_pred.json()["routing_target"] != r_anom.json()["routing_target"]

    # ── Sector Analysis → Agent Spécifique du secteur ────────────────────────

    def test_sector_analysis_routes_to_sector_agent(self, client):
        """sector_analysis + transport → transport_agent [sector_explanation]."""
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="sector_analysis",
            requires_orchestrator=True,
            routing_target="transport_agent",        # résolu depuis SectorContext
            orchestrator_payload={"task_type": "sector_explanation",
                                  "sub_agent": "sector_explanation"},
        )
        r = client.post("/chat", json=_base_chat_body(question="Analyse complète transport"))
        assert r.json()["requires_orchestrator"] is True
        assert r.json()["routing_target"]        == "transport_agent"
        assert r.json()["intent"]                == "sector_analysis"

    # ── Insight Agent ────────────────────────────────────────────────────────

    def test_dashboard_routes_to_insight_agent(self, client):
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="dashboard", requires_orchestrator=True,
            routing_target="insight_agent",
            orchestrator_payload={"output_type": "dashboard"},
        )
        r = client.post("/chat", json=_base_chat_body(question="Génère le dashboard"))
        assert r.json()["requires_orchestrator"] is True
        assert r.json()["routing_target"]        == "insight_agent"
        assert r.json()["intent"]                == "dashboard"

    def test_kpi_chart_routes_to_insight_agent(self, client):
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="kpi_chart", requires_orchestrator=True, routing_target="insight_agent",
        )
        r = client.post("/chat", json=_base_chat_body(question="Crée graphique retard"))
        assert r.json()["routing_target"] == "insight_agent"
        assert r.json()["intent"]         == "kpi_chart"

    def test_insight_routes_to_insight_agent(self, client):
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent="insight", requires_orchestrator=True, routing_target="insight_agent",
        )
        r = client.post("/chat", json=_base_chat_body(question="Export rapport Power BI"))
        assert r.json()["routing_target"] == "insight_agent"
        assert r.json()["intent"]         == "insight"

    # ── Schema commun pour tous les routings ─────────────────────────────────

    @pytest.mark.parametrize("intent,target", [
        ("prediction",    "transport_agent"),          # résolu depuis SectorContext Transport
        ("anomaly",       "generic_predictive_agent"), # toujours statique
        ("sector_analysis","transport_agent"),          # résolu depuis SectorContext Transport
        ("dashboard",     "insight_agent"),
        ("kpi_chart",     "insight_agent"),
        ("insight",       "insight_agent"),
    ])
    def test_routing_response_schema(self, client, intent, target):
        client._mock_nlq.chat.return_value = make_nlq_response(
            intent=intent, requires_orchestrator=True, routing_target=target
        )
        r    = client.post("/chat", json=_base_chat_body())
        body = r.json()
        assert r.status_code                == 200
        assert body["requires_orchestrator"] is True
        assert body["routing_target"]        == target
        assert body["intent"]                == intent
        assert body["answer"]               != ""


# ══════════════════════════════════════════════════════════
# 5. MULTI-USER SESSIONS
# ══════════════════════════════════════════════════════════

class TestMultiUser:

    def test_two_users_isolated(self, client):
        client._mock_nlq.history_length.side_effect = lambda uid: (
            2 if uid == "u1" else 1
        )
        r1 = client.post("/chat", json=_base_chat_body("u1"))
        r2 = client.post("/chat", json=_base_chat_body("u2"))
        assert r1.json()["history_length"] == 2
        assert r2.json()["history_length"] == 1

    def test_different_users_different_intents(self, client):
        responses = {
            "u1": make_nlq_response("aggregation", False, None),
            "u2": make_nlq_response("prediction",  True, "transport_agent"),
        }
        def side_effect(user_id, **kwargs):
            return responses[user_id]
        client._mock_nlq.chat.side_effect = lambda *a, **k: responses.get(a[0], responses["u1"])
        client._mock_nlq.history_length.side_effect = lambda uid: 1 if uid == "u1" else 0

        r1 = client.post("/chat", json=_base_chat_body("u1"))
        r2 = client.post("/chat", json=_base_chat_body("u2"))

        assert r1.json()["requires_orchestrator"] is False
        assert r2.json()["requires_orchestrator"] is True


# ══════════════════════════════════════════════════════════
# 6. RESET SESSION
# ══════════════════════════════════════════════════════════

class TestReset:

    def test_200(self, client):
        assert client.post("/chat/reset", json={"user_id": "u1"}).status_code == 200

    def test_history_cleared_true(self, client):
        assert client.post("/chat/reset", json={"user_id": "u1"}).json()["history_cleared"] is True

    def test_user_id_in_response(self, client):
        r = client.post("/chat/reset", json={"user_id": "u1"})
        assert r.json()["user_id"] == "u1"

    def test_nonexistent_session_false(self, client):
        client._mock_nlq.reset_conversation.return_value = False
        r = client.post("/chat/reset", json={"user_id": "ghost"})
        assert r.json()["history_cleared"] is False
        assert r.status_code == 200

    def test_missing_user_id_422(self, client):
        assert client.post("/chat/reset", json={}).status_code == 422

    def test_reset_then_fresh_start(self, client):
        client._mock_nlq.reset_conversation.return_value = True
        client._mock_nlq.history_length.return_value     = 0
        client.post("/chat/reset", json={"user_id": "u1"})
        client._mock_nlq.history_length.return_value = 1
        r = client.post("/chat", json=_base_chat_body("u1"))
        assert r.json()["history_length"] == 1


# ══════════════════════════════════════════════════════════
# 7. ERROR HANDLING
# ══════════════════════════════════════════════════════════

class TestErrors:

    def test_detect_sector_empty_body_422(self, client):
        r = client.post("/detect-sector", json={})
        assert r.status_code == 422
        assert "detail" in r.json()

    def test_chat_no_user_id_422(self, client):
        body = {"question": "test", "sector_context": TRANSPORT_CTX.model_dump()}
        assert client.post("/chat", json=body).status_code == 422

    def test_chat_no_question_422(self, client):
        body = {"user_id": "u1", "sector_context": TRANSPORT_CTX.model_dump()}
        assert client.post("/chat", json=body).status_code == 422

    def test_chat_incomplete_context_422(self, client):
        body = {"user_id": "u1", "question": "test",
                "sector_context": {"sector": "transport"}}
        assert client.post("/chat", json=body).status_code == 422

    def test_reset_no_user_id_422(self, client):
        assert client.post("/chat/reset", json={}).status_code == 422

    def test_full_flow(self, client):
        """Flux complet : detect → chat direct → routing → reset."""
        r_detect = client.post("/detect-sector", json={"user_query": "expérience passagers"})
        assert r_detect.status_code == 200

        r_chat = client.post("/chat", json={
            "user_id": "u1", "question": "Retard moyen ?",
            "sector_context": r_detect.json(),
        })
        assert r_chat.status_code == 200

        client._mock_nlq.chat.return_value = make_nlq_response(
            "prediction", True, "transport_agent"
        )
        r_pred = client.post("/chat", json={
            "user_id": "u1", "question": "Prédis le retard",
            "sector_context": r_detect.json(),
        })
        assert r_pred.json()["routing_target"] == "transport_agent"

        r_reset = client.post("/chat/reset", json={"user_id": "u1"})
        assert r_reset.json()["history_cleared"] is True
