# MinioClient : wrapper pour interagir avec MinIO de manière structurée et réutilisable.
from __future__ import annotations

import io
import json
import logging
from datetime import datetime
from pathlib import Path
from datetime import timedelta
import pandas as pd
from minio import Minio
from minio.error import S3Error

from config.settings import get_settings

logger = logging.getLogger(__name__)


class MinioClient:
    """
    Client MinIO réutilisable pour les 3 layers.

    Usage dans un node :
        client = MinioClient()
        path = client.upload_bronze(job_id, sector, local_file_path)
        client.upload_silver(job_id, sector, clean_df)
        client.upload_gold(job_id, sector, report_dict)
    """

    def __init__(self) -> None:
        settings = get_settings()

        # Client MinIO officiel
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

        self._bronze = settings.minio_bronze_bucket
        self._silver = settings.minio_silver_bucket
        self._gold   = settings.minio_gold_bucket

        logger.info(
            "MinioClient initialisé — endpoint: %s",
            settings.minio_endpoint,
        )

    def initialize_buckets(self) -> None:
        """
        Crée les 3 buckets s'ils n'existent pas.

        Appelé une seule fois au démarrage de l'API (on_startup).
        MinIO ne lève pas d'erreur si le bucket existe déjà
        grâce à la vérification préalable.
        """
        for bucket in [self._bronze, self._silver, self._gold]:
            try:
                if not self._client.bucket_exists(bucket):
                    self._client.make_bucket(bucket)
                    logger.info("Bucket créé : %s", bucket)
                else:
                    logger.debug("Bucket existant : %s", bucket)
            except S3Error as e:
                logger.error("Erreur création bucket %s : %s", bucket, e)
                raise

    # ── Bronze ───────────────────────────────────────────────────────────────

    def upload_bronze(
        self,
        job_id:     str,
        sector:     str,
        local_path: str,
        filename:   str,
    ) -> str:
        """
        Upload le fichier brut original dans le bucket Bronze.

        Le Bronze est IMMUABLE : on ne modifie jamais ce fichier.
        Il sert de source de vérité si on veut rejouer le pipeline.

        Args:
            job_id:     UUID du job (sous-dossier dans le bucket)
            sector:     Secteur (sous-dossier par secteur)
            local_path: Chemin local du fichier uploadé par l'user
            filename:   Nom du fichier original

        Returns:
            Chemin MinIO du fichier (ex: "assurance/job123/raw.csv")
        """
        object_name = f"{sector}/{job_id}/{filename}"

        self._client.fput_object(
            bucket_name=self._bronze,
            object_name=object_name,
            file_path=local_path,
        )

        logger.info(
            "Bronze uploadé : %s/%s", self._bronze, object_name
        )
        return object_name

    # ── Silver ───────────────────────────────────────────────────────────────

    def upload_silver(
        self,
        job_id:   str,
        sector:   str,
        clean_df: pd.DataFrame,
    ) -> str:
        """
        Upload le DataFrame nettoyé en CSV dans Silver.

        CSV = format tabulaire texte, lisible et facilement exportable.
        On le sérialise en bytes en mémoire (pas de fichier temporaire).

        Args:
            job_id:   UUID du job
            sector:   Secteur
            clean_df: DataFrame Pandas nettoyé

        Returns:
            Chemin MinIO du CSV.
        """
        object_name = f"{sector}/{job_id}/clean.csv"

        # Sérialiser en CSV en mémoire (buffer bytes)
        buffer = io.BytesIO()
        clean_df.to_csv(buffer, index=False, encoding="utf-8")
        buffer.seek(0)  # Revenir au début du buffer

        self._client.put_object(
            bucket_name=self._silver,
            object_name=object_name,
            data=buffer,
            length=buffer.getbuffer().nbytes,
            content_type="application/octet-stream",
        )

        logger.info(
            "Silver uploadé : %s/%s (%d lignes)",
            self._silver,
            object_name,
            len(clean_df),
        )
        return object_name

    # ── Gold ─────────────────────────────────────────────────────────────────

    def upload_gold(
        self,
        job_id:  str,
        sector:  str,
        report:  dict,
        filename: str = "quality_report.json",
    ) -> str:
        """
        Upload un rapport JSON dans Gold.

        Gold contient tous les rapports et logs du pipeline :
            quality_report.json → scores dimensions AVANT/APRÈS
            cleaning_log.json   → log des opérations effectuées

        Args:
            job_id:   UUID du job
            sector:   Secteur
            report:   Dict à sérialiser en JSON
            filename: Nom du fichier dans Gold

        Returns:
            Chemin MinIO du fichier JSON.
        """
        object_name = f"{sector}/{job_id}/{filename}"

        # Sérialiser en JSON encodé UTF-8
        json_bytes = json.dumps(
            report, ensure_ascii=False, indent=2, default=str
        ).encode("utf-8")

        buffer = io.BytesIO(json_bytes)

        self._client.put_object(
            bucket_name=self._gold,
            object_name=object_name,
            data=buffer,
            length=len(json_bytes),
            content_type="application/json",
        )

        logger.info("Gold uploadé : %s/%s", self._gold, object_name)
        return object_name

    # ── Lecture ───────────────────────────────────────────────────────────────

    def download_silver(self, job_id: str, sector: str) -> pd.DataFrame:
        """
        Télécharge et retourne le DataFrame Silver d'un job.

        Utile pour le Predictive Agent qui lit directement
        les données nettoyées depuis MinIO Silver.

        Args:
            job_id: UUID du job
            sector: Secteur

        Returns:
            DataFrame Pandas lu depuis le CSV Silver.
        """
        object_name = f"{sector}/{job_id}/clean.csv"

        response = self._client.get_object(self._silver, object_name)
        buffer   = io.BytesIO(response.read())
        return pd.read_csv(buffer, encoding="utf-8")

    def list_jobs(self, sector: str, bucket: str = "gold") -> list[dict]:
        """
        Liste les jobs disponibles pour un secteur.

        Args:
            sector: Secteur à filtrer
            bucket: Bucket à lister (default: gold)

        Returns:
            Liste de dicts avec job_id et metadata.
        """
        target_bucket = getattr(self, f"_{bucket}", self._gold)
        objects = self._client.list_objects(
            target_bucket,
            prefix=f"{sector}/",
            recursive=False,
        )
        return [
            {"job_id": obj.object_name.split("/")[1]}
            for obj in objects
        ]
    def download_gold_json(self, job_id: str, sector: str, filename: str) -> dict:
        """
        Lit un fichier JSON depuis MinIO Gold et le retourne en dict.

        Gère les valeurs non-standard produites par ydata-profiling :
            NaN, Infinity, -Infinity → remplacés par null avant parsing.
        Ces valeurs sont valides en JavaScript mais pas en JSON strict.
        """
        import re

        object_name = f"{sector}/{job_id}/{filename}"
        response    = self._client.get_object(self._gold, object_name)
        content     = response.read().decode("utf-8")

        # Remplacer NaN / Infinity / -Infinity par null (JSON strict)
        content = re.sub(r'\bNaN\b',       'null', content)
        content = re.sub(r'\bInfinity\b',  'null', content)
        content = re.sub(r'\b-Infinity\b', 'null', content)

        return json.loads(content)
    def upload_gold_raw(self, job_id: str, sector: str, raw_bytes: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
            """Upload des bytes bruts dans Gold (rapport HTML ydata-profiling)."""
            object_name = f"{sector}/{job_id}/{filename}"
            buffer      = io.BytesIO(raw_bytes)
            self._client.put_object(
                bucket_name=self._gold,
                object_name=object_name,
                data=buffer,
                length=len(raw_bytes),
                content_type=content_type,
            )
            logger.info("Gold raw uploadé : %s/%s (%.1f KB)", self._gold, object_name, len(raw_bytes) / 1024)
            return object_name

        # ── URL présignée ─────────────────────────────────────────────────────

    def get_presigned_url(self, job_id: str, sector: str, filename: str, expires: int = 3600) -> str:
            """
            Génère une URL présignée pour accéder directement à un fichier Gold.

            L'URL est valide pendant `expires` secondes (défaut : 1 heure).
            Permet d'ouvrir le rapport HTML dans le navigateur sans credentials.
            """
            object_name = f"{sector}/{job_id}/{filename}"
            url = self._client.presigned_get_object(
                bucket_name=self._gold,
                object_name=object_name,
                expires=timedelta(seconds=expires),
            )
            return url

        # ── Listing ───────────────────────────────────────────────────────────

    def list_jobs(self, sector: str, bucket: str = "gold") -> list[dict]:
        target  = getattr(self, f"_{bucket}", self._gold)
        objects = self._client.list_objects(target, prefix=f"{sector}/", recursive=False)
        return [{"job_id": obj.object_name.split("/")[1]} for obj in objects]
        