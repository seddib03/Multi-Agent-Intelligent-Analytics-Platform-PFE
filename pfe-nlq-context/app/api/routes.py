from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings
from app.core.llm_client import OpenAILLMClient
from app.nlq.nlq_service import NLQService
from app.context.context_service import ContextService

router = APIRouter()

class AskRequest(BaseModel):
    question: str
    debug: bool = True

llm = OpenAILLMClient(api_key=settings.openai_api_key)
nlq_service = NLQService(llm)
context_service = ContextService(llm)

@router.post("/ask")
def ask(req: AskRequest):
    try:
        nlq = nlq_service.process(req.question)
        ctx = context_service.enrich(nlq)

        resp = {"next_action": ctx.execution_type, "message": "ok"}
        if req.debug:
            resp["nlq"] = nlq.model_dump()
            resp["context"] = ctx.model_dump()
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))