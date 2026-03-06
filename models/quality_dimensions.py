from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DimensionName(str, Enum):
    """
    Noms officiels des 5 dimensions de qualité.

    Utiliser une Enum plutôt que des strings libres :
    → Impossible d'écrire "completnes" par erreur
    → L'IDE autocompléte le nom correct
    → Refactoring sûr (renommer dans toute la codebase)
    """

    COMPLETENESS = "completeness"
    UNIQUENESS   = "uniqueness"
    VALIDITY     = "validity"
    CONSISTENCY  = "consistency"
    ACCURACY     = "accuracy"


class Severity(str, Enum):
    """
    Niveaux de sévérité d'un problème de qualité.

    BLOCKING → La ligne est inutilisable (ID null, doublon exact)
    MAJOR    → Problème important qui biaise les analyses
    MINOR    → Anomalie à signaler mais non bloquante
    """

    BLOCKING = "BLOCKING"
    MAJOR    = "MAJOR"
    MINOR    = "MINOR"


@dataclass
class DimensionScore:
    """
    Score d'une dimension de qualité pour un dataset.

    Exemple :
        DimensionScore(
            name=DimensionName.COMPLETENESS,
            score=81.25,
            total_checks=16,
            passed_checks=13,
            failed_checks=3,
            details=["contrat_id null ligne 7", ...]
        )
    """

    # Nom de la dimension
    name: DimensionName

    # Score entre 0.0 et 100.0
    # Formule : (passed_checks / total_checks) * 100
    score: float

    # Nombre total de vérifications effectuées
    total_checks: int

    # Nombre de vérifications réussies
    passed_checks: int

    # Nombre de vérifications échouées
    failed_checks: int

    # Liste des problèmes détectés (texte lisible)
    details: list[str] = field(default_factory=list)

    # Lignes exactes concernées par les problèmes
    # Format : {numéro_ligne: description_problème}
    affected_rows: dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Validation automatique après initialisation.

        __post_init__ est appelé par Python automatiquement
        après __init__ dans une dataclass.
        On l'utilise pour vérifier la cohérence des données.
        """
        if not 0.0 <= self.score <= 100.0:
            raise ValueError(
                f"Score {self.score} invalide pour {self.name}. "
                f"Doit être entre 0.0 et 100.0."
            )

        if self.passed_checks + self.failed_checks != self.total_checks:
            raise ValueError(
                f"Incohérence : passed({self.passed_checks}) + "
                f"failed({self.failed_checks}) != total({self.total_checks})"
            )


@dataclass
class QualityDimensionsReport:
    """
    Rapport complet des 5 dimensions de qualité.

    Utilisé à 2 moments dans le pipeline :
        1. AVANT cleaning → mesure la qualité initiale
        2. APRÈS cleaning → mesure l'amélioration

    Exemple d'usage :
        report_before = QualityDimensionsReport(...)
        report_after  = QualityDimensionsReport(...)
        gain = report_after.global_score - report_before.global_score
    """

    # Scores individuels par dimension
    completeness: DimensionScore
    uniqueness:   DimensionScore
    validity:     DimensionScore
    consistency:  DimensionScore
    accuracy:     DimensionScore

    # Contexte
    sector:    str
    timestamp: str
    label:     str  # "AVANT" ou "APRÈS"

    @property
    def global_score(self) -> float:
        """
        Score global = moyenne pondérée des 5 dimensions.

        Pondération :
            Completeness : 25% → donnée manquante = inutilisable
            Uniqueness   : 20% → doublon = biais statistique
            Validity     : 25% → règle métier non respectée
            Consistency  : 15% → incohérence entre colonnes
            Accuracy     : 15% → valeur impossible

        Pourquoi une propriété (@property) et pas un champ ?
        → Calculé automatiquement depuis les scores individuels
        → Toujours cohérent, jamais désynchronisé
        """
        weights = {
            "completeness": 0.25,
            "uniqueness":   0.20,
            "validity":     0.25,
            "consistency":  0.15,
            "accuracy":     0.15,
        }

        return round(
            self.completeness.score * weights["completeness"]
            + self.uniqueness.score   * weights["uniqueness"]
            + self.validity.score     * weights["validity"]
            + self.consistency.score  * weights["consistency"]
            + self.accuracy.score     * weights["accuracy"],
            2,
        )

    @property
    def all_dimensions(self) -> list[DimensionScore]:
        """
        Retourne les 5 dimensions sous forme de liste.

        Utile pour itérer sur toutes les dimensions
        sans répéter le code pour chacune.
        """
        return [
            self.completeness,
            self.uniqueness,
            self.validity,
            self.consistency,
            self.accuracy,
        ]

    def to_dict(self) -> dict:
        """
        Convertit le rapport en dict pour l'API JSON.

        Returns:
            Dict sérialisable en JSON avec tous les scores.
        """
        return {
            "label":     self.label,
            "sector":    self.sector,
            "timestamp": self.timestamp,
            "global_score": self.global_score,
            "dimensions": {
                dim.name.value: {
                    "score":        dim.score,
                    "total_checks": dim.total_checks,
                    "passed":       dim.passed_checks,
                    "failed":       dim.failed_checks,
                    "details":      dim.details,
                    "affected_rows": dim.affected_rows,
                }
                for dim in self.all_dimensions
            },
        }