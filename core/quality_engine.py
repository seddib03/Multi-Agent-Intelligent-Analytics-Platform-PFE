"""
Moteur de calcul des 3 dimensions de qualité par colonne.

LOGIQUE :
    Pour chaque colonne du dataset, on lit son ColumnMeta
    et on applique les règles correspondantes.

    Completeness → applicable si nullable=false
    Uniqueness   → applicable si identifier=true
    Validity     → applicable si type + règles définies (range/enum/pattern/format)

FORMULES :
    Completeness(col) = (total - nulls) / total * 100
    Uniqueness(col)   = nb_unique / total * 100
    Validity(col)     = valeurs_valides / valeurs_non_nulles * 100


"""
from __future__ import annotations

import logging
import re
from typing import Optional

import pandas as pd

from models.metadata_schema import ColumnMeta
from models.quality_report import ColumnQualityScore, QualityReport

logger = logging.getLogger(__name__)

# Formats de date courants → format Python strptime
DATE_FORMAT_MAP = {
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD-MM-YYYY": "%d-%m-%Y",
    "MM-DD-YYYY": "%m-%d-%Y",
    "YYYY/MM/DD": "%Y/%m/%d",
}


def compute_quality_report(
    df:       pd.DataFrame,
    metadata: list[ColumnMeta],
    label:    str,
    sector:   str,
    job_id:   str,
) -> QualityReport:
    """
    Calcule le rapport de qualité complet du dataset.

    Itère sur chaque colonne définie dans le metadata
    et calcule les 3 dimensions applicables.

    Args:
        df:       DataFrame Pandas à évaluer
        metadata: Liste de ColumnMeta du formulaire
        label:    "AVANT" ou "APRÈS" (pour la comparaison)
        sector:   Secteur du dataset
        job_id:   UUID du job

    Returns:
        QualityReport avec scores par colonne et globaux.
    """
    report = QualityReport(
        label=label,
        sector=sector,
        job_id=job_id,
        total_rows=len(df),
    )

    # Créer un index {column_name: ColumnMeta} pour accès rapide
    meta_index = {m.column_name: m for m in metadata}

    for col_meta in metadata:
        col_name = col_meta.column_name

        # Vérifier que la colonne existe dans le dataset
        if col_name not in df.columns:
            logger.warning(
                "Colonne '%s' dans le metadata mais absente du dataset",
                col_name,
            )
            continue

        col_score = _score_column(df, col_meta)
        report.columns.append(col_score)

        logger.debug(
            "  %s → completeness=%s validity=%s uniqueness=%s",
            col_name,
            col_score.completeness,
            col_score.validity,
            col_score.uniqueness,
        )

    logger.info(
        "Quality report [%s] — global: %.1f "
        "(completeness: %.1f | validity: %.1f | uniqueness: %.1f)",
        label,
        report.global_score,
        report.completeness_global,
        report.validity_global,
        report.uniqueness_global,
    )

    return report


def _score_column(
    df:       pd.DataFrame,
    col_meta: ColumnMeta,
) -> ColumnQualityScore:
    """
    Calcule les scores des 3 dimensions pour une colonne.

    Args:
        df:       DataFrame complet
        col_meta: Metadata de la colonne

    Returns:
        ColumnQualityScore avec les scores et détails.
    """
    col_name = col_meta.column_name
    series   = df[col_name]
    total    = len(series)

    score = ColumnQualityScore(
        column_name=col_name,
        business_name=col_meta.business_name,
    )

    # ── COMPLETENESS ───────────────────────────────────────────────────────
    # Règle : si nullable=false → 0 null autorisé
    if not col_meta.nullable:
        null_count = series.isna().sum()
        score.completeness = round((total - null_count) / total * 100, 1)
        score.completeness_detail = {
            "null_count": int(null_count),
            "total":      total,
            "null_rows":  series[series.isna()].index.tolist(),
        }

    # ── UNIQUENESS ────────────────────────────────────────────────────────
    # Règle : si identifier=true → toutes les valeurs uniques
    if col_meta.identifier:
        non_null  = series.dropna()
        n_unique  = non_null.nunique()
        n_total   = len(non_null)
        dup_mask  = series.duplicated(keep="first") & series.notna()
        dup_count = dup_mask.sum()

        score.uniqueness = round(n_unique / n_total * 100, 1) if n_total > 0 else 100.0
        score.uniqueness_detail = {
            "duplicate_count": int(dup_count),
            "unique_count":    int(n_unique),
            "total_non_null":  int(n_total),
            "duplicate_rows":  series[dup_mask].index.tolist(),
            "duplicate_values": series[dup_mask].tolist()[:10],
        }

    # ── VALIDITY ──────────────────────────────────────────────────────────
    # Plusieurs sous-règles selon le type et les contraintes metadata
    validity_score, validity_detail = _compute_validity(series, col_meta, total)
    score.validity        = validity_score
    score.validity_detail = validity_detail

    return score


