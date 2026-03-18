"""
Evaluation Framework — LLM-as-Judge
=====================================
PFE — DXC Technology | Intelligence Analytics Platform
Remarque encadrant R3

Architecture :
--------------
    use_cases.yaml (100 cas)
            │
            ▼
    EvaluationRunner.run()
            │  pour chaque cas
            ▼
    NLQAgent.chat()  ←── réponse du LLM actuel (Llama 3.1 8B)
            │
            ▼
    LLMJudge.judge()  ←── juge : Llama 3.1 70B (OpenRouter) ou GPT-4o
            │
            ▼
    EvaluationReport (JSON + console)

Métriques évaluées par le juge :
---------------------------------
  1. intent_accuracy    — intent prédit == intent attendu (0 ou 1)
  2. answer_relevance   — la réponse répond à la question (0–5)
  3. language_match     — langue réponse == langue question (0 ou 1)
  4. kpi_accuracy       — KPI référencé == KPI attendu (0 ou 1, si applicable)
  5. sql_quality        — SQL correct et précis (0–5, si applicable)
  6. orchestrator_match — routing correct (0 ou 1, si applicable)

Score global : moyenne pondérée des métriques applicables (0–100%)

Usage :
-------
    # Lancer tous les cas
    python -m tests.evaluation.run_evaluation

    # Lancer un secteur spécifique
    python -m tests.evaluation.run_evaluation --sector transport

    # Lancer N cas aléatoires
    python -m tests.evaluation.run_evaluation --sample 20

    # Utiliser un modèle juge spécifique
    python -m tests.evaluation.run_evaluation --judge-model gpt-4o
"""

# ── sys.path fix — DOIT être en premier, avant tout import projet ────────────
# Fonctionne avec : python run_evaluation.py
#                   python -m tests.evaluation.run_evaluation
#                   pytest tests/evaluation/
import sys
import os
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
import time
import random
import argparse
import yaml
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from agents.context_sector_agent import ContextSectorAgent, ColumnMetadata
from agents.nlq_agent import NLQAgent


# ══════════════════════════════════════════════════════════════════════════════
# MODÈLES DE DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class JudgeScore:
    """Score détaillé retourné par le juge LLM."""
    intent_accuracy    : float = 0.0   # 0 ou 1
    answer_relevance   : float = 0.0   # 0–5 → normalisé sur 1
    language_match     : float = 0.0   # 0 ou 1
    kpi_accuracy       : Optional[float] = None   # None si non applicable
    sql_quality        : Optional[float] = None   # None si non applicable
    orchestrator_match : Optional[float] = None   # None si non applicable
    reasoning          : str = ""

    @property
    def global_score(self) -> float:
        """Moyenne pondérée des métriques applicables (0–1)."""
        scores, weights = [], []

        scores.append(self.intent_accuracy);    weights.append(2.0)   # poids fort
        scores.append(self.answer_relevance / 5.0); weights.append(2.0)
        scores.append(self.language_match);     weights.append(1.5)   # R4

        if self.kpi_accuracy is not None:
            scores.append(self.kpi_accuracy);  weights.append(1.5)
        if self.sql_quality is not None:
            scores.append(self.sql_quality / 5.0); weights.append(1.5)
        if self.orchestrator_match is not None:
            scores.append(self.orchestrator_match); weights.append(2.0)

        if not scores:
            return 0.0
        return round(sum(s * w for s, w in zip(scores, weights)) / sum(weights), 4)

    @property
    def global_score_pct(self) -> str:
        return f"{self.global_score * 100:.1f}%"


@dataclass
class EvaluationResult:
    """Résultat d'un cas de test."""
    case_id      : str
    sector       : str
    intent_gt    : str   # ground truth
    intent_pred  : str   # prédit par le système
    language     : str
    question     : str
    answer       : str
    score        : JudgeScore
    latency_ms   : int
    error        : Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.score.global_score >= 0.6 and self.error is None


