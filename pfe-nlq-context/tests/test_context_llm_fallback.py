from app.context.context_service import ContextService
from app.nlq.schemas import NLQOutput
from app.core.config import settings

class MockLLM:
    def generate_pydantic(self, **kwargs):
        # Simule exactement la sortie attendue par ContextOutput
        return {
            "intent": "analyze",
            "sector": "retail",
            "canonical_metric": "total_sales_amount",
            "execution_type": "sql",
            "data_source": {
                "database": "retail_db",
                "table": "transactions",
                "columns_allowed": ["total_sales_amount"]
            },
            "model_hint": None,
            "filters": {},
            "schema_version": settings.schema_version,
            "confidence": 0.75
        }

def test_context_llm_fallback_called():
    service = ContextService(MockLLM())

    nlq = NLQOutput(
        raw_question="Show revenue in 2023 in Casablanca",
        intent="analyze",
        metric="revenueZZZ_unknown",  # <- force no match deterministic
        timeframe="2023",
        location="Casablanca",
        filters={},
        confidence=0.8
    )

    ctx = service.enrich(nlq)

    assert ctx.sector == "retail"
    assert ctx.canonical_metric == "total_sales_amount"
    assert ctx.execution_type == "sql"
    assert ctx.schema_version == settings.schema_version