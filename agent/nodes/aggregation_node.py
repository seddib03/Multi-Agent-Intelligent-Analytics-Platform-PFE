# agent/nodes/aggregation_node.py

# Standard library
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime

# Third-party
import polars as pl

# Local
from agent.state import AgentState, STATUS_FAILED, STATUS_SUCCESS


logger = logging.getLogger(__name__)

# Version de l'agent — à incrémenter à chaque déploiement
AGENT_VERSION = os.getenv("APP_VERSION", "1.0.0")


# ─── Node ────────────────────────────────────────────────────────────────────


def aggregation_node(state: AgentState) -> AgentState:
    """Node 4 — Data Aggregation.

    Prépare le dataset final pour les agents en aval :
        1. Sélectionner uniquement les colonnes déclarées
           dans le metadata (exclure colonnes inattendues)
        2. Ajouter les colonnes de tracking pour la traçabilité
        3. Sauvegarder dans le Gold layer via StorageManager
        4. Marquer le pipeline comme SUCCESS

    Args:
        state: AgentState contenant clean_df, quality_report,
               action_plan et tous les chemins de stockage.

    Returns:
        AgentState mis à jour avec final_df et status SUCCESS.
    """
    logger.info(">>> NODE 4 : Data Aggregation — démarrage")

    # ── Vérifications préalables ──────────────────────────────────────
    if state.get("clean_df") is None:
        error_msg = (
            "Aggregation impossible : clean_df absent. "
            "Vérifier que cleaning_node s est exécuté correctement."
        )
        logger.error(error_msg)
        state["status"] = STATUS_FAILED
        state["errors"].append(error_msg)
        return state

    try:
        clean_df      = state["clean_df"]
        action_plan   = state["action_plan"]
        quality_report = state.get("quality_report", {})
        quality_score  = state.get("quality_score", 0.0)

        # ── Étape 1 : Sélectionner les colonnes du metadata ───────────
        final_df = _select_metadata_columns(clean_df, action_plan)

        # ── Étape 2 : Ajouter les colonnes de tracking ────────────────
        final_df = _add_tracking_columns(
            final_df,
            sector        = action_plan["sector"],
            quality_score = quality_score,
            job_id        = state.get("started_at", str(uuid.uuid4())),
        )

        # ── Étape 3 : Sauvegarder dans Gold layer ─────────────────────
        _save_to_gold(state, action_plan["sector"], quality_report)

        # ── Étape 4 : Mettre à jour le state ──────────────────────────
        state["final_df"]     = final_df
        state["status"]       = STATUS_SUCCESS
        state["completed_at"] = datetime.now().isoformat()

        logger.info(
            "NODE 4 terminé — %d lignes | %d colonnes finales | "
            "status : SUCCESS",
            final_df.height,
            final_df.width,
        )

    except Exception as error:
        logger.error("NODE 4 échoué : %s", error)
        state["status"] = STATUS_FAILED
        state["errors"].append(str(error))

    return state


# ─── Fonctions privées ───────────────────────────────────────────────────────


def _select_metadata_columns(
    clean_df: pl.DataFrame,
    action_plan: dict,
) -> pl.DataFrame:
    """Sélectionne uniquement les colonnes déclarées dans le metadata.

    Les colonnes extra (non déclarées) sont exclues du dataset final.
    Cela garantit que les agents en aval reçoivent exactement
    ce qui était attendu.

    Args:
        clean_df:    DataFrame nettoyé avec potentiellement
                     des colonnes supplémentaires.
        action_plan: Plan d'action avec all_column_names.

    Returns:
        DataFrame avec uniquement les colonnes du metadata.
    """
    declared_columns = action_plan.get("all_column_names", [])

    # Garder seulement les colonnes qui existent ET sont déclarées
    columns_to_keep = [
        col for col in declared_columns
        if col in clean_df.columns
    ]

    excluded = set(clean_df.columns) - set(columns_to_keep)
    if excluded:
        logger.info(
            "Colonnes exclues du dataset final "
            "(non déclarées dans metadata) : %s",
            list(excluded),
        )

    return clean_df.select(columns_to_keep)


def _add_tracking_columns(
    df: pl.DataFrame,
    sector: str,
    quality_score: float,
    job_id: str,
) -> pl.DataFrame:
    """Ajoute les colonnes de tracking au dataset final.

    Ces colonnes permettent aux agents en aval de savoir :
        - De quel secteur viennent les données
        - Quand elles ont été traitées
        - Quel était leur niveau de qualité
        - Quelle version de l'agent les a traitées

    Convention : toutes les colonnes de tracking
    commencent par _ pour les distinguer des données métier.

    Args:
        df:            DataFrame à enrichir.
        sector:        Secteur du dataset.
        quality_score: Score de qualité calculé.
        job_id:        Identifiant du job de traitement.

    Returns:
        DataFrame enrichi avec les 5 colonnes de tracking.
    """
    ingestion_ts = datetime.now().isoformat()

    return df.with_columns([
        pl.lit(sector).alias("_sector"),
        pl.lit(ingestion_ts).alias("_ingestion_ts"),
        pl.lit(quality_score).alias("_quality_score"),
        pl.lit(AGENT_VERSION).alias("_agent_version"),
        pl.lit(job_id).alias("_job_id"),
    ])


def _save_to_gold(
    state: AgentState,
    sector: str,
    quality_report: dict,
) -> None:
    """Sauvegarde les métadonnées de traçabilité dans le Gold layer.

    Import local pour éviter les imports circulaires.

    Args:
        state:          AgentState complet avec tous les champs.
        sector:         Secteur du dataset.
        quality_report: Rapport qualité à persister.
    """
    # Import local intentionnel — StorageManager n'est instancié
    # qu'au moment où on en a besoin, pas au démarrage du module
    from core.storage_manager import StorageManager

    manager = StorageManager()
    manager.save_to_gold(
        job_id        = state.get("started_at", "unknown"),
        sector        = sector,
        status        = state.get("status", "UNKNOWN"),
        bronze_path   = state.get("bronze_path", ""),
        silver_path   = state.get("silver_path", ""),
        quality_report = quality_report,
        cleaning_log  = state.get("cleaning_log", []),
    )