@dataclass
class EvaluationReport:
    """Rapport complet de l'évaluation."""
    timestamp    : str
    model_tested : str
    judge_model  : str
    total_cases  : int
    results      : list[EvaluationResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total_cases if self.total_cases else 0.0

    @property
    def avg_global_score(self) -> float:
        scores = [r.score.global_score for r in self.results if not r.error]
        return round(sum(scores) / len(scores), 4) if scores else 0.0

    @property
    def avg_latency_ms(self) -> float:
        lats = [r.latency_ms for r in self.results if not r.error]
        return round(sum(lats) / len(lats), 1) if lats else 0.0

    def by_sector(self) -> dict[str, dict]:
        """Métriques agrégées par secteur."""
        sectors: dict[str, list[EvaluationResult]] = {}
        for r in self.results:
            sectors.setdefault(r.sector, []).append(r)
        out = {}
        for s, results in sectors.items():
            scores = [r.score.global_score for r in results if not r.error]
            out[s] = {
                "total"     : len(results),
                "passed"    : sum(1 for r in results if r.passed),
                "avg_score" : round(sum(scores) / len(scores), 4) if scores else 0.0,
                "pass_rate" : f"{sum(1 for r in results if r.passed) / len(results) * 100:.1f}%",
            }
        return out

    def by_intent(self) -> dict[str, dict]:
        """Métriques agrégées par intent ground truth."""
        intents: dict[str, list[EvaluationResult]] = {}
        for r in self.results:
            intents.setdefault(r.intent_gt, []).append(r)
        out = {}
        for i, results in intents.items():
            scores = [r.score.global_score for r in results if not r.error]
            correct = sum(1 for r in results if r.intent_pred == r.intent_gt)
            out[i] = {
                "total"          : len(results),
                "intent_correct" : correct,
                "intent_accuracy": f"{correct / len(results) * 100:.1f}%",
                "avg_score"      : round(sum(scores) / len(scores), 4) if scores else 0.0,
            }
        return out

    def language_scores(self) -> dict[str, float]:
        """Taux de respect de la langue par langue."""
        langs: dict[str, list[float]] = {}
        for r in self.results:
            if not r.error:
                langs.setdefault(r.language, []).append(r.score.language_match)
        return {
            lang: round(sum(vals) / len(vals) * 100, 1)
            for lang, vals in langs.items()
        }


# ══════════════════════════════════════════════════════════════════════════════
# LLM JUDGE
# ══════════════════════════════════════════════════════════════════════════════

class LLMJudge:
    """
    Juge LLM — évalue la qualité des réponses du système.

    Modèle recommandé :
      - meta-llama/llama-3.1-70b-instruct (OpenRouter, gratuit)
      - openai/gpt-4o (payant, haute précision)

    Le juge reçoit :
    - La question originale
    - L'intent ground truth
    - La réponse du système
    - Les éléments attendus (expected)
    Et retourne un JSON structuré avec les scores.
    """

    def __init__(self, openrouter_api_key: str, model: str = "meta-llama/llama-3.1-70b-instruct"):
        self.model = model
        self.llm = ChatOpenAI(
            model       = model,
            temperature = 0,
            api_key     = openrouter_api_key,
            base_url    = "https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://dxc-pfe-analytics.local",
                "X-Title"     : "DXC Intelligence Analytics Platform — Evaluation",
            },
        )

    def judge(
        self,
        question     : str,
        intent_gt    : str,
        intent_pred  : str,
        language_gt  : str,   # "fr" | "ar" | "en"
        answer       : str,
        expected     : dict,
        routing_info : dict,  # {requires_orchestrator, routing_target, sub_agent}
    ) -> JudgeScore:
        """Évalue une réponse et retourne un JudgeScore."""

        # Construire le contexte attendu pour le juge
        expected_text = json.dumps(expected, ensure_ascii=False, indent=2)

        # Mapping langue → nom complet pour le juge
        lang_names = {"fr": "French", "ar": "Arabic", "en": "English"}
        expected_lang = lang_names.get(language_gt, language_gt)

        judge_prompt = f"""You are an expert AI system evaluator for a business analytics platform.
Evaluate the system's response against the ground truth criteria.

═══ QUESTION ═══
Language: {expected_lang}
Question: {question}

═══ GROUND TRUTH ═══
Expected intent: {intent_gt}
Expected language of response: {expected_lang}
Expected elements: {expected_text}

═══ SYSTEM RESPONSE ═══
Intent predicted: {intent_pred}
Routing: requires_orchestrator={routing_info.get('requires_orchestrator')}, target={routing_info.get('routing_target')}, sub_agent={routing_info.get('sub_agent')}
Answer: {answer[:800]}

═══ SCORING INSTRUCTIONS ═══
Score each applicable metric strictly and objectively.

1. intent_accuracy (0 or 1):
   - 1 if predicted intent matches expected intent EXACTLY
   - 0 otherwise

2. answer_relevance (0–5):
   - 5: Perfect answer, addresses all aspects of the question with correct data/SQL
   - 4: Good answer, minor gaps or imprecisions
   - 3: Acceptable, answers the question but misses important details
   - 2: Partial, only addresses part of the question
   - 1: Poor, mostly irrelevant or wrong
   - 0: Completely wrong or empty

3. language_match (0 or 1):
   - 1 if the 'answer' field is written ENTIRELY in {expected_lang}
   - 0 if the answer is in a different language or mixes languages
   - IMPORTANT: Arabic responses must contain Arabic script, not just romanized Arabic

4. kpi_accuracy (0 or 1, or null if no KPI expected):
   - 1 if the correct KPI name is referenced
   - 0 if wrong or missing KPI
   - null if no specific KPI was expected

5. sql_quality (0–5, or null if no SQL expected):
   - 5: Syntactically correct SQL with exact column names, proper filters/aggregations
   - 3: Mostly correct SQL with minor issues
   - 1: SQL present but with significant errors
   - 0: No SQL when SQL was required
   - null if SQL was not expected for this intent

6. orchestrator_match (0 or 1, or null if orchestrator not expected):
   - 1 if requires_orchestrator=true AND routing_target matches expected
   - 0 if routing is wrong
   - null if orchestrator was not expected

OUTPUT: Respond ONLY with valid JSON, no markdown.
{{
  "intent_accuracy"    : 0,
  "answer_relevance"   : 0,
  "language_match"     : 0,
  "kpi_accuracy"       : null,
  "sql_quality"        : null,
  "orchestrator_match" : null,
  "reasoning"          : "Brief 2-3 sentence justification of the scores"
}}"""

        try:
            raw = self.llm.invoke([HumanMessage(content=judge_prompt)]).content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)
            return JudgeScore(
                intent_accuracy    = float(data.get("intent_accuracy", 0)),
                answer_relevance   = float(data.get("answer_relevance", 0)),
                language_match     = float(data.get("language_match", 0)),
                kpi_accuracy       = float(data["kpi_accuracy"]) if data.get("kpi_accuracy") is not None else None,
                sql_quality        = float(data["sql_quality"])   if data.get("sql_quality")   is not None else None,
                orchestrator_match = float(data["orchestrator_match"]) if data.get("orchestrator_match") is not None else None,
                reasoning          = data.get("reasoning", ""),
            )
        except Exception as e:
            # Fallback en cas d'erreur du juge
            return JudgeScore(
                intent_accuracy  = 1.0 if intent_pred == intent_gt else 0.0,
                answer_relevance = 3.0,
                language_match   = 0.0,
                reasoning        = f"Judge error: {e}",
            )


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

