from langgraph.graph import StateGraph, END
from app.graph.state import OrchestratorState, RouteEnum
from app.graph.nodes.sector_detection import sector_detection_node
from app.graph.nodes.nlq_node import nlq_node
from app.graph.nodes.routing_node import routing_node
from app.graph.nodes.dispatch_node import dispatch_node
from app.graph.nodes.response_node import response_node
from app.graph.nodes.data_prep_node import data_prep_node


def build_orchestrator_graph():
    """
    Pipeline :
    sector_detection → nlq → data_prep → routing → dispatch → response → END
                                                  ↘ (clarification) → response
    """
    graph =StateGraph(OrchestratorState) #StateGraph(dict)

    

    # ── Nodes ──────────────────────────────────────────────────────
    graph.add_node("sector_detection", _wrap(sector_detection_node))
    graph.add_node("nlq",              _wrap(nlq_node))
    graph.add_node("data_prep",        _wrap(data_prep_node))
    graph.add_node("routing",          _wrap(routing_node))
    graph.add_node("dispatch",         _wrap(dispatch_node))
    graph.add_node("response",         _wrap(response_node))

    # ── Entry point ────────────────────────────────────────────────
    graph.set_entry_point("sector_detection")

    # ── Edges fixes ────────────────────────────────────────────────
    graph.add_edge("sector_detection", "nlq")
    graph.add_edge("nlq",              "data_prep")
    graph.add_edge("data_prep",        "routing")
    # ⚠️ Pas de add_edge depuis "routing" — géré par le conditionnel
    graph.add_edge("dispatch",         "response")
    graph.add_edge("response",         END)

    # ── Edge conditionnel depuis routing ───────────────────────────
    graph.add_conditional_edges(
        "routing",
        _should_dispatch,
        {
            "dispatch": "dispatch",
            "response": "response",
        }
    )

    return graph.compile()


def _should_dispatch(state: dict) -> str:
    route = state.get("route")
    if route == RouteEnum.CLARIFICATION.value:
        return "response"
    return "dispatch"


def _wrap(node_fn):
    def wrapped(state: dict) -> dict:
        s = OrchestratorState(**state)
        result = node_fn(s)
        return result.model_dump()
    return wrapped