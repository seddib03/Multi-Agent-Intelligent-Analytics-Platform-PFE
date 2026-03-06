"""
Tests — Sprint 1 | Context/Sector Agent & NLQ Agent
=====================================================
PFE — DXC Technology | Intelligence Analytics Platform

Organisation des tests
-----------------------
1. TestKPIConfig          → Validation du fichier kpi_config.yaml
2. TestColumnMetadata     → Validation du modèle ColumnMetadata
3. TestSectorContext       → Validation du modèle SectorContext
4. TestContextSectorAgent → Tests de l'agent de détection (avec mock LLM)
5. TestNLQResponse        → Validation du modèle NLQResponse
6. TestNLQAgent           → Tests du chatbot (avec mock LLM)
7. TestPipelineIntegration → Tests d'intégration des deux agents ensemble

Tous les tests utilisent des mocks pour le LLM (unittest.mock).
Aucune clé API n'est nécessaire pour exécuter ces tests.

Usage
-----
    # Lancer tous les tests
    pytest tests/test_sprint1.py -v

    # Lancer une classe spécifique
    pytest tests/test_sprint1.py::TestContextSectorAgent -v

    # Lancer avec rapport de couverture
    pytest tests/test_sprint1.py -v --tb=short
"""

import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch

# Ajouter le répertoire racine au path Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.context_sector_agent import (
    ContextSectorAgent,
    ColumnMetadata,
    KPI,
    SectorContext,
    load_kpi_config,
    format_kpi_config_for_prompt,
    format_metadata_for_prompt,
)
from agents.nlq_agent import NLQAgent, NLQResponse


# ══════════════════════════════════════════════════════════
# FIXTURES — Données réutilisables entre les tests
# ══════════════════════════════════════════════════════════

@pytest.fixture
def transport_context():
    """
    SectorContext Transport complet pour utiliser dans les tests NLQ.
    Simule ce que le ContextSectorAgent produirait pour une query aéroport.
    """
    return SectorContext(
        sector="transport",
        confidence=0.95,
        use_case="Améliorer l'expérience des passagers de l'aéroport",
        metadata_used=False,
        kpis=[
            KPI(name="On-Time Performance",
                description="% of flights on time",
                unit="%",
                priority="high"),
            KPI(name="Passenger Satisfaction Score",
                description="Average satisfaction rating",
                unit="score/5",
                priority="high"),
            KPI(name="Average Delay",
                description="Mean delay in minutes",
                unit="minutes",
                priority="medium"),
            KPI(name="Security Wait Time",
                description="Average security queue time",
                unit="minutes",
                priority="low"),
        ],
        dashboard_focus="Passenger Experience & Operational Efficiency",
        recommended_charts=[
            "Flight delay distribution (histogram)",
            "Satisfaction score over time (line chart)",
            "On-time performance by route (bar chart)"
        ],
        routing_target="transport_agent",
        explanation="Query mentions airport and passenger experience — Transport sector."
    )


@pytest.fixture
def finance_context():
    """SectorContext Finance pour tester un secteur différent."""
    return SectorContext(
        sector="finance",
        confidence=0.88,
        use_case="Analyser la performance financière et réduire les risques",
        metadata_used=False,
        kpis=[
            KPI(name="Revenue Growth", description="YoY revenue growth", unit="%", priority="high"),
            KPI(name="Net Profit Margin", description="Net profit as % of revenue", unit="%", priority="high"),
            KPI(name="Default Rate", description="% loans in default", unit="%", priority="medium"),
        ],
        dashboard_focus="Financial Performance & Risk Monitoring",
        recommended_charts=["Revenue trend (line chart)", "Profit margin by segment"],
        routing_target="finance_agent",
        explanation="Query mentions financial performance and risk — Finance sector."
    )


@pytest.fixture
def sample_data_profile():
    """
    Profil de dataset simplifié simulant la sortie du DataPrepAgent.
    Utilisé pour tester le NLQ Agent avec données réelles.
    """
    return {
        "row_count": 500,
        "columns": ["flight_id", "departure_date", "route", "delay_minutes",
                    "passenger_count", "satisfaction", "gate", "status"],
        "numeric_columns": ["delay_minutes", "passenger_count", "satisfaction"],
        "categorical_columns": ["route", "gate", "status"],
        "datetime_columns": ["departure_date"],
        "missing_summary": {"satisfaction": 5.2, "gate": 3.1},
        "quality_score": 85.0
    }


