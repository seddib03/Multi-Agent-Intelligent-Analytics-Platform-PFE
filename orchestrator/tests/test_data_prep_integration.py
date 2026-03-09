import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.graph.state import OrchestratorState, DataPrepStatusEnum
from app.clients.data_prep_client import call_prepare, call_get_data_profile

def make_state(csv_path="test.csv"):
    return OrchestratorState(
        user_id="u_test",
        session_id="sess_test",
        query_raw="améliorer l expérience passagers",
        csv_path=csv_path,
        metadata={
            "table_name": "flights",
            "columns": [
                {"name": "flight_id", "type": "integer",
                 "nullable": False},
                {"name": "delay_minutes", "type": "float",
                 "min_val": 0}
            ],
            "business_rules": ["delay_minutes must be >= 0"]
        }
    )

@pytest.mark.asyncio
async def test_call_prepare_success():
    """Teste POST /prepare avec réponse simulée."""

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "job_id":   "job_test_001",
        "status":   "waiting_validation",
        "quality_before": {
            "global_scores": {
                "global":       0.85,
                "completeness": 0.90,
                "validity":     0.80
            }
        }
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=None)

    state = make_state()

    # Mock open() pour éviter de lire un vrai fichier
    mock_file = MagicMock()
    with patch("app.clients.data_prep_client.httpx.AsyncClient",
               return_value=mock_client), \
         patch("builtins.open", return_value=mock_file):
        result = await call_prepare(state)

    assert result.data_prep_job_id == "job_test_001"
    assert result.data_prep_status == DataPrepStatusEnum.WAITING_VALIDATION
    assert result.data_prep_quality["global"] == 0.85
    assert any("data_prep" in s for s in result.processing_steps)

@pytest.mark.asyncio
async def test_call_prepare_api_unavailable():
    """Teste que l'erreur de connexion est gérée proprement."""
    import httpx

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=None)

    state = make_state()

    mock_file = MagicMock()
    with patch("app.clients.data_prep_client.httpx.AsyncClient",
               return_value=mock_client), \
         patch("builtins.open", return_value=mock_file):
        result = await call_prepare(state)

    assert result.data_prep_status == DataPrepStatusEnum.FAILED
    assert result.data_prep_error is not None
    assert result.data_prep_error is not None
    assert len(result.data_prep_error) > 0

@pytest.mark.asyncio
async def test_call_get_data_profile():
    """Teste GET /profiling-json et la conversion vers data_profile."""

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "summary": {
            "dataset": {"total_rows": 500},
            "columns": {
                "flight_id":     {"type": "Numeric",  "missing_pct": 0},
                "delay_minutes": {"type": "Numeric",  "missing_pct": 2.5},
                "gate":          {"type": "Categorical", "missing_pct": 0},
            }
        }
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=None)

    state = make_state()
    state.data_prep_job_id  = "job_test_001"
    state.data_prep_quality = {"global": 0.85}

    with patch("app.clients.data_prep_client.httpx.AsyncClient",
               return_value=mock_client):
        result = await call_get_data_profile(state)

    assert result.data_profile["row_count"] == 500
    assert "flight_id"     in result.data_profile["columns"]
    assert "delay_minutes" in result.data_profile["numeric_columns"]
    assert "gate"          in result.data_profile["categorical_columns"]
    assert result.data_profile["missing_summary"]["delay_minutes"] == 2.5