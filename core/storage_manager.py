# core/storage_manager.py

# Standard library
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

# Third-party
import duckdb
import polars as pl


logger = logging.getLogger(__name__)


# ─── Constantes ──────────────────────────────────────────────────────────────

BRONZE_PATH  = os.getenv("BRONZE_PATH", "storage/bronze")
SILVER_PATH  = os.getenv("SILVER_PATH", "storage/silver")
GOLD_PATH    = os.getenv("GOLD_PATH", "storage/gold")
GOLD_DB_PATH = os.getenv(
    "GOLD_DB_PATH", "storage/gold/analytics.duckdb"
)


# ─── Classe principale ───────────────────────────────────────────────────────


class StorageManager:
    """Gestionnaire centralisé des 3 layers de stockage.

    Responsabilités :
        Bronze → sauvegarder les fichiers bruts originaux
        Silver → sauvegarder les datasets nettoyés en Parquet
        Gold   → persister les quality reports et logs dans DuckDB

    Le Gold layer est cumulatif — chaque run ajoute une entrée.
    Cela permet d'avoir un historique complet des traitements.

    Example:
        >>> manager = StorageManager()
        >>> manager.initialize_gold_layer()
        >>> manager.save_to_gold(job_id, quality_report, cleaning_log)
    """

    def __init__(self) -> None:
        """Initialise le StorageManager et crée les dossiers."""
        os.makedirs(BRONZE_PATH, exist_ok=True)
        os.makedirs(SILVER_PATH, exist_ok=True)
        os.makedirs(GOLD_PATH,   exist_ok=True)

    # ── Gold Layer ────────────────────────────────────────────────────

    def initialize_gold_layer(self) -> None:
        """Crée les tables DuckDB si elles n'existent pas.

        Tables créées :
            ingestion_log    → historique de tous les runs
            quality_reports  → rapports qualité par run
            cleaning_logs    → détail des opérations par run

        Appelée au démarrage de l'application FastAPI.
        Idempotente — peut être appelée plusieurs fois.
        """
        conn = self._get_duckdb_connection()

        try:
            # Table 1 : historique des runs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_log (
                    id            VARCHAR PRIMARY KEY,
                    job_id        VARCHAR,
                    sector        VARCHAR,
                    timestamp     TIMESTAMP,
                    status        VARCHAR,
                    bronze_path   VARCHAR,
                    silver_path   VARCHAR,
                    rows_before   INTEGER,
                    rows_after    INTEGER,
                    quality_score FLOAT,
                    decision      VARCHAR
                )
            """)

            # Table 2 : rapports qualité détaillés
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quality_reports (
                    id          VARCHAR PRIMARY KEY,
                    job_id      VARCHAR,
                    sector      VARCHAR,
                    timestamp   TIMESTAMP,
                    report_json VARCHAR
                )
            """)

            # Table 3 : logs de cleaning détaillés
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cleaning_logs (
                    id          VARCHAR PRIMARY KEY,
                    job_id      VARCHAR,
                    sector      VARCHAR,
                    timestamp   TIMESTAMP,
                    operation   VARCHAR,
                    column_name VARCHAR,
                    rows_affected INTEGER,
                    detail      VARCHAR
                )
            """)

            logger.info("Gold layer initialisé : %s", GOLD_DB_PATH)

        finally:
            conn.close()

    def save_to_gold(
        self,
        job_id: str,
        sector: str,
        status: str,
        bronze_path: str,
        silver_path: str,
        quality_report: dict,
        cleaning_log: list[dict],
    ) -> None:
        """Persiste toutes les données de traçabilité dans DuckDB.

        Args:
            job_id:         Identifiant unique du job.
            sector:         Secteur du dataset.
            status:         Statut final du pipeline.
            bronze_path:    Chemin du fichier brut sauvegardé.
            silver_path:    Chemin du fichier nettoyé.
            quality_report: Rapport qualité complet.
            cleaning_log:   Log des opérations de nettoyage.
        """
        conn = self._get_duckdb_connection()

        try:
            summary       = quality_report.get("summary", {})
            quality_score = summary.get("quality_score", 0)
            decision      = summary.get("decision", "UNKNOWN")
            rows_before   = summary.get("rows_before_cleaning", 0)
            rows_after    = summary.get("rows_after_cleaning", 0)
            timestamp     = datetime.now()

            # ── Insérer dans ingestion_log ────────────────────────────
            conn.execute("""
                INSERT INTO ingestion_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                str(uuid.uuid4()),
                job_id,
                sector,
                timestamp,
                status,
                bronze_path,
                silver_path,
                rows_before,
                rows_after,
                quality_score,
                decision,
            ])

            # ── Insérer dans quality_reports ──────────────────────────
            conn.execute("""
                INSERT INTO quality_reports VALUES (?, ?, ?, ?, ?)
            """, [
                str(uuid.uuid4()),
                job_id,
                sector,
                timestamp,
                json.dumps(quality_report),
            ])

            # ── Insérer les entrées du cleaning_log ───────────────────
            for entry in cleaning_log:
                conn.execute("""
                    INSERT INTO cleaning_logs VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    str(uuid.uuid4()),
                    job_id,
                    sector,
                    timestamp,
                    entry.get("operation", ""),
                    entry.get("column", ""),
                    entry.get("rows_affected", 0),
                    entry.get("detail", ""),
                ])

            logger.info(
                "Gold layer mis à jour — job : %s | score : %.1f",
                job_id,
                quality_score,
            )

        finally:
            conn.close()

    def get_sector_history(self, sector: str) -> list[dict]:
        """Retourne l'historique des runs pour un secteur.

        Utilisé par GET /history/{sector} dans l'API.

        Args:
            sector: Secteur dont on veut l'historique.

        Returns:
            Liste des runs avec score et statut, du plus récent
            au plus ancien.
        """
        conn = self._get_duckdb_connection()

        try:
            result = conn.execute("""
                SELECT
                    job_id,
                    timestamp,
                    status,
                    quality_score,
                    decision,
                    rows_before,
                    rows_after
                FROM ingestion_log
                WHERE sector = ?
                ORDER BY timestamp DESC
                LIMIT 50
            """, [sector]).fetchall()

            columns = [
                "job_id", "timestamp", "status",
                "quality_score", "decision",
                "rows_before", "rows_after",
            ]

            return [dict(zip(columns, row)) for row in result]

        finally:
            conn.close()

    # ── Utilitaire privé ──────────────────────────────────────────────

    def _get_duckdb_connection(self) -> duckdb.DuckDBPyConnection:
        """Ouvre et retourne une connexion DuckDB.

        Returns:
            Connexion DuckDB active.
        """
        return duckdb.connect(GOLD_DB_PATH)
