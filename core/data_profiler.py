# core/data_profiler.py

# Standard library
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

# Third-party
import polars as pl


logger = logging.getLogger(__name__)


# ─── Fonction publique principale ────────────────────────────────────────────


def compute_profile(
    df: pl.DataFrame,
    action_plan: dict,
    label: str,
) -> dict:
    """Calcule le profil qualité complet d'un DataFrame.

    Analyse chaque colonne selon son rôle défini dans
    le action_plan et produit un snapshot de qualité.

    Utilisé 2 fois dans le pipeline :
        - Après ingestion  → profile_before (données brutes)
        - Après cleaning   → profile_after  (données nettoyées)

    Args:
        df:          DataFrame à profiler.
        action_plan: Plan d'action avec colonnes par rôle et règles.
        label:       Étiquette du snapshot ("AVANT" ou "APRÈS").

    Returns:
        Dictionnaire complet du profil qualité avec :
            - global_stats   : statistiques globales du DataFrame
            - columns        : profil détaillé par colonne
            - quality_index  : score synthétique 0-100
            - label          : étiquette du snapshot
            - timestamp      : horodatage du profil
    """
    logger.info("Calcul profil qualité — %s cleaning", label)

    total_rows = df.height
    total_cols = df.width

    # Profiler chaque colonne
    columns_profiles = {}
    for col_name in df.columns:
        columns_profiles[col_name] = _profile_column(
            df, col_name, action_plan
        )

    # Calculer le quality index global
    quality_index = _compute_quality_index(
        columns_profiles, total_rows
    )

    profile = {
        "label":     label,
        "timestamp": datetime.now().isoformat(),

        # ── Statistiques globales ──────────────────────────────────
        "global_stats": {
            "total_rows":    total_rows,
            "total_columns": total_cols,
            "total_nulls":   sum(
                c["null_count"]
                for c in columns_profiles.values()
            ),
            "total_duplicates": _count_duplicates(
                df, action_plan
            ),
            "quality_index": quality_index,
        },

        # ── Profil par colonne ─────────────────────────────────────
        "columns": columns_profiles,
    }

    logger.info(
        "Profil %s — %d lignes | %d nulls | "
        "quality index : %.1f",
        label,
        total_rows,
        profile["global_stats"]["total_nulls"],
        quality_index,
    )

    return profile


def build_comparison_report(
    profile_before: dict,
    profile_after: dict,
) -> dict:
    """Construit le rapport de comparaison AVANT vs APRÈS.

    Compare les 2 snapshots et calcule les améliorations
    apportées par le cleaning.

    Args:
        profile_before: Profil calculé avant cleaning.
        profile_after:  Profil calculé après cleaning.

    Returns:
        Rapport de comparaison avec les deltas et améliorations.
    """
    before_stats = profile_before["global_stats"]
    after_stats  = profile_after["global_stats"]

    # Calcul des améliorations
    nulls_fixed = (
        before_stats["total_nulls"] - after_stats["total_nulls"]
    )
    duplicates_fixed = (
        before_stats["total_duplicates"]
        - after_stats["total_duplicates"]
    )
    quality_improvement = (
        after_stats["quality_index"]
        - before_stats["quality_index"]
    )

    return {
        "before": {
            "rows":          before_stats["total_rows"],
            "nulls":         before_stats["total_nulls"],
            "duplicates":    before_stats["total_duplicates"],
            "quality_index": before_stats["quality_index"],
        },
        "after": {
            "rows":          after_stats["total_rows"],
            "nulls":         after_stats["total_nulls"],
            "duplicates":    after_stats["total_duplicates"],
            "quality_index": after_stats["quality_index"],
        },
        "improvements": {
            "nulls_fixed":          nulls_fixed,
            "duplicates_removed":   duplicates_fixed,
            "rows_dropped":         (
                before_stats["total_rows"]
                - after_stats["total_rows"]
            ),
            "quality_gain":         round(quality_improvement, 1),
            "quality_improved":     quality_improvement > 0,
        },
    }


