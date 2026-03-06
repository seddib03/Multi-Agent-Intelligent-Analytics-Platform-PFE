"""
agent/nodes/dimension_node.py
──────────────────────────────
NODE 3 — LLM lit le metadata et mappe colonnes → dimensions qualité.

RÔLE :
    Le LLM reçoit le metadata de l'user (dans son format libre)
    + le résumé du profiling.
    Il retourne :
        - Le secteur confirmé
        - Quelles dimensions s'appliquent à chaque colonne
        - Les règles extraites du metadata (range, pattern, nullable...)

    CET APPEL LLM résout le problème du schema fixe de la V1 :
    l'user peut écrire son metadata dans n'importe quel format,
    le LLM comprend et standardise les règles.
"""

from __future__ import annotations

import logging

from agent.state import AgentState
from core.llm_client import LLMClient
from prompts.strategy_prompt import (
    DIMENSION_SYSTEM_PROMPT,
    build_dimension_user_prompt,
)

logger = logging.getLogger(__name__)


def dimension_node(state: AgentState) -> dict:
    """
    Utilise le LLM pour extraire les règles depuis le metadata flexible.

    Args:
        state: Doit contenir raw_metadata et profiling_report

    Returns:
        Dict avec sector, dimension_mapping, dimension_rules.
    """
    logger.info(">>> NODE 3 : Dimension mapping (LLM) — démarrage")

    raw_metadata    = state.get("raw_metadata", {})
    profiling_report = state.get("profiling_report")

    if profiling_report is None:
        error_msg = "profiling_report absent — profiling_node a-t-il réussi ?"
        logger.error(error_msg)
        return {"status": "error", "errors": [error_msg]}

    # Construire le prompt avec le résumé du profiling
    user_prompt = build_dimension_user_prompt(
        raw_metadata=raw_metadata,
        profiling_summary=profiling_report.build_llm_summary(),
    )

    # Appel LLM — on attend du JSON structuré
    client = LLMClient()
    result = client.call_structured(
        system_prompt=DIMENSION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # Extraire les champs de la réponse LLM
    # On utilise .get() avec des valeurs par défaut
    # pour éviter les KeyError si le LLM oublie un champ
    sector            = result.get("sector", state.get("sector", "unknown"))
    dimension_mapping = result.get("dimension_mapping", {})
    dimension_rules   = result.get("dimension_rules", {})

    logger.info(
        "NODE 3 terminé — secteur: %s | %d colonnes mappées",
        sector,
        len(dimension_mapping),
    )

    return {
        "sector":            sector,
        "dimension_mapping": dimension_mapping,
        "dimension_rules":   dimension_rules,
    }