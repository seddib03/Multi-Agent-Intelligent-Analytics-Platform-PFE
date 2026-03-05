"""
agent/nodes/ingestion_node.py — NODE 1
Charge dataset CSV + metadata JSON, upload Bronze MinIO.
"""
from __future__ import annotations
import json, logging, shutil
from pathlib import Path
import pandas as pd
from agent.state import AgentState
from config.settings import get_settings
from core.minio_client import MinioClient
from models.metadata_schema import parse_metadata

logger = logging.getLogger(__name__)

def ingestion_node(state: AgentState) -> dict:
    logger.info(">>> NODE 1 : Ingestion")
    settings = get_settings()

    # Charger le metadata JSON
    with open(state["metadata_path"], encoding="utf-8") as f:
        raw_meta = json.load(f)

    # Parser le metadata (liste ou dict avec clé "columns")
    if isinstance(raw_meta, list):
        meta_list = raw_meta
    elif isinstance(raw_meta, dict) and "columns" in raw_meta:
        meta_list = raw_meta["columns"]
    else:
        meta_list = raw_meta

    metadata = parse_metadata(meta_list)

    # Charger le CSV avec Pandas
    df = pd.read_csv(state["dataset_path"], dtype=str, keep_default_na=True)
    logger.info("Dataset chargé — %d lignes x %d colonnes", len(df), len(df.columns))

    # Détecter le secteur depuis le metadata si présent
    sector = "unknown"
    if isinstance(raw_meta, dict):
        sector = raw_meta.get("sector", raw_meta.get("secteur", "unknown"))

    # Upload Bronze MinIO
    minio = MinioClient()
    filename = Path(state["dataset_path"]).name
    bronze_path = minio.upload_bronze(
        state["job_id"], sector,
        state["dataset_path"], filename
    )

    # Sérialiser le DataFrame pour le state LangGraph
    raw_df_dict = {
        "columns": df.columns.tolist(),
        "data":    df.values.tolist(),
    }

    # Sérialiser les ColumnMeta (dataclasses → dicts)
    import dataclasses
    meta_dicts = [dataclasses.asdict(m) for m in metadata]

    logger.info("NODE 1 terminé — Bronze: %s", bronze_path)
    return {
        "raw_df":      raw_df_dict,
        "metadata":    meta_dicts,
        "bronze_path": bronze_path,
        "sector":      sector,
    }