@pytest.fixture
def mock_sector_llm_response():
    """Réponse JSON simulée du LLM pour la détection Transport."""
    return json.dumps({
        "sector": "transport",
        "confidence": 0.95,
        "use_case": "Améliorer l'expérience des passagers de l'aéroport",
        "metadata_used": False,
        "kpis": [
            {"name": "On-Time Performance", "description": "% flights on time",
             "unit": "%", "priority": "high"},
            {"name": "Passenger Satisfaction Score", "description": "Avg satisfaction rating",
             "unit": "score/5", "priority": "high"},
            {"name": "Average Delay", "description": "Mean delay in minutes",
             "unit": "minutes", "priority": "medium"}
        ],
        "dashboard_focus": "Passenger Experience & Operational Efficiency",
        "recommended_charts": [
            "Flight delay histogram",
            "Satisfaction line chart",
            "On-time performance bar chart"
        ],
        "routing_target": "transport_agent",
        "explanation": "Airport and passenger experience keywords detected."
    })


@pytest.fixture
def mock_nlq_llm_response():
    """Réponse JSON simulée du LLM pour une question NLQ."""
    return json.dumps({
        "answer": "Le taux de retard moyen ce mois est de 12.4 minutes.",
        "query_type": "aggregation",
        "generated_query": "SELECT AVG(delay_minutes) FROM flights WHERE MONTH(departure_date) = MONTH(NOW())",
        "kpi_referenced": "Average Delay",
        "suggested_chart": "KPI card with monthly trend",
        "needs_more_data": False
    })


# ══════════════════════════════════════════════════════════
# 1. TESTS — KPI CONFIG
# ══════════════════════════════════════════════════════════

class TestKPIConfig:
    """Tests de validation du fichier kpi_config.yaml."""

    def test_config_loads_without_error(self):
        """Le fichier YAML doit se charger sans exception."""
        config = load_kpi_config("config/kpi_config.yaml")
        assert config is not None
        assert isinstance(config, dict)

    def test_config_has_sectors_key(self):
        """La config doit avoir une clé 'sectors' au niveau racine."""
        config = load_kpi_config("config/kpi_config.yaml")
        assert "sectors" in config

    def test_all_five_sectors_present(self):
        """Les 5 secteurs cibles doivent tous être définis."""
        config = load_kpi_config("config/kpi_config.yaml")
        expected = {"transport", "finance", "retail", "manufacturing", "public"}
        actual = set(config["sectors"].keys())
        assert expected.issubset(actual), f"Missing sectors: {expected - actual}"

    def test_each_sector_has_minimum_3_kpis(self):
        """Chaque secteur doit définir au minimum 3 KPIs."""
        config = load_kpi_config("config/kpi_config.yaml")
        for sector, data in config["sectors"].items():
            assert "kpis" in data, f"Sector '{sector}' has no 'kpis' key"
            assert len(data["kpis"]) >= 3, \
                f"Sector '{sector}' has only {len(data['kpis'])} KPI(s), minimum is 3"

    def test_each_kpi_has_required_fields(self):
        """Chaque KPI doit avoir les champs name, description et unit."""
        config = load_kpi_config("config/kpi_config.yaml")
        required = {"name", "description", "unit"}
        for sector, data in config["sectors"].items():
            for i, kpi in enumerate(data["kpis"]):
                missing = required - set(kpi.keys())
                assert not missing, \
                    f"KPI #{i} in sector '{sector}' missing fields: {missing}"

    def test_each_sector_has_dashboard_focus(self):
        """Chaque secteur doit avoir un champ 'dashboard_focus'."""
        config = load_kpi_config("config/kpi_config.yaml")
        for sector, data in config["sectors"].items():
            assert "dashboard_focus" in data, \
                f"Sector '{sector}' missing 'dashboard_focus'"
            assert len(data["dashboard_focus"]) > 0

    def test_each_sector_has_recommended_charts(self):
        """Chaque secteur doit avoir au moins 1 chart recommandé."""
        config = load_kpi_config("config/kpi_config.yaml")
        for sector, data in config["sectors"].items():
            assert "recommended_charts" in data
            assert len(data["recommended_charts"]) >= 1

    def test_transport_has_passenger_satisfaction_kpi(self):
        """Le secteur transport doit inclure un KPI de satisfaction passagers."""
        config = load_kpi_config("config/kpi_config.yaml")
        transport_kpis = [k["name"].lower() for k in config["sectors"]["transport"]["kpis"]]
        has_satisfaction = any(
            "satisfaction" in name or "passenger" in name
            for name in transport_kpis
        )
        assert has_satisfaction, "Transport sector must have a passenger satisfaction KPI"

    def test_format_kpi_config_returns_string(self):
        """format_kpi_config_for_prompt doit retourner une chaîne non vide."""
        config = load_kpi_config("config/kpi_config.yaml")
        result = format_kpi_config_for_prompt(config)
        assert isinstance(result, str)
        assert len(result) > 100
        assert "TRANSPORT" in result
        assert "FINANCE" in result


