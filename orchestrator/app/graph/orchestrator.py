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
    # ✅ FIX : On utilise OrchestratorState directement comme schéma
    # au lieu de `dict` pour éviter le InvalidUpdateError sur __root__
    graph = StateGraph(OrchestratorState)

    # ── Nodes ──────────────────────────────────────────────────────
    graph.add_node("sector_detection", sector_detection_node)
    graph.add_node("nlq",              nlq_node)
    graph.add_node("data_prep",        data_prep_node)
    graph.add_node("routing",          routing_node)
    graph.add_node("dispatch",         dispatch_node)
    graph.add_node("response",         response_node)

    # ── Entry point ────────────────────────────────────────────────
    graph.set_entry_point("sector_detection")

    # ── Edges fixes ────────────────────────────────────────────────
    graph.add_edge("sector_detection", "nlq")
    graph.add_edge("nlq",              "data_prep")
    graph.add_edge("data_prep",        "routing")
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


def _should_dispatch(state: OrchestratorState) -> str:
    route = state.route
    if route == RouteEnum.CLARIFICATION.value:
        return "response"
    return "dispatch"