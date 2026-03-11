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


def quality_node(state: AgentState) -> dict:
    logger.info(">>> NODE 3 : Quality Scoring — démarrage")

    df       = _load_df(state["raw_df"])
    metadata = _load_metadata(state["metadata"])
    business_rules = state.get("business_rules", [])

    if business_rules:
        logger.info("  %d business rules à traiter", len(business_rules))

    quality_before = compute_quality_report(
        metadata=metadata,
        label="AVANT",
        sector=state.get("sector", "unknown"),
        job_id=state["job_id"],
        duckdb_path=state["duckdb_path"],
        business_rules=business_rules,
    )

    logger.info(
        "NODE 3 terminé — score global: %.1f%% "
        "(Completeness: %.1f%% | Validity: %.1f%% | Uniqueness: %.1f%% "
        "| Accuracy: %.1f%% | Consistency: %.1f%%)",
        quality_before.global_score,
        quality_before.completeness_global,
        quality_before.validity_global,
        quality_before.uniqueness_global,
        quality_before.accuracy_global,
        quality_before.consistency_global,
    )
    return {"quality_before": quality_before.to_dict(apply_offsets=False)}