# quality_report.py : modèles de données pour représenter les scores de qualité par colonne et le rapport global de qualité du dataset.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


def _to_native(obj: Any) -> Any:
    """
    Recursively convert numpy types to Python native types 
    AND remove empty values (None, [], {}) to keep JSON compact.
    """
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        obj = obj.tolist()

    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            val = _to_native(v)
            if val is not None:
                # Keep if not an empty collection
                # EXCEPT for critical keys we want to see even if empty (like affected_rows)
                if isinstance(val, (dict, list)) and len(val) == 0:
                    exempt_keys = (
                        "affected_rows", "rows", "null_rows", "duplicate_rows", 
                        "invalid_rows", "range_errors", "enum_errors", 
                        "pattern_errors", "date_errors", "type_errors",
                        "out_of_range_rows", "inconsistent_rows",
                        "br_accuracy_rows", "br_validity_rows"
                    )
                    if k not in exempt_keys:
                        continue
                cleaned[k] = val
        return cleaned

    if isinstance(obj, (list, tuple)):
        cleaned = []
        for v in obj:
            val = _to_native(v)
            if val is not None:
                if isinstance(val, (dict, list)) and len(val) == 0:
                    continue
                cleaned.append(val)
        return cleaned

    return obj


# Offset à ajouter aux indices Pandas pour afficher des numéros de ligne
# correspondant au fichier CSV/Excel (ligne 1 = en-tête, ligne 2 = 1ère donnée)
ROW_DISPLAY_OFFSET = 2


def _offset_detail(detail: dict) -> dict:
    """Convertit les indices Pandas (0-based) en numéros de ligne CSV/Excel."""
    result = {}
    # Clés contenant des listes d'indices de lignes
    ROW_KEYS = {
        "null_rows", "duplicate_rows", "invalid_rows", 
        "range_errors", "enum_errors", "pattern_errors", "date_errors",
        "type_errors", "out_of_range_rows", "inconsistent_rows",
        "br_accuracy_rows", "br_validity_rows", "br_completeness_rows", 
        "br_uniqueness_rows", "failed_rows", "rows"
    }
    for k, v in detail.items():
        if k in ROW_KEYS and isinstance(v, list):
            result[k] = [r + ROW_DISPLAY_OFFSET for r in v]
        else:
            result[k] = v
    return result


@dataclass
class ColumnQualityScore:
    """
    Score de qualité d'une seule colonne sur les 5 dimensions.

    completeness : None si nullable=true (pas applicable)
    uniqueness   : None si identifier=false (pas applicable)
    validity     : None si aucune règle de validation définie
    accuracy     : None si pas de range (in_range) défini
    consistency  : None si pas de business rules applicables
    """
    column_name:   str
    business_name: str

    # Scores 0.0 à 100.0 — None si la dimension ne s'applique pas
    completeness: Optional[float] = None
    validity:     Optional[float] = None
    uniqueness:   Optional[float] = None
    accuracy:     Optional[float] = None
    consistency:  Optional[float] = None

    # Détail des violations par dimension
    completeness_detail: dict = field(default_factory=dict)
    validity_detail:     dict = field(default_factory=dict)
    uniqueness_detail:   dict = field(default_factory=dict)
    accuracy_detail:     dict = field(default_factory=dict)
    consistency_detail:  dict = field(default_factory=dict)

    @property
    def global_score(self) -> Optional[float]:
        """
        Moyenne des dimensions applicables pour cette colonne.
        Retourne None si aucune dimension n'est applicable.
        """
        scores = [s for s in [
            self.completeness, self.validity, self.uniqueness,
            self.accuracy, self.consistency,
        ] if s is not None]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 1)

    def to_dict(self, apply_offsets: bool = True) -> dict:
        details = {
            "completeness": self.completeness_detail,
            "validity":     self.validity_detail,
            "uniqueness":   self.uniqueness_detail,
            "accuracy":     self.accuracy_detail,
            "consistency":  self.consistency_detail,
        }
        if apply_offsets:
            details = {k: _offset_detail(v) for k, v in details.items()}

        return _to_native({
            "column_name":   self.column_name,
            "business_name": self.business_name,
            "scores": {
                "completeness": self.completeness,
                "validity":     self.validity,
                "uniqueness":   self.uniqueness,
                "accuracy":     self.accuracy,
                "consistency":  self.consistency,
                "global":       self.global_score,
            },
            "details": details,
        })

    @classmethod
    def from_dict(cls, d: dict) -> ColumnQualityScore:
        scores  = d.get("scores", {})
        details = d.get("details", {})
        return cls(
            column_name=d.get("column_name", ""),
            business_name=d.get("business_name", ""),
            completeness=scores.get("completeness"),
            validity=scores.get("validity"),
            uniqueness=scores.get("uniqueness"),
            accuracy=scores.get("accuracy"),
            consistency=scores.get("consistency"),
            completeness_detail=details.get("completeness", {}),
            validity_detail=details.get("validity", {}),
            uniqueness_detail=details.get("uniqueness", {}),
            accuracy_detail=details.get("accuracy", {}),
            consistency_detail=details.get("consistency", {}),
        )


