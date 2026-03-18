"""
Lanceur rapide — Évaluation LLM-as-Judge
=========================================
PFE DXC Technology — Remarque encadrant R3

Usage depuis le dossier sprint1/ :
    python run_eval.py                          # tous les 100 cas
    python run_eval.py --sector transport       # 20 cas transport
    python run_eval.py --sample 10              # 10 cas aléatoires
    python run_eval.py --sector finance --sample 5
    python run_eval.py --tags kpi arabic        # filtrer par tags
"""
import sys
import os
from pathlib import Path

# ── 1. Ajouter sprint1/ au path ───────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 2. Charger le .env AVANT tout import qui lit os.getenv() ─────────────────
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

# ── 3. Imports projet ─────────────────────────────────────────────────────────
from tests.evaluation import EvaluationRunner
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DXC PFE — Evaluation LLM-as-Judge (Remarque R3)"
    )
    parser.add_argument("--sector",      type=str,   default=None,
                        help="transport|finance|retail|manufacturing|public")
    parser.add_argument("--sample",      type=int,   default=None,
                        help="N cas aleatoires (defaut: tous les 100)")
    parser.add_argument("--tags",        type=str,   nargs="+", default=None,
                        help="kpi arabic sql comparison ...")
    parser.add_argument("--judge-model", type=str,
                        default="meta-llama/llama-3.1-70b-instruct",
                        help="Modele juge OpenRouter")
    parser.add_argument("--delay",       type=float, default=1.0,
                        help="Delai entre appels API en secondes")
    parser.add_argument("--no-verbose",  action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY non trouve")
        print(f"   .env cherche dans : {_ROOT / '.env'}")
        sys.exit(1)

    print(f"API Key OK ({api_key[:20]}...)")

    runner = EvaluationRunner(
        openrouter_api_key  = api_key,
        judge_model         = args.judge_model,
        verbose             = not args.no_verbose,
        delay_between_calls = args.delay,
    )

    runner.run(
        sector = args.sector,
        sample = args.sample,
        tags   = args.tags,
    )