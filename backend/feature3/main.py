from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import projects, datasets
from backend.app.schemas import auth


# ─── Lifespan ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 DXC Insight API démarrée — environnement : {settings.ENVIRONMENT}")
    yield
    # Shutdown
    print("👋 DXC Insight API arrêtée")


# ─── App ──────────────────────────────────────────────────
app = FastAPI(
    title="DXC Insight Platform — API",
    description=(
        "Plateforme d'analyse sectorielle pilotée par des agents IA. "
        "Feature 3 : Infrastructure · Projects · Upload"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"] if settings.ENVIRONMENT == "development"
        else ["https://your-frontend-domain.com"]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────
app.include_router(projects.router)
app.include_router(datasets.router)
app.include_router(auth.router,  prefix="/api/auth",  tags=["Auth"])


# ─── Health check ─────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}


# ─── Root ─────────────────────────────────────────────────
@app.get("/", tags=["system"])
async def root():
    return {
        "app": "DXC Insight Platform",
        "version": "1.0.0",
        "docs": "/docs",
    }