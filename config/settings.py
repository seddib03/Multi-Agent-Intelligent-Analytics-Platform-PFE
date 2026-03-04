from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


# ─── Chemins racine ────────────────────────────────────────────────────────────
# __file__ = config/settings.py
# .parent  = config/
# .parent  = racine du projet
ROOT_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """
    Configuration complète de l'application.

    Toutes les valeurs peuvent être surchargées via :
        - fichier .env à la racine du projet
        - variables d'environnement système

    Exemple .env :
        OPENROUTER_API_KEY=sk-or-...
        LLM_MODEL=openai/gpt-4o-mini
        LOG_LEVEL=DEBUG
    """

    # ── LLM OpenRouter ─────────────────────────────────────────────────────────
    # La clé API est obligatoire — pas de valeur par défaut
    openrouter_api_key: str = Field(
        default=os.getenv("OPENROUTER_API_KEY"),
        description="Clé API OpenRouter (obligatoire)",
    )

    # Modèle choisi : gpt-4o-mini — bon rapport qualité/prix
    llm_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Modèle LLM à utiliser via OpenRouter",
    )

    # URL de base de l'API OpenRouter (compatible OpenAI SDK)
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="URL de base de l'API OpenRouter",
    )

    # Température du LLM : 0.0 = déterministe, 1.0 = créatif
    # Pour l'analyse de données on veut du déterminisme → 0.2
    llm_temperature: float = Field(
        default=0.2,
        description="Température du LLM (0.0 = déterministe)",
    )

    # Limite de tokens pour les réponses LLM
    llm_max_tokens: int = Field(
        default=4000,
        description="Nombre maximum de tokens par réponse LLM",
    )

    # ── Chemins de stockage ────────────────────────────────────────────────────
    # Tous relatifs à ROOT_DIR pour portabilité
    bronze_dir: Path = Field(
        default=ROOT_DIR / "storage" / "bronze",
        description="Dossier pour les fichiers bruts originaux",
    )

    silver_dir: Path = Field(
        default=ROOT_DIR / "storage" / "silver",
        description="Dossier pour les datasets nettoyés (Parquet)",
    )

    gold_db_path: Path = Field(
        default=ROOT_DIR / "storage" / "gold" / "analytics.duckdb",
        description="Chemin vers la base DuckDB Gold Layer",
    )

    tmp_dir: Path = Field(
        default=ROOT_DIR / "storage" / "tmp",
        description="Dossier temporaire pour les fichiers uploadés",
    )

    # ── Projet dbt ────────────────────────────────────────────────────────────
    dbt_project_dir: Path = Field(
        default=ROOT_DIR / "DataQuality",
        description="Racine du projet dbt",
    )

    # ── API FastAPI ────────────────────────────────────────────────────────────
    api_host: str = Field(
        default="0.0.0.0",
        description="Hôte de l'API",
    )

    api_port: int = Field(
        default=8000,
        description="Port de l'API",
    )

    # Version de l'agent — injectée dans les colonnes tracking du dataset final
    agent_version: str = Field(
        default="2.0.0",
        description="Version de l'agent (injectée dans les données)",
    )

    # ── Qualité des données ────────────────────────────────────────────────────
    # Seuil minimum pour que le pipeline continue vers delivery
    quality_threshold: float = Field(
        default=80.0,
        description="Score global minimum pour accepter le dataset (0-100)",
    )

    # Multiplicateur IQR pour la détection des outliers (règle de Tukey)
    # 1.5 = standard académique reconnu
    iqr_multiplier: float = Field(
        default=1.5,
        description="Multiplicateur IQR pour détection outliers (Tukey)",
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="Niveau de log (DEBUG, INFO, WARNING, ERROR)",
    )

    # ── LangGraph ─────────────────────────────────────────────────────────────
    # Délai maximum (secondes) pour attendre la validation humaine
    # Après ce délai, le graph expire et retourne un timeout
    human_validation_timeout: int = Field(
        default=3600,
        description="Délai max (secondes) pour la validation humaine",
    )

    class Config:
        # Nom du fichier .env à lire automatiquement
        env_file = ROOT_DIR / ".env"
        # Ne pas crasher si des champs supplémentaires sont dans .env
        extra = "ignore"
        # Sensible à la casse pour les variables d'env
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Retourne l'instance unique des settings (singleton).

    lru_cache(maxsize=1) garantit que Settings() est instancié
    une seule fois, même si get_settings() est appelé 100 fois.
    → Performance : .env lu une seule fois au démarrage
    → Cohérence : tous les modules partagent la même instance

    Usage dans n'importe quel module :
        from config.settings import get_settings
        settings = get_settings()
        api_key = settings.openrouter_api_key

    Returns:
        Instance unique et partagée de Settings.
    """
    return Settings()