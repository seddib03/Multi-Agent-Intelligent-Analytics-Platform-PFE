# agent/nodes/cleaning_node.py

# Standard library
from __future__ import annotations

import logging
from datetime import datetime

# Local
from agent.state import AgentState, STATUS_FAILED
from core.cleaning_engine import CleaningEngine
from core.data_profiler import compute_profile, build_comparison_report


logger = logging.getLogger(__name__)


# ─── Node ────────────────────────────────────────────────────────────────────


def cleaning_node(state: AgentState) -> AgentState:
    """Node 2 — Data Cleaning.

    Orchestre le nettoyage complet du DataFrame brut
    en utilisant le CleaningEngine piloté par le action_plan.

    Stratégies appliquées par rôle :
        IDENTIFIER → drop null + drop doublons
        TEMPORAL   → parse dates + cohérence temporelle
        METRIC     → cast float + impute médiane + flag outliers
        DIMENSION  → cast string + trim + impute mode + check pattern

    Args:
        state: AgentState contenant raw_df et action_plan.

    Returns:
        AgentState mis à jour avec clean_df et cleaning_log enrichi.
        Status = FAILED si raw_df absent ou erreur inattendue.
    """
    logger.info(">>> NODE 2 : Data Cleaning — démarrage")

    # ── Vérification préalable ────────────────────────────────────────
    # raw_df doit avoir été rempli par ingestion_node
    if state.get("raw_df") is None:
        error_msg = (
            "Cleaning impossible : raw_df absent du state. "
            "Vérifier que ingestion_node s est exécuté correctement."
        )
        logger.error(error_msg)
        state["status"]  = STATUS_FAILED
        state["errors"].append(error_msg)
        return state

    if state.get("action_plan") is None:
        error_msg = (
            "Cleaning impossible : action_plan absent du state. "
            "Vérifier que le metadata a été parsé correctement."
        )
        logger.error(error_msg)
        state["status"]  = STATUS_FAILED
        state["errors"].append(error_msg)
        return state

    try:
        raw_df      = state["raw_df"]
        action_plan = state["action_plan"]

        rows_before = raw_df.height

        # ── Créer et exécuter le CleaningEngine ───────────────────────
        engine = CleaningEngine(raw_df, action_plan)
        engine.run()

        # Profil APRÈS cleaning
        logger.info("Calcul profil qualité APRÈS cleaning")
        profile_after = compute_profile(
            engine.clean_df,
            action_plan,
            label="APRÈS",
        )
        state["profile_after"] = profile_after

        # Rapport de comparaison AVANT vs APRÈS
        comparison = build_comparison_report(
            state["profile_before"],
            profile_after,
        )

        # Logger la comparaison clairement
        logger.info("=" * 60)
        logger.info("COMPARAISON QUALITÉ AVANT vs APRÈS CLEANING")
        logger.info("=" * 60)
        logger.info(
            "Lignes      : %d → %d (%d supprimées)",
            comparison["before"]["rows"],
            comparison["after"]["rows"],
            comparison["improvements"]["rows_dropped"],
        )
        logger.info(
            "Nulls       : %d → %d (%d corrigés)",
            comparison["before"]["nulls"],
            comparison["after"]["nulls"],
            comparison["improvements"]["nulls_fixed"],
        )
        logger.info(
            "Doublons    : %d → %d (%d supprimés)",
            comparison["before"]["duplicates"],
            comparison["after"]["duplicates"],
            comparison["improvements"]["duplicates_removed"],
        )
        logger.info(
            "Quality idx : %.1f → %.1f (gain : +%.1f)",
            comparison["before"]["quality_index"],
            comparison["after"]["quality_index"],
            comparison["improvements"]["quality_gain"],
        )
        logger.info("=" * 60)

        # Stocker la comparaison dans le cleaning_log
        state["cleaning_log"].append({
            "timestamp": datetime.now().isoformat(),
            "column":    "ALL",
            "role":      "quality_comparison",
            "operation": "before_after_comparison",
            "rows_affected": comparison["improvements"]["rows_dropped"],
            "detail":    (
                f"Quality index : "
                f"{comparison['before']['quality_index']} → "
                f"{comparison['after']['quality_index']} "
                f"(gain : +{comparison['improvements']['quality_gain']})"
            ),
        })

        rows_after  = engine.clean_df.height
        rows_dropped = rows_before - rows_after

        # ── Mettre à jour le state ────────────────────────────────────
        state["clean_df"] = engine.clean_df

        # Ajouter les opérations de cleaning au log existant
        state["cleaning_log"].extend(engine.cleaning_log)

        # Ajouter un résumé global du cleaning
        state["cleaning_log"].append({
            "timestamp":    datetime.now().isoformat(),
            "column":       "ALL",
            "role":         "summary",
            "operation":    "cleaning_completed",
            "rows_affected": rows_dropped,
            "detail": (
                f"Cleaning terminé — "
                f"{rows_before} lignes en entrée | "
                f"{rows_after} lignes en sortie | "
                f"{rows_dropped} lignes supprimées | "
                f"{len(engine.cleaning_log)} opérations effectuées"
            ),
        })

        logger.info(
            "NODE 2 terminé — %d → %d lignes (%d supprimées)",
            rows_before,
            rows_after,
            rows_dropped,
        )

    except Exception as error:
        logger.error("NODE 2 échoué : %s", error)
        state["status"] = STATUS_FAILED
        state["errors"].append(str(error))

    return state