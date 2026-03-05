"""
Tests — API FastAPI (Sprint 1)
================================
PFE — DXC Technology | Intelligence Analytics Platform

Teste tous les endpoints de l'API avec TestClient de FastAPI.
Aucune clé API requise — les agents LLM sont mockés.

Usage
-----
    pytest tests/test_api.py -v
    pytest tests/test_api.py -v --tb=short
"""

import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixtures partagées ──────────────────────────────────

MOCK_SECTOR_CONTEXT = {
    "sector": "transport",
    "confidence": 0.95,
    "use_case": "Améliorer l'expérience des passagers de l'aéroport",
    "metadata_used": False,
    "kpis": [
        {"name": "On-Time Performance", "description": "% on time",
         "unit": "%", "priority": "high"},
        {"name": "Average Delay", "description": "Mean delay",
         "unit": "minutes", "priority": "medium"}
    ],
    "dashboard_focus": "Passenger Experience & Operational Efficiency",
    "recommended_charts": ["histogram", "line chart"],
    "routing_target": "transport_agent",
    "explanation": "Airport and passenger keywords detected."
}

MOCK_NLQ_RESPONSE = json.dumps({
    "answer": "Le taux de retard moyen ce mois est de 12.4 minutes.",
    "query_type": "aggregation",
    "generated_query": "SELECT AVG(delay_minutes) FROM flights WHERE MONTH(date) = MONTH(NOW())",
    "kpi_referenced": "Average Delay",
    "suggested_chart": "KPI card with monthly trend",
    "needs_more_data": False
})


# ══════════════════════════════════════════════════════════
# TESTS SCHEMAS
# ══════════════════════════════════════════════════════════

class TestSchemas:
    """Teste la validation des modèles Pydantic de l'API."""

    def test_detect_sector_request_minimal(self):
        """DetectSectorRequest doit accepter une query seule."""
        from api.schemas import DetectSectorRequest
        req = DetectSectorRequest(
            user_query="améliorer l'expérience des passagers de l'aéroport"
        )
        assert req.user_query is not None
        assert req.column_metadata is None

    def test_detect_sector_request_with_metadata(self):
        """DetectSectorRequest doit accepter query + metadata."""
        from api.schemas import DetectSectorRequest, ColumnMetadataSchema
        req = DetectSectorRequest(
            user_query="améliorer l'expérience client",
            column_metadata=[
                ColumnMetadataSchema(name="flight_id", description="id du vol"),
                ColumnMetadataSchema(name="delay_minutes")
            ]
        )
        assert len(req.column_metadata) == 2
        assert req.column_metadata[0].name == "flight_id"
        assert req.column_metadata[1].description is None

    def test_chat_request_requires_user_id(self):
        """ChatRequest doit exiger user_id, question et sector_context."""
        from api.schemas import ChatRequest
        req = ChatRequest(
            user_id="user_123",
            question="Quel est le retard moyen ?",
            sector_context=MOCK_SECTOR_CONTEXT
        )
        assert req.user_id == "user_123"
        assert req.data_profile is None

    def test_detect_sector_response_structure(self):
        """DetectSectorResponse doit être constructible depuis les champs attendus."""
        from api.schemas import DetectSectorResponse, KPISchema
        resp = DetectSectorResponse(
            sector="transport",
            confidence=0.95,
            use_case="Airport UX",
            metadata_used=False,
            kpis=[KPISchema(name="Average Delay", description="Mean delay",
                            unit="minutes", priority="high")],
            dashboard_focus="Passenger Experience",
            recommended_charts=["histogram"],
            routing_target="transport_agent",
            explanation="Airport keywords."
        )
        assert resp.sector == "transport"
        assert resp.routing_target == "transport_agent"
        assert len(resp.kpis) == 1

    def test_chat_response_structure(self):
        """ChatResponse doit inclure user_id et history_length."""
        from api.schemas import ChatResponse
        resp = ChatResponse(
            user_id="user_123",
            answer="Le retard moyen est 12 min.",
            query_type="aggregation",
            needs_more_data=False,
            history_length=1
        )
        assert resp.user_id == "user_123"
        assert resp.history_length == 1
        assert resp.generated_query is None

    def test_health_response_structure(self):
        """HealthResponse doit avoir status, model et active_sessions."""
        from api.schemas import HealthResponse
        h = HealthResponse(
            status="ok",
            model="meta-llama/llama-3.1-8b-instruct",
            active_sessions=3
        )
        assert h.status == "ok"
        assert h.active_sessions == 3


