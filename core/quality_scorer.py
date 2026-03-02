# core/quality_scorer.py

# Standard library
from __future__ import annotations

import logging
from datetime import datetime


logger = logging.getLogger(__name__)


# ─── Poids des tests ─────────────────────────────────────────────────────────

TEST_WEIGHTS = {
    "not_null":           3,
    "unique":             3,
    "accepted_range":     2,
    "regex_match":        2,
    "date_not_in_future": 1,
}

DEFAULT_WEIGHT = 1


# ─── Fonction publique principale ────────────────────────────────────────────


def compute_quality_report(
    test_results: list[dict],
    sector: str,
    rows_before: int,
    rows_after: int,
) -> tuple[float, dict]:
    """Calcule le quality score et construit le rapport complet.

    Le score est pondéré par criticité :
        Tests critiques (not_null, unique)    → poids 3
        Tests importants (range, pattern)     → poids 2
        Tests mineurs (date_not_in_future)    → poids 1

    Args:
        test_results: Liste des résultats dbt parsés par dbt_runner.
        sector:       Secteur du dataset.
        rows_before:  Nombre de lignes avant cleaning.
        rows_after:   Nombre de lignes après cleaning.

    Returns:
        Tuple :
            - quality_score (float) : score entre 0 et 100
            - quality_report (dict) : rapport complet structuré
    """
    if not test_results:
        logger.warning(
            "Aucun résultat dbt — quality score par défaut : 100"
        )
        return 100.0, _build_empty_report(sector)

    # Calculer le score pondéré
    quality_score = _calculate_weighted_score(test_results)

    # Construire le rapport structuré
    quality_report = _build_quality_report(
        test_results,
        quality_score,
        sector,
        rows_before,
        rows_after,
    )

    # Logger un résumé lisible
    _log_quality_summary(quality_report)

    return quality_score, quality_report


# ─── Fonctions privées ───────────────────────────────────────────────────────


def _calculate_weighted_score(test_results: list[dict]) -> float:
    """Calcule le score de qualité pondéré.

    Formule :
        score = (somme poids tests passés / somme poids totaux) × 100

    Args:
        test_results: Résultats dbt avec status pass/fail.

    Returns:
        Score entre 0.0 et 100.0, arrondi à 1 décimale.
    """
    total_weight  = 0
    earned_weight = 0

    for result in test_results:
        test_name = result.get("test_name", "")
        weight    = TEST_WEIGHTS.get(test_name, DEFAULT_WEIGHT)

        total_weight += weight

        if result.get("status") == "pass":
            earned_weight += weight

    if total_weight == 0:
        return 100.0

    score = (earned_weight / total_weight) * 100
    return round(score, 1)


def _build_quality_report(
    test_results: list[dict],
    quality_score: float,
    sector: str,
    rows_before: int,
    rows_after: int,
) -> dict:
    """Construit le rapport de qualité complet et structuré.

    Args:
        test_results:  Résultats dbt.
        quality_score: Score calculé.
        sector:        Secteur du dataset.
        rows_before:   Lignes avant cleaning.
        rows_after:    Lignes après cleaning.

    Returns:
        Rapport structuré avec summary, passed, failed, details.
    """
    passed_tests = [t for t in test_results if t["status"] == "pass"]
    failed_tests = [t for t in test_results if t["status"] == "fail"]

    return {
        # ── Résumé global ─────────────────────────────────────────────
        "summary": {
            "sector":         sector,
            "timestamp":      datetime.now().isoformat(),
            "quality_score":  quality_score,
            "decision":       _get_decision(quality_score),
            "total_tests":    len(test_results),
            "passed_tests":   len(passed_tests),
            "failed_tests":   len(failed_tests),
            "rows_before_cleaning": rows_before,
            "rows_after_cleaning":  rows_after,
            "rows_dropped":         rows_before - rows_after,
        },
        # ── Détail des tests passés ───────────────────────────────────
        "passed": [
            {
                "test":    t["test_name"],
                "column":  t["column"],
                "status":  "pass",
            }
            for t in passed_tests
        ],
        # ── Détail des tests échoués ──────────────────────────────────
        "failed": [
            {
                "test":     t["test_name"],
                "column":   t["column"],
                "status":   "fail",
                "failures": t["failures"],
                "message":  t["message"],
            }
            for t in failed_tests
        ],
    }


def _get_decision(quality_score: float) -> str:
    """Détermine la décision basée sur le quality score.

    Seuils :
        >= 90 : EXCELLENT — pipeline continue sans avertissement
        >= 80 : ACCEPTABLE — pipeline continue avec avertissement
        >= 60 : WARNING — pipeline continue mais signalement requis
        <  60 : FAILED — pipeline arrêté, alerte Orchestrateur

    Args:
        quality_score: Score entre 0 et 100.

    Returns:
        Décision sous forme de string.
    """
    if quality_score >= 90:
        return "EXCELLENT"
    if quality_score >= 80:
        return "ACCEPTABLE"
    if quality_score >= 60:
        return "WARNING"
    return "FAILED"


def _build_empty_report(sector: str) -> dict:
    """Construit un rapport vide quand aucun test n'est disponible.

    Args:
        sector: Secteur du dataset.

    Returns:
        Rapport minimal avec score 100 et aucun test.
    """
    return {
        "summary": {
            "sector":        sector,
            "timestamp":     datetime.now().isoformat(),
            "quality_score": 100.0,
            "decision":      "EXCELLENT",
            "total_tests":   0,
            "passed_tests":  0,
            "failed_tests":  0,
        },
        "passed": [],
        "failed": [],
    }


def _log_quality_summary(quality_report: dict) -> None:
    """Loggue un résumé lisible du rapport qualité.

    Args:
        quality_report: Rapport complet construit.
    """
    summary = quality_report["summary"]
    failed  = quality_report["failed"]

    logger.info(
        "Quality Report — score : %.1f | decision : %s | "
        "tests : %d/%d passés",
        summary["quality_score"],
        summary["decision"],
        summary["passed_tests"],
        summary["total_tests"],
    )

    if failed:
        logger.warning("Tests échoués :")
        for test in failed:
            logger.warning(
                "  FAIL — [%s] %s : %d lignes en erreur",
                test["column"],
                test["test"],
                test["failures"],
            )