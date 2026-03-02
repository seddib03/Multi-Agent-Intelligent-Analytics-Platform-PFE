# Standard library
from __future__ import annotations

import logging
import shutil
import os
from datetime import datetime

# Local
from agent.state import AgentState, STATUS_FAILED
from core.file_loader import load_dataset
from core.metadata_parser import parse_metadata, validate_schema_matching
from core.data_profiler import compute_profile


logger = logging.getLogger(__name__)

BRONZE_PATH = os.getenv("BRONZE_PATH", "storage/bronze")


# ─── Node ────────────────────────────────────────────────────────────────────


def ingestion_node(state: AgentState) -> AgentState:
    """Node 1 — Raw Data Ingestion.

    Orchestre les 3 opérations d'ingestion :
        1. Parsing et validation du metadata
        2. Chargement du dataset
        3. Validation de la cohérence colonnes

    Args:
        state: AgentState contenant dataset_path et metadata_path.

    Returns:
        AgentState mis à jour avec raw_df, metadata, action_plan,
        bronze_path. Status = FAILED si une erreur bloquante survient.
    """
    logger.info(">>> NODE 1 : Raw Data Ingestion — démarrage")

    try:
        # ── Étape 1 : Parser le metadata ──────────────────────────────
        metadata, action_plan = parse_metadata(state["metadata_path"])

        # ── Étape 2 : Charger le dataset ──────────────────────────────
        raw_df, ingestion_info = load_dataset(state["dataset_path"])

        # ── Étape 3 : Schema matching ─────────────────────────────────
        schema_result = validate_schema_matching(
            raw_df.columns,
            metadata,
        )

        # ── Étape 4 : Profiler les données brutes → AVANT cleaning ────
        logger.info("Calcul profil qualité AVANT cleaning")
        profile_before = compute_profile(
            raw_df,
            action_plan,
            label="AVANT",
        )
        state["profile_before"] = profile_before

        logger.info(
            "Quality index AVANT cleaning : %.1f/100",
            profile_before["global_stats"]["quality_index"],
        )

        # Colonnes manquantes = erreur bloquante
        if not schema_result["is_valid"]:
            error_msg = (
                f"Schema matching échoué — colonnes manquantes : "
                f"{schema_result['missing_columns']}"
            )
            logger.error(error_msg)
            state["status"] = STATUS_FAILED
            state["errors"].append(error_msg)
            return state

        # ── Étape 4 : Sauvegarder le fichier brut → Bronze ────────────
        bronze_path = _save_to_bronze(
            state["dataset_path"],
            metadata.sector,
        )

        # ── Étape 5 : Mettre à jour le state ──────────────────────────
        state["metadata"]     = metadata.model_dump()
        state["action_plan"]  = action_plan
        state["raw_df"]       = raw_df
        state["bronze_path"]  = bronze_path

        # Ajouter les infos d'ingestion au cleaning_log
        state["cleaning_log"].append({
            "node":       "ingestion",
            "timestamp":  datetime.now().isoformat(),
            "operation":  "file_loaded",
            "details":    ingestion_info,
            "schema_check": schema_result,
        })

        logger.info(
            "NODE 1 terminé — %d lignes | %d colonnes | bronze : %s",
            ingestion_info["nb_rows"],
            ingestion_info["nb_columns"],
            bronze_path,
        )

    except (FileNotFoundError, ValueError) as error:
        logger.error("NODE 1 échoué : %s", error)
        state["status"] = STATUS_FAILED
        state["errors"].append(str(error))

    return state


# ─── Fonction privée ─────────────────────────────────────────────────────────


def _save_to_bronze(dataset_path: str, sector: str) -> str:
    """Sauvegarde le fichier original dans le Bronze layer.

    Le fichier est copié tel quel, sans aucune modification.
    Cela permet de toujours pouvoir rejouer le pipeline
    depuis les données originales.

    Args:
        dataset_path: Chemin du fichier source.
        sector:       Secteur du dataset (pour l'organisation).

    Returns:
        Chemin où le fichier a été sauvegardé dans le Bronze layer.
    """
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    sector_dir  = os.path.join(BRONZE_PATH, sector)
    os.makedirs(sector_dir, exist_ok=True)

    # Conserver l'extension originale du fichier
    extension   = os.path.splitext(dataset_path)[1]
    destination = os.path.join(
        sector_dir,
        f"{timestamp}_raw{extension}",
    )

    shutil.copy2(dataset_path, destination)
    logger.info("Fichier brut sauvegardé dans Bronze : %s", destination)

    return destination