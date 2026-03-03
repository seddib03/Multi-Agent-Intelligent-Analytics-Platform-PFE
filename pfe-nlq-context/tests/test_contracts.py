from app.nlq.schemas import NLQOutput
from app.context.schemas import ContextOutput

def test_nlq_contract():
    obj = NLQOutput(
        raw_question="Total sales in 2023 in Casablanca",
        intent="analyze",
        metric="sales",
        timeframe="2023",
        location="Casablanca",
        filters={"year": 2023},
        confidence=0.85
    )
    assert obj.intent == "analyze"

def test_context_contract():
    obj = ContextOutput(
        intent="analyze",
        sector="retail",
        canonical_metric="total_sales_amount",
        execution_type="sql",
        data_source={"database": "retail_db", "table": "transactions", "columns_allowed": ["total_sales_amount"]},
        model_hint=None,
        filters={"year": 2023},
        schema_version="0.1",
        confidence=0.8
    )
    assert obj.sector == "retail"