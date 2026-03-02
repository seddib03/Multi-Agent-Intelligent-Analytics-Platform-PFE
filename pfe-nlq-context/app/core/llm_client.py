from openai import OpenAI
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class OpenAILLMClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def parse_with_pydantic(
        self,
        *,
        model: str,
        system: str,
        user: str,
        response_model: Type[T],
    ) -> T:
        """
        Utilise la méthode parse() du SDK pour obtenir directement un objet Pydantic.
        (Structured Outputs)
        """
        completion = self.client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=response_model,  # le SDK construit le json_schema
        )
        # .parsed -> objet Pydantic
        return completion.choices[0].message.parsed