from app.core.config import settings
from app.nlq.schemas import NLQOutput
from .schemas import ContextOutput
from .prompts import CONTEXT_SYSTEM, context_user_prompt
from .resources_loader import load_yaml

class ContextService:
    def __init__(self, llm):
        self.llm = llm
        self.kpi_catalog = load_yaml("sector_kpi_map.yaml")
        self.schema_registry = load_yaml("sector_schema_registry.yaml")

    def enrich(self, nlq: NLQOutput) -> ContextOutput:
        prompt = context_user_prompt(
            nlq_dict=nlq.model_dump(),
            kpi_catalog=self.kpi_catalog,
            schema_registry=self.schema_registry,
            schema_version=settings.schema_version,
        )

        data = self.llm.generate_pydantic(
            system=CONTEXT_SYSTEM,
            user=prompt,
            response_model=dict,      # <- raw dict first
            temperature=0.0,
        )

        # ---- Guardrails / Normalization ----
        if "intent" not in data or not data["intent"]:
            data["intent"] = nlq.intent

        if "schema_version" not in data or not data["schema_version"]:
            data["schema_version"] = settings.schema_version

        if "filters" not in data or data["filters"] is None:
            data["filters"] = nlq.filters or {}

        if "confidence" not in data:
            data["confidence"] = 0.6

        # Now validate
        return ContextOutput(**data)