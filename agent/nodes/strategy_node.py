from __future__ import annotations

import json
import logging

from agent.state import AgentState
from core.llm_client import LLMClient
from prompts.anomaly_impact_prompt import (
    ANOMALY_IMPACT_SYSTEM_PROMPT,
    build_anomaly_impact_user_prompt,
)

logger = logging.getLogger(__name__)

STRATEGY_SYSTEM_PROMPT = """Tu es un expert Data Quality Engineer.
Tu reçois un rapport d'anomalies détectées dans un dataset.

Tu dois :
1. Écrire un résumé global clair en français (2-4 phrases maximum)
   destiné à un utilisateur non-technicien.
   Explique ce qui ne va pas et pourquoi c'est important.

2. Pour chaque anomalie, écrire une reformulation courte et compréhensible
   en 1-2 phrases. Évite le jargon technique.

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après :
{
  "resume_global": "...",
  "reformulations": {
    "<anomaly_id>": "Explication claire de l'anomalie en 1-2 phrases"
  }
}"""


def strategy_node(state: AgentState) -> dict:
    logger.info(">>> NODE 5 : Strategy LLM — démarrage")

    cleaning_plan    = state["cleaning_plan"]
    profiling_summary = state.get("profiling_summary")

    # Construire le résumé des anomalies pour le LLM
    anomalies_summary = [
        {
            "id":       a.anomaly_id,
            "colonne":  a.column_name,
            "type":     a.anomaly_type.value,
            "probleme": a.problem_description,
            "lignes":   a.affected_count,
            "pct":      round(a.affected_pct, 1),
            "actions":  {
                "action_1": a.action_1.value,
                "action_2": a.action_2.value,
                "action_3": a.action_3.value,
            },
        }
        for a in cleaning_plan.anomalies
    ]

    user_prompt = (
        f"Secteur : {cleaning_plan.sector}\n"
        f"Nombre d'anomalies : {len(cleaning_plan.anomalies)}\n\n"
        f"Anomalies détectées :\n"
        f"{json.dumps(anomalies_summary, ensure_ascii=False, indent=2)}"
    )

    client = LLMClient()

    # ── Appel 1 : résumé global + reformulations ──────────────────────────
    try:
        result             = client.call_structured(STRATEGY_SYSTEM_PROMPT, user_prompt)
        llm_summary        = result.get("resume_global", "")
        llm_reformulations = result.get("reformulations", {})
        logger.info(
            "LLM réponse reçue — résumé: %d chars | %d reformulations",
            len(llm_summary),
            len(llm_reformulations),
        )
    except Exception as e:
        logger.warning("LLM échoué, fallback sur descriptions par défaut : %s", e)
        llm_summary        = (
            f"Le dataset contient {len(cleaning_plan.anomalies)} anomalie(s) "
            f"à corriger avant utilisation."
        )
        llm_reformulations = {
            a.anomaly_id: a.problem_description
            for a in cleaning_plan.anomalies
        }

    # ── Appel 2 : impact + action recommandée par anomalie ─────────────────
    if cleaning_plan.anomalies:
        if not profiling_summary or not profiling_summary.get("columns"):
            logger.warning(
                "⚠ profiling_summary est VIDE — le LLM n'aura pas les stats "
                "de profiling pour contextualiser l'impact. Vérifiez NODE 2."
            )
        try:
            impact_prompt = build_anomaly_impact_user_prompt(
                anomalies_summary=anomalies_summary,
                profiling_summary=profiling_summary,
                sector=cleaning_plan.sector,
            )
            impact_result = client.call_structured(ANOMALY_IMPACT_SYSTEM_PROMPT, impact_prompt)

            # Injecter impact + recommandation dans chaque AnomalyItem
            enriched = 0
            for anomaly in cleaning_plan.anomalies:
                enrichment = impact_result.get(anomaly.anomaly_id, {})
                if enrichment:
                    anomaly.impact_1           = enrichment.get("action_1_impact")
                    anomaly.impact_2           = enrichment.get("action_2_impact")
                    anomaly.impact_3           = enrichment.get("action_3_impact")
                    anomaly.recommended_action = enrichment.get("recommended_action")
                    anomaly.recommended_reason = enrichment.get("recommended_reason")
                    enriched += 1

            logger.info("Impact LLM généré pour %d/%d anomalies", enriched, len(cleaning_plan.anomalies))

        except Exception as e:
            logger.warning("LLM impact échoué — anomalies sans enrichissement : %s", e)

    # Injecter les reformulations dans le plan
    cleaning_plan.llm_summary        = llm_summary
    cleaning_plan.llm_reformulations = llm_reformulations

    logger.info("NODE 5 terminé — plan prêt pour validation humaine")
    return {
        "cleaning_plan":     cleaning_plan,
        "llm_summary":        llm_summary,
        "llm_reformulations": llm_reformulations,
        "status":             "waiting_validation",
    }