def _compute_validity(
    series:   pd.Series,
    col_meta: ColumnMeta,
    total:    int,
) -> tuple[Optional[float], dict]:
    """
    Calcule le score de Validity pour une colonne.

    RÈGLES APPLIQUÉES (dans l'ordre) :

    1. TYPE : la valeur est-elle castable dans le type attendu ?
       (int, float, date)

    2. RANGE : si min/max défini → la valeur est-elle dans [min, max] ?

    3. ENUM : si enum défini → la valeur est-elle dans la liste ?

    4. PATTERN : si pattern défini → la valeur matche-t-elle le regex ?

    5. DATE FORMAT : si type=date et format défini → parseable ?

    Une valeur est INVALIDE si elle échoue au moins une règle.

    Args:
        series:   Série Pandas de la colonne
        col_meta: Metadata de la colonne
        total:    Nombre total de lignes

    Returns:
        Tuple (score 0-100 ou None, dict de détails).
    """
    # Travailler sur les valeurs non-nulles uniquement
    # (les nulls sont gérés par Completeness)
    non_null = series.dropna()

    if len(non_null) == 0:
        return None, {}

    # Collecter les indices invalides par sous-règle
    invalid_indices: set[int] = set()
    details: dict = {
        "type_errors":    [],
        "range_errors":   [],
        "enum_errors":    [],
        "pattern_errors": [],
        "date_errors":    [],
    }

    # ── 1. Vérification de type ───────────────────────────────────────────
    if col_meta.type in ("int", "float"):
        type_errors = _check_numeric_type(non_null, col_meta.type)
        invalid_indices.update(type_errors)
        details["type_errors"] = type_errors[:10]

    elif col_meta.type == "date":
        date_format = _normalize_date_format(col_meta.format)
        date_errors = _check_date_format(non_null, date_format)
        invalid_indices.update(date_errors)
        details["date_errors"] = date_errors[:10]

    # ── 2. Vérification range (int/float seulement) ───────────────────────
    if col_meta.type in ("int", "float") and col_meta.has_range:
        # Ne vérifier le range que sur les valeurs correctement typées
        valid_numeric = non_null.drop(index=invalid_indices, errors="ignore")
        range_errors  = _check_range(valid_numeric, col_meta.min, col_meta.max)
        invalid_indices.update(range_errors)
        details["range_errors"] = range_errors[:10]
        if col_meta.min is not None or col_meta.max is not None:
            details["range_rule"] = f"[{col_meta.min}, {col_meta.max}]"

    # ── 3. Vérification enum (string seulement) ───────────────────────────
    if col_meta.type == "string" and col_meta.has_enum:
        enum_errors = _check_enum(non_null, col_meta.enum)
        invalid_indices.update(enum_errors)
        details["enum_errors"] = enum_errors[:10]
        details["valid_enum"]  = col_meta.enum

    # ── 4. Vérification pattern (string seulement) ────────────────────────
    if col_meta.type == "string" and col_meta.has_pattern:
        pattern_errors = _check_pattern(non_null, col_meta.pattern)
        invalid_indices.update(pattern_errors)
        details["pattern_errors"] = pattern_errors[:10]
        details["pattern_rule"]   = col_meta.pattern

    # ── Calcul du score ───────────────────────────────────────────────────
    # Si aucune règle ne s'applique → dimension non calculée
    has_any_rule = (
        col_meta.type in ("int", "float", "date")
        or col_meta.has_enum
        or col_meta.has_pattern
        or col_meta.has_range
    )

    if not has_any_rule:
        return None, {}

    n_invalid = len(invalid_indices)
    n_valid   = len(non_null) - n_invalid
    score     = round(n_valid / len(non_null) * 100, 1)

    details["invalid_count"] = n_invalid
    details["valid_count"]   = n_valid
    details["invalid_rows"]  = sorted(list(invalid_indices))[:20]
    details["sample_invalid"] = series.iloc[
        sorted(list(invalid_indices))[:5]
    ].tolist() if invalid_indices else []

    return score, details