# ─── Fonctions privées ───────────────────────────────────────────────────────


def _profile_column(
    df: pl.DataFrame,
    col_name: str,
    action_plan: dict,
) -> dict:
    """Calcule le profil d'une colonne selon son rôle.

    Args:
        df:          DataFrame complet.
        col_name:    Nom de la colonne à profiler.
        action_plan: Plan d'action pour connaître le rôle.

    Returns:
        Dictionnaire avec les métriques qualité de la colonne.
    """
    col_series  = df[col_name]
    total_rows  = df.height
    null_count  = col_series.null_count()
    null_pct    = round((null_count / total_rows * 100), 1) if total_rows > 0 else 0

    # Déterminer le rôle de la colonne
    role = _get_column_role(col_name, action_plan)

    profile: dict[str, Any] = {
        "role":       role,
        "null_count": null_count,
        "null_pct":   null_pct,
        "is_healthy": null_count == 0,
    }

    # Métriques spécifiques par rôle
    if role == "metric":
        profile.update(
            _profile_metric_column(col_series, col_name, action_plan)
        )

    elif role == "identifier":
        profile.update(
            _profile_identifier_column(col_series, total_rows)
        )

    elif role == "dimension":
        profile.update(
            _profile_dimension_column(
                col_series, col_name, action_plan
            )
        )

    elif role == "temporal_key":
        profile.update(_profile_temporal_column(col_series))

    return profile


def _profile_metric_column(
    col_series: pl.Series,
    col_name: str,
    action_plan: dict,
) -> dict:
    """Profil spécifique pour une colonne METRIC.

    Args:
        col_series:  Série Polars de la colonne.
        col_name:    Nom de la colonne.
        action_plan: Pour récupérer le range configuré.

    Returns:
        Métriques numériques + violations de range.
    """
    non_null = col_series.drop_nulls()
    result: dict[str, Any] = {}

    if not non_null.is_empty():
        try:
            result = {
                "min":    round(float(non_null.min()), 4),
                "max":    round(float(non_null.max()), 4),
                "mean":   round(float(non_null.mean()), 4),
                "median": round(float(non_null.median()), 4),
                "std":    round(float(non_null.std()), 4),
            }
        except Exception:
            result = {}

    # Vérifier les violations de range si configuré
    ranges = action_plan.get("columns_with_range", {})
    if col_name in ranges:
        min_val    = ranges[col_name]["min"]
        max_val    = ranges[col_name]["max"]
        violations = col_series.drop_nulls().filter(
            (col_series.drop_nulls() < min_val)
            | (col_series.drop_nulls() > max_val)
        ).len()

        result["range_config"]     = ranges[col_name]
        result["range_violations"] = int(violations)
        result["range_ok"]         = violations == 0

    return result


def _profile_identifier_column(
    col_series: pl.Series,
    total_rows: int,
) -> dict:
    """Profil spécifique pour une colonne IDENTIFIER.

    Args:
        col_series: Série Polars de la colonne.
        total_rows: Nombre total de lignes du DataFrame.

    Returns:
        Métriques d'unicité et doublons.
    """
    non_null     = col_series.drop_nulls()
    unique_count = non_null.n_unique()
    duplicates   = len(non_null) - unique_count

    return {
        "unique_count":  unique_count,
        "duplicate_count": duplicates,
        "is_unique":     duplicates == 0,
    }


