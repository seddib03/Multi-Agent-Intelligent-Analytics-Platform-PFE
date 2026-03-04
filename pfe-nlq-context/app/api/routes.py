from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings
from app.core.llm_client import OpenRouterLLMClient
from app.nlq.nlq_service import NLQService
from app.context.context_service import ContextService
from app.core.request_id import new_request_id, now_ms
import logging
log = logging.getLogger("api")

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
    rid = new_request_id()
    t0 = now_ms()
    try:
        nlq_out = _nlq.process(req.question)
        ctx_out = _ctx.enrich(nlq_out)
        dt = now_ms() - t0
        log.info(f"rid={rid} intent={nlq_out.intent} sector={ctx_out.sector} exec={ctx_out.execution_type} ms={dt}")

        response = {"request_id": rid, "next_action": ctx_out.execution_type, "message": "ok"}
        if req.debug:
            response["nlq"] = nlq_out.model_dump()
            response["context"] = ctx_out.model_dump()
        return response
    except Exception as e:
        dt = now_ms() - t0
        log.exception(f"rid={rid} failed ms={dt}")
        raise HTTPException(status_code=500, detail=str(e))