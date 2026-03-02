from app.core.config import settings
from app.core.llm_client import OpenAILLMClient
from app.nlq.schemas import NLQOutput
from .schemas import ContextOutput
from .prompts import CONTEXT_SYSTEM, context_user_prompt
from .resources_loader import load_yaml

class ContextService:
    def __init__(self, llm: OpenAILLMClient):
        self.llm = llm
        self.kpi_catalog = load_yaml("sector_kpi_map.yaml")
        self.schema_registry = load_yaml("sector_schema_registry.yaml")

    def enrich(self, nlq: NLQOutput) -> ContextOutput:
        # On passe les ressources au LLM pour qu'il reste “grounded”
        user = context_user_prompt(
            nlq=nlq.model_dump(),
            kpi_catalog=self.kpi_catalog,
            schema_version=settings.schema_version,
        )

        ctx = self.llm.parse_with_pydantic(
            model=settings.openai_model,
            system=CONTEXT_SYSTEM,
            user=user,
            response_model=ContextOutput,
        )

        # Petite correction backend (pro) : forcer la version
        ctx.schema_version = settings.schema_version
        return ctx