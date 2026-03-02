
# Standard library
from __future__ import annotations

import logging

# Local
from agent.state import AgentState, STATUS_FAILED, STATUS_WARNING
from core.dbt_generator import generate_dbt_artifacts
from core.dbt_runner import run_dbt_tests, save_clean_dataset
from core.quality_scorer import compute_quality_report
from core.data_profiler import build_comparison_report
from models.metadata_schema import DatasetMetadata


logger = logging.getLogger(__name__)


# ─── Node ────────────────────────────────────────────────────────────────────


def quality_node(state: AgentState) -> AgentState:
    """Node 3 — Data Quality Validation via dbt.

    Ordre d'exécution strict :
        1. Sauvegarder clean_df en Parquet → Silver
           (dbt a besoin du fichier AVANT de générer les artifacts)
        2. Générer les artifacts dbt depuis le metadata
        3. Exécuter dbt run + dbt test
        4. Calculer le quality score
        5. Mettre à jour le state

    Args:
        state: AgentState contenant clean_df et metadata.

    Returns:
        AgentState avec quality_score (toujours float) et
        quality_report remplis.
    """
    logger.info(">>> NODE 3 : Data Quality Validation — démarrage")

    # ── Vérifications préalables ──────────────────────────────────────
    if state.get("clean_df") is None:
        error_msg = (
            "Quality validation impossible : clean_df absent. "
            "Vérifier que cleaning_node s est exécuté correctement."
        )
        logger.error(error_msg)
        state["status"]        = STATUS_FAILED
        state["quality_score"] = 0.0
        state["errors"].append(error_msg)
        return state

    if state.get("metadata") is None:
        error_msg = "Quality validation impossible : metadata absent."
        logger.error(error_msg)
        state["status"]        = STATUS_FAILED
        state["quality_score"] = 0.0
        state["errors"].append(error_msg)
        return state

    try:
        clean_df    = state["clean_df"]
        action_plan = state["action_plan"]
        sector      = action_plan["sector"]
        metadata    = DatasetMetadata.model_validate(state["metadata"])

        rows_before = (
            state["raw_df"].height
            if state.get("raw_df") is not None
            else 0
        )
        rows_after = clean_df.height

        # ── Étape 1 : Sauvegarder Parquet → Silver ────────────────────
        # DOIT être fait avant generate_dbt_artifacts
        # car dbt lit ce fichier comme source
        logger.info(
            "Étape 1 — Sauvegarde Parquet Silver avant dbt"
        )
        silver_path = save_clean_dataset(clean_df, sector)
        state["silver_path"] = silver_path

        # ── Étape 2 : Générer les artifacts dbt ───────────────────────
        logger.info("Étape 2 — Génération artifacts dbt")
        dbt_artifacts = generate_dbt_artifacts(metadata, silver_path)

        logger.info(
            "%d tests dbt générés pour le secteur '%s'",
            len(dbt_artifacts["tests_generated"]),
            sector,
        )

        # ── Étape 3 : Exécuter dbt run + dbt test ─────────────────────
        logger.info("Étape 3 — Exécution dbt")
        test_results = run_dbt_tests(dbt_artifacts["model_name"])

        # ── Étape 4 : Calculer le quality score ───────────────────────
        logger.info("Étape 4 — Calcul quality score")
        quality_score, quality_report = compute_quality_report(
            test_results,
            sector,
            rows_before,
            rows_after,
        )
        if state.get("profile_before") and state.get("profile_after"):
            comparison = build_comparison_report(
                state["profile_before"],
                state["profile_after"],
            )
            quality_report["before_after_comparison"] = comparison

            logger.info(
                "Quality index AVANT : %.1f | APRÈS : %.1f | "
                "dbt score final : %.1f",
                comparison["before"]["quality_index"],
                comparison["after"]["quality_index"],
                quality_score,
            )

        # ── Étape 5 : Mettre à jour le state ──────────────────────────
        state["quality_score"]  = quality_score
        state["quality_report"] = quality_report

        decision = quality_report["summary"]["decision"]
        if decision == "WARNING":
            state["status"] = STATUS_WARNING

        logger.info(
            "NODE 3 terminé — score : %.1f | décision : %s",
            quality_score,
            decision,
        )

    except Exception as error:
        logger.error("NODE 3 échoué : %s", error)
        state["quality_score"]  = 0.0
        state["quality_report"] = _build_error_report(str(error))
        state["status"]         = STATUS_FAILED
        state["errors"].append(str(error))

    return state


# ─── Utilitaire privé ────────────────────────────────────────────────────────


def _build_error_report(error_message: str) -> dict:
    """Construit un rapport d'erreur minimal.

    Garantit que quality_report n'est jamais None
    même en cas d'erreur critique.

    Args:
        error_message: Message d'erreur à inclure dans le rapport.

    Returns:
        Rapport minimal structuré.
    """
    from datetime import datetime

    return {
        "summary": {
            "sector":        "unknown",
            "timestamp":     datetime.now().isoformat(),
            "quality_score": 0.0,
            "decision":      "FAILED",
            "total_tests":   0,
            "passed_tests":  0,
            "failed_tests":  0,
            "error":         error_message,
        },
        "passed": [],
        "failed": [],
    }