# ══════════════════════════════════════════════════════════
# 2. TESTS — COLUMN METADATA
# ══════════════════════════════════════════════════════════

class TestColumnMetadata:
    """Tests du modèle ColumnMetadata."""

    def test_creation_with_name_only(self):
        """ColumnMetadata doit se créer avec seulement le nom."""
        col = ColumnMetadata(name="flight_id")
        assert col.name == "flight_id"
        assert col.description is None
        assert col.sample_values is None

    def test_creation_with_all_fields(self):
        """ColumnMetadata doit accepter tous les champs."""
        col = ColumnMetadata(
            name="delay_minutes",
            description="Retard du vol en minutes",
            sample_values=["0", "15", "45", "120"]
        )
        assert col.name == "delay_minutes"
        assert col.description == "Retard du vol en minutes"
        assert len(col.sample_values) == 4

    def test_format_metadata_without_descriptions(self):
        """format_metadata_for_prompt doit fonctionner sans descriptions."""
        cols = [ColumnMetadata(name="flight_id"), ColumnMetadata(name="delay_minutes")]
        result = format_metadata_for_prompt(cols)
        assert "flight_id" in result
        assert "delay_minutes" in result
        assert "USER DATASET COLUMNS" in result

    def test_format_metadata_with_descriptions(self):
        """Les descriptions doivent apparaître dans le prompt formaté."""
        cols = [
            ColumnMetadata(name="delay_minutes", description="Retard en minutes"),
            ColumnMetadata(name="gate", description="Porte d'embarquement",
                          sample_values=["A1", "B2", "C3"])
        ]
        result = format_metadata_for_prompt(cols)
        assert "Retard en minutes" in result
        assert "Porte d'embarquement" in result
        assert "A1" in result


# ══════════════════════════════════════════════════════════
# 3. TESTS — SECTOR CONTEXT
# ══════════════════════════════════════════════════════════

class TestSectorContext:
    """Tests du modèle SectorContext."""

    def test_creation_with_valid_data(self, transport_context):
        """SectorContext doit se créer correctement avec des données valides."""
        assert transport_context.sector == "transport"
        assert transport_context.confidence == 0.95
        assert transport_context.metadata_used is False
        assert len(transport_context.kpis) == 4
        assert transport_context.routing_target == "transport_agent"

    def test_routing_target_follows_naming_convention(self, transport_context, finance_context):
        """Le routing_target doit suivre le format '{sector}_agent'."""
        assert transport_context.routing_target == "transport_agent"
        assert finance_context.routing_target == "finance_agent"

    def test_confidence_is_within_valid_range(self, transport_context, finance_context):
        """La confiance doit être entre 0.0 et 1.0."""
        assert 0.0 <= transport_context.confidence <= 1.0
        assert 0.0 <= finance_context.confidence <= 1.0

    def test_kpi_priority_values_are_valid(self, transport_context):
        """Les priorités KPI doivent être exactement 'high', 'medium' ou 'low'."""
        valid = {"high", "medium", "low"}
        for kpi in transport_context.kpis:
            assert kpi.priority in valid, \
                f"KPI '{kpi.name}' has invalid priority: '{kpi.priority}'"

    def test_kpis_sorted_high_first(self, transport_context):
        """
        Les KPIs doivent être triés du plus prioritaire au moins prioritaire.
        Au moins le premier KPI doit être 'high'.
        """
        assert transport_context.kpis[0].priority == "high"

    def test_recommended_charts_is_non_empty_list(self, transport_context):
        """La liste de charts recommandés ne doit pas être vide."""
        assert isinstance(transport_context.recommended_charts, list)
        assert len(transport_context.recommended_charts) >= 1


# ══════════════════════════════════════════════════════════
# 4. TESTS — CONTEXT/SECTOR AGENT
# ══════════════════════════════════════════════════════════

