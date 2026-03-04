from __future__ import annotations

import logging

from agent.state import AgentState
from core.data_profiler import run_profiling
from core.df_serializer import dict_to_df


logger = logging.getLogger(__name__)


def profiling_node(state: AgentState) -> dict:
    """
    Profile le dataset et détecte toutes les anomalies.

    Args:
        state: Doit contenir raw_df rempli par ingestion_node

    Returns:
        Dict avec profiling_report et profile_before mis à jour.
    """
    logger.info(">>> NODE 2 : Profiling — démarrage")

    raw_df_dict = state.get("raw_df")
    if raw_df_dict is None:
        error_msg = "raw_df absent du state — ingestion_node a-t-il réussi ?"
        logger.error(error_msg)
        return {"status": "error", "errors": [error_msg]}

    raw_df = dict_to_df(raw_df_dict)
    if raw_df.is_empty():
        error_msg = "raw_df absent du state — ingestion_node a-t-il réussi ?"
        logger.error(error_msg)
        return {"status": "error", "errors": [error_msg]}

    # Lancer le profiling complet
    profiling_report = run_profiling(raw_df)

    # Snapshot "AVANT" pour la comparaison finale
    profile_before = profiling_report.to_dict()
    profile_before["label"] = "AVANT"

    logger.info(
        "NODE 2 terminé — %d anomalies détectées "
        "(%d nulls, %d doublons, %d outliers)",
        profiling_report.total_anomalies,
        len(profiling_report.anomalies_by_type.get("null", [])),
        len(profiling_report.anomalies_by_type.get("duplicate", [])),
        len(profiling_report.anomalies_by_type.get("outlier", [])),
    )

    return {
        "profiling_report": profiling_report,
        "profile_before":   profile_before,
    }