# ── Sous-règles de Validity ───────────────────────────────────────────────────


def _check_numeric_type(series: pd.Series, expected_type: str) -> list[int]:
    """
    Identifie les valeurs non castables en int ou float.

    Args:
        series:        Série non-nulle
        expected_type: "int" ou "float"

    Returns:
        Liste des indices (Pandas) invalides.
    """
    invalid = []
    for idx, val in series.items():
        try:
            float(val)  # float() accepte aussi les entiers
            if expected_type == "int":
                # Vérifier que c'est bien un entier (pas 3.7)
                if float(val) != int(float(val)):
                    invalid.append(idx)
        except (ValueError, TypeError):
            invalid.append(idx)
    return invalid


def _check_range(
    series: pd.Series,
    min_val: Optional[float],
    max_val: Optional[float],
) -> list[int]:
    """
    Identifie les valeurs hors de [min_val, max_val].

    Args:
        series:  Série de valeurs numériques
        min_val: Borne inférieure (None = pas de borne)
        max_val: Borne supérieure (None = pas de borne)

    Returns:
        Liste des indices (Pandas) hors range.
    """
    invalid = []
    for idx, val in series.items():
        try:
            num = float(val)
            if min_val is not None and num < min_val:
                invalid.append(idx)
            elif max_val is not None and num > max_val:
                invalid.append(idx)
        except (ValueError, TypeError):
            pass  # Déjà capturé par _check_numeric_type
    return invalid


def _check_enum(series: pd.Series, valid_values: list[str]) -> list[int]:
    """
    Identifie les valeurs absentes de la liste enum.

    La vérification est insensible à la casse pour la robustesse.

    Args:
        series:       Série de valeurs texte
        valid_values: Liste des valeurs valides

    Returns:
        Liste des indices (Pandas) avec valeur invalide.
    """
    valid_lower = {v.lower() for v in valid_values}
    invalid = []
    for idx, val in series.items():
        if str(val).lower() not in valid_lower:
            invalid.append(idx)
    return invalid


def _check_pattern(series: pd.Series, pattern: str) -> list[int]:
    """
    Identifie les valeurs ne matchant pas le regex.

    Args:
        series:  Série de valeurs texte
        pattern: Expression régulière

    Returns:
        Liste des indices (Pandas) ne matchant pas.
    """
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        logger.warning("Pattern regex invalide '%s' : %s", pattern, e)
        return []

    invalid = []
    for idx, val in series.items():
        if not compiled.match(str(val)):
            invalid.append(idx)
    return invalid


def _check_date_format(series: pd.Series, date_format: str) -> list[int]:
    """
    Identifie les valeurs non parseable selon le format de date.

    Args:
        series:      Série de valeurs texte
        date_format: Format strptime (ex: "%m/%d/%Y")

    Returns:
        Liste des indices (Pandas) avec date invalide.
    """
    invalid = []
    for idx, val in series.items():
        try:
            pd.to_datetime(str(val), format=date_format)
        except (ValueError, TypeError):
            invalid.append(idx)
    return invalid


def _normalize_date_format(format_str: Optional[str]) -> str:
    """
    Convertit un format lisible en format strptime.

    Ex: "MM/DD/YYYY" → "%m/%d/%Y"

    Args:
        format_str: Format fourni dans le metadata

    Returns:
        Format strptime utilisable par pandas.
    """
    if not format_str:
        return "%Y-%m-%d"  # Format par défaut

    # Chercher dans le mapping
    if format_str in DATE_FORMAT_MAP:
        return DATE_FORMAT_MAP[format_str]

    # Si déjà au format strptime (commence par %)
    if "%" in format_str:
        return format_str

    # Fallback
    logger.warning(
        "Format de date non reconnu : '%s' → utilisation '%s'",
        format_str,
        DATE_FORMAT_MAP.get(format_str, "%Y-%m-%d"),
    )
    return "%Y-%m-%d"