class EvaluationRunner:
    """
    Orchestrateur de l'évaluation — charge les cas, appelle le système,
    fait juger les réponses, génère le rapport.
    """

    USE_CASES_PATH = Path(__file__).parent / "use_cases.yaml"
    REPORTS_DIR    = Path(__file__).parent / "reports"

    # Colonnes de test génériques pour la détection de secteur
    SECTOR_COLUMNS = {
        "transport"     : [
            ColumnMetadata(name="flight_id",      description="Identifiant de vol"),
            ColumnMetadata(name="delay_minutes",  description="Retard en minutes"),
            ColumnMetadata(name="route",          description="Route de vol"),
            ColumnMetadata(name="departure_time", description="Heure de départ"),
        ],
        "finance"       : [
            ColumnMetadata(name="loan_id",        description="Identifiant du prêt"),
            ColumnMetadata(name="credit_score",   description="Score de crédit"),
            ColumnMetadata(name="npl_flag",       description="Indicateur de créance douteuse"),
            ColumnMetadata(name="amount_mad",     description="Montant en MAD"),
        ],
        "retail"        : [
            ColumnMetadata(name="product_id",     description="Identifiant produit"),
            ColumnMetadata(name="sales_amount",   description="Montant des ventes"),
            ColumnMetadata(name="customer_id",    description="Identifiant client"),
            ColumnMetadata(name="category",       description="Catégorie produit"),
        ],
        "manufacturing" : [
            ColumnMetadata(name="machine_id",     description="Identifiant machine"),
            ColumnMetadata(name="downtime_hours", description="Heures d'arrêt"),
            ColumnMetadata(name="oee_score",      description="Score OEE"),
            ColumnMetadata(name="defect_count",   description="Nombre de défauts"),
        ],
        "public"        : [
            ColumnMetadata(name="request_id",     description="Identifiant de demande"),
            ColumnMetadata(name="processing_days",description="Délai de traitement en jours"),
            ColumnMetadata(name="service_type",   description="Type de service public"),
            ColumnMetadata(name="citizen_id",     description="Identifiant citoyen"),
        ],
    }

    def __init__(
        self,
        openrouter_api_key : str,
        judge_model        : str = "meta-llama/llama-3.1-70b-instruct",
        verbose            : bool = True,
        delay_between_calls: float = 1.0,  # secondes entre appels API (rate limit)
    ):
        self.verbose             = verbose
        self.delay               = delay_between_calls

        # Agent testé (Llama 3.1 8B via OpenRouter)
        self.sector_agent = ContextSectorAgent(
            openrouter_api_key = openrouter_api_key,
            verbose            = False,
        )
        self.nlq_agent = NLQAgent(
            openrouter_api_key = openrouter_api_key,
            verbose            = False,
        )

        # Juge LLM (modèle plus puissant)
        self.judge = LLMJudge(
            openrouter_api_key = openrouter_api_key,
            model              = judge_model,
        )

        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def load_cases(
        self,
        sector : Optional[str] = None,
        sample : Optional[int] = None,
        tags   : Optional[list[str]] = None,
    ) -> list[dict]:
        """Charge et filtre les cas de test depuis use_cases.yaml."""
        with open(self.USE_CASES_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        cases = data["use_cases"]

        if sector:
            cases = [c for c in cases if c["sector"] == sector]
        if tags:
            cases = [c for c in cases if any(t in c.get("tags", []) for t in tags)]
        if sample and sample < len(cases):
            cases = random.sample(cases, sample)

        return cases

    def run_single(self, case: dict) -> EvaluationResult:
        """Exécute un cas de test unique et retourne son résultat."""
        case_id    = case["id"]
        sector     = case["sector"]
        intent_gt  = case["intent"]
        question   = case["question"]
        language   = case["language"]
        expected   = case.get("expected", {})

        if self.verbose:
            print(f"  [{case_id}] {question[:60]}...")

        t_start = time.time()

        try:
            # 1. Détection de secteur (avec métadonnées — R2)
            columns = self.SECTOR_COLUMNS.get(sector, [])
            ctx = self.sector_agent.detect(question, columns=columns)

            # 2. Chat NLQ
            result = self.nlq_agent.chat(
                user_id        = f"eval_{case_id}",
                question       = question,
                sector_context = ctx,
            )

            latency_ms = int((time.time() - t_start) * 1000)

            # 3. Jugement LLM
            routing_info = {
                "requires_orchestrator": result.requires_orchestrator,
                "routing_target"       : result.routing_target,
                "sub_agent"            : result.sub_agent,
            }
            score = self.judge.judge(
                question     = question,
                intent_gt    = intent_gt,
                intent_pred  = result.intent,
                language_gt  = language,
                answer       = result.answer,
                expected     = expected,
                routing_info = routing_info,
            )

            eval_result = EvaluationResult(
                case_id     = case_id,
                sector      = sector,
                intent_gt   = intent_gt,
                intent_pred = result.intent,
                language    = language,
                question    = question,
                answer      = result.answer,
                score       = score,
                latency_ms  = latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.time() - t_start) * 1000)
            eval_result = EvaluationResult(
                case_id     = case_id,
                sector      = sector,
                intent_gt   = intent_gt,
                intent_pred = "error",
                language    = language,
                question    = question,
                answer      = "",
                score       = JudgeScore(),
                latency_ms  = latency_ms,
                error       = str(e),
            )

        if self.verbose:
            status = "✅" if eval_result.passed else "❌"
            print(f"    {status} Score: {eval_result.score.global_score_pct} | "
                  f"intent: {eval_result.intent_pred} "
                  f"({'✓' if eval_result.intent_pred == intent_gt else '✗'}) | "
                  f"lang: {'✓' if eval_result.score.language_match else '✗'} | "
                  f"{latency_ms}ms")

        return eval_result

    def run(
        self,
        sector : Optional[str] = None,
        sample : Optional[int] = None,
        tags   : Optional[list[str]] = None,
    ) -> EvaluationReport:
        """
        Lance l'évaluation complète (ou filtrée).

        Parameters
        ----------
        sector : str, optional
            Filtre sur un secteur (transport|finance|retail|manufacturing|public)
        sample : int, optional
            Nombre de cas aléatoires à évaluer
        tags   : list[str], optional
            Filtre sur des tags (ex: ["kpi", "arabic"])
        """
        cases = self.load_cases(sector=sector, sample=sample, tags=tags)

        report = EvaluationReport(
            timestamp    = datetime.now().isoformat(),
            model_tested = NLQAgent.MODEL,
            judge_model  = self.judge.model,
            total_cases  = len(cases),
        )

        sep = "═" * 70
        print(f"\n{sep}")
        print(f"  DXC Intelligence Analytics — Evaluation (R3)")
        print(f"  Model : {report.model_tested}")
        print(f"  Judge : {report.judge_model}")
        print(f"  Cases : {len(cases)}")
        print(f"{sep}\n")

        for i, case in enumerate(cases, 1):
            sector_label = f"[{case['sector'].upper()}]"
            print(f"Case {i:3d}/{len(cases)} {sector_label}")
            result = self.run_single(case)
            report.results.append(result)

            # Délai entre appels pour respecter les rate limits
            if i < len(cases):
                time.sleep(self.delay)

        # Rapport final
        self._print_report(report)
        self._save_report(report)
        return report

    def _print_report(self, report: EvaluationReport) -> None:
        sep  = "═" * 70
        sep2 = "─" * 70
        print(f"\n{sep}")
        print(f"  RAPPORT FINAL")
        print(f"{sep2}")
        print(f"  Total        : {report.total_cases} cas")
        print(f"  Passés       : {report.passed_count} ({report.pass_rate * 100:.1f}%)")
        print(f"  Score moyen  : {report.avg_global_score * 100:.1f}%")
        print(f"  Latence moy. : {report.avg_latency_ms:.0f} ms")
        print(f"{sep2}")
        print(f"  PAR SECTEUR :")
        for sector, stats in report.by_sector().items():
            print(f"    {sector.upper():<16} {stats['pass_rate']:>7} pass | "
                  f"avg {stats['avg_score'] * 100:.1f}%")
        print(f"{sep2}")
        print(f"  PAR INTENT :")
        for intent, stats in report.by_intent().items():
            print(f"    {intent:<20} {stats['intent_accuracy']:>7} intent_acc | "
                  f"avg {stats['avg_score'] * 100:.1f}%")
        print(f"{sep2}")
        print(f"  LANGUES (taux respect R4) :")
        for lang, pct in report.language_scores().items():
            print(f"    {lang:<5} → {pct:.1f}%")
        print(f"{sep}")

    def _save_report(self, report: EvaluationReport) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.REPORTS_DIR / f"eval_{ts}.json"

        # Sérialisation
        out = {
            "timestamp"       : report.timestamp,
            "model_tested"    : report.model_tested,
            "judge_model"     : report.judge_model,
            "total_cases"     : report.total_cases,
            "passed_count"    : report.passed_count,
            "pass_rate"       : f"{report.pass_rate * 100:.1f}%",
            "avg_global_score": f"{report.avg_global_score * 100:.1f}%",
            "avg_latency_ms"  : report.avg_latency_ms,
            "by_sector"       : report.by_sector(),
            "by_intent"       : report.by_intent(),
            "language_scores" : report.language_scores(),
            "results"         : [
                {
                    "case_id"     : r.case_id,
                    "sector"      : r.sector,
                    "intent_gt"   : r.intent_gt,
                    "intent_pred" : r.intent_pred,
                    "language"    : r.language,
                    "passed"      : r.passed,
                    "latency_ms"  : r.latency_ms,
                    "error"       : r.error,
                    "score"       : {
                        "global"             : r.score.global_score_pct,
                        "intent_accuracy"    : r.score.intent_accuracy,
                        "answer_relevance"   : r.score.answer_relevance,
                        "language_match"     : r.score.language_match,
                        "kpi_accuracy"       : r.score.kpi_accuracy,
                        "sql_quality"        : r.score.sql_quality,
                        "orchestrator_match" : r.score.orchestrator_match,
                        "reasoning"          : r.score.reasoning,
                    },
                    "question" : r.question,
                    "answer"   : r.answer[:300],
                }
                for r in report.results
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print(f"\n  💾 Rapport sauvegardé : {path}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DXC PFE — Évaluation LLM-as-Judge (Remarque R3)"
    )
    parser.add_argument("--sector",       type=str,  default=None,
                        help="Filtre secteur: transport|finance|retail|manufacturing|public")
    parser.add_argument("--sample",       type=int,  default=None,
                        help="Évalue N cas aléatoires au lieu de tous")
    parser.add_argument("--tags",         type=str,  nargs="+", default=None,
                        help="Filtre par tags: kpi arabic sql comparison ...")
    parser.add_argument("--judge-model",  type=str,
                        default="meta-llama/llama-3.1-70b-instruct",
                        help="Modèle juge (défaut: llama-3.1-70b via OpenRouter)")
    parser.add_argument("--delay",        type=float, default=1.0,
                        help="Délai en secondes entre appels API (défaut: 1.0)")
    parser.add_argument("--no-verbose",   action="store_true",
                        help="Désactive les logs détaillés")
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY non défini dans .env")
        sys.exit(1)

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