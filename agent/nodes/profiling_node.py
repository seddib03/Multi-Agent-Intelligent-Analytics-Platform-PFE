"""
agent/nodes/profiling_node.py
NODE 2 — Profiling
─────────────────────────────
Calcule les statistiques de base pour chaque colonne du dataset :
    - Nombre et % de valeurs nulles
    - Nombre de valeurs uniques
    - Exemples de valeurs
Ce résumé est stocké dans le state et utilisé pour les logs.
La mesure de qualité réelle est faite dans quality_node (NODE 3).
"""
from __future__ import annotations

import logging

import pandas as pd

from agent.state import AgentState

logger = logging.getLogger(__name__)


def _load_df(df_dict: dict) -> pd.DataFrame:
    """Reconstruit un DataFrame Pandas depuis le dict sérialisé du state."""
    if df_dict is None:
        return pd.DataFrame()
    return pd.DataFrame(
        data=df_dict.get("data", []),
        columns=df_dict.get("columns", []),
    )


def profiling_node(state: AgentState) -> dict:
    logger.info(">>> NODE 2 : Profiling — démarrage")

    df    = _load_df(state["raw_df"])
    total = len(df)

    summary = {}
    for col in df.columns:
        s          = df[col]
        null_count = int(s.isna().sum())
        summary[col] = {
            "total":         total,
            "null_count":    null_count,
            "null_pct":      round(null_count / total * 100, 1) if total > 0 else 0.0,
            "unique_count":  int(s.nunique()),
            "sample_values": s.dropna().head(3).tolist(),
        }

    logger.info(
        "NODE 2 terminé — %d colonnes profilées | %d lignes au total",
        len(summary), total,
    )
    return {"profiling_summary": summary}