from langgraph.graph import StateGraph, END
from app.graph.state import OrchestratorState, RouteEnum
from app.graph.nodes.sector_detection import sector_detection_node
from app.graph.nodes.nlq_node import nlq_node
from app.graph.nodes.routing_node import routing_node
from app.graph.nodes.dispatch_node import dispatch_node
from app.graph.nodes.response_node import response_node

def build_orchestrator_graph():
    """
    Builds and compiles the LangGraph orchestrator graph.
    """
    graph = StateGraph(dict)  # Using dict for LangGraph compatibility

    # add nodes

    graph.add_node("sector_detection", _wrap(sector_detection_node))
    graph.add_node("nlq",              _wrap(nlq_node))
    graph.add_node("routing",          _wrap(routing_node))
    graph.add_node("dispatch",         _wrap(dispatch_node))
    graph.add_node("response",         _wrap(response_node))

    # Define entry point and edges
    graph.set_entry_point("sector_detection")
    # Sequential edges

    graph.add_edge("sector_detection", "nlq")
    graph.add_edge("nlq",              "routing")
    graph.add_edge("dispatch",         "response")
    graph.add_edge("response",         END)

    # Conditional edge after routing
    # If clarification is needed, route to clarification node instead of dispatch
    # Otherwise, proceed to dispatch
    graph.add_conditional_edges(
        "routing",
        _should_dispatch,
        {
            "dispatch":  "dispatch",
            "response":  "response",
        }
    )

    return graph.compile()
def _should_dispatch(state: dict) -> str:
    """
    Condition: should the request be dispatched to an agent
    or go directly to the response node (clarification)?
    """
    route = state.get("route")
    if route == RouteEnum.CLARIFICATION.value:
        # Prepare clarification message in the state
        state["needs_clarification"] = True
        state["final_response"] = (
            "I could not confidently identify your request. "
            "Could you please specify the sector? "
            "(Transport, Finance, Retail, Manufacturing, Public)"
        )
        return "response"
    return "dispatch"

def _wrap(node_fn):
    """
    Adapter between the LangGraph dict state
    and our Pydantic OrchestratorState.
    """
    def wrapped(state: dict) -> dict:
        s = OrchestratorState(**state)
        result = node_fn(s)
        return result.model_dump()
    return wrapped