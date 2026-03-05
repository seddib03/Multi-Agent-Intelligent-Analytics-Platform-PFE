from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
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
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()