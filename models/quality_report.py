"""
Structures pour les scores de qualité par colonne et par dimension.

3 DIMENSIONS :
    Completeness → % valeurs non-nulles sur colonnes nullable=false
    Validity     → % valeurs respectant les règles metadata (type, range, enum, pattern, format)
    Uniqueness   → % unicité sur colonnes identifier=true

SCORE PAR COLONNE :
    Chaque colonne a son propre score par dimension applicable.
    Si une dimension ne s'applique pas à une colonne
    (ex: Uniqueness sur colonne identifier=false),
    elle est None (pas calculée, pas comptée).

SCORE GLOBAL :
    Moyenne pondérée des dimensions applicables.
    Poids configurables dans settings.py.
"""
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
                if isinstance(val, (dict, list)) and len(val) == 0:
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
    ROW_KEYS = {"null_rows", "duplicate_rows", "invalid_rows"}
    for k, v in detail.items():
        if k in ROW_KEYS and isinstance(v, list):
            result[k] = [r + ROW_DISPLAY_OFFSET for r in v]
        else:
            result[k] = v
    return result


@dataclass
class ColumnQualityScore:
    """
    Score de qualité d'une seule colonne sur les 3 dimensions.

    completeness : None si nullable=true (pas applicable)
    uniqueness   : None si identifier=false (pas applicable)
    validity     : None si aucune règle de validation définie
    """
    column_name:   str
    business_name: str

    # Scores 0.0 à 100.0 — None si la dimension ne s'applique pas
    completeness: Optional[float] = None
    validity:     Optional[float] = None
    uniqueness:   Optional[float] = None

    # Détail des violations par dimension
    completeness_detail: dict = field(default_factory=dict)
    validity_detail:     dict = field(default_factory=dict)
    uniqueness_detail:   dict = field(default_factory=dict)

    @property
    def global_score(self) -> Optional[float]:
        """
        Moyenne des dimensions applicables pour cette colonne.
        Retourne None si aucune dimension n'est applicable.
        """
        scores = [s for s in [self.completeness, self.validity, self.uniqueness]
                  if s is not None]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 1)

    def to_dict(self) -> dict:
        return _to_native({
            "column_name":   self.column_name,
            "business_name": self.business_name,
            "scores": {
                "completeness": self.completeness,
                "validity":     self.validity,
                "uniqueness":   self.uniqueness,
                "global":       self.global_score,
            },
            "details": {
                "completeness": _offset_detail(self.completeness_detail),
                "validity":     _offset_detail(self.validity_detail),
                "uniqueness":   _offset_detail(self.uniqueness_detail),
            },
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
            completeness_detail=details.get("completeness", {}),
            validity_detail=details.get("validity", {}),
            uniqueness_detail=details.get("uniqueness", {}),
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
        """Score Uniqueness global = moyenne des colonnes concernées."""
        scores = [c.uniqueness for c in self.columns if c.uniqueness is not None]
        return round(sum(scores) / len(scores), 1) if scores else 100.0

    @property
    def global_score(self) -> float:
        """
        Score global pondéré des 3 dimensions.
        Poids depuis settings : completeness=0.4, validity=0.4, uniqueness=0.2
        """
        from config.settings import get_settings
        s = get_settings()
        return round(
            self.completeness_global * s.weight_completeness
            + self.validity_global   * s.weight_validity
            + self.uniqueness_global * s.weight_uniqueness,
            1,
        )

    def to_dict(self) -> dict:
        return _to_native({
            "label":      self.label,
            "sector":     self.sector,
            "job_id":     self.job_id,
            "total_rows": self.total_rows,
            "global_scores": {
                "completeness": self.completeness_global,
                "validity":     self.validity_global,
                "uniqueness":   self.uniqueness_global,
                "global":       self.global_score,
            },
            "columns": [c.to_dict() for c in self.columns],
        })

    @classmethod
    def from_dict(cls, d: dict) -> QualityReport:
        return cls(
            label=d.get("label", ""),
            sector=d.get("sector", ""),
            job_id=d.get("job_id", ""),
            total_rows=d.get("total_rows", 0),
            columns=[
                ColumnQualityScore.from_dict(c)
                for c in d.get("columns", [])
            ],
        )