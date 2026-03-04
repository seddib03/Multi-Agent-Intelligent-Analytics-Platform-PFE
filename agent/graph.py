"""
agent/graph.py
───────────────
Définition du graph LangGraph V2 avec Human-in-the-Loop.

FLUX DU GRAPH :
    ingestion → profiling → dimension(LLM) → strategy(LLM)
        ↓
    [PAUSE — attendre validation user]
        ↓
    cleaning → evaluation(LLM) → delivery

HUMAN-IN-THE-LOOP :
    LangGraph supporte nativement l'interruption du pipeline.
    On utilise interrupt_before=["cleaning_node"] :
    → Le graph s'arrête AVANT cleaning_node
    → L'état est sauvegardé dans le checkpointer (mémoire)
    → L'API retourne le plan à l'user
    → L'user valide via POST /prepare/{job_id}/validate
    → On reprend le graph avec l'état mis à jour

CHECKPOINTER :
    MemorySaver sauvegarde l'état en RAM.
    Pour la production, utiliser SqliteSaver ou RedisSaver
    pour persister entre les redémarrages.
"""

from __future__ import annotations

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agent.nodes.cleaning_node import cleaning_node
from agent.nodes.delivery_node import delivery_node
from agent.nodes.dimension_node import dimension_node
from agent.nodes.evaluation_node import evaluation_node
from agent.nodes.ingestion_node import ingestion_node
from agent.nodes.profiling_node import profiling_node
from agent.nodes.strategy_node import strategy_node
from agent.state import AgentState

logger = logging.getLogger(__name__)

# ── Checkpointer ──────────────────────────────────────────────────────────────
# Sauvegarde l'état entre les 2 appels API :
#   Appel 1 : POST /prepare → state sauvegardé avant cleaning
#   Appel 2 : POST /validate → state repris et pipeline continué
checkpointer = MemorySaver()


def _decide_after_strategy(state: AgentState) -> str:
    """
    Décision après strategy_node.

    Si le plan a été proposé → on attend la validation humaine
    (le graph s'interrompt avant cleaning_node grâce à
    interrupt_before dans compile()).

    Si une erreur s'est produite → on arrête le pipeline.

    Args:
        state: État courant

    Returns:
        "wait" si le plan est proposé
        "error" si une erreur technique s'est produite
    """
    status = state.get("status", "")

    if status == "error":
        logger.error(
            "Erreur détectée après strategy_node — arrêt pipeline"
        )
        return "error"

    # Plan proposé — on continue vers cleaning
    # (LangGraph s'interrompra avant cleaning_node
    # grâce à interrupt_before)
    return "continue"


def _decide_after_evaluation(state: AgentState) -> str:
    """
    Décision après evaluation_node.

    Compare le score global APRÈS cleaning avec le seuil.
    Si score suffisant → delivery
    Si score insuffisant → on livre quand même mais avec WARNING

    NOTE : En V2, on livre toujours car l'user a validé le plan.
    Le score sert d'information dans le rapport final.

    Args:
        state: État courant

    Returns:
        "deliver" dans tous les cas (l'user a validé)
    """
    dimensions_after = state.get("dimensions_after")

    if dimensions_after:
        score = dimensions_after.global_score
        logger.info("Score global après cleaning : %.1f", score)

    # En V2 : on livre toujours car l'user a pris la décision
    return "deliver"


def build_graph():
    """
    Construit et compile le graph LangGraph V2.

    STRUCTURE :
        StateGraph(AgentState) → définit que chaque node
        reçoit et retourne un AgentState.

        add_node()  → enregistre une fonction comme node
        add_edge()  → connexion inconditionnelle
        add_conditional_edges() → connexion avec décision

    Returns:
        Graph compilé avec checkpointer et interrupt_before.
    """
    workflow = StateGraph(AgentState)

    # ── Enregistrement des nodes ──────────────────────────────────────────────
    workflow.add_node("ingestion",   ingestion_node)
    workflow.add_node("profiling",   profiling_node)
    workflow.add_node("dimension",   dimension_node)
    workflow.add_node("strategy",    strategy_node)
    workflow.add_node("cleaning",    cleaning_node)
    workflow.add_node("evaluation",  evaluation_node)
    workflow.add_node("delivery",    delivery_node)

    # ── Connexions séquentielles ──────────────────────────────────────────────
    # Point d'entrée du graph
    workflow.set_entry_point("ingestion")

    # Séquence linéaire jusqu'à strategy
    workflow.add_edge("ingestion", "profiling")
    workflow.add_edge("profiling", "dimension")
    workflow.add_edge("dimension", "strategy")

    # Décision après strategy
    # (normalement toujours "continue" — l'erreur arrête le graph)
    workflow.add_conditional_edges(
        "strategy",
        _decide_after_strategy,
        {
            "continue": "cleaning",
            "error":    END,
        },
    )

    # Après cleaning → évaluation
    workflow.add_edge("cleaning", "evaluation")

    # Décision après évaluation
    workflow.add_conditional_edges(
        "evaluation",
        _decide_after_evaluation,
        {
            "deliver": "delivery",
        },
    )

    # Delivery → fin du pipeline
    workflow.add_edge("delivery", END)

    # ── Compilation avec Human-in-the-Loop ────────────────────────────────────
    # interrupt_before=["cleaning"] :
    #   Le graph s'arrête AVANT d'exécuter cleaning_node
    #   L'état est sauvegardé dans le checkpointer
    #   On peut reprendre avec graph.invoke() sur le même thread_id
    compiled_graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["cleaning"],
    )

    logger.info(
        "Graph V2 compilé — nodes: %s | interrupt_before: cleaning",
        ["ingestion", "profiling", "dimension", "strategy",
         "cleaning", "evaluation", "delivery"],
    )

    return compiled_graph


# Instance unique du graph — partagée par tous les appels API
# (thread-safe avec LangGraph)
agent_graph = build_graph()