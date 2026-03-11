from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AnomalyType(str, Enum):
    """Types d'anomalies détectables selon le metadata."""
    NULL_VALUE       = "null_value"        # Completeness
    DUPLICATE        = "duplicate"         # Uniqueness
    WRONG_TYPE       = "wrong_type"        # Validity
    OUT_OF_RANGE     = "out_of_range"      # Validity
    INVALID_ENUM     = "invalid_enum"      # Validity
    PATTERN_MISMATCH = "pattern_mismatch"  # Validity
    INVALID_DATE     = "invalid_date"      # Validity
    CUSTOM_RULE      = "custom_rule"       # Business Rules (Consistency/Accuracy)


class CleaningAction(str, Enum):
    """Actions de nettoyage disponibles pour cleaning_engine."""
    DROP_ROWS         = "drop_rows"          # Supprimer les lignes concernées
    DROP_DUPLICATES   = "drop_duplicates"    # Supprimer les doublons
    IMPUTE_MEDIAN     = "impute_median"      # Imputer la médiane
    IMPUTE_MODE       = "impute_mode"        # Imputer la valeur la plus fréquente
    IMPUTE_CONSTANT   = "impute_constant"    # Imputer une valeur fixe
    CAST_TYPE         = "cast_type"          # Convertir le type
    CLIP_RANGE        = "clip_range"         # Clipper aux bornes min/max
    REPLACE_ENUM      = "replace_enum"       # Remplacer par valeur enum la plus proche
    FLAG_ONLY         = "flag_only"          # Signaler sans modifier
    PARSE_DATE        = "parse_date"         # Parser la date selon le format


class UserDecision(str, Enum):
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


@dataclass
class AnomalyItem:
    """
    Une anomalie détectée sur une colonne.

    Contient :
        - La description du problème (lisible par l'user)
        - Les lignes concernées (index Pandas)
        - 3 actions proposées (du plus conservateur au plus agressif)
        - La dimension de qualité impactée
    """
    anomaly_id:  str
    column_name: str
    dimension:   str   # "completeness", "validity", "uniqueness"
    anomaly_type: AnomalyType

    # Explication claire du problème pour l'user
    problem_description: str

    # Lignes concernées (index Pandas, 0-based)
    affected_rows: list[int]

    # Nombre de valeurs concernées
    affected_count: int

    # Pourcentage du dataset concerné
    affected_pct: float

    # 3 stratégies proposées (classées de plus sûre à plus agressive)
    action_1: CleaningAction  # Conservative (flag, impute)
    action_2: CleaningAction  # Modérée
    action_3: CleaningAction  # Agressive (drop)

    # Justification de chaque action
    justification_1: str
    justification_2: str
    justification_3: str

    # Source de l'anomalie ("metadata" ou "business_rule")
    anomaly_source: str = "metadata"

    # Valeurs invalides trouvées (sample pour affichage)
    sample_invalid_values: list = field(default_factory=list)

    # Paramètres additionnels (ex: valeur de remplacement)
    params: dict = field(default_factory=dict)

    # Décision de l'user (remplie après validation)
    user_decision: Optional[UserDecision] = None
    chosen_action: Optional[CleaningAction] = None
    user_params:   Optional[dict] = None

    def to_dict(self, apply_offsets: bool = True) -> dict:
        from models.quality_report import ROW_DISPLAY_OFFSET, _to_native
        
        rows = self.affected_rows[:50]
        if apply_offsets:
            rows = [r + ROW_DISPLAY_OFFSET for r in rows]

        return _to_native({
            "anomaly_id":    self.anomaly_id,
            "column_name":   self.column_name,
            "dimension":     self.dimension,
            "anomaly_type":  self.anomaly_type.value,
            "anomaly_source": self.anomaly_source,
            "problem":       self.problem_description,
            "affected_rows": rows,
            "affected_count": self.affected_count,
            "affected_pct":  round(self.affected_pct, 2),
            "sample_invalid": [str(v) for v in self.sample_invalid_values[:5]],
            "proposed_actions": {
                "action_1": {
                    "action":        self.action_1.value,
                    "justification": self.justification_1,
                },
                "action_2": {
                    "action":        self.action_2.value,
                    "justification": self.justification_2,
                },
                "action_3": {
                    "action":        self.action_3.value,
                    "justification": self.justification_3,
                },
            },
            "user_decision":  self.user_decision.value if self.user_decision else None,
            "chosen_action":  self.chosen_action.value if self.chosen_action else None,
        })


@dataclass
class CleaningPlan:
    """Plan complet avec toutes les anomalies et les décisions user."""
    plan_id:  str
    job_id:   str
    sector:   str
    anomalies: list[AnomalyItem] = field(default_factory=list)

    # Analyse LLM globale du dataset
    llm_summary: str = ""

    # Reformulations LLM par anomalie {anomaly_id: texte_reformulé}
    llm_reformulations: dict = field(default_factory=dict)

    status: str = "proposed"  # proposed → validated → executed

    @property
    def approved_anomalies(self) -> list[AnomalyItem]:
        """Anomalies avec décision approved ou modified."""
        return [
            a for a in self.anomalies
            if a.user_decision in (UserDecision.APPROVED, UserDecision.MODIFIED)
        ]

    @property
    def is_fully_validated(self) -> bool:
        """True si toutes les anomalies ont une décision."""
        return all(a.user_decision is not None for a in self.anomalies)

    def to_dict(self, apply_offsets: bool = True) -> dict:
        from models.quality_report import _to_native
        return _to_native({
            "plan_id":  self.plan_id,
            "job_id":   self.job_id,
            "sector":   self.sector,
            "status":   self.status,
            "llm_summary": self.llm_summary,
            "total_anomalies": len(self.anomalies),
            "anomalies": [a.to_dict(apply_offsets=apply_offsets) for a in self.anomalies],
            "llm_reformulations": self.llm_reformulations,
        })
