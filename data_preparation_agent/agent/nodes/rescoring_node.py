# rescoring_node.py
"""
agent/nodes/rescoring_node.py
NODE 7 — Rescoring
─────────────────────────────
Recalcule les 5 dimensions de qualité APRÈS nettoyage.

Utilise le même quality_engine que NODE 3 mais sur clean_df
au lieu de raw_df. Le label est "APRÈS" pour la comparaison.

Le QualityReport "APRÈS" est comparé au "AVANT" dans la réponse
finale de l'API (POST /jobs/{id}/validate) pour afficher le gain.
"""
from __future__ import annotations

import logging

import pandas as pd

from agent.state import AgentState
from core.quality_engine import compute_quality_report
from models.metadata_schema import ColumnMeta

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


def rescoring_node(state: AgentState) -> dict:
    logger.info(">>> NODE 7 : Rescoring — démarrage")

    df       = _load_df(state["clean_df"])
    metadata = _load_metadata(state["metadata"])
    business_rules = state.get("business_rules", [])
    br_tests = state.get("business_rule_tests")

    logger.info("clean_df reçu — %d lignes x %d colonnes", len(df), len(df.columns))

    # ── Mettre à jour DuckDB avec les données nettoyées ───────────────────
    import duckdb
    with duckdb.connect(state["duckdb_path"]) as conn:
        conn.execute("DROP TABLE IF EXISTS raw_data")
        conn.execute("CREATE TABLE raw_data AS SELECT * FROM df")
    
    logger.info("DuckDB mis à jour avec clean_df avant rescoring")

    quality_after, _ = compute_quality_report(
        metadata=metadata,
        label="APRÈS",
        sector=state.get("sector", "unknown"),
        job_id=state["job_id"],
        duckdb_path=state["duckdb_path"],
        business_rules=business_rules,
        precomputed_br_tests=br_tests,
    )

    # Calculer le gain par rapport au score AVANT
    quality_before = state.get("quality_before")
    gain = 0.0
    if quality_before:
        before_score = quality_before.get("global_scores", {}).get("global", 0.0)
        gain = round(quality_after.global_score - before_score, 1)

    logger.info(
        "NODE 7 terminé — score global APRÈS: %.1f%% "
        "(Completeness: %.1f%% | Validity: %.1f%% | Uniqueness: %.1f%% "
        "| Accuracy: %.1f%% | Consistency: %.1f%%) | gain: %+.1f%%",
        quality_after.global_score,
        quality_after.completeness_global,
        quality_after.validity_global,
        quality_after.uniqueness_global,
        quality_after.accuracy_global,
        quality_after.consistency_global,
        gain,
    )
    return {"quality_after": quality_after.to_dict()}