class TestContextSectorAgent:
    """Tests du ContextSectorAgent avec LLM mocké."""

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_agent_initializes_correctly(self, mock_openai):
        """L'agent doit s'initialiser sans erreur avec une clé API."""
        agent = ContextSectorAgent(
            openrouter_api_key="test-key",
            config_path="config/kpi_config.yaml",
            verbose=False
        )
        assert agent is not None
        assert agent.config is not None
        assert agent.kpi_reference is not None

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_agent_loads_kpi_config_on_init(self, mock_openai):
        """L'agent doit charger et formater la config KPI à l'initialisation."""
        agent = ContextSectorAgent(
            openrouter_api_key="test-key",
            config_path="config/kpi_config.yaml",
            verbose=False
        )
        # La référence KPI doit contenir les secteurs
        assert "TRANSPORT" in agent.kpi_reference
        assert "FINANCE" in agent.kpi_reference
        assert "RETAIL" in agent.kpi_reference

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_returns_sector_context(self, mock_openai, mock_sector_llm_response):
        """detect() doit retourner un objet SectorContext valide."""
        # Configuration du mock LLM
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_sector_llm_response)
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent(
            openrouter_api_key="test-key",
            config_path="config/kpi_config.yaml",
            verbose=False
        )
        result = agent.detect("améliorer l'expérience des passagers de l'aéroport")

        assert isinstance(result, SectorContext)
        assert result.sector == "transport"
        assert result.confidence == 0.95
        assert len(result.kpis) == 3
        assert result.routing_target == "transport_agent"

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_calls_llm_once(self, mock_openai, mock_sector_llm_response):
        """detect() doit appeler le LLM exactement une fois."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_sector_llm_response)
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent("test-key", verbose=False)
        agent.detect("test query")

        mock_llm.invoke.assert_called_once()

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_with_metadata_sets_metadata_used_true(self, mock_openai):
        """Quand metadata est fournie et décisive, metadata_used doit être True."""
        response_with_metadata = json.dumps({
            "sector": "transport",
            "confidence": 0.97,
            "use_case": "Améliorer l'expérience client dans l'aéroport",
            "metadata_used": True,          # ← metadata a été décisive
            "kpis": [
                {"name": "On-Time Performance", "description": "% on time",
                 "unit": "%", "priority": "high"}
            ],
            "dashboard_focus": "Passenger Experience",
            "recommended_charts": ["histogram"],
            "routing_target": "transport_agent",
            "explanation": "Column names like flight_id confirm Transport sector."
        })
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=response_with_metadata)
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent("test-key", verbose=False)
        metadata = [
            ColumnMetadata(name="flight_id"),
            ColumnMetadata(name="delay_minutes", description="retard en minutes")
        ]
        result = agent.detect("améliorer l'expérience client", column_metadata=metadata)

        assert result.metadata_used is True
        assert result.sector == "transport"

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_prompt_contains_metadata_when_provided(self, mock_openai, mock_sector_llm_response):
        """Le prompt doit contenir les noms de colonnes quand metadata est fournie."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_sector_llm_response)
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent("test-key", verbose=False)

        # On vérifie le prompt en inspectant l'appel au LLM
        metadata = [
            ColumnMetadata(name="flight_id"),
            ColumnMetadata(name="delay_minutes")
        ]
        agent.detect("améliorer l'expérience client", column_metadata=metadata)

        call_args = mock_llm.invoke.call_args[0][0]   # [0] = args, [0] = premier arg (messages)
        prompt_text = call_args[0].content             # premier message = HumanMessage

        assert "flight_id" in prompt_text
        assert "delay_minutes" in prompt_text

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_prompt_does_not_contain_metadata_when_absent(self, mock_openai, mock_sector_llm_response):
        """Le prompt ne doit PAS contenir la section metadata si aucune colonne n'est fournie."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_sector_llm_response)
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent("test-key", verbose=False)
        agent.detect("améliorer l'expérience des passagers de l'aéroport")  # sans metadata

        call_args = mock_llm.invoke.call_args[0][0]
        prompt_text = call_args[0].content

        assert "USER DATASET COLUMNS" not in prompt_text

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_raises_on_invalid_json(self, mock_openai):
        """detect() doit lever ValueError si le LLM retourne un JSON invalide."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="This is not JSON at all.")
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent("test-key", verbose=False)
        with pytest.raises(ValueError, match="invalid JSON"):
            agent.detect("test query")

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_cleans_markdown_backticks(self, mock_openai, mock_sector_llm_response):
        """
        detect() doit fonctionner même si le LLM encadre sa réponse JSON
        avec des backticks markdown (comportement courant de Llama).
        """
        # Simulation du comportement Llama avec backticks
        wrapped_response = f"```json\n{mock_sector_llm_response}\n```"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=wrapped_response)
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent("test-key", verbose=False)
        result = agent.detect("test query")

        # Doit parser correctement malgré les backticks
        assert isinstance(result, SectorContext)
        assert result.sector == "transport"

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_from_dict_builds_metadata(self, mock_openai, mock_sector_llm_response):
        """detect_from_dict() doit convertir le dict en ColumnMetadata et appeler detect()."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_sector_llm_response)
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent("test-key", verbose=False)
        result = agent.detect_from_dict(
            "améliorer l'expérience client",
            {"flight_id": "id du vol", "delay_minutes": "retard en minutes"}
        )

        assert isinstance(result, SectorContext)
        # Les noms de colonnes doivent apparaître dans le prompt
        call_args = mock_llm.invoke.call_args[0][0]
        prompt_text = call_args[0].content
        assert "flight_id" in prompt_text
        assert "delay_minutes" in prompt_text

    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_detect_from_dataframe_columns(self, mock_openai, mock_sector_llm_response):
        """detect_from_dataframe_columns() doit accepter une liste brute de noms."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_sector_llm_response)
        mock_openai.return_value = mock_llm

        agent = ContextSectorAgent("test-key", verbose=False)
        cols = ["flight_id", "delay_minutes", "gate", "passenger_count"]
        result = agent.detect_from_dataframe_columns("améliorer l'expérience client", cols)

        assert isinstance(result, SectorContext)


