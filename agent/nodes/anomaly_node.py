"""
agent/nodes/anomaly_node.py
NODE 4 — Anomaly Detection
─────────────────────────────
Lit le QualityReport (NODE 3) pour identifier précisément
les lignes et colonnes en anomalie.

Pour chaque problème détecté, propose 3 actions :
    action_1 → Conservative  (flag, imputer)
    action_2 → Modérée       (remplacer, clipper)
    action_3 → Agressive     (supprimer la ligne)

Produit un CleaningPlan qui sera enrichi par le LLM (NODE 5)
puis validé par l'utilisateur avant exécution (NODE 6).
"""
from __future__ import annotations

import logging

import pandas as pd

from agent.state import AgentState
from core.anomaly_engine import detect_anomalies
from models.metadata_schema import ColumnMeta
from models.quality_report import QualityReport

logger = logging.getLogger(__name__)


def _load_df(df_dict: dict) -> pd.DataFrame:
    if df_dict is None:
        return pd.DataFrame()
    return pd.DataFrame(
        data=df_dict.get("data", []),
        columns=df_dict.get("columns", []),
    )


def _load_metadata(meta_dicts: list) -> list[ColumnMeta]:
    result = []
    for d in (meta_dicts or []):
        try:
            result.append(ColumnMeta(**d))
        except Exception as e:
            logger.warning("Impossible de charger ColumnMeta : %s", e)
    return result


def anomaly_node(state: AgentState) -> dict:
    logger.info(">>> NODE 4 : Anomaly Detection — démarrage")

    df             = _load_df(state["raw_df"])
    metadata       = _load_metadata(state["metadata"])
    quality_before = QualityReport.from_dict(state["quality_before"])

    cleaning_plan = detect_anomalies(
        df=df,
        metadata=metadata,
        quality_report=quality_before,
        job_id=state["job_id"],
        sector=state.get("sector", "unknown"),
    )

    logger.info(
        "NODE 4 terminé — %d anomalie(s) détectée(s) sur %d colonne(s)",
        len(cleaning_plan.anomalies),
        len(metadata),
    )
    return {"cleaning_plan": cleaning_plan}