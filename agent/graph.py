from __future__ import annotations
import logging
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from agent.state import AgentState
from agent.nodes.ingestion_node  import ingestion_node
from agent.nodes.profiling_node  import profiling_node
from agent.nodes.quality_node    import quality_node
from agent.nodes.anomaly_node    import anomaly_node
from agent.nodes.strategy_node   import strategy_node
from agent.nodes.cleaning_node   import cleaning_node
from agent.nodes.rescoring_node  import rescoring_node
from agent.nodes.delivery_node   import delivery_node

logger = logging.getLogger(__name__)

checkpointer = MemorySaver()

def build_graph():
    wf = StateGraph(AgentState)

    wf.add_node("ingestion",  ingestion_node)
    wf.add_node("profiling",  profiling_node)
    wf.add_node("quality",    quality_node)
    wf.add_node("anomaly",    anomaly_node)
    wf.add_node("strategy",   strategy_node)
    wf.add_node("cleaning",   cleaning_node)
    wf.add_node("rescoring",  rescoring_node)
    wf.add_node("delivery",   delivery_node)

    wf.set_entry_point("ingestion")
    wf.add_edge("ingestion", "profiling")
    wf.add_edge("profiling", "quality")
    wf.add_edge("quality",   "anomaly")
    wf.add_edge("anomaly",   "strategy")

    # ── PAUSE ICI — human-in-the-loop ──────────────────────────────────────
    # Le graph s'interrompt AVANT cleaning et attend la validation user
    wf.add_edge("strategy",  "cleaning")
    wf.add_edge("cleaning",  "rescoring")
    wf.add_edge("rescoring", "delivery")
    wf.add_edge("delivery",  END)

    return wf.compile(
        checkpointer=checkpointer,
        interrupt_before=["cleaning"],
    )

agent_graph = build_graph()