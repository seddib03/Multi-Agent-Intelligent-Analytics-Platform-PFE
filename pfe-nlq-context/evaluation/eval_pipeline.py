import json
from pathlib import Path
from app.core.config import settings
from app.core.llm_client import OpenRouterLLMClient
from app.nlq.nlq_service import NLQService
from app.context.context_service import ContextService

DATA = Path(__file__).parent / "dataset.json"

def main():
    items = json.loads(DATA.read_text(encoding="utf-8"))

    llm = OpenRouterLLMClient(api_key=settings.openrouter_api_key, model=settings.openrouter_model)
    nlq = NLQService(llm)
    ctx = ContextService(llm)

    total = len(items)
    ok_intent = 0
    ok_sector = 0

    for it in items:
        q = it["question"]
        exp_intent = it["expected_intent"]
        exp_sector = it["expected_sector"]

        nlq_out = nlq.process(q)
        ctx_out = ctx.enrich(nlq_out)

        if nlq_out.intent == exp_intent:
            ok_intent += 1
        if ctx_out.sector == exp_sector:
            ok_sector += 1

        print(f"- Q: {q}")
        print(f"  got: intent={nlq_out.intent}, sector={ctx_out.sector}, exec={ctx_out.execution_type}")

    print("\nRESULTS")
    print(f"Intent accuracy: {ok_intent}/{total} = {ok_intent/total:.2f}")
    print(f"Sector accuracy: {ok_sector}/{total} = {ok_sector/total:.2f}")

if __name__ == "__main__":
    main()