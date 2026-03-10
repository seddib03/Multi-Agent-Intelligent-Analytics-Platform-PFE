from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):

    # ── App ──────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "production"] = "development"
    DEBUG: bool = True

    # ── Database ─────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://dxc:dxcpassword@localhost:5432/dxc_insight"
    )

    # ── MinIO ─────────────────────────────────────────────
    MINIO_ENDPOINT:      str  = "localhost:9000"
    MINIO_ROOT_USER:     str  = "minioadmin"
    MINIO_ROOT_PASSWORD: str  = "minioadmin123"
    MINIO_BUCKET:        str  = "dxc-datasets"
    MINIO_SECURE:        bool = False

    # Sous-dossiers logiques dans le bucket unique
    MINIO_PREFIX_RAW:       str = "raw"
    MINIO_PREFIX_PROCESSED: str = "processed"
    MINIO_PREFIX_EXPORTS:   str = "exports"

   # ── Keycloak ──────────────────────────────────────────
    KEYCLOAK_URL:           str = "http://localhost:8080"
    KEYCLOAK_REALM:         str = "dxc"
    KEYCLOAK_CLIENT_ID:     str = "dxc_frontend"
    KEYCLOAK_CLIENT_SECRET: str = "0TEEu2mA9sOIY3YHZhMIMBfseUImh3WY"
    KEYCLOAK_ADMIN_CLIENT_ID:    str = "dxc_backend"
    KEYCLOAK_ADMIN_CLIENT_SECRET:str = "sbZ2ol7kpC6uUrZbmmO1zTn1C8TcrIzB"

    @property
    def KEYCLOAK_TOKEN_URL(self) -> str:
        return (
            f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"
            f"/protocol/openid-connect/token"
        )

    @property
    def KEYCLOAK_LOGOUT_URL(self) -> str:
        return (
            f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"
            f"/protocol/openid-connect/logout"
        )

    @property
    def KEYCLOAK_ADMIN_USERS_URL(self) -> str:
        return (
            f"{self.KEYCLOAK_URL}/admin/realms/{self.KEYCLOAK_REALM}"
            f"/users"
        )
    # ── Upload ────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50

    # ── CORS ──────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()