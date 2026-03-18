from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


# ── Engine ───────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo          = settings.DEBUG,   # log SQL en dev uniquement
    pool_pre_ping = True,             # vérifie la connexion avant usage
    pool_size     = 10,               # connexions permanentes dans le pool
    max_overflow  = 20,               # connexions supplémentaires si besoin
)


# ── Session factory ──────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind            = engine,
    class_          = AsyncSession,
    expire_on_commit = False,         # évite le lazy load après commit
    autocommit      = False,
    autoflush       = False,
)


# ── Base declarative ─────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency FastAPI ───────────────────────────────────────
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()   # ← ajouter cette ligne
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db_schema() -> None:
    """Create missing tables from current ORM models (safe in dev)."""
    # Ensure all model classes are imported so metadata is complete.
    from app.models import dataset, project, user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Compatibility patch for legacy datasets schemas.
        await conn.execute(text("""
            ALTER TABLE datasets
            ADD COLUMN IF NOT EXISTS file_path VARCHAR(500);
        """))
        await conn.execute(text("""
            ALTER TABLE datasets
            ADD COLUMN IF NOT EXISTS processed_path VARCHAR(500);
        """))
        await conn.execute(text("""
            UPDATE datasets
            SET file_path = minio_key
            WHERE file_path IS NULL
              AND EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'datasets' AND column_name = 'minio_key'
              );
        """))
        await conn.execute(text("""
            ALTER TABLE datasets
            ALTER COLUMN file_path SET NOT NULL;
        """))

        # Old databases may still keep minio columns with NOT NULL constraints.
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'datasets' AND column_name = 'minio_key'
                ) THEN
                    ALTER TABLE datasets ALTER COLUMN minio_key DROP NOT NULL;
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'datasets' AND column_name = 'minio_processed_key'
                ) THEN
                    ALTER TABLE datasets ALTER COLUMN minio_processed_key DROP NOT NULL;
                END IF;
            END
            $$;
        """))