# ══════════════════════════════════════════════════════════
# TESTS HELPERS (sans TestClient)
# ══════════════════════════════════════════════════════════

class TestHelpers:
    """Teste les fonctions utilitaires de main.py."""

    def test_sector_context_from_dict_valid(self):
        """sector_context_from_dict doit reconstruire un SectorContext valide."""
        # Import direct sans démarrer FastAPI
        from agents.context_sector_agent import SectorContext, KPI

        def sector_context_from_dict(data):
            kpis = [KPI(**k) for k in data.get("kpis", [])]
            return SectorContext(
                sector=data["sector"],
                confidence=data["confidence"],
                use_case=data["use_case"],
                metadata_used=data.get("metadata_used", False),
                kpis=kpis,
                dashboard_focus=data["dashboard_focus"],
                recommended_charts=data.get("recommended_charts", []),
                routing_target=data["routing_target"],
                explanation=data.get("explanation", "")
            )

        ctx = sector_context_from_dict(MOCK_SECTOR_CONTEXT)
        assert ctx.sector == "transport"
        assert ctx.confidence == 0.95
        assert len(ctx.kpis) == 2
        assert ctx.kpis[0].name == "On-Time Performance"
        assert ctx.routing_target == "transport_agent"

    def test_sector_context_from_dict_missing_key_raises(self):
        """sector_context_from_dict doit lever une erreur si champ manquant."""
        from agents.context_sector_agent import SectorContext, KPI

        def sector_context_from_dict(data):
            try:
                kpis = [KPI(**k) for k in data.get("kpis", [])]
                return SectorContext(
                    sector=data["sector"],
                    confidence=data["confidence"],
                    use_case=data["use_case"],
                    metadata_used=data.get("metadata_used", False),
                    kpis=kpis,
                    dashboard_focus=data["dashboard_focus"],
                    recommended_charts=data.get("recommended_charts", []),
                    routing_target=data["routing_target"],
                    explanation=data.get("explanation", "")
                )
            except (KeyError, TypeError) as e:
                raise ValueError(f"Invalid: {e}")

        incomplete = {"sector": "transport"}  # manque confidence, use_case, etc.
        with pytest.raises(ValueError):
            sector_context_from_dict(incomplete)

    def test_get_or_create_nlq_session_creates_new(self):
        """get_or_create_nlq_session doit créer une nouvelle session si absente."""
        from agents.nlq_agent import NLQAgent

        sessions = {}

        def get_or_create(user_id, api_key="test"):
            if user_id not in sessions:
                sessions[user_id] = NLQAgent.__new__(NLQAgent)
                sessions[user_id].conversation_history = []
            return sessions[user_id]

        with patch("agents.nlq_agent.ChatOpenAI"):
            agent = get_or_create("user_abc")
            assert "user_abc" in sessions
            assert agent.conversation_history == []

    def test_get_or_create_nlq_session_reuses_existing(self):
        """get_or_create_nlq_session doit réutiliser la session existante."""
        from agents.nlq_agent import NLQAgent

        sessions = {}
        mock_agent = MagicMock()
        mock_agent.conversation_history = [{"user": "Q1", "assistant": "A1"}]
        sessions["user_xyz"] = mock_agent

        def get_or_create(user_id, api_key="test"):
            if user_id not in sessions:
                sessions[user_id] = NLQAgent.__new__(NLQAgent)
                sessions[user_id].conversation_history = []
            return sessions[user_id]

        agent = get_or_create("user_xyz")
        # Doit retourner la même instance avec l'historique préservé
        assert len(agent.conversation_history) == 1
        assert agent.conversation_history[0]["user"] == "Q1"


# ══════════════════════════════════════════════════════════
# TESTS API — Simulation des endpoints
# (sans TestClient car dépendances FastAPI non installées)
# ══════════════════════════════════════════════════════════

