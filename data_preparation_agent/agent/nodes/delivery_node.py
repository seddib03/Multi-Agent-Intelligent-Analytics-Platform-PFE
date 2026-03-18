# delivery_node.py
"""
agent/nodes/delivery_node.py
NODE 8 — Delivery
─────────────────────────────
Dernière étape du pipeline.

1. Ajoute les colonnes de tracking au dataset nettoyé :
       _sector, _job_id, _ingestion_ts, _agent_version, _quality_score

2. Upload Silver dans MinIO :
       bucket silver / {sector}/{job_id}/clean.csv

3. Upload Gold dans MinIO :
       bucket gold / {sector}/{job_id}/quality_report.json
       bucket gold / {sector}/{job_id}/cleaning_log.json

Le Silver est le dataset final prêt pour l'analyse ou
le Predictive Agent qui lira directement ce Parquet.

Le Gold contient l'historique complet du run
(scores AVANT/APRÈS, plan de nettoyage, logs).
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from agent.state import AgentState
from config.settings import get_settings
from core.minio_client import MinioClient

logger = logging.getLogger(__name__)


def _load_df(df_dict: dict) -> pd.DataFrame:
    if df_dict is None:
        return pd.DataFrame()
    return pd.DataFrame(
        data=df_dict.get("data", []),
        columns=df_dict.get("columns", []),
    )


def delivery_node(state: AgentState) -> dict:
    logger.info(">>> NODE 8 : Delivery — démarrage")

    df       = _load_df(state["clean_df"])
    job_id   = state["job_id"]
    sector   = state.get("sector", "unknown")
    settings = get_settings()
    minio    = MinioClient()
    now      = datetime.now().isoformat()

    # ── 1. Ajouter les colonnes de tracking ───────────────────────────────
    df["_sector"]        = sector
    df["_job_id"]        = job_id
    df["_ingestion_ts"]  = now
    df["_agent_version"] = settings.agent_version

    quality_after = state.get("quality_after")
    if quality_after:
        df["_quality_score"] = quality_after.get("global_scores", {}).get("global", 0)

    logger.info(
        "Dataset final : %d lignes x %d colonnes (tracking inclus)",
        len(df), len(df.columns),
    )

    # ── 2. Upload Silver (Parquet) ────────────────────────────────────────
    silver_path = minio.upload_silver(
        job_id=job_id,
        sector=sector,
        clean_df=df,
    )

    # ── 3. Construire le rapport Gold ─────────────────────────────────────
    quality_before = state.get("quality_before")
    cleaning_plan  = state.get("cleaning_plan")

    after_score  = quality_after.get("global_scores", {}).get("global", 0) if quality_after else 0
    before_score = quality_before.get("global_scores", {}).get("global", 0) if quality_before else 0

    quality_report = {
        "job_id":        job_id,
        "sector":        sector,
        "timestamp":     now,
        "agent_version": settings.agent_version,
        "quality": {
            "before": quality_before if quality_before else {},
            "after":  quality_after  if quality_after  else {},
            "gain":   round(after_score - before_score, 1),
        },
        "plan":         cleaning_plan.to_dict() if cleaning_plan else {},
        "cleaning_log": state.get("cleaning_log", []),
    }

    # ── 4. Upload Gold (JSON) ─────────────────────────────────────────────
    gold_path = minio.upload_gold(
        job_id=job_id,
        sector=sector,
        report=quality_report,
        filename="quality_report.json",
    )

    # Log de nettoyage séparé
    minio.upload_gold(
        job_id=job_id,
        sector=sector,
        report={"cleaning_log": state.get("cleaning_log", [])},
        filename="cleaning_log.json",
    )

    logger.info(
        "NODE 8 terminé — Silver: %s | Gold: %s | status: SUCCESS",
        silver_path, gold_path,
    )
    return {
        "silver_path":  silver_path,
        "gold_path":    gold_path,
        "status":       "success",
        "completed_at": now,
    }