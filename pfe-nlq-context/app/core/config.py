from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    app_name: str = "PFE - NLQ & Context"
    debug: bool = os.getenv("APP_DEBUG", "true").lower() == "true"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06")
    schema_version: str = "0.1"

settings = Settings()