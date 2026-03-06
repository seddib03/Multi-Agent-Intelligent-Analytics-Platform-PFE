from __future__ import annotations

import logging
from datetime import datetime

from agent.state import AgentState
from core.data_profiler import run_profiling
from core.df_serializer import dict_to_df
from core.llm_client import LLMClient
from models.quality_dimensions import (
    DimensionName,
    DimensionScore,
    QualityDimensionsReport,
)
from prompts.strategy_prompt import (
    EVALUATION_SYSTEM_PROMPT,
    build_evaluation_user_prompt,
)

logger = logging.getLogger(__name__)


def evaluation_node(state: AgentState) -> dict:
    """
    Évalue la qualité APRÈS cleaning et génère l'analyse LLM.

    Étapes :
        1. Profile le clean_df (snapshot APRÈS)
        2. Calcule les 5 dimensions sur le clean_df
        3. LLM compare AVANT/APRÈS et commente

    Args:
        state: Doit contenir clean_df, profiling_report (AVANT),
               cleaning_log, dbt_results

    Returns:
        Dict avec dimensions_after, profile_after, llm_evaluation.
    """
    logger.info(">>> NODE 6 : Evaluation — démarrage")

    clean_df_dict = state.get("clean_df")
    if clean_df_dict is None:
        return {"status": "error", "errors": ["clean_df absent du state"]}
    clean_df = dict_to_df(clean_df_dict)

    sector = state.get("sector", "unknown")

    # ── 1. Profile APRÈS ──────────────────────────────────────────────────────
    profile_after_report = run_profiling(clean_df)
    profile_after        = profile_after_report.to_dict()
    profile_after["label"] = "APRÈS"

    # ── 2. Calcul des 5 dimensions APRÈS ────────────────────────────────────
    dimension_rules = state.get("dimension_rules", {})
    dimensions_after = _compute_dimensions_after(
        profile_after_report,
        dimension_rules,
        sector,
    )

    # ── 3. LLM analyse les résultats ─────────────────────────────────────────
    profile_before   = state.get("profile_before", {})
    cleaning_log     = state.get("cleaning_log") or []
    dbt_results      = state.get("dbt_results") or []

    user_prompt = build_evaluation_user_prompt(
        dimensions_before=profile_before,
        dimensions_after=profile_after,
        cleaning_log=cleaning_log,
        dbt_results=dbt_results,
    )

    client = LLMClient()
    llm_result = client.call_structured(
        system_prompt=EVALUATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    llm_evaluation = llm_result.get("resume_executif", "")

    logger.info(
        "NODE 6 terminé — score global AVANT: %.1f → APRÈS: %.1f "
        "(gain: +%.1f)",
        _get_global_before(profile_before),
        dimensions_after.global_score,
        dimensions_after.global_score - _get_global_before(profile_before),
    )

    return {
        "dimensions_after": dimensions_after,
        "profile_after":    profile_after,
        "llm_evaluation":   llm_evaluation,
    }


def _compute_dimensions_after(
    profile_report,
    dimension_rules: dict,
    sector: str,
) -> QualityDimensionsReport:
    """
    Calcule les scores des 5 dimensions sur le dataset nettoyé.

    Logique simplifiée basée sur les anomalies restantes
    dans le profiling_report du clean_df.

    Args:
        profile_report: ProfilingReport du clean_df
        dimension_rules: Règles de qualité par colonne
        sector: Secteur du dataset

    Returns:
        QualityDimensionsReport avec les 5 scores calculés.
    """
    total_rows = profile_report.total_rows
    by_type    = profile_report.anomalies_by_type

    # COMPLETENESS : basé sur les nulls restants
    null_count      = len(by_type.get("null", []))
    total_cells     = total_rows * profile_report.total_columns
    completeness_score = max(0.0, 100.0 - (null_count / max(1, total_cells) * 100 * 5))

    # UNIQUENESS : basé sur les doublons restants
    dup_count       = len(by_type.get("duplicate", []))
    uniqueness_score = max(0.0, 100.0 - (dup_count / max(1, total_rows) * 100))

    # VALIDITY : basé sur les violations de type restantes
    type_errors      = len(by_type.get("type_error", []))
    validity_score   = max(0.0, 100.0 - (type_errors / max(1, total_rows) * 100 * 3))

    # CONSISTENCY : basé sur les incohérences restantes
    inconsistencies  = len(by_type.get("inconsistency", []))
    consistency_score = max(0.0, 100.0 - (inconsistencies / max(1, total_rows) * 100 * 2))

    # ACCURACY : basé sur les outliers restants (flaggés, non supprimés)
    outliers        = len(by_type.get("outlier", []))
    accuracy_score  = max(0.0, 100.0 - (outliers / max(1, total_rows) * 100))

    def make_score(name, score, anomalies_list):
        failed = len(anomalies_list)
        total  = max(failed, total_rows)
        return DimensionScore(
            name=name,
            score=round(min(100.0, score), 1),
            total_checks=total,
            passed_checks=total - failed,
            failed_checks=failed,
            affected_rows={a.ligne: a.description for a in anomalies_list},
        )

    return QualityDimensionsReport(
        completeness=make_score(
            DimensionName.COMPLETENESS, completeness_score,
            by_type.get("null", [])
        ),
        uniqueness=make_score(
            DimensionName.UNIQUENESS, uniqueness_score,
            by_type.get("duplicate", [])
        ),
        validity=make_score(
            DimensionName.VALIDITY, validity_score,
            by_type.get("type_error", [])
        ),
        consistency=make_score(
            DimensionName.CONSISTENCY, consistency_score,
            by_type.get("inconsistency", [])
        ),
        accuracy=make_score(
            DimensionName.ACCURACY, accuracy_score,
            by_type.get("outlier", [])
        ),
        sector=sector,
        timestamp=datetime.now().isoformat(),
        label="APRÈS",
    )


def _get_global_before(profile_before: dict) -> float:
    """Extrait le score global du snapshot AVANT pour le log."""
    try:
        return profile_before.get("global", {}).get("null_pct", 0.0)
    except Exception:
        return 0.0