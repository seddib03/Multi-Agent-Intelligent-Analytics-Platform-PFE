from app.core.config import settings
from .schemas import NLQOutput, Intent
from .prompts import NLQ_SYSTEM, nlq_user_prompt
import re

import re
from .schemas import NLQOutput

ALLOWED_INTENTS = {"analyze", "compare", "predict", "explain", "other"}


def rule_intent(question: str) -> str | None:
    q = question.lower()

    # predict ONLY if explicit forecast words exist
    if re.search(r"\b(predict|forecast|next|prochain|prochaine|prévoir|prévision)\b", q):
        return "predict"

    # compare
    if re.search(r"\b(compare|vs|versus|between|compar)\b", q):
        return "compare"

    # explain
    if re.search(r"\b(explain|why|pourquoi|expliquer)\b", q):
        return "explain"

    # analyze (including KPI + year)
    if re.search(r"\b(total|average|avg|sum|count|rate|volume|in\s+20\d{2}|by)\b", q):
        return "analyze"

    return None


class NLQService:
    def __init__(self, llm):
        self.llm = llm

    def process(self, question: str) -> NLQOutput:
        data = self.llm.generate_pydantic(
            system=NLQ_SYSTEM,
            user=nlq_user_prompt(question),
            response_model=dict,
            temperature=0.0,
        )

        # ---- Guardrails / Normalization ----
        if "raw_question" not in data or not data["raw_question"]:
            data["raw_question"] = question

        # ✅ rule-based override (fix analyze vs predict)
        forced = rule_intent(question)
        if forced:
            data["intent"] = forced

        # intent validation
        intent = data.get("intent", "other")
        if intent not in ALLOWED_INTENTS:
            if data.get("metric") is None:
                data["metric"] = intent
            data["intent"] = "analyze"

        if "confidence" not in data:
            data["confidence"] = 0.6

        if "filters" not in data or data["filters"] is None:
            data["filters"] = {}

        return NLQOutput(**data)