@dataclass
class QualityReport:
    """
    Rapport de qualité complet du dataset.
    Contient les scores par colonne + scores globaux par dimension.
    """
    label:   str  # "AVANT" ou "APRÈS"
    sector:  str
    job_id:  str
    total_rows: int

    # Score par colonne
    columns: list[ColumnQualityScore] = field(default_factory=list)

    # Score de duplication de lignes (table-level, pour uniqueness)
    row_duplication_score: Optional[float] = None
    row_duplication_detail: dict = field(default_factory=dict)

    # Business rules affectant plusieurs colonnes (table-level)
    table_level_business_rules: list[dict] = field(default_factory=list)

    @property
    def completeness_global(self) -> float:
        """Score Completeness global = moyenne des colonnes concernées."""
        scores = [c.completeness for c in self.columns if c.completeness is not None]
        return round(sum(scores) / len(scores), 1) if scores else 100.0

    @property
    def validity_global(self) -> float:
        """Score Validity global = moyenne des colonnes concernées."""
        scores = [c.validity for c in self.columns if c.validity is not None]
        return round(sum(scores) / len(scores), 1) if scores else 100.0

    @property
    def uniqueness_global(self) -> float:
        """Score Uniqueness global = moyenne des colonnes concernées + duplication lignes."""
        scores = [c.uniqueness for c in self.columns if c.uniqueness is not None]
        if self.row_duplication_score is not None:
            scores.append(self.row_duplication_score)
        return round(sum(scores) / len(scores), 1) if scores else 100.0

    @property
    def accuracy_global(self) -> float:
        """Score Accuracy global = moyenne des colonnes concernées."""
        scores = [c.accuracy for c in self.columns if c.accuracy is not None]
        return round(sum(scores) / len(scores), 1) if scores else 100.0

    @property
    def consistency_global(self) -> float:
        """Score Consistency global = moyenne des colonnes concernées."""
        scores = [c.consistency for c in self.columns if c.consistency is not None]
        return round(sum(scores) / len(scores), 1) if scores else 100.0

    @property
    def global_score(self) -> float:
        """
        Score global pondéré des 5 dimensions.
        Poids depuis settings : completeness=0.25, validity=0.25,
        uniqueness=0.20, accuracy=0.15, consistency=0.15
        """
        from config.settings import get_settings
        s = get_settings()
        return round(
            self.completeness_global * s.weight_completeness
            + self.validity_global   * s.weight_validity
            + self.uniqueness_global * s.weight_uniqueness
            + self.accuracy_global   * s.weight_accuracy
            + self.consistency_global * s.weight_consistency,
            1,
        )

    def to_dict(self, apply_offsets: bool = True) -> dict:
        row_dup_detail = self.row_duplication_detail
        table_br = self.table_level_business_rules
        
        if apply_offsets:
            row_dup_detail = _offset_detail(row_dup_detail)
            table_br = [_offset_detail(br) for br in table_br]

        return _to_native({
            "label":      self.label,
            "sector":     self.sector,
            "job_id":     self.job_id,
            "total_rows": self.total_rows,
            "global_scores": {
                "completeness": self.completeness_global,
                "validity":     self.validity_global,
                "uniqueness":   self.uniqueness_global,
                "accuracy":     self.accuracy_global,
                "consistency":  self.consistency_global,
                "global":       self.global_score,
            },
            "row_duplication": {
                "score": self.row_duplication_score,
                "detail": row_dup_detail,
            },
            "table_level_business_rules": table_br,
            "columns": [c.to_dict(apply_offsets=apply_offsets) for c in self.columns],
        })

    @classmethod
    def from_dict(cls, d: dict) -> QualityReport:
        row_dup = d.get("row_duplication", {})
        return cls(
            label=d.get("label", ""),
            sector=d.get("sector", ""),
            job_id=d.get("job_id", ""),
            total_rows=d.get("total_rows", 0),
            row_duplication_score=row_dup.get("score"),
            row_duplication_detail=row_dup.get("detail", {}),
            table_level_business_rules=d.get("table_level_business_rules", []),
            columns=[
                ColumnQualityScore.from_dict(c)
                for c in d.get("columns", [])
            ],
        )