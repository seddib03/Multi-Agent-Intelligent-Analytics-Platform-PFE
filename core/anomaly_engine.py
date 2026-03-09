"""
Moteur de détection des anomalies et proposition d'actions.

DIFFÉRENCE AVEC quality_engine :
    quality_engine  → MESURE les scores (%, chiffres)
    anomaly_engine  → IDENTIFIE les lignes exactes + PROPOSE des actions

POUR CHAQUE ANOMALIE, 3 ACTIONS PROPOSÉES :
    action_1 → Conservative  (flag, imputer, conserver)
    action_2 → Modérée       (remplacer par valeur proche)
    action_3 → Agressive     (supprimer la ligne)

LOGIQUE :
    On lit le QualityReport (scores) pour savoir
    quelles colonnes ont des problèmes.
    Puis on crée un AnomalyItem pour chaque problème détecté.
"""
from __future__ import annotations

import logging
import uuid

import pandas as pd

from models.anomaly_report import (
    AnomalyItem,
    AnomalyType,
    CleaningAction,
    CleaningPlan,
)
from models.metadata_schema import ColumnMeta
from models.quality_report import QualityReport

logger = logging.getLogger(__name__)


def detect_anomalies(
    metadata:       list[ColumnMeta],
    quality_report: QualityReport,
    job_id:         str,
    sector:         str,
) -> CleaningPlan:
    """
    Détecte toutes les anomalies et propose les actions.

    Utilise le QualityReport pour savoir quelles colonnes
    ont des violations, puis crée les AnomalyItems détaillés.

    Args:
        metadata:       Liste de ColumnMeta
        quality_report: Rapport qualité AVANT (contient les détails)
        job_id:         UUID du job
        sector:         Secteur

    Returns:
        CleaningPlan avec toutes les anomalies et actions proposées.
    """
    anomalies = []
    meta_index = {m.column_name: m for m in metadata}
    total      = quality_report.total_rows

    # Pour chaque colonne du rapport qualité
    for col_score in quality_report.columns:
        col_name = col_score.column_name
        col_meta = meta_index.get(col_name)
        if col_meta is None:
            continue

        # ── Anomalies de Completeness (nulls) ─────────────────────────────
        if col_score.completeness is not None and col_score.completeness < 100:
            detail   = col_score.completeness_detail
            null_rows = detail.get("null_rows", [])
            null_count = detail.get("null_count", 0)

            anomalies.append(_make_null_anomaly(
                col_meta, null_rows, null_count, total
            ))

        # ── Anomalies de Uniqueness (doublons) ────────────────────────────
        if col_score.uniqueness is not None and col_score.uniqueness < 100:
            detail    = col_score.uniqueness_detail
            dup_rows  = detail.get("duplicate_rows", [])
            dup_count = detail.get("duplicate_count", 0)

            anomalies.append(_make_duplicate_anomaly(
                col_meta, dup_rows, dup_count, total
            ))

        # ── Anomalies de Validity ─────────────────────────────────────────
        if col_score.validity is not None and col_score.validity < 100:
            detail = col_score.validity_detail

            # Type errors
            if detail.get("type_errors"):
                anomalies.append(_make_type_anomaly(
                    col_meta, detail["type_errors"], total
                ))

            # Range errors
            if detail.get("range_errors"):
                anomalies.append(_make_range_anomaly(
                    col_meta, detail["range_errors"],
                    detail.get("range_errors_samples", []), total
                ))

            # Enum errors
            if detail.get("enum_errors"):
                anomalies.append(_make_enum_anomaly(
                    col_meta, detail["enum_errors"],
                    detail.get("enum_errors_samples", []), total
                ))

            # Pattern errors
            if detail.get("pattern_errors"):
                anomalies.append(_make_pattern_anomaly(
                    col_meta, detail["pattern_errors"],
                    detail.get("pattern_errors_samples", []), total
                ))

            # Date errors
            if detail.get("date_errors"):
                anomalies.append(_make_date_anomaly(
                    col_meta, detail["date_errors"],
                    detail.get("date_errors_samples", []), total
                ))

        # ── Anomalies de Consistency (Business Rules) ─────────────────────
        if col_score.consistency is not None and col_score.consistency < 100:
            detail = col_score.consistency_detail
            if detail.get("business_rule_errors"):
                for br_error in detail["business_rule_errors"]:
                    anomalies.append(_make_business_rule_anomaly(
                        col_meta, br_error, "consistency", total
                    ))

        # ── Anomalies de Accuracy (Côté Business Rules / Custom) ───────────
        if col_score.accuracy is not None and col_score.accuracy < 100:
            detail = col_score.accuracy_detail
            if detail.get("business_rule_errors"):
                for br_error in detail["business_rule_errors"]:
                    anomalies.append(_make_business_rule_anomaly(
                        col_meta, br_error, "accuracy", total
                    ))

    # ── Anomalies Table-Level (ex: row_not_duplicate ou règles métier globales) ──
    for tl_rule in getattr(quality_report, "table_level_business_rules", []):
        rule_name = tl_rule.get("test_type", "règle métier")
        count = tl_rule.get("count", 0)
        rows = tl_rule.get("rows", [])
        
        anomalies.append(AnomalyItem(
            anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
            column_name="", # Table-level
            dimension=tl_rule.get("dimension", "consistency"),
            anomaly_type=AnomalyType.CUSTOM_RULE,
            problem_description=f"Violation de la règle métier : '{rule_name}'. Affecte {count} ligne(s).",
            affected_rows=rows[:500],
            affected_count=count,
            affected_pct=float(count / total * 100) if total else 0.0,
            anomaly_source="business_rule",
            action_1=CleaningAction.FLAG_ONLY,
            justification_1="Signaler la violation pour investigation",
            action_2=CleaningAction.DROP_ROWS,
            justification_2="Supprimer les lignes invalides",
            action_3=CleaningAction.FLAG_ONLY,
            justification_3="Conserver sans modification",
        ))

    plan = CleaningPlan(
        plan_id=f"plan_{job_id[:8]}",
        job_id=job_id,
        sector=sector,
        anomalies=anomalies,
        status="proposed",
    )

    logger.info(
        "Anomaly detection terminée — %d anomalies sur %d colonnes",
        len(anomalies),
        len(metadata),
    )

    return plan