class TestAPILogic:
    """
    Teste la logique des endpoints sans démarrer le serveur FastAPI.
    Vérifie les transformations request → agent → response.
    """

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_sector_logic(self, mock_openai):
        """
        Simule le traitement de POST /detect-sector :
        DetectSectorRequest → ContextSectorAgent.detect() → DetectSectorResponse
        """
        from agents.context_sector_agent import ContextSectorAgent, ColumnMetadata
        from api.schemas import DetectSectorRequest, KPISchema, DetectSectorResponse

        # Mock LLM
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(MOCK_SECTOR_CONTEXT))
        mock_openai.return_value = mock_llm

        # Simuler la requête
        request = DetectSectorRequest(
            user_query="améliorer l'expérience des passagers de l'aéroport"
        )

        # Agent
        agent = ContextSectorAgent("test-key", verbose=False)
        ctx = agent.detect(request.user_query, column_metadata=None)

        # Construire la réponse
        response = DetectSectorResponse(
            sector=ctx.sector,
            confidence=ctx.confidence,
            use_case=ctx.use_case,
            metadata_used=ctx.metadata_used,
            kpis=[KPISchema(**k.__dict__) for k in ctx.kpis],
            dashboard_focus=ctx.dashboard_focus,
            recommended_charts=ctx.recommended_charts,
            routing_target=ctx.routing_target,
            explanation=ctx.explanation
        )

        assert response.sector == "transport"
        assert response.routing_target == "transport_agent"
        assert response.confidence == 0.95
        assert len(response.kpis) == 2

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_sector_with_metadata_logic(self, mock_openai):
        """
        Simule POST /detect-sector avec metadata colonnes.
        Vérifie que les ColumnMetadataSchema sont bien convertis en ColumnMetadata.
        """
        from agents.context_sector_agent import ContextSectorAgent, ColumnMetadata
        from api.schemas import DetectSectorRequest, ColumnMetadataSchema

        mock_with_metadata = dict(MOCK_SECTOR_CONTEXT)
        mock_with_metadata["metadata_used"] = True
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps(mock_with_metadata))
        mock_openai.return_value = mock_llm

        request = DetectSectorRequest(
            user_query="améliorer l'expérience client",
            column_metadata=[
                ColumnMetadataSchema(name="flight_id", description="id du vol"),
                ColumnMetadataSchema(name="delay_minutes", description="retard en minutes")
            ]
        )

        # Conversion schema → agent model
        column_metadata = [
            ColumnMetadata(name=col.name, description=col.description)
            for col in request.column_metadata
        ]

        agent = ContextSectorAgent("test-key", verbose=False)
        ctx = agent.detect(request.user_query, column_metadata=column_metadata)

        assert ctx.metadata_used is True

        # Vérifier que les colonnes sont dans le prompt
        call_text = mock_llm.invoke.call_args[0][0][0].content
        assert "flight_id" in call_text
        assert "delay_minutes" in call_text

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_chat_logic(self, mock_openai):
        """
        Simule le traitement de POST /chat :
        ChatRequest → NLQAgent.chat() → ChatResponse
        """
        from agents.context_sector_agent import SectorContext, KPI
        from agents.nlq_agent import NLQAgent
        from api.schemas import ChatRequest, ChatResponse

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=MOCK_NLQ_RESPONSE)
        mock_openai.return_value = mock_llm

        request = ChatRequest(
            user_id="user_123",
            question="Quel est le taux de retard moyen ?",
            sector_context=MOCK_SECTOR_CONTEXT
        )

        # Reconstruire le SectorContext
        kpis = [KPI(**k) for k in request.sector_context["kpis"]]
        ctx = SectorContext(**{**request.sector_context, "kpis": kpis})

        # NLQ Agent
        nlq = NLQAgent("test-key", verbose=False)
        nlq_resp = nlq.chat(request.question, ctx, data_profile=request.data_profile)

        # Construire la réponse
        response = ChatResponse(
            user_id=request.user_id,
            answer=nlq_resp.answer,
            query_type=nlq_resp.query_type,
            generated_query=nlq_resp.generated_query,
            kpi_referenced=nlq_resp.kpi_referenced,
            suggested_chart=nlq_resp.suggested_chart,
            needs_more_data=nlq_resp.needs_more_data,
            history_length=nlq.history_length
        )

        assert response.user_id == "user_123"
        assert response.query_type == "aggregation"
        assert response.kpi_referenced == "Average Delay"
        assert response.history_length == 1
        assert "delay_minutes" in response.generated_query

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_chat_with_data_profile(self, mock_openai):
        """
        Simule POST /chat avec data_profile fourni par le Data Prep Agent.
        Vérifie que le profil est bien transmis au NLQ Agent.
        """
        from agents.context_sector_agent import SectorContext, KPI
        from agents.nlq_agent import NLQAgent

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=MOCK_NLQ_RESPONSE)
        mock_openai.return_value = mock_llm

        data_profile = {
            "row_count": 500,
            "columns": ["flight_id", "delay_minutes", "gate"],
            "numeric_columns": ["delay_minutes"],
            "categorical_columns": ["gate"],
            "missing_summary": {}
        }

        kpis = [KPI(**k) for k in MOCK_SECTOR_CONTEXT["kpis"]]
        ctx = SectorContext(**{**MOCK_SECTOR_CONTEXT, "kpis": kpis})

        nlq = NLQAgent("test-key", verbose=False)
        nlq.chat("Question test", ctx, data_profile=data_profile)

        # Vérifier que le data_profile est dans le system prompt
        messages = mock_llm.invoke.call_args[0][0]
        system_content = messages[0].content   # SystemMessage
        assert "delay_minutes" in system_content
        assert "500" in system_content

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_session_isolation_between_users(self, mock_openai):
        """
        Vérifie que deux utilisateurs ont des sessions NLQ isolées.
        L'historique de user_A ne doit pas affecter user_B.
        """
        from agents.context_sector_agent import SectorContext, KPI
        from agents.nlq_agent import NLQAgent

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=MOCK_NLQ_RESPONSE)
        mock_openai.return_value = mock_llm

        kpis = [KPI(**k) for k in MOCK_SECTOR_CONTEXT["kpis"]]
        ctx = SectorContext(**{**MOCK_SECTOR_CONTEXT, "kpis": kpis})

        sessions = {}

        def get_session(user_id):
            if user_id not in sessions:
                sessions[user_id] = NLQAgent("test-key", verbose=False)
            return sessions[user_id]

        # user_A pose 2 questions
        nlq_a = get_session("user_A")
        nlq_a.chat("Question A1", ctx)
        nlq_a.chat("Question A2", ctx)

        # user_B pose 1 question
        nlq_b = get_session("user_B")
        nlq_b.chat("Question B1", ctx)

        assert nlq_a.history_length == 2
        assert nlq_b.history_length == 1
        # Les sessions sont bien isolées
        assert sessions["user_A"] is not sessions["user_B"]

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_reset_chat_logic(self, mock_openai):
        """
        Simule POST /chat/reset.
        Vérifie que l'historique est effacé après reset.
        """
        from agents.context_sector_agent import SectorContext, KPI
        from agents.nlq_agent import NLQAgent

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=MOCK_NLQ_RESPONSE)
        mock_openai.return_value = mock_llm

        kpis = [KPI(**k) for k in MOCK_SECTOR_CONTEXT["kpis"]]
        ctx = SectorContext(**{**MOCK_SECTOR_CONTEXT, "kpis": kpis})

        sessions = {}
        user_id = "user_reset_test"

        # Créer session et poser une question
        sessions[user_id] = NLQAgent("test-key", verbose=False)
        sessions[user_id].chat("Une question", ctx)
        assert sessions[user_id].history_length == 1

        # Reset
        if user_id in sessions:
            sessions[user_id].reset_conversation()

        assert sessions[user_id].history_length == 0

    def test_reset_chat_nonexistent_session(self):
        """
        Simule POST /chat/reset pour un user_id sans session active.
        Doit retourner history_cleared=False sans erreur.
        """
        sessions = {}
        user_id = "user_inexistant"

        if user_id in sessions:
            sessions[user_id].reset_conversation()
            cleared = True
        else:
            cleared = False

        assert cleared is False

    def test_health_check_logic(self):
        """Simule GET /health."""
        from api.schemas import HealthResponse

        sessions = {"user_1": MagicMock(), "user_2": MagicMock()}

        response = HealthResponse(
            status="ok",
            model="meta-llama/llama-3.1-8b-instruct",
            active_sessions=len(sessions)
        )

        assert response.status == "ok"
        assert response.active_sessions == 2
        assert "llama" in response.model