# ══════════════════════════════════════════════════════════
# 5. TESTS — NLQ RESPONSE
# ══════════════════════════════════════════════════════════

class TestNLQResponse:
    """Tests du modèle NLQResponse."""

    def test_creation_with_required_fields_only(self):
        """NLQResponse doit se créer avec seulement answer et query_type."""
        r = NLQResponse(answer="Le retard moyen est de 12 min.", query_type="aggregation")
        assert r.answer == "Le retard moyen est de 12 min."
        assert r.query_type == "aggregation"
        assert r.generated_query is None
        assert r.kpi_referenced is None
        assert r.needs_more_data is False

    def test_creation_with_all_fields(self):
        """NLQResponse doit accepter tous les champs optionnels."""
        r = NLQResponse(
            answer="Voici les données de retard.",
            query_type="sql",
            generated_query="SELECT AVG(delay_minutes) FROM flights",
            kpi_referenced="Average Delay",
            suggested_chart="KPI card",
            needs_more_data=False
        )
        assert r.generated_query is not None
        assert r.kpi_referenced == "Average Delay"
        assert r.suggested_chart == "KPI card"

    def test_needs_more_data_defaults_to_false(self):
        """needs_more_data doit valoir False par défaut."""
        r = NLQResponse(answer="Test", query_type="explanation")
        assert r.needs_more_data is False


# ══════════════════════════════════════════════════════════
# 6. TESTS — NLQ AGENT
# ══════════════════════════════════════════════════════════