# ── Constructeurs d'anomalies ─────────────────────────────────────────────────


def _make_null_anomaly(
    meta:       ColumnMeta,
    null_rows:  list[int],
    null_count: int,
    total:      int,
) -> AnomalyItem:
    """Anomalie : valeurs nulles sur colonne nullable=false."""

    # Choisir les actions selon le type de la colonne
    if meta.type in ("int", "float"):
        a1, j1 = CleaningAction.IMPUTE_MEDIAN, \
            "Imputer la médiane — robuste aux outliers, préserve la distribution"
        a2, j2 = CleaningAction.IMPUTE_MODE, \
            "Imputer la valeur la plus fréquente — adapté si distribution unimodale"
        a3, j3 = CleaningAction.DROP_ROWS, \
            "Supprimer les lignes — si les nulls représentent < 5% du dataset"
    else:
        a1, j1 = CleaningAction.IMPUTE_MODE, \
            "Imputer la valeur la plus fréquente — conserve la cohérence catégorielle"
        a2, j2 = CleaningAction.FLAG_ONLY, \
            "Signaler sans modifier — si la valeur inconnue est significative"
        a3, j3 = CleaningAction.DROP_ROWS, \
            "Supprimer les lignes — si l'identifiant est manquant"

    return AnomalyItem(
        anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
        column_name=meta.column_name,
        dimension="completeness",
        anomaly_type=AnomalyType.NULL_VALUE,
        problem_description=(
            f"La colonne '{meta.business_name}' ({meta.column_name}) "
            f"contient {null_count} valeur(s) nulle(s) "
            f"({round(null_count/total*100, 1)}% du dataset) "
            f"alors qu'elle est marquée obligatoire (nullable=false)."
        ),
        affected_rows=null_rows,
        affected_count=null_count,
        affected_pct=float(null_count / total * 100),
        action_1=a1, justification_1=j1,
        action_2=a2, justification_2=j2,
        action_3=a3, justification_3=j3,
    )