def _profile_dimension_column(
    col_series: pl.Series,
    col_name: str,
    action_plan: dict,
) -> dict:
    """Profil spécifique pour une colonne DIMENSION.

    Args:
        col_series:  Série Polars de la colonne.
        col_name:    Nom de la colonne.
        action_plan: Pour récupérer le pattern configuré.

    Returns:
        Métriques catégorielles + violations de pattern.
    """
    non_null     = col_series.drop_nulls()
    unique_count = non_null.n_unique()

    result: dict[str, Any] = {
        "unique_values": unique_count,
        "top_values":    (
            non_null.value_counts()
            .sort("count", descending=True)
            .head(3)[col_series.name]
            .to_list()
            if not non_null.is_empty()
            else []
        ),
    }

    # Vérifier les violations de pattern si configuré
    patterns = action_plan.get("columns_with_pattern", {})
    if col_name in patterns:
        pattern = patterns[col_name]
        try:
            matches_mask     = non_null.str.contains(pattern)
            invalid_count    = (matches_mask == False).sum()  # noqa: E712
            result["pattern"]            = pattern
            result["pattern_violations"] = int(invalid_count)
            result["pattern_ok"]         = invalid_count == 0
        except Exception:
            pass

    return result


def _profile_temporal_column(col_series: pl.Series) -> dict:
    """Profil spécifique pour une colonne TEMPORAL.

    Args:
        col_series: Série Polars de la colonne.

    Returns:
        Métriques temporelles min/max date.
    """
    non_null = col_series.drop_nulls()

    if non_null.is_empty():
        return {}

    try:
        return {
            "min_date": str(non_null.min()),
            "max_date": str(non_null.max()),
        }
    except Exception:
        return {}


def _count_duplicates(
    df: pl.DataFrame,
    action_plan: dict,
) -> int:
    """Compte les doublons complets dans le DataFrame.

    Args:
        df:          DataFrame à analyser.
        action_plan: Pour récupérer les colonnes identifier.

    Returns:
        Nombre de lignes dupliquées.
    """
    total_rows  = df.height
    unique_rows = df.unique().height
    return total_rows - unique_rows


def _get_column_role(col_name: str, action_plan: dict) -> str:
    """Retourne le rôle d'une colonne depuis le action_plan.

    Args:
        col_name:    Nom de la colonne.
        action_plan: Plan d'action avec colonnes par rôle.

    Returns:
        Rôle de la colonne ou "unknown" si non trouvé.
    """
    role_map = {
        "metric":     action_plan.get("metric_columns", []),
        "dimension":  action_plan.get("dimension_columns", []),
        "identifier": action_plan.get("identifier_columns", []),
        "temporal_key": action_plan.get("temporal_columns", []),
    }

    for role, columns in role_map.items():
        if col_name in columns:
            return role

    return "unknown"


def _compute_quality_index(
    columns_profiles: dict,
    total_rows: int,
) -> float:
    """Calcule un score synthétique de qualité globale 0-100.

    Formule :
        Pénalités sur :
            - % de nulls dans tout le DataFrame
            - présence de doublons
            - violations de range sur metrics
            - violations de pattern sur dimensions

    Args:
        columns_profiles: Profil de chaque colonne.
        total_rows:       Nombre total de lignes.

    Returns:
        Score entre 0.0 et 100.0.
    """
    if total_rows == 0:
        return 0.0

    score = 100.0

    total_cells = total_rows * len(columns_profiles)

    # Pénalité nulls — max 30 points
    total_nulls = sum(
        c.get("null_count", 0)
        for c in columns_profiles.values()
    )
    null_pct = (total_nulls / total_cells * 100) if total_cells > 0 else 0
    score   -= min(30.0, null_pct * 3)

    # Pénalité doublons — max 20 points
    has_duplicates = any(
        c.get("duplicate_count", 0) > 0
        for c in columns_profiles.values()
    )
    if has_duplicates:
        score -= 20.0

    # Pénalité violations range — max 25 points
    range_violations = sum(
        c.get("range_violations", 0)
        for c in columns_profiles.values()
    )
    if range_violations > 0:
        violation_pct = range_violations / total_rows * 100
        score        -= min(25.0, violation_pct * 2.5)

    # Pénalité violations pattern — max 25 points
    pattern_violations = sum(
        c.get("pattern_violations", 0)
        for c in columns_profiles.values()
    )
    if pattern_violations > 0:
        violation_pct = pattern_violations / total_rows * 100
        score        -= min(25.0, violation_pct * 2.5)

    return round(max(0.0, score), 1)