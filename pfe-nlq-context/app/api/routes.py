from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings
from app.core.llm_client import OpenRouterLLMClient
from app.nlq.nlq_service import NLQService
from app.context.context_service import ContextService

router = APIRouter()

class AskRequest(BaseModel):
    question: str
    debug: bool = True

_llm = OpenRouterLLMClient(
    api_key=settings.openrouter_api_key,
    model=settings.openrouter_model
)
_nlq = NLQService(_llm)
_ctx = ContextService(_llm)

@router.post("/ask")
def ask(req: AskRequest):
    try:
        nlq_out = _nlq.process(req.question)
        ctx_out = _ctx.enrich(nlq_out)

        response = {
            "next_action": ctx_out.execution_type,
            "message": "parsed_ok_openrouter"
        }
        if req.debug:
            response["nlq"] = nlq_out.model_dump()
            response["context"] = ctx_out.model_dump()

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))