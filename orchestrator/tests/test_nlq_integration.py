import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.graph.state import OrchestratorState, SectorEnum, ExecutionTypeEnum
from app.clients.nlq_client import call_nlq_and_context


@pytest.mark.asyncio
async def test_real_nlq_integration():
    """Teste l'intégration avec l'API de ta collègue (mockée)"""

    # ── Réponses simulées de son API ──────────────────────────────
    mock_nlq = {
        "intent": "compare",
        "metric": "revenue",
        "timeframe": "2022-2023",
        "location": "Rabat",
        "confidence": 0.82
    }
    mock_ctx = {
        "sector": "retail",
        "canonical_metric": "total_sales_amount",
        "execution_type": "sql",
        "confidence": 0.88,
        "data_source": {"database": "retail_db", "table": "transactions"}
    }

    # ── State initial ─────────────────────────────────────────────
    state = OrchestratorState(
        user_id="u_test",
        session_id="sess_test",
        query_raw="Compare revenue between 2022 and 2023 in Rabat"
    )

    # ── Mock du client HTTP ───────────────────────────────────────
    mock_nlq_resp = MagicMock()
    mock_nlq_resp.json.return_value = mock_nlq

    mock_ctx_resp = MagicMock()
    mock_ctx_resp.json.return_value = mock_ctx

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[mock_nlq_resp, mock_ctx_resp])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    # ── Lancer le test ────────────────────────────────────────────
    with patch("app.clients.nlq_client.httpx.AsyncClient", return_value=mock_client):
        result = await call_nlq_and_context(state)

    # ── Assertions ────────────────────────────────────────────────
    assert result.sector == SectorEnum.RETAIL
    assert result.sector_confidence == 0.88
    assert result.intent.value == "compare"
    assert result.intent_confidence == 0.82
    assert result.execution_type == ExecutionTypeEnum.SQL
    assert result.canonical_metric == "total_sales_amount"
    assert result.metric_raw == "revenue"
    assert result.timeframe == "2022-2023"
    assert result.location == "Rabat"
    assert result.data_source == {"database": "retail_db", "table": "transactions"}
    assert any("nlq_client" in step for step in result.processing_steps)