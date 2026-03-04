from app.context.context_service import ContextService
from app.nlq.schemas import NLQOutput

class DummyLLM:
    # Should NOT be called in deterministic path
    def generate_pydantic(self, **kwargs):
        raise AssertionError("LLM should not be called for deterministic path")

def test_context_deterministic_no_llm():
    service = ContextService(DummyLLM())

    nlq = NLQOutput(
        raw_question="Total sales in 2023 in Casablanca",
        intent="analyze",
        metric="sales",
        timeframe="2023",
        location="Casablanca",
        filters={},
        confidence=0.8
    )

    ctx = service.enrich(nlq)

    assert ctx.sector == "retail"
    assert ctx.canonical_metric == "total_sales_amount"
    assert ctx.execution_type == "sql"
    assert ctx.data_source is not None
    assert ctx.data_source["database"] == "retail_db"