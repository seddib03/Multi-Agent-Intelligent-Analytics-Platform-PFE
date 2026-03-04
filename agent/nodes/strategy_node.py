"""
agent/nodes/strategy_node.py
─────────────────────────────
NODE 4 — LLM propose le plan de nettoyage ligne par ligne.

RÔLE :
    C'est le cœur intelligent de la V2.
    Le LLM reçoit le rapport de profiling complet
    + le mapping des dimensions
    + les règles métier.

    Il propose un plan d'actions précis :
        - Quelle action sur quelle colonne
        - Sur quelles lignes exactement
        - Pourquoi cette action est proposée
        - Quel niveau de sévérité

    Après ce node, le graph s'interrompt pour
    attendre la validation de l'utilisateur.
"""

from __future__ import annotations

import logging
import uuid

from agent.state import AgentState
from core.llm_client import LLMClient
from models.cleaning_plan import ActionItem, CleaningAction, CleaningPlan
from prompts.strategy_prompt import (
    STRATEGY_SYSTEM_PROMPT,
    build_strategy_user_prompt,
)

logger = logging.getLogger(__name__)


def strategy_node(state: AgentState) -> dict:
    """
    Génère le plan de nettoyage via le LLM.

    Le plan est stocké dans le state avec status="proposed".
    Le graph s'interrompt ensuite (interrupt_before=["cleaning_node"])
    et attend que l'user valide via l'API.

    Args:
        state: Doit contenir profiling_report, dimension_mapping,
               dimension_rules, raw_metadata

    Returns:
        Dict avec cleaning_plan et llm_analysis.
    """
    logger.info(">>> NODE 4 : Strategy (LLM) — démarrage")

    profiling_report  = state.get("profiling_report")
    dimension_mapping = state.get("dimension_mapping", {})
    dimension_rules   = state.get("dimension_rules", {})
    raw_metadata      = state.get("raw_metadata", {})

    if profiling_report is None:
        error_msg = "profiling_report absent du state"
        logger.error(error_msg)
        return {"status": "error", "errors": [error_msg]}

    # Construire le prompt complet
    user_prompt = build_strategy_user_prompt(
        profiling_summary=profiling_report.build_llm_summary(),
        dimension_mapping=dimension_mapping,
        dimension_rules=dimension_rules,
        raw_metadata=raw_metadata,
    )

    # Appel LLM
    client = LLMClient()
    result = client.call_structured(
        system_prompt=STRATEGY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # Construire le CleaningPlan depuis la réponse LLM
    cleaning_plan = _build_cleaning_plan(
        llm_result=result,
        sector=state.get("sector", "unknown"),
        job_id=state.get("job_id", ""),
    )

    logger.info(
        "NODE 4 terminé — %d actions proposées | "
        "status: waiting_validation",
        len(cleaning_plan.actions),
    )

    return {
        "cleaning_plan":   cleaning_plan,
        "llm_analysis":    result.get("llm_analysis", ""),
        "status":          "waiting_validation",
    }


def _build_cleaning_plan(
    llm_result: dict,
    sector: str,
    job_id: str,
) -> CleaningPlan:
    """
    Convertit la réponse JSON du LLM en objet CleaningPlan typé.

    POURQUOI CETTE CONVERSION :
        Le LLM retourne un dict non typé.
        On veut un objet avec des types précis pour que
        cleaning_node puisse l'utiliser sans risque.

    Args:
        llm_result: Dict parsé depuis la réponse LLM
        sector:     Secteur du dataset
        job_id:     ID du job courant

    Returns:
        CleaningPlan avec les ActionItems typés.
    """
    actions = []

    for raw_action in llm_result.get("actions", []):
        # Valider que l'action proposée par le LLM
        # est dans notre liste d'actions reconnues
        action_name = raw_action.get("action", "")
        try:
            action_enum = CleaningAction(action_name)
        except ValueError:
            # Action inconnue → on la loggue et on l'ignore
            logger.warning(
                "Action LLM non reconnue : '%s' — ignorée",
                action_name,
            )
            continue

        actions.append(
            ActionItem(
                action_id=raw_action.get(
                    "action_id", f"action_{uuid.uuid4().hex[:6]}"
                ),
                colonne=raw_action.get("colonne", ""),
                lignes_concernees=raw_action.get("lignes_concernees", []),
                dimension=raw_action.get("dimension", ""),
                probleme=raw_action.get("probleme", ""),
                action=action_enum,
                justification=raw_action.get("justification", ""),
                severite=raw_action.get("severite", "MINOR"),
                parametre=raw_action.get("parametre", {}),
            )
        )

    return CleaningPlan(
        plan_id=f"plan_{job_id[:8]}",
        sector=sector,
        actions=actions,
        llm_analysis=llm_result.get("llm_analysis", ""),
        risques=llm_result.get("risques", []),
        status="proposed",
    )