class TestNLQAgent:
    """Tests du NLQAgent avec LLM mocké."""

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_agent_initializes_with_empty_history(self, mock_openai):
        """L'agent doit s'initialiser avec un historique vide."""
        nlq = NLQAgent(openrouter_api_key="test-key", verbose=False)
        assert nlq is not None
        assert nlq.conversation_history == []
        assert nlq.history_length == 0

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_chat_returns_nlq_response(self, mock_openai, transport_context, mock_nlq_llm_response):
        """chat() doit retourner un NLQResponse valide."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_nlq_llm_response)
        mock_openai.return_value = mock_llm

        nlq = NLQAgent("test-key", verbose=False)
        result = nlq.chat("Quel est le taux de retard moyen ?", transport_context)

        assert isinstance(result, NLQResponse)
        assert result.query_type == "aggregation"
        assert result.kpi_referenced == "Average Delay"
        assert "delay_minutes" in result.generated_query

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_chat_saves_to_history(self, mock_openai, transport_context, mock_nlq_llm_response):
        """Chaque appel à chat() doit ajouter un tour dans l'historique."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_nlq_llm_response)
        mock_openai.return_value = mock_llm

        nlq = NLQAgent("test-key", verbose=False)
        assert nlq.history_length == 0

        nlq.chat("Question 1", transport_context)
        assert nlq.history_length == 1

        nlq.chat("Question 2", transport_context)
        assert nlq.history_length == 2

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_conversation_history_format(self, mock_openai, transport_context, mock_nlq_llm_response):
        """L'historique doit stocker les paires user/assistant."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_nlq_llm_response)
        mock_openai.return_value = mock_llm

        nlq = NLQAgent("test-key", verbose=False)
        nlq.chat("Quel est le retard moyen ?", transport_context)

        turn = nlq.conversation_history[0]
        assert "user" in turn
        assert "assistant" in turn
        assert turn["user"] == "Quel est le retard moyen ?"
        assert len(turn["assistant"]) > 0

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_reset_conversation_clears_history(self, mock_openai, transport_context, mock_nlq_llm_response):
        """reset_conversation() doit vider complètement l'historique."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_nlq_llm_response)
        mock_openai.return_value = mock_llm

        nlq = NLQAgent("test-key", verbose=False)
        nlq.chat("Question", transport_context)
        assert nlq.history_length == 1

        nlq.reset_conversation()
        assert nlq.history_length == 0
        assert nlq.conversation_history == []

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_system_prompt_contains_sector(self, mock_openai, transport_context):
        """Le system prompt doit contenir le secteur détecté."""
        mock_openai.return_value = MagicMock()
        nlq = NLQAgent("test-key", verbose=False)
        prompt = nlq._build_system_prompt(transport_context, data_profile=None)

        assert "transport" in prompt.lower() or "TRANSPORT" in prompt
        assert "On-Time Performance" in prompt
        assert "Passenger Satisfaction Score" in prompt

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_system_prompt_contains_data_profile_when_provided(
        self, mock_openai, transport_context, sample_data_profile
    ):
        """Le system prompt doit inclure les colonnes du dataset quand le profil est fourni."""
        mock_openai.return_value = MagicMock()
        nlq = NLQAgent("test-key", verbose=False)
        prompt = nlq._build_system_prompt(transport_context, data_profile=sample_data_profile)

        assert "delay_minutes" in prompt
        assert "passenger_count" in prompt
        assert "500" in prompt  # row_count

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_system_prompt_has_no_data_section_without_profile(
        self, mock_openai, transport_context
    ):
        """Sans profil de données, la section dataset ne doit pas apparaître."""
        mock_openai.return_value = MagicMock()
        nlq = NLQAgent("test-key", verbose=False)
        prompt = nlq._build_system_prompt(transport_context, data_profile=None)

        assert "UPLOADED DATASET PROFILE" not in prompt

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_chat_injects_history_in_messages(
        self, mock_openai, transport_context, mock_nlq_llm_response
    ):
        """
        Après plusieurs échanges, le LLM doit recevoir l'historique complet.
        Vérifie que le nombre de messages augmente correctement.
        """
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_nlq_llm_response)
        mock_openai.return_value = mock_llm

        nlq = NLQAgent("test-key", verbose=False)

        # Premier échange : 1 system + 1 human = 2 messages
        nlq.chat("Question 1", transport_context)
        first_call_messages = mock_llm.invoke.call_args_list[0][0][0]
        assert len(first_call_messages) == 2   # SystemMessage + HumanMessage

        # Deuxième échange : 1 system + 2 history (human+ai) + 1 human = 4 messages
        nlq.chat("Question 2", transport_context)
        second_call_messages = mock_llm.invoke.call_args_list[1][0][0]
        assert len(second_call_messages) == 4

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_chat_fallback_on_invalid_json(self, mock_openai, transport_context):
        """Si le LLM retourne du texte invalide, chat() doit retourner un NLQResponse de fallback."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Je ne peux pas répondre.")
        mock_openai.return_value = mock_llm

        nlq = NLQAgent("test-key", verbose=False)
        result = nlq.chat("Question test", transport_context)

        # Le fallback doit quand même retourner un NLQResponse valide
        assert isinstance(result, NLQResponse)
        assert result.query_type == "explanation"
        assert "Je ne peux pas" in result.answer

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_chat_cleans_markdown_backticks(self, mock_openai, transport_context, mock_nlq_llm_response):
        """chat() doit parser correctement même si Llama ajoute des backticks."""
        wrapped = f"```json\n{mock_nlq_llm_response}\n```"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=wrapped)
        mock_openai.return_value = mock_llm

        nlq = NLQAgent("test-key", verbose=False)
        result = nlq.chat("Test", transport_context)

        assert isinstance(result, NLQResponse)
        assert result.query_type == "aggregation"


# ══════════════════════════════════════════════════════════
# 7. TESTS — INTÉGRATION DES DEUX AGENTS
# ══════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """
    Tests d'intégration : vérifient que les deux agents s'enchaînent correctement.
    Le SectorContext produit par le ContextSectorAgent est directement utilisable
    par le NLQAgent sans transformation.
    """

    @patch("agents.nlq_agent.ChatOpenAI")
    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_sector_context_flows_to_nlq(
        self, mock_sector_openai, mock_nlq_openai,
        mock_sector_llm_response, mock_nlq_llm_response
    ):
        """
        Le SectorContext produit par le ContextSectorAgent doit être
        directement utilisable par le NLQAgent.
        """
        # Mock du Sector Agent
        mock_sector_llm = MagicMock()
        mock_sector_llm.invoke.return_value = MagicMock(content=mock_sector_llm_response)
        mock_sector_openai.return_value = mock_sector_llm

        # Mock du NLQ Agent
        mock_nlq_llm = MagicMock()
        mock_nlq_llm.invoke.return_value = MagicMock(content=mock_nlq_llm_response)
        mock_nlq_openai.return_value = mock_nlq_llm

        # Étape 1 : Sector Agent produit le contexte
        sector_agent = ContextSectorAgent("test-key", verbose=False)
        ctx = sector_agent.detect("améliorer l'expérience des passagers de l'aéroport")

        assert ctx.sector == "transport"

        # Étape 2 : NLQ Agent utilise le contexte
        nlq = NLQAgent("test-key", verbose=False)
        response = nlq.chat("Quel est le taux de retard ?", ctx)

        assert isinstance(response, NLQResponse)
        assert response.kpi_referenced == "Average Delay"

    @patch("agents.nlq_agent.ChatOpenAI")
    @patch("agents.context_sector_agent.ChatOpenAI")
    def test_nlq_system_prompt_reflects_detected_sector(
        self, mock_sector_openai, mock_nlq_openai,
        mock_sector_llm_response, mock_nlq_llm_response
    ):
        """
        Le system prompt du NLQ doit refléter le secteur détecté par
        le ContextSectorAgent — transport dans ce cas.
        """
        mock_sector_llm = MagicMock()
        mock_sector_llm.invoke.return_value = MagicMock(content=mock_sector_llm_response)
        mock_sector_openai.return_value = mock_sector_llm

        mock_nlq_llm = MagicMock()
        mock_nlq_llm.invoke.return_value = MagicMock(content=mock_nlq_llm_response)
        mock_nlq_openai.return_value = mock_nlq_llm

        sector_agent = ContextSectorAgent("test-key", verbose=False)
        ctx = sector_agent.detect("améliorer l'expérience des passagers de l'aéroport")

        nlq = NLQAgent("test-key", verbose=False)
        nlq.chat("Question", ctx)

        # Vérifier que le system prompt du NLQ mentionne "transport"
        nlq_messages = mock_nlq_llm.invoke.call_args[0][0]
        system_content = nlq_messages[0].content  # SystemMessage
        assert "transport" in system_content.lower()

    @patch("agents.nlq_agent.ChatOpenAI")
    def test_multiple_questions_maintain_context(
        self, mock_openai, transport_context, mock_nlq_llm_response
    ):
        """
        Sur plusieurs questions consécutives, le NLQ doit maintenir
        le même secteur/contexte et enrichir l'historique correctement.
        """
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_nlq_llm_response)
        mock_openai.return_value = mock_llm

        nlq = NLQAgent("test-key", verbose=False)

        questions = [
            "Quel est le retard moyen ?",
            "Et pour la route CMN-CDG spécifiquement ?",
            "Compare avec le mois dernier"
        ]

        for i, q in enumerate(questions):
            nlq.chat(q, transport_context)
            assert nlq.history_length == i + 1

        # L'historique doit contenir toutes les questions
        user_questions = [t["user"] for t in nlq.conversation_history]
        assert "Quel est le retard moyen ?" in user_questions
        assert "Et pour la route CMN-CDG spécifiquement ?" in user_questions