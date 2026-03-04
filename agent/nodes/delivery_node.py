"""
agent/nodes/delivery_node.py
─────────────────────────────
NODE 7 — Livraison finale : structurer, enrichir, persister.

IDENTIQUE À V1 dans son principe — 3 responsabilités :
    1. Sélectionner uniquement les colonnes du metadata
    2. Ajouter les colonnes de tracking (_sector, _quality_score...)
    3. Persister dans le Gold Layer (DuckDB)
"""

from __future__ import annotations

import logging
from datetime import datetime

import polars as pl

from agent.state import AgentState
from config.settings import get_settings
from core.df_serializer import df_to_dict, dict_to_df
from core.storage_manager import StorageManager

logger = logging.getLogger(__name__)


def delivery_node(state: AgentState) -> dict:
    """
    Prépare et livre le dataset final.

    Args:
        state: Doit contenir clean_df, dimensions_after, sector

    Returns:
        Dict avec final_df, silver_path, status=success.
    """
    logger.info(">>> NODE 7 : Delivery — démarrage")

    clean_df_dict = state.get("clean_df")
    sector        = state.get("sector", "unknown")
    job_id        = state.get("job_id", "")
    settings      = get_settings()

    if clean_df_dict is None:
        return {"status": "error", "errors": ["clean_df absent du state"]}

    # Reconvertir de dict → DataFrame Polars (clean_df est stocké sérialisé)
    clean_df = dict_to_df(clean_df_dict)

    # ── 1. Récupérer le score global APRÈS ───────────────────────────────────
    dimensions_after = state.get("dimensions_after")
    quality_score = (
        dimensions_after.global_score
        if dimensions_after else 0.0
    )

    # ── 2. Ajouter les colonnes de tracking ──────────────────────────────────
    ingestion_ts = datetime.now().isoformat()

    final_df = clean_df.with_columns([
        pl.lit(sector).alias("_sector"),
        pl.lit(ingestion_ts).alias("_ingestion_ts"),
        pl.lit(quality_score).alias("_quality_score"),
        pl.lit(settings.agent_version).alias("_agent_version"),
        pl.lit(job_id).alias("_job_id"),
    ])

    # ── 3. Sauvegarder en Silver ──────────────────────────────────────────────
    silver_dir  = settings.silver_dir / sector
    silver_dir.mkdir(parents=True, exist_ok=True)
    silver_path = silver_dir / "clean_dataset.parquet"

    final_df.write_parquet(str(silver_path))
    logger.info("Silver sauvegardé : %s", silver_path)

    # ── 4. Persister dans Gold (DuckDB) ───────────────────────────────────────
    storage = StorageManager()
    storage.save_to_gold(
        job_id=job_id,
        sector=sector,
        status="success",
        bronze_path=state.get("bronze_path", ""),
        silver_path=str(silver_path),
        quality_report=_build_quality_report(state),
        cleaning_log=state.get("cleaning_log") or [],
    )

    logger.info(
        "NODE 7 terminé — %d lignes livrées | "
        "score: %.1f | status: SUCCESS",
        final_df.height,
        quality_score,
    )

    return {
        "final_df":   df_to_dict(final_df),
        "silver_path": str(silver_path),
        "status":      "success",
        "completed_at": datetime.now().isoformat(),
    }


def _build_quality_report(state: AgentState) -> dict:
    """
    Construit le rapport qualité final pour le Gold Layer.
    """
    dimensions_before = state.get("dimensions_before")
    dimensions_after  = state.get("dimensions_after")

    return {
        "job_id":       state.get("job_id", ""),
        "sector":       state.get("sector", "unknown"),
        "llm_analysis": state.get("llm_analysis", ""),
        "llm_evaluation": state.get("llm_evaluation", ""),
        "dimensions_before": (
            dimensions_before.to_dict() if dimensions_before else {}
        ),
        "dimensions_after": (
            dimensions_after.to_dict() if dimensions_after else {}
        ),
        "cleaning_plan": (
            state["cleaning_plan"].to_dict()
            if state.get("cleaning_plan") else {}
        ),
    }