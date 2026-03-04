from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

import polars as pl

from agent.state import AgentState
from config.settings import get_settings
from core.df_serializer import df_to_dict
from core.file_loader import load_dataset

logger = logging.getLogger(__name__)


def ingestion_node(state: AgentState) -> dict:
    """
    Charge le dataset et le metadata, sauvegarde en Bronze.

    Retourne uniquement les champs modifiés — LangGraph
    merge automatiquement avec l'état existant.

    Args:
        state: État courant du pipeline

    Returns:
        Dict avec les champs mis à jour par ce node.
    """
    logger.info(">>> NODE 1 : Ingestion — démarrage")
    settings = get_settings()

    # ── 1. Charger le metadata ────────────────────────────────────────────────
    metadata_path = Path(state["metadata_path"])

    if not metadata_path.exists():
        error_msg = f"Metadata introuvable : {metadata_path}"
        logger.error(error_msg)
        return {"status": "error", "errors": [error_msg]}

    with open(metadata_path, encoding="utf-8") as f:
        raw_metadata = json.load(f)

    logger.info(
        "Metadata chargé — %d clés de premier niveau",
        len(raw_metadata),
    )

    # ── 2. Charger le dataset ─────────────────────────────────────────────────
    dataset_path = Path(state["dataset_path"])

    if not dataset_path.exists():
        error_msg = f"Dataset introuvable : {dataset_path}"
        logger.error(error_msg)
        return {"status": "error", "errors": [error_msg]}

    raw_df, ingestion_info = load_dataset(str(dataset_path))

    logger.info(
        "Dataset chargé — %d lignes x %d colonnes | format: %s | encoding: %s",
        raw_df.height,
        raw_df.width,
        ingestion_info["file_format"],
        ingestion_info.get("encoding", "N/A"),
    )

    # ── 3. Sauvegarder en Bronze ──────────────────────────────────────────────
    # Détecter le secteur depuis le metadata (clé flexible)
    sector = _extract_sector(raw_metadata)
    bronze_path = _save_to_bronze(dataset_path, sector, settings)

    logger.info("NODE 1 terminé — Bronze : %s", bronze_path)

    return {
        "raw_df":        df_to_dict(raw_df),
        "raw_metadata":  raw_metadata,
        "ingestion_info": ingestion_info,
        "bronze_path":   str(bronze_path),
        "sector":        sector,
    }

def _df_to_dict(df: pl.DataFrame) -> dict:
    """
    Convertit un DataFrame Polars en dict JSON-sérialisable.
    
    Format choisi : orienté "colonnes" pour faciliter
    la reconstruction avec pl.DataFrame(data).
    
        {
          "columns": ["contrat_id", "prime_annuelle", ...],
          "data": [
              ["CTR-000001", "1200.00", ...],  ← ligne 1
              ["CTR-000002", "850.50",  ...],  ← ligne 2
          ]
        }
    """
    return {
        "columns": df.columns,
        "data":    df.rows(),     
        "schema":  {col: str(dtype) 
                    for col, dtype in zip(df.columns, df.dtypes)}
    }

def _extract_sector(raw_metadata: dict) -> str:
    """
    Extrait le secteur depuis le metadata avec plusieurs clés possibles.

    Le metadata de l'user peut utiliser différentes clés :
    "sector", "secteur", "domain", "domaine", etc.
    On teste toutes les variantes connues.

    Args:
        raw_metadata: Metadata brut de l'user

    Returns:
        Nom du secteur ou "unknown" si non trouvé.
    """
    possible_keys = ["sector", "secteur", "domain", "domaine", "industry"]

    for key in possible_keys:
        if key in raw_metadata:
            return str(raw_metadata[key]).lower().strip()

    logger.warning("Secteur non trouvé dans le metadata — utilisation 'unknown'")
    return "unknown"



def _save_to_bronze(
    source_path: Path,
    sector: str,
    settings,
) -> Path:
    """
    Copie le fichier original dans le dossier Bronze.

    Le Bronze est IMMUABLE : on copie, on ne déplace pas.
    Le fichier original reste en tmp pour le reste du pipeline.

    Args:
        source_path: Chemin du fichier uploadé
        sector:      Nom du secteur (sous-dossier Bronze)
        settings:    Configuration centralisée

    Returns:
        Chemin du fichier copié en Bronze.
    """
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    bronze_dir  = settings.bronze_dir / sector
    bronze_dir.mkdir(parents=True, exist_ok=True)

    bronze_path = bronze_dir / f"{timestamp}_raw{source_path.suffix}"
    shutil.copy2(source_path, bronze_path)

    return bronze_path