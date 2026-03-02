from app.core.config import settings
from app.core.llm_client import OpenAILLMClient
from .schemas import NLQOutput
from .prompts import NLQ_SYSTEM, nlq_user_prompt

class NLQService:
    def __init__(self, llm: OpenAILLMClient):
        self.llm = llm

    def process(self, question: str) -> NLQOutput:
        return self.llm.parse_with_pydantic(
            model=settings.openai_model,
            system=NLQ_SYSTEM,
            user=nlq_user_prompt(question),
            response_model=NLQOutput,
        )