from app.graph.orchestrator import build_orchestrator_graph
from app.graph.state import OrchestratorState
from app.schemas.input_schema import UserQueryInput
from app.schemas.output_schema import OrchestratorResponse
import uuid


# Compile the graph once at startup
orchestrator = build_orchestrator_graph()


def run_orchestrator(user_input: UserQueryInput) -> OrchestratorResponse:
    """
    Main entry point for the orchestrator.
    """
    # Initialize the state
    initial_state = OrchestratorState(
        user_id=user_input.user_id,
        session_id=user_input.session_id,
        query_raw=user_input.query,
    ).model_dump()

    # Run the graph
    final_state = orchestrator.invoke(initial_state)

    # Build the response
    return OrchestratorResponse(
        user_id=final_state["user_id"],
        session_id=final_state["session_id"],
        query_raw=final_state["query_raw"],
        response=final_state["final_response"],
        response_format=final_state["response_format"],
        route_taken=final_state.get("route"),
        route_reason=final_state.get("route_reason", ""),
        sector_detected=final_state.get("sector", ""),
        intent_detected=final_state.get("intent", ""),
        needs_clarification=final_state.get("needs_clarification", False),
        clarification_question=final_state.get("clarification_question", ""),
        data_payload=final_state.get("agent_response", {}).get("data_payload", {}),
    )


if __name__ == "__main__":
    #  Quick tests to validate Sprint 1 
    test_queries = [
        ("Show me transport KPIs for the month",     "Transport + KPI"),
        ("Revenue forecast Q2",        "Finance + Prediction"),
        ("Compare performance across sectors",   "Cross-sector + Dashboard"),
        ("blabla incomprehensible request xyz",       "Clarification"),
        ("Global summary dashboard",           "Insight Agent"),
    ]

    print("\n" + " "*20)
    print("   DEMO SPRINT 1 — MULTI-AGENT ORCHESTRATOR")
    print(" "*20 + "\n")

    for query, label in test_queries:
        print(f"\n{'─'*60}")
        print(f" TEST: {label}")
        print(f"{'─'*60}")

        result = run_orchestrator(UserQueryInput(
            user_id="u_demo",
            session_id=str(uuid.uuid4()),
            query=query
        ))

        print(f" Response     : {result.response}")
        print(f" Route        : {result.route_taken}")
        print(f" Reason       : {result.route_reason}")
        print(f" Sector       : {result.sector_detected}")
        print(f" Intent       : {result.intent_detected}")
        if result.data_payload:
            print(f" Data payload : {result.data_payload}")