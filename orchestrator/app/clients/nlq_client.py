import httpx
from app.graph.state import OrchestratorState, SectorEnum, IntentEnum, RouteEnum, ExecutionTypeEnum 

NLQ_API_URL = "http://127.0.0.1:8000"  # Update with actual URL

async def call_nlq_and_context(state: OrchestratorState) -> OrchestratorState:
    """
    Calls the NLQ Agent with the current state and updates the state with the response.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: Call NLQ Agent
        nlq_response = await client.post(f"{NLQ_API_URL}/nlq", json={"query": state.query_raw})
        nlq_data = nlq_response.json()

        #Step 2: Call Context Agent with NLQ results
        ctx_response = await client.post(f"{NLQ_API_URL}/context", json=nlq_data)
        ctx_data = ctx_response.json()
        # Update state with Context Agent results
        state.intent= IntentEnum(nlq_data.get("intent", "unknown"))
        state.intent_confidence = nlq_data.get("intent_confidence", 0.0)
        state.metric_raw = nlq_data.get("metric_raw", "")
        state.timeframe = nlq_data.get("timeframe", "")
        state.location = nlq_data.get("location", "")

        state.sector = SectorEnum(ctx_data.get("sector", "unknown").capitalize())
        state.sector_confidence = ctx_data.get("sector_confidence", 0.0)
        state.canonical_metrics = ctx_data.get("canonical_metrics", "")
        state.execution_type = ExecutionTypeEnum(ctx_data.get("execution_type", "unknown"))
        state.data_source = ctx_data.get("data_source", {})

        state.processing_steps.append(
            f"nlq_client -> intent: {state.intent.value}, sector: {state.sector.value}, execution_type: {state.execution_type.value}"
            )
        return state    
    