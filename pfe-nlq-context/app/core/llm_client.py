import json
from typing import Type, TypeVar
from pydantic import BaseModel
from openai import OpenAI

T = TypeVar("T", bound=BaseModel)

class OpenRouterLLMClient:
    """
    OpenRouter client (OpenAI-compatible API).
    Uses JSON mode (response_format=json_object) then validates via Pydantic.
    """
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is missing. Set it in .env")

        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "http://localhost",
                "X-Title": "PFE Multi-Agent Project"
            }
        )

    def generate_pydantic(
        self,
        *,
        system: str,
        user: str,
        response_model: Type[T],
        temperature: float = 0.0,
    ) -> T:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system.strip()},
                {"role": "user", "content": user.strip()},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )

        content = completion.choices[0].message.content
        if not content:
            raise RuntimeError("LLM returned empty content.")

        # Parse JSON then validate via Pydantic
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from LLM: {e}\nRaw content: {content}")

        if response_model is dict:
            return data  # raw dict

        return response_model(**data)