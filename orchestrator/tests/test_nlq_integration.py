from unittest.mock import patch, AsyncMock
from app.clients.nlq_client import call_nlq_and_context
from app.graph.state import OrchestratorState

async def test_real_nlq_integration():
    """Teste l'intégration avec l'API de ta collègue (mockée)"""
    mock_nlq = {"intent": "compare", "metric": "revenue",
                "timeframe": "2022-2023", "location": "Rabat", "confidence": 0.82}
    mock_ctx = {"sector": "retail", "canonical_metric": "total_sales_amount",
                "execution_type": "sql", "confidence": 0.88,
                "data_source": {"database": "retail_db", "table": "transactions"}}

    with patch("app.clients.nlq_client.httpx.AsyncClient") as mock:
        # ... setup mock responses ...
        state = OrchestratorState(user_id="u_test", query_raw="Compare revenue between 2022 and 2023 in Rabat", session_id="sess_test")        assert result.sector.value == "Retail"
        