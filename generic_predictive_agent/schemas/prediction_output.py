"""
schemas/prediction_output.py — SHARED (Dev 1 + Dev 2)

Contrat d'interface entre :
- Dev 2 (ml_layer)   qui PRODUIT un PredictionOutput
- Orchestrateur      qui CONSOMME un PredictionOutput

Dev 2 remplit tous les champs après évaluation + sélection.
L'orchestrateur retourne ce dict à l'UI.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelResult:
    """Résultat d'un modèle individuel."""
    name:          str   = ""
    metrics:       dict  = field(default_factory=dict)
    training_time: float = 0.0
    # ex metrics classification : {"accuracy": 0.92, "f1": 0.89, "auc": 0.95}
    # ex metrics regression      : {"rmse": 12.3, "mae": 9.1, "r2": 0.87}
    # ex metrics clustering      : {"silhouette": 0.68, "inertia": 234.5}


@dataclass
class PredictionOutput:
    """
    Contrat d'interface Dev 2 → Orchestrateur.
    Produit par ml_layer, retourné à l'UI via l'orchestrateur.
    """

    # ── Identifiant ───────────────────────────────────────────────
    job_id:    str = ""
    task_type: str = ""

    # ── Meilleur modèle sélectionné ───────────────────────────────
    best_model_name:    str  = ""
    best_model_metrics: dict = field(default_factory=dict)

    # ── Comparaison tous les modèles ──────────────────────────────
    all_models: list = field(default_factory=list)
    # liste de ModelResult

    # ── Feature importance (si disponible) ───────────────────────
    feature_importance: list = field(default_factory=list)
    # ex: [{"feature": "age", "importance": 0.35}, ...]

    # ── Prédictions sur X_test ────────────────────────────────────
    predictions: list = field(default_factory=list)

    # ── Interprétation LLM (Dev 2) ────────────────────────────────
    llm_explanation:     str  = ""
    llm_recommendations: list = field(default_factory=list)
    # ex: ["Concentrez-vous sur les clients âgés de 60+", ...]

    # ── Statut ────────────────────────────────────────────────────
    status: str  = "completed"
    # "completed" | "failed"
    error:  Optional[str] = None

    def to_dict(self) -> dict:
        """Sérialise pour retour JSON à l'orchestrateur."""
        return {
            "job_id":               self.job_id,
            "task_type":            self.task_type,
            "best_model":           self.best_model_name,
            "best_model_metrics":   self.best_model_metrics,
            "all_models":           [
                {"name": m.name, "metrics": m.metrics, "training_time": m.training_time}
                for m in self.all_models
            ],
            "feature_importance":   self.feature_importance,
            "llm_explanation":      self.llm_explanation,
            "llm_recommendations":  self.llm_recommendations,
            "status":               self.status,
            "error":                self.error,
        }