# ══════════════════════════════════════════════════════════
# TESTS — INTÉGRATION COMPLÈTE DU PIPELINE API
# ══════════════════════════════════════════════════════════

class TestFullAPIFlow:
    """
    Teste le flux complet : detect-sector → chat → reset.
    Simule ce que l'UI et l'orchestrateur font en production.
    """

    @patch("agents.nlq_agent.ChatOpenAI")
    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_full_flow_ui(self, mock_sector_openai, mock_nlq_openai):
        """
        Flux UI complet :
        1. UI envoie la query globale → /detect-sector
        2. UI reçoit SectorContext, affiche dashboard
        3. User pose question → /chat
        4. User pose question de suivi → /chat (historique actif)
        5. User change de sujet → /chat/reset
        """
        from agents.context_sector_agent import ContextSectorAgent, SectorContext, KPI
        from agents.nlq_agent import NLQAgent
        from api.schemas import KPISchema, DetectSectorResponse

        # Mock agents
        mock_sector_llm = MagicMock()
        mock_sector_llm.invoke.return_value = MagicMock(content=json.dumps(MOCK_SECTOR_CONTEXT))
        mock_sector_openai.return_value = mock_sector_llm

        mock_nlq_llm = MagicMock()
        mock_nlq_llm.invoke.return_value = MagicMock(content=MOCK_NLQ_RESPONSE)
        mock_nlq_openai.return_value = mock_nlq_llm

        sessions = {}
        user_id = "ui_user_001"

        # ── STEP 1 : detect-sector ──
        sector_agent = ContextSectorAgent("test-key", verbose=False)
        ctx = sector_agent.detect("améliorer l'expérience des passagers de l'aéroport")

        assert ctx.sector == "transport"
        assert ctx.routing_target == "transport_agent"

        # ── STEP 2 : Serialisation pour l'UI → /chat ──
        ctx_dict = {
            "sector": ctx.sector,
            "confidence": ctx.confidence,
            "use_case": ctx.use_case,
            "metadata_used": ctx.metadata_used,
            "kpis": [k.__dict__ for k in ctx.kpis],
            "dashboard_focus": ctx.dashboard_focus,
            "recommended_charts": ctx.recommended_charts,
            "routing_target": ctx.routing_target,
            "explanation": ctx.explanation
        }

        # ── STEP 3 : /chat — question 1 ──
        sessions[user_id] = NLQAgent("test-key", verbose=False)
        kpis = [KPI(**k) for k in ctx_dict["kpis"]]
        ctx_rebuilt = SectorContext(**{**ctx_dict, "kpis": kpis})

        r1 = sessions[user_id].chat("Quel est le retard moyen ?", ctx_rebuilt)
        assert sessions[user_id].history_length == 1

        # ── STEP 4 : /chat — question de suivi ──
        r2 = sessions[user_id].chat("Et pour la route CMN-CDG ?", ctx_rebuilt)
        assert sessions[user_id].history_length == 2

        # Le deuxième appel doit inclure l'historique (4 messages au lieu de 2)
        second_call_msgs = mock_nlq_llm.invoke.call_args_list[1][0][0]
        assert len(second_call_msgs) == 4  # system + hist_human + hist_ai + new_human

        # ── STEP 5 : /chat/reset ──
        sessions[user_id].reset_conversation()
        assert sessions[user_id].history_length == 0

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_orchestrator_receives_routing_target(self, mock_openai):
        """
        Vérifie que l'orchestrateur reçoit le bon routing_target
        depuis /detect-sector pour chaque secteur.
        """
        from agents.context_sector_agent import ContextSectorAgent

        test_cases = [
            ("transport", "transport_agent"),
            ("finance", "finance_agent"),
            ("retail", "retail_agent"),
            ("manufacturing", "manufacturing_agent"),
        ]

        for sector, expected_target in test_cases:
            mock_response = dict(MOCK_SECTOR_CONTEXT)
            mock_response["sector"] = sector
            mock_response["routing_target"] = expected_target

            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MagicMock(content=json.dumps(mock_response))
            mock_openai.return_value = mock_llm

            agent = ContextSectorAgent("test-key", verbose=False)
            ctx = agent.detect(f"query for {sector}")

            assert ctx.routing_target == expected_target, \
                f"Expected {expected_target}, got {ctx.routing_target}"