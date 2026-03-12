from __future__ import annotations
import logging
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from agent.state import AgentState
from config.settings import get_settings
from agent.nodes.ingestion_node  import ingestion_node
from agent.nodes.profiling_node  import profiling_node
from agent.nodes.quality_node    import quality_node
from agent.nodes.anomaly_node    import anomaly_node
from agent.nodes.strategy_node   import strategy_node
from agent.nodes.cleaning_node   import cleaning_node
from agent.nodes.rescoring_node  import rescoring_node
from agent.nodes.delivery_node   import delivery_node

logger = logging.getLogger(__name__)

settings = get_settings()

# Création du pool de connexions PostgreSQL pour LangGraph
connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
}
# Si un schema spécifique est défini, l'ajouter au search_path
if settings.agent_schema:
    connection_kwargs["options"] = f"-c search_path={settings.agent_schema},public"

pool = ConnectionPool(
    conninfo=settings.database_url,
    max_size=20,
    kwargs=connection_kwargs,
)

checkpointer = PostgresSaver(pool)
# Auto-créer les tables nécessaires si elles n'existent pas
checkpointer.setup()


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