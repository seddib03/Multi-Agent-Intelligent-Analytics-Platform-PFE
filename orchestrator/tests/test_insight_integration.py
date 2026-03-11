import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.graph.state import OrchestratorState, SectorEnum, RouteEnum
from app.clients.insight_client import call_generate_dashboard, _build_sector_context
from app.graph.nodes.insight_node import insight_node


# ── Helpers ───────────────────────────────────────────────────────
def make_state(csv_path="insurance_data.csv"):
    return OrchestratorState(
        user_id="u_test",
        query_raw="Analyse les primes d'assurance",
        sector=SectorEnum.FINANCE,
        sector_confidence=0.92,
        kpi_mapping=[
            {"name": "Total Premium Amount"},
            {"name": "Average Client Age"},
        ],
        csv_path=csv_path,
        metadata={"metadata_path": "metadata_insurance.json"},
        route=RouteEnum.INSIGHT_AGENT,
    )


# ── Tests _build_sector_context ───────────────────────────────────
class TestBuildSectorContext:

    def test_sector_context_structure(self):
        """Vérifie que le sector_context est bien formé."""
        state = make_state()
        ctx = _build_sector_context(state)

        assert ctx["sector"] == "Finance"
        assert ctx["context"] == "Analyse les primes d'assurance"
        assert "Total Premium Amount" in ctx["recommended_kpis"]
        assert "Average Client Age" in ctx["recommended_kpis"]
        assert "dashboard_focus" in ctx
        assert isinstance(ctx["recommended_charts"], list)

    def test_kpi_mapping_as_strings(self):
        """kpi_mapping peut contenir des strings ou des dicts."""
        state = make_state()
        state.kpi_mapping = ["KPI A", "KPI B"]
        ctx = _build_sector_context(state)
        assert "KPI A" in ctx["recommended_kpis"]
        assert "KPI B" in ctx["recommended_kpis"]


# ── Tests call_generate_dashboard ────────────────────────────────
class TestCallGenerateDashboard:

    @pytest.mark.asyncio
    async def test_success_response(self):
        """Teste une réponse success de l'Insight Agent."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "agent": "insight_agent_pipeline",
            "dashboard_mode": "general",
            "sector": "Finance",
            "template": "executive_dashboard",
            "title": "Finance Analytics Dashboard",
            "kpis": [
                {"name": "Total Premiums", "column": "Prime",
                 "aggregation": "SUM", "value": 393000000},
                {"name": "Average Client Age", "column": "client_age",
                 "aggregation": "AVG", "value": 42.31},
            ],
            "charts": [
                {"type": "line", "title": "Premium Over Time",
                 "x": "datedeb", "y": "Prime"}
            ],
            "insights": [
                "Premiums show a consistent increase over time.",
                "Clients aged 30-40 represent the highest premium payments."
            ]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        state = make_state()

        with patch("app.clients.insight_client.httpx.AsyncClient",
                   return_value=mock_client):
            result = await call_generate_dashboard(state)

        assert result.agent_response["status"] == "success"
        assert result.response_format == "kpi"
        assert "Total Premiums" in result.final_response
        assert "Finance Analytics Dashboard" in result.final_response
        assert any("insight_agent" in s for s in result.processing_steps)

    @pytest.mark.asyncio
    async def test_api_unavailable(self):
        """Teste que l'erreur de connexion est gérée proprement."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        state = make_state()

        with patch("app.clients.insight_client.httpx.AsyncClient",
                   return_value=mock_client):
            result = await call_generate_dashboard(state)

        assert len(result.errors) > 0
        assert "non disponible" in result.errors[0]


# ── Tests insight_node ────────────────────────────────────────────
class TestInsightNode:

    def test_no_csv_returns_clarification(self):
        """Sans CSV → needs_clarification=True."""
        state = make_state(csv_path="")
        result = insight_node(state)

        assert result.needs_clarification is True
        assert result.final_response != ""
        assert any("skipped" in s for s in result.processing_steps)

    def test_with_csv_calls_agent(self):
        """Avec CSV → appelle l'Insight Agent."""
        state = make_state(csv_path="insurance_data.csv")

        mock_result = state.model_copy()
        mock_result.final_response = "Dashboard généré"
        mock_result.response_format = "kpi"

        with patch(
            "app.graph.nodes.insight_node.call_generate_dashboard",
            new=AsyncMock(return_value=mock_result)
        ):
            result = insight_node(state)

        assert result.final_response == "Dashboard généré"
        assert result.response_format == "kpi"