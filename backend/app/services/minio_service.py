from app.core.minio import MinioService as CoreMinioService


class MinioService(CoreMinioService):
    """Compatibility wrapper re-exporting core MinIO service."""
