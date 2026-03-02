import logging
import os

from langgraph.graph import END, StateGraph

from agent.nodes.aggregation_node import aggregation_node
from agent.nodes.cleaning_node import cleaning_node
from agent.nodes.ingestion_node import ingestion_node
from agent.nodes.quality_node import quality_node
from agent.state import AgentState, STATUS_FAILED


logger = logging.getLogger(__name__)


# ─── Constante ───────────────────────────────────────────────────────────────

# Lire le seuil depuis .env, valeur par défaut 80 si non défini
QUALITY_THRESHOLD = float(os.getenv("QUALITY_SCORE_THRESHOLD", "80"))


# ─── Nodes spéciaux ──────────────────────────────────────────────────────────


def alert_node(state: AgentState) -> AgentState:
    """Node d'alerte — quality_score insuffisant.

    Args:
        state: AgentState contenant quality_score.

    Returns:
        AgentState avec status = FAILED.
    """
    score = state.get("quality_score", 0.0)

    # Correction : forcer float pour éviter TypeError avec None
    score_display = float(score) if score is not None else 0.0

    logger.warning(
        "Quality score insuffisant : %.1f < %.1f — pipeline arrêté",
        score_display,
        QUALITY_THRESHOLD,
    )

    state["status"] = STATUS_FAILED
    return state

# ─── Fonction de décision ────────────────────────────────────────────────────


def _decide_after_quality(state: AgentState) -> str:
    """Décide la prochaine étape après la validation qualité.

    Gère le cas où quality_score est None —
    peut arriver si quality_node échoue partiellement.

    Args:
        state: AgentState contenant quality_score.

    Returns:
        "continue" si qualité suffisante, "alert" sinon.
    """
    # Protection contre None — si score absent on alerte
    score = state.get("quality_score")

    if score is None:
        logger.warning(
            "quality_score absent du state → alerte Orchestrateur"
        )
        return "alert"

    if score >= QUALITY_THRESHOLD:
        logger.info(
            "Quality score OK : %.1f >= %.1f → continuation",
            score,
            QUALITY_THRESHOLD,
        )
        return "continue"

    logger.warning(
        "Quality score insuffisant : %.1f < %.1f → alerte",
        score,
        QUALITY_THRESHOLD,
    )
    return "alert"

# ─── Construction du graph ───────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Construit et compile le graph LangGraph du Data Preparation Agent.

    Structure du graph :
        ingestion → cleaning → quality → [décision]
                                              ↙        ↘
                                        aggregation   alert
                                              ↓          ↓
                                             END        END

    Returns:
        Graph LangGraph compilé, prêt à être invoqué.
    """
    # 1. Créer le workflow avec notre AgentState
    workflow = StateGraph(AgentState)

    # 2. Enregistrer tous les nodes
    # Syntaxe : add_node("nom_du_node", fonction_du_node)
    # Le "nom_du_node" est utilisé dans add_edge pour les connexions
    workflow.add_node("ingestion",   ingestion_node)
    workflow.add_node("cleaning",    cleaning_node)
    workflow.add_node("quality",     quality_node)
    workflow.add_node("aggregation", aggregation_node)
    workflow.add_node("alert",       alert_node)

    # 3. Définir le point d'entrée du graph
    workflow.set_entry_point("ingestion")

    # 4. Connecter les nodes séquentiellement
    # add_edge("source", "destination") = toujours aller vers destination
    workflow.add_edge("ingestion", "cleaning")
    workflow.add_edge("cleaning",  "quality")

    # 5. Conditional edge après quality
    # Syntaxe :
    #   add_conditional_edges(
    #       "node_source",
    #       fonction_qui_retourne_une_string,
    #       {"string_retournée": "node_destination"}
    #   )
    workflow.add_conditional_edges(
        "quality",
        _decide_after_quality,
        {
            "continue": "aggregation",
            "alert":    "alert",
        },
    )

    # 6. Les deux chemins mènent à END
    workflow.add_edge("aggregation", END)
    workflow.add_edge("alert",       END)

    # 7. Compiler — transforme le workflow en graph exécutable
    return workflow.compile()


# ─── Instance globale ────────────────────────────────────────────────────────

# Créée une seule fois au démarrage de l'application
# Toutes les requêtes FastAPI utilisent cette même instance
agent_graph = build_graph()
