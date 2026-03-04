import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

from app.core.config import settings
from app.core.llm_client import OpenRouterLLMClient
from app.nlq.nlq_service import NLQService
from app.context.context_service import ContextService

DATA = Path(__file__).parent / "dataset.json"


def acc(hits: int, total: int) -> float:
    return 0.0 if total == 0 else hits / total


def evaluate(llm_client) -> Dict[str, Any]:
    items = json.loads(DATA.read_text(encoding="utf-8"))

    nlq = NLQService(llm_client)
    ctx = ContextService(llm_client)

    total = len(items)

    hit_intent = 0
    hit_sector = 0
    hit_kpi = 0

    intent_errors: List[Dict[str, Any]] = []
    sector_errors: List[Dict[str, Any]] = []
    kpi_errors: List[Dict[str, Any]] = []

    for idx, it in enumerate(items, start=1):
        q = it["question"]
        exp_intent = it.get("expected_intent")
        exp_sector = it.get("expected_sector")
        exp_kpi = it.get("expected_kpi")  # required in our dataset, but kept safe

        nlq_out = nlq.process(q)
        ctx_out = ctx.enrich(nlq_out)

        got_intent = nlq_out.intent
        got_sector = ctx_out.sector
        got_kpi = ctx_out.canonical_metric

        ok_i = (got_intent == exp_intent)
        ok_s = (got_sector == exp_sector)
        ok_k = (got_kpi == exp_kpi)

        hit_intent += int(ok_i)
        hit_sector += int(ok_s)
        hit_kpi += int(ok_k)

        # Print one-line per sample (good for debugging)
        print(
            f"[{idx:02d}] intent {got_intent} ({'OK' if ok_i else 'NO'}) | "
            f"sector {got_sector} ({'OK' if ok_s else 'NO'}) | "
            f"kpi {got_kpi} ({'OK' if ok_k else 'NO'}) | Q: {q}"
        )

        if not ok_i:
            intent_errors.append({
                "question": q,
                "expected": exp_intent,
                "got": got_intent
            })

        if not ok_s:
            sector_errors.append({
                "question": q,
                "expected": exp_sector,
                "got": got_sector
            })

        if not ok_k:
            kpi_errors.append({
                "question": q,
                "expected": exp_kpi,
                "got": got_kpi
            })

    results = {
        "total": total,
        "intent_accuracy": acc(hit_intent, total),
        "sector_accuracy": acc(hit_sector, total),
        "kpi_accuracy": acc(hit_kpi, total),
        "intent_hits": f"{hit_intent}/{total}",
        "sector_hits": f"{hit_sector}/{total}",
        "kpi_hits": f"{hit_kpi}/{total}",
        "intent_errors_count": len(intent_errors),
        "sector_errors_count": len(sector_errors),
        "kpi_errors_count": len(kpi_errors),
        "intent_errors": intent_errors[:10],  # show first 10 (avoid huge output)
        "sector_errors": sector_errors[:10],
        "kpi_errors": kpi_errors[:10],
        "model": settings.openrouter_model,
        "schema_version": settings.schema_version,
    }

    return results


def main():
    # Mode: "openrouter" only (you already use it and it works)
    llm = OpenRouterLLMClient(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model
    )

    results = evaluate(llm)
    print("\n=== EVALUATION SUMMARY (OpenRouter) ===")
    for k, v in results.items():
        if isinstance(v, list):
            continue
        print(f"{k}: {v}")

    # Print errors nicely
    if results["intent_errors_count"] > 0:
        print("\n--- Intent Errors (first 10) ---")
        for e in results["intent_errors"]:
            print(f"- expected={e['expected']} got={e['got']} | Q: {e['question']}")

    if results["sector_errors_count"] > 0:
        print("\n--- Sector Errors (first 10) ---")
        for e in results["sector_errors"]:
            print(f"- expected={e['expected']} got={e['got']} | Q: {e['question']}")

    if results["kpi_errors_count"] > 0:
        print("\n--- KPI Errors (first 10) ---")
        for e in results["kpi_errors"]:
            print(f"- expected={e['expected']} got={e['got']} | Q: {e['question']}")


if __name__ == "__main__":
    main()