def _make_duplicate_anomaly(
    meta:      ColumnMeta,
    dup_rows:  list[int],
    dup_count: int,
    total:     int,
) -> AnomalyItem:
    """Anomalie : doublons sur colonne identifier=true."""
    return AnomalyItem(
        anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
        column_name=meta.column_name,
        dimension="uniqueness",
        anomaly_type=AnomalyType.DUPLICATE,
        problem_description=(
            f"La colonne '{meta.business_name}' ({meta.column_name}) "
            f"est un identifiant (identifier=true) mais contient "
            f"{dup_count} doublon(s) sur {total} lignes. "
            f"Chaque valeur devrait être unique."
        ),
        affected_rows=dup_rows,
        affected_count=dup_count,
        affected_pct=float(dup_count / total * 100),
        action_1=CleaningAction.FLAG_ONLY,
        justification_1="Signaler sans modifier — examiner manuellement avant suppression",
        action_2=CleaningAction.DROP_DUPLICATES,
        justification_2="Supprimer les doublons en gardant la première occurrence",
        action_3=CleaningAction.DROP_ROWS,
        justification_3="Supprimer toutes les lignes dupliquées (y compris la première occurrence)",
    )


def _make_range_anomaly(
    meta:       ColumnMeta,
    range_rows: list[int],
    sample:     list[Any],
    total:      int,
) -> AnomalyItem:
    """Anomalie : valeurs hors range [min, max]."""
    rule   = f"[{meta.min}, {meta.max}]"

    return AnomalyItem(
        anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
        column_name=meta.column_name,
        dimension="validity",
        anomaly_type=AnomalyType.OUT_OF_RANGE,
        problem_description=(
            f"La colonne '{meta.business_name}' contient {len(range_rows)} "
            f"valeur(s) hors de la plage autorisée {rule}. "
            f"Exemples : {sample}"
        ),
        affected_rows=range_rows,
        affected_count=len(range_rows),
        affected_pct=float(len(range_rows) / total * 100),
        sample_invalid_values=sample,
        params={"min": meta.min, "max": meta.max},
        action_1=CleaningAction.FLAG_ONLY,
        justification_1="Signaler sans modifier — la valeur peut être légitime (ex: contrat VIP)",
        action_2=CleaningAction.CLIP_RANGE,
        justification_2=f"Limiter aux bornes {rule} — remplace par min ou max si dépassé",
        action_3=CleaningAction.DROP_ROWS,
        justification_3="Supprimer les lignes hors range — si la règle métier est stricte",
    )


def _make_enum_anomaly(
    meta:      ColumnMeta,
    enum_rows: list[int],
    sample:    list[Any],
    total:     int,
) -> AnomalyItem:
    """Anomalie : valeurs absentes de la liste enum."""

    return AnomalyItem(
        anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
        column_name=meta.column_name,
        dimension="validity",
        anomaly_type=AnomalyType.INVALID_ENUM,
        problem_description=(
            f"La colonne '{meta.business_name}' contient {len(enum_rows)} "
            f"valeur(s) non autorisée(s). Valeurs valides : {meta.enum}. "
            f"Valeurs invalides trouvées : {list(set(sample))}"
        ),
        affected_rows=enum_rows,
        affected_count=len(enum_rows),
        affected_pct=float(len(enum_rows) / total * 100),
        sample_invalid_values=sample,
        params={"valid_enum": meta.enum},
        action_1=CleaningAction.FLAG_ONLY,
        justification_1="Signaler sans modifier — vérifier si la liste enum est complète",
        action_2=CleaningAction.REPLACE_ENUM,
        justification_2="Remplacer par la valeur enum la plus proche (distance de Levenshtein)",
        action_3=CleaningAction.DROP_ROWS,
        justification_3="Supprimer les lignes avec valeur invalide",
    )


def _make_pattern_anomaly(
    meta:         ColumnMeta,
    pattern_rows: list[int],
    sample:       list[Any],
    total:        int,
) -> AnomalyItem:
    """Anomalie : valeurs ne matchant pas le pattern regex."""

    return AnomalyItem(
        anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
        column_name=meta.column_name,
        dimension="validity",
        anomaly_type=AnomalyType.PATTERN_MISMATCH,
        problem_description=(
            f"La colonne '{meta.business_name}' contient {len(pattern_rows)} "
            f"valeur(s) ne respectant pas le pattern '{meta.pattern}'. "
            f"Exemples invalides : {sample}"
        ),
        affected_rows=pattern_rows,
        affected_count=len(pattern_rows),
        affected_pct=float(len(pattern_rows) / total * 100),
        sample_invalid_values=sample,
        params={"pattern": meta.pattern},
        action_1=CleaningAction.FLAG_ONLY,
        justification_1="Signaler — vérifier si le pattern est correct avant de modifier",
        action_2=CleaningAction.IMPUTE_MODE,
        justification_2="Remplacer par la valeur la plus fréquente (qui respecte le pattern)",
        action_3=CleaningAction.DROP_ROWS,
        justification_3="Supprimer les lignes avec pattern invalide",
    )


