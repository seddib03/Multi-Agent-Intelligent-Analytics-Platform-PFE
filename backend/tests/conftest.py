"""
Shared pytest fixtures for the backend test suite.

Integration tests (test_auth.py) require:
  - PostgreSQL running (e.g. via docker-compose)
  - The DATABASE_URL from app.core.config.settings pointing to the test DB

Pure unit tests (test_quality_service.py, test_dataset_service_unit.py,
test_schemas_dataset.py, test_sector_detection.py) run without infrastructure.
All heavy imports are deferred inside fixtures so that collecting unit tests
does not require asyncpg/PostgreSQL to be installed.
"""
import pytest
import pytest_asyncio


# ── Async mode ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ── DB engine (session-scoped, lazy) ─────────────────────────────────────────

@pytest.fixture(scope="session")
def test_engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.core.config import settings
    return create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)


# ── Schema bootstrap (only runs when DB tests request it) ────────────────────

@pytest_asyncio.fixture(scope="session")
async def init_schema(test_engine):
    """Create all tables (safe: CREATE IF NOT EXISTS)."""
    from app.core.database import Base
    from app.models import dataset, project, user  # noqa: F401
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


# ── Per-test transactional session ───────────────────────────────────────────

@pytest_asyncio.fixture()
async def db_session(test_engine, init_schema):
    """
    Isolated async DB session.  All writes are rolled back after each test so
    tests never pollute each other.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker
    async with test_engine.connect() as conn:
        await conn.begin()
        factory = async_sessionmaker(bind=conn, expire_on_commit=False, autoflush=False)
        async with factory() as session:
            yield session
        await conn.rollback()


# ── HTTP test client ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def client(db_session):
    """
    Async HTTP client wired directly to the FastAPI app (no real network).
    The DB dependency is shadowed by the per-test rollback session.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.database import get_db

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
