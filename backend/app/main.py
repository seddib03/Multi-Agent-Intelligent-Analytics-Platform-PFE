from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db_schema
from app.routers import auth, users, projects, datasets
from backend.app.routers import sector as sector


# ─── Lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 DXC Insight API started — environment: {settings.ENVIRONMENT}")
    try:
        await init_db_schema()
        print("✅ Database schema ready")
    except Exception as e:
        print(f"⚠️  Database schema init warning: {e}")
    try:
        import os
        os.makedirs(settings.TEMP_UPLOAD_DIR, exist_ok=True)
        print(f"✅ Temp upload dir '{settings.TEMP_UPLOAD_DIR}' ready")
    except Exception as e:
        print(f"⚠️  Temp upload dir init warning: {e}")
    yield
    print("👋 DXC Insight API stopped")


# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DXC Insight Platform — API",
    description="Multi-Agent Analytics Platform powered by AI agents.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ────────────────────────────────────────────────────────────────────
origins = [settings.FRONTEND_URL]
if settings.DEBUG:
    origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth.router,     prefix="/api/auth",     tags=["Auth"])
app.include_router(users.router,    prefix="/api/users",    tags=["Users"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(datasets.router, prefix="/api/projects/{project_id}/datasets", tags=["Datasets"])
app.include_router(sector.router, prefix="/api/sector", tags=["Sector Detection"])


# ─── Health ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "healthy", "env": settings.ENVIRONMENT}

@app.get("/")
async def root():
    return {"message": "DXC Insight Platform API"}