def _make_type_anomaly(
    meta:       ColumnMeta,
    type_rows:  list[int],
    total:      int,
) -> AnomalyItem:
    """Anomalie : valeurs non castables dans le type attendu."""
    return AnomalyItem(
        anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
        column_name=meta.column_name,
        dimension="validity",
        anomaly_type=AnomalyType.WRONG_TYPE,
        problem_description=(
            f"La colonne '{meta.business_name}' contient {len(type_rows)} "
            f"valeur(s) qui ne peuvent pas être converties en type '{meta.type}'. "
            f"Ces valeurs violent la règle de type définie dans le metadata."
        ),
        affected_rows=type_rows,
        affected_count=len(type_rows),
        affected_pct=float(len(type_rows) / total * 100),
        action_1=CleaningAction.CAST_TYPE,
        justification_1=f"Forcer la conversion en {meta.type} (les non-convertibles → NaN)",
        action_2=CleaningAction.FLAG_ONLY,
        justification_2="Signaler sans modifier — vérifier si le type metadata est correct",
        action_3=CleaningAction.DROP_ROWS,
        justification_3="Supprimer les lignes avec type invalide",
    )


def _make_date_anomaly(
    meta:      ColumnMeta,
    date_rows: list[int],
    sample:    list[Any],
    total:     int,
) -> AnomalyItem:
    """Anomalie : dates non parseable selon le format."""

    return AnomalyItem(
        anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
        column_name=meta.column_name,
        dimension="validity",
        anomaly_type=AnomalyType.INVALID_DATE,
        problem_description=(
            f"La colonne '{meta.business_name}' contient {len(date_rows)} "
            f"date(s) invalides ne respectant pas le format '{meta.format}'. "
            f"Exemples : {sample}"
        ),
        affected_rows=date_rows,
        affected_count=len(date_rows),
        affected_pct=float(len(date_rows) / total * 100),
        sample_invalid_values=sample,
        params={"expected_format": meta.format},
        action_1=CleaningAction.PARSE_DATE,
        justification_1="Tenter de parser avec plusieurs formats courants automatiquement",
        action_2=CleaningAction.FLAG_ONLY,
        justification_2="Signaler sans modifier — correction manuelle recommandée",
        action_3=CleaningAction.DROP_ROWS,
        justification_3="Supprimer les lignes avec date invalide",
    )


def _make_business_rule_anomaly(
    meta:       ColumnMeta,
    br_error:   dict,
    dimension:  str,
    total:      int,
) -> AnomalyItem:
    """Anomalie : violation d'une règle métier (Business Rule)."""
    
    rule_name  = br_error.get("rule_name", "règle métier inconnue")
    error_rows = br_error.get("failed_rows", [])
    count      = len(error_rows)
    
    return AnomalyItem(
        anomaly_id=f"anomaly_{uuid.uuid4().hex[:6]}",
        column_name=meta.column_name,
        dimension=dimension,
        anomaly_type=AnomalyType.CUSTOM_RULE if hasattr(AnomalyType, 'CUSTOM_RULE') else AnomalyType.OUT_OF_RANGE,
        anomaly_source="business_rule",
        problem_description=(
            f"La colonne '{meta.business_name}' viole la règle métier : '{rule_name}'. "
            f"Ceci a affecté {count} ligne(s)."
        ),
        affected_rows=error_rows[:100],  # Limiter pour éviter les out-of-memory
        affected_count=count,
        affected_pct=float(count / total * 100) if total else 0.0,
        action_1=CleaningAction.FLAG_ONLY,
        justification_1="Signaler la violation pour investigation manuelle",
        action_2=CleaningAction.DROP_ROWS,
        justification_2="Supprimer les lignes ne respectant pas la règle métier",
        action_3=CleaningAction.FLAG_ONLY, # Fallback
        justification_3="Conserver en isolant",
    )