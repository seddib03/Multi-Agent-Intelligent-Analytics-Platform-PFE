from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    app_name: str = "PFE - NLQ & Context Agents"
    debug: bool = os.getenv("APP_DEBUG", "true").lower() == "true"
    schema_version: str = os.getenv("SCHEMA_VERSION", "0.1")

    # Provider switch
    llm_provider: str = os.getenv("LLM_PROVIDER", "openrouter")  # openai | openrouter | mock

    # OpenRouter
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

settings = Settings()