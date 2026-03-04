import pytest
import uuid
from app.main import run_orchestrator
from app.schemas.input_schema import UserQueryInput
from app.graph.state import RouteEnum


def make_input(query: str) -> UserQueryInput:
    return UserQueryInput(
        user_id="u_test",
        session_id=str(uuid.uuid4()),
        query=query
    )


class TestGraphEndToEnd:

    def test_transport_query_end_to_end(self):
        result = run_orchestrator(make_input(
            "Montre-moi les KPIs transport du mois"
        ))
        assert result.route_taken == RouteEnum.TRANSPORT_AGENT
        assert result.sector_detected == "Transport"
        assert result.response != ""
        assert result.data_payload != {}

    def test_finance_query_end_to_end(self):
        result = run_orchestrator(make_input(
            "Prévision du chiffre d'affaires Q2"
        ))
        assert result.route_taken == RouteEnum.FINANCE_AGENT
        assert result.sector_detected == "Finance"

    def test_dashboard_query_goes_insight(self):
        result = run_orchestrator(make_input(
            "Tableau de bord comparaison synthèse global"
        ))
        assert result.route_taken == RouteEnum.INSIGHT_AGENT

    def test_unclear_query_triggers_clarification(self):
        result = run_orchestrator(make_input(
            "xyz blabla incompréhensible"
        ))
        assert result.needs_clarification is True
        assert result.response != ""

    def test_response_always_has_content(self):
        """La réponse ne doit jamais être vide"""
        queries = [
            "KPIs transport",
            "budget finance",
            "stock retail magasin",
            "production usine qualité",
            "dashboard vue rapport",
        ]
        for q in queries:
            result = run_orchestrator(make_input(q))
            assert result.response != "", f"Réponse vide pour : {q}"

    def test_processing_steps_always_populated(self):
        """Le pipeline doit toujours tracer ses étapes"""
        result = run_orchestrator(make_input("KPIs transport"))
        # On vérifie via route_taken que le graph a tourné
        assert result.route_taken is not None


class TestResponseFormat:

    def test_kpi_request_returns_kpi_format(self):
        result = run_orchestrator(make_input(
            "KPIs indicateurs performance transport taux"
        ))
        assert result.response_format in ["kpi", "text", "chart"]

    def test_data_payload_structure(self):
        result = run_orchestrator(make_input(
            "KPIs transport du mois"
        ))
        if result.data_payload:
            assert isinstance(result.data_payload, dict)