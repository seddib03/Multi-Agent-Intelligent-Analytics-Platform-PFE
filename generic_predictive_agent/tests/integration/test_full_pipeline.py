"""
schemas/task_config.py — SHARED (Dev 1 + Dev 2)

Contrat d'interface entre :
- Dev 1 (data_layer) qui PRODUIT un TaskConfig
- Dev 2 (ml_layer)   qui CONSOMME un TaskConfig

Dev 1 remplit tous les champs après profiling + task detection.
Dev 2 lit ces champs pour lancer l'entraînement.
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class TaskConfig:
    """
    Contrat d'interface Dev 1 → Dev 2.
    Produit par data_layer, consommé par ml_layer.
    """

    # ── Identifiant du job ─────────────────────────────────────────
    job_id: str = ""

    # ── Tâche ML détectée par Dev 1 ───────────────────────────────
    task_type: str = ""
    # "classification" | "regression" | "clustering"

    # ── Colonne cible ─────────────────────────────────────────────
    target_column: Optional[str] = None
    # None pour clustering (pas de colonne cible)

    # ── Features retenues par Dev 1 ───────────────────────────────
    feature_names: list = field(default_factory=list)
    # Colonnes sélectionnées après feature selection

    # ── Données préprocessées prêtes pour l'entraînement ──────────
    X_train: Optional[object] = None   # pd.DataFrame
    X_test:  Optional[object] = None   # pd.DataFrame
    y_train: Optional[object] = None   # pd.Series (None si clustering)
    y_test:  Optional[object] = None   # pd.Series (None si clustering)

    # ── Contexte métier (depuis la query utilisateur) ─────────────
    user_query: str = ""
    sector: str = ""
    # ex: "insurance", "retail", "transport"

    # ── Profiling summary (pour les LLMs de Dev 2) ────────────────
    dataset_summary: dict = field(default_factory=dict)
    # ex: {"n_rows": 500, "n_cols": 8, "missing_pct": 0.02}

    # ── Stratégie recommandée par LLM Dev 1 ───────────────────────
    llm_strategy: dict = field(default_factory=dict)
    # ex: {"recommended_models": ["XGBoost", "RandomForest"],
    #      "reason": "dataset tabulaire avec features mixtes"}