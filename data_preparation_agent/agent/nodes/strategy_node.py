"""
agent/nodes/strategy_node.py
NODE 5 — Strategy (LLM)
─────────────────────────────
Appelle le LLM (GPT-4o-mini via OpenRouter) pour :

    1. Produire un résumé global en français compréhensible
       par un non-technicien

    2. Reformuler chaque anomalie détectée de façon claire
       et actionnable

Le LLM NE DÉCIDE PAS des actions — celles-ci sont déjà
proposées par anomaly_engine (3 choix par anomalie).
Le LLM sert uniquement à rendre le plan lisible pour l'user.

Après ce node, le graph s'interrompt (interrupt_before=["cleaning"])
et attend la validation humaine via POST /jobs/{id}/validate.
"""
from __future__ import annotations

import json
import logging

from agent.state import AgentState
from core.llm_client import LLMClient

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

    cleaning_plan = state["cleaning_plan"]

    # Construire le résumé des anomalies pour le LLM
    anomalies_summary = [
        {
            "id":       a.anomaly_id,
            "colonne":  a.column_name,
            "type":     a.anomaly_type.value,
            "probleme": a.problem_description,
            "lignes":   a.affected_count,
            "pct":      round(a.affected_pct, 1),
        }
        for a in cleaning_plan.anomalies
    ]

    user_prompt = (
        f"Secteur : {cleaning_plan.sector}\n"
        f"Nombre d'anomalies : {len(cleaning_plan.anomalies)}\n\n"
        f"Anomalies détectées :\n"
        f"{json.dumps(anomalies_summary, ensure_ascii=False, indent=2)}"
    )

    # Appel LLM
    client = LLMClient()
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
        # Fallback : utiliser les descriptions techniques par défaut
        logger.warning("LLM échoué, fallback sur descriptions par défaut : %s", e)
        llm_summary        = (
            f"Le dataset contient {len(cleaning_plan.anomalies)} anomalie(s) "
            f"à corriger avant utilisation."
        )
        llm_reformulations = {
            a.anomaly_id: a.problem_description
            for a in cleaning_plan.anomalies
        }

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