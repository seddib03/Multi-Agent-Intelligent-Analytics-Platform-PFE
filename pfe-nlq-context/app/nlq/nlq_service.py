from app.core.config import settings
from .schemas import NLQOutput, Intent
from .prompts import NLQ_SYSTEM, nlq_user_prompt

ALLOWED_INTENTS = {"analyze", "compare", "predict", "explain", "other"}

class NLQService:
    def __init__(self, llm):
        self.llm = llm

    def process(self, question: str) -> NLQOutput:
        data = self.llm.generate_pydantic(
            system=NLQ_SYSTEM,
            user=nlq_user_prompt(question),
            response_model=dict,   # <- IMPORTANT: get raw dict first
            temperature=0.0,
        )

        # ---- Guardrails / Normalization ----
        if "raw_question" not in data:
            data["raw_question"] = question

        # intent fix: if model outputs something else => map to analyze/other
        intent = data.get("intent", "other")
        if intent not in ALLOWED_INTENTS:
            # heuristic: if metric-like value was put in intent -> treat as metric
            if data.get("metric") is None:
                data["metric"] = intent
            data["intent"] = "analyze"

        if "confidence" not in data:
            data["confidence"] = 0.6

        if "filters" not in data or data["filters"] is None:
            data["filters"] = {}

        # Now validate with Pydantic (strict contract)
        return NLQOutput(**data)