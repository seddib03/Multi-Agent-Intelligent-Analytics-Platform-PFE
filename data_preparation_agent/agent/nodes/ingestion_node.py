# ingestion_node.py
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

    metadata_path = state.get("metadata_path", "")

    # ── Metadata optionnel (absent en mode Import léger) ──────────────────
    if metadata_path and Path(metadata_path).exists():
        with open(metadata_path, encoding="utf-8") as f:
            raw_meta = json.load(f)

        if isinstance(raw_meta, list):
            meta_list = raw_meta
        elif isinstance(raw_meta, dict) and "columns" in raw_meta:
            meta_list = raw_meta["columns"]
        else:
            meta_list = raw_meta

        metadata = parse_metadata(meta_list)
        sector = "unknown"
        business_rules = []
        if isinstance(raw_meta, dict):
            sector = raw_meta.get("sector", raw_meta.get("secteur", "unknown"))
            business_rules = raw_meta.get("business_rules", [])
    else:
        logger.info("Pas de metadata fourni — mode Import léger")
        raw_meta = {}
        metadata = []
        business_rules = []
        sector = state.get("sector", "unknown")

    # Charger le CSV avec Pandas
    df = pd.read_csv(state["dataset_path"], dtype=str, keep_default_na=True)
    logger.info("Dataset chargé — %d lignes x %d colonnes", len(df), len(df.columns))

    # Upload Bronze MinIO
    minio = MinioClient()
    filename = Path(state["dataset_path"]).name
    bronze_path = minio.upload_bronze(
        state["job_id"], sector,
        state["dataset_path"], filename
    )
    with duckdb.connect(duckdb_path) as conn:
        # Créer la table raw_data avec le contenu de df
        conn.execute("CREATE TABLE raw_data AS SELECT * FROM df")
    
    logger.info("Données ingérées dans DuckDB: %s", duckdb_path)

    # Sérialiser le DataFrame pour le state LangGraph (inclut __row_id)
    raw_df_dict = {
        "columns": df.columns.tolist(),
        "data":    df.where(pd.notnull(df), None).values.tolist(),
    }

    # Sérialiser les ColumnMeta (dataclasses → dicts)
    import dataclasses
    meta_dicts = [dataclasses.asdict(m) for m in metadata]

    logger.info("NODE 1 terminé — Bronze: %s, %d business rules", bronze_path, len(business_rules))
    return {
        "raw_df":         raw_df_dict,
        "metadata":       meta_dicts,
        "business_rules": business_rules,
        "bronze_path":    bronze_path,
        "duckdb_path":    duckdb_path,
        "sector":         sector,
    }