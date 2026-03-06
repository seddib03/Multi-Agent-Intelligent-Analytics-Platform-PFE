from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import io
from datetime import timedelta

# ── Client singleton ─────────────────────────────────────────
minio_client = Minio(
    endpoint   = settings.MINIO_ENDPOINT,
    access_key = settings.MINIO_ROOT_USER,
    secret_key = settings.MINIO_ROOT_PASSWORD,
    secure     = settings.MINIO_SECURE,
)

# ── Bucket principal (depuis docker-compose) ─────────────────
BUCKET = settings.MINIO_BUCKET


def ensure_buckets_exist() -> None:
    """Create the configured bucket if it does not exist yet."""
    if not minio_client.bucket_exists(BUCKET):
        minio_client.make_bucket(BUCKET)

# ── Préfixes par type de fichier ─────────────────────────────
class Prefix:
    RAW       = "raw"        # fichiers bruts uploadés
    PROCESSED = "processed"  # fichiers après corrections
    MODELS    = "models"     # artefacts ML
    EXPORTS   = "exports"    # exports CSV/PDF

def build_key(user_id: str, project_id: str,
              prefix: str, filename: str) -> str:
    """
    Structure : {user_id}/{project_id}/{prefix}/{filename}
    Exemple   : abc123/proj456/raw/1710000000_customers.csv
    """
    return f"{user_id}/{project_id}/{prefix}/{filename}"


# ── Service MinIO ─────────────────────────────────────────────
class MinioService:

    @staticmethod
    async def upload_file(
        user_id:      str,
        project_id:   str,
        filename:     str,
        data:         bytes,
        content_type: str,
        prefix:       str = Prefix.RAW,
    ) -> str:
        """
        Upload un fichier dans MinIO.
        Retourne la clé objet (object_key).
        """
        from time import time
        ts  = int(time())
        key = build_key(user_id, project_id, prefix,
                        f"{ts}_{filename}")

        minio_client.put_object(
            bucket_name  = BUCKET,
            object_name  = key,
            data         = io.BytesIO(data),
            length       = len(data),
            content_type = content_type,
            metadata     = {
                "x-user-id":    user_id,
                "x-project-id": project_id,
            }
        )
        return key

    @staticmethod
    async def get_object_bytes(object_key: str) -> bytes:
        """
        Lire un fichier depuis MinIO.
        Retourne le contenu en bytes.
        """
        response = minio_client.get_object(
            bucket_name = BUCKET,
            object_name = object_key,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    @staticmethod
    async def get_presigned_url(
        object_key:      str,
        expires_seconds: int = 900,   # 15 min par défaut
    ) -> str:
        """
        Générer une URL de téléchargement temporaire.
        """
        return minio_client.presigned_get_object(
            bucket_name = BUCKET,
            object_name = object_key,
            expires     = timedelta(seconds=expires_seconds),
        )

    @staticmethod
    async def delete_file(object_key: str) -> None:
        """
        Supprimer un fichier depuis MinIO.
        """
        try:
            minio_client.remove_object(
                bucket_name = BUCKET,
                object_name = object_key,
            )
        except S3Error as e:
            # Fichier déjà supprimé → pas bloquant
            if e.code != "NoSuchKey":
                raise

    @staticmethod
    async def delete_project_files(
        user_id:    str,
        project_id: str,
    ) -> None:
        """
        Supprimer tous les fichiers d'un projet.
        Appelé lors de DELETE /api/projects/:id
        """
        prefix  = f"{user_id}/{project_id}/"
        objects = minio_client.list_objects(
            BUCKET, prefix=prefix, recursive=True
        )
        keys = [obj.object_name for obj in objects]

        if keys:
            from minio.deleteobjects import DeleteObject
            errors = minio_client.remove_objects(
                BUCKET,
                [DeleteObject(k) for k in keys]
            )
            for err in errors:
                print(f"MinIO delete error: {err}")

    @staticmethod
    async def delete_user_files(user_id: str) -> None:
        """
        Supprimer tous les fichiers d'un utilisateur.
        Appelé lors de DELETE /api/users/me
        """
        prefix  = f"{user_id}/"
        objects = minio_client.list_objects(
            BUCKET, prefix=prefix, recursive=True
        )
        keys = [obj.object_name for obj in objects]

        if keys:
            from minio.deleteobjects import DeleteObject
            errors = minio_client.remove_objects(
                BUCKET,
                [DeleteObject(k) for k in keys]
            )
            for err in errors:
                print(f"MinIO delete error: {err}")

    @staticmethod
    def file_exists(object_key: str) -> bool:
        """
        Vérifier si un fichier existe dans MinIO.
        """
        try:
            minio_client.stat_object(BUCKET, object_key)
            return True
        except S3Error:
            return False