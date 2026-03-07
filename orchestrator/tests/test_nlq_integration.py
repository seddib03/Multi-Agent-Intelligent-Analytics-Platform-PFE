# tests/test_nlq_integration.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.graph.state import OrchestratorState, SectorEnum, RouteEnum
from app.clients.nlq_client import call_detect_sector


@pytest.mark.asyncio
async def test_detect_sector_transport():
    """Teste POST /detect-sector avec une query Transport"""

    # Réponse simulée de son API
    mock_sector_context = {
        "sector": "transport",
        "confidence": 0.92,
        "kpis": ["retard_moyen", "taux_ponctualite", "charge_vols"],
        "routing_target": "transport_agent"
    }

    state = OrchestratorState(
        user_id="u_test",
        session_id="sess_test",
        query_raw="améliorer l'expérience des passagers de l'aéroport"
    )

    mock_response = MagicMock()
    mock_response.json.return_value = mock_sector_context

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.clients.nlq_client.httpx.AsyncClient", return_value=mock_client):
        result_state, suggested_route = await call_detect_sector(state)

    assert result_state.sector == SectorEnum.TRANSPORT
    assert result_state.sector_confidence == 0.92
    assert "retard_moyen" in result_state.kpi_mapping
    assert suggested_route == RouteEnum.TRANSPORT_AGENT
    assert any("detect_sector" in step for step in result_state.processing_steps)