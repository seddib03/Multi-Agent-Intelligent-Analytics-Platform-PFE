"""
NLQ Layer — LangGraph
======================
PFE — DXC Technology | Intelligence Analytics Platform
Sprint 1 → Sprint 2

Architecture LangGraph
-----------------------
Ce module implémente le bloc "NLQ Layer" comme un StateGraph LangGraph
à 3 nœuds :

    ┌─────────────────────────────────────────────────────────────┐
    │                     NLQ Layer Graph                         │
    │                                                             │
    │  [classify_intent]                                          │
    │       │                                                     │
    │       ├── requires_orchestrator=True ──► [prepare_routing]  │
    │       │                                       │             │
    │       └── requires_orchestrator=False ─► [generate_answer]  │
    │                                               │             │
    │                                              END            │
    └─────────────────────────────────────────────────────────────┘

Changements Sprint 2
---------------------
FIX 1 — classify_intent : guard "intent not in ROUTING_TABLE" → fallback "explanation"
         intent ne peut plus jamais valoir "unknown" ou une valeur hors table

FIX 2 — classify_intent : historique 3 derniers tours + colonnes disponibles
         injectés dans le prompt LLM
         → meilleure détection is_follow_up
         → meilleure distinction sql (colonne citée) vs aggregation

FIX 3 — generate_answer : column_stats + quality_score ajoutés dans data_section
         → SQL généré avec min/max/mean réels des colonnes du dataset

FIX 4 — generate_answer : fallback NLQResponse avec tous les champs explicites
         → requires_orchestrator=False, routing_target=None, sub_agent=None garantis
         même quand le LLM retourne du texte non-JSON

FIX 5 — NLQAgent.chat() : historique sauvegardé pour TOUS les intents
         (NLQ direct + Orchestrateur)
         → contexte conversationnel complet pour les questions de suivi

NOUVEAU Sprint 2 — Memory Layer (Redis)
----------------------------------------
L'historique des conversations est persisté dans Redis (illimité).
Si Redis est indisponible → fallback automatique dict RAM (session courante).
Variable d'environnement : REDIS_URL (défaut: redis://localhost:6379)

Note data_profile
-----------------
L'Orchestrateur transforme le JSON du Data Prep Agent en format plat
compatible NLQAgent avant d'appeler /chat. Ce module reçoit donc
directement un dict { columns, numeric_columns, column_stats, ... }
sans conversion supplémentaire nécessaire.

Table de routing complète (architecture DXC)
---------------------------------------------
NLQ direct (requires_orchestrator=False) :
    sql, aggregation, comparison, explanation

→ Orchestrateur :
    prediction      → {sector}_agent     [sub_agent=sector_prediction]
    sector_analysis → {sector}_agent     [sub_agent=sector_explanation]
    anomaly         → generic_predictive_agent
    dashboard       → insight_agent
    kpi_chart       → insight_agent
    insight         → insight_agent
"""

import json
import os
from typing import Optional, TypedDict
from pydantic import BaseModel, Field

# Redis — import optionnel
# Si redis-py n'est pas installé → fallback RAM automatique
try:
    import redis as redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from langgraph.graph import StateGraph, END

from agents.context_sector_agent import SectorContext


# ══════════════════════════════════════════════════════════════════
# REMARQUE ENCADRANT R4 — DÉTECTION DE LANGUE
# La réponse est systématiquement dans la langue de la question.
# FR→FR | AR→AR | EN→EN — détecté à chaque appel, sans configuration.
# ══════════════════════════════════════════════════════════════════

import re as _re

_LANG_AR = _re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
_LANG_FR = _re.compile(
    r'\b(je|tu|il|elle|nous|vous|ils|elles|le|la|les|de|du|des|un|une|'
    r'quel|quelle|quels|quelles|est|sont|avoir|faire|aller|comment|'
    r'pourquoi|combien|quand|où|bonjour|merci|avec|pour|dans|sur|par|'
    r'que|qui|dont|mais|ou|et|donc|car|même|tout|très|bien|ici|là|'
    r'retard|moyen|taux|nombre|montant|secteur|analyse|données|résultat)\b',
    _re.IGNORECASE
)
_LANG_EN = _re.compile(
    r'\b(i|you|he|she|we|they|the|a|an|is|are|was|were|have|has|do|does|'
    r'what|which|who|where|when|why|how|show|give|list|find|get|'
    r'please|thank|yes|no|and|or|but|with|for|in|on|by|to|from|of|at|'
    r'this|that|my|your|our|their|can|could|would|should|'
    r'delay|average|rate|number|amount|sector|analysis|data|result)\b',
    _re.IGNORECASE
)


def detect_language(text: str) -> str:
    """
    Détecte la langue principale du texte (R4 — encadrant).

    Priorité : Arabe (Unicode) > Français (mots-clés) > Anglais.
    Retourne "French" | "Arabic" | "English".
    """
    if _LANG_AR.search(text):
        return "Arabic"
    fr = len(_LANG_FR.findall(text))
    en = len(_LANG_EN.findall(text))
    if fr >= en:
        return "French"
    return "English"


# ══════════════════════════════════════════════════════════════════
# TABLE DE ROUTING — source de vérité
# ══════════════════════════════════════════════════════════════════

ROUTING_TABLE: dict[str, dict] = {
    # ── NLQ répond directement ──────────────────────────────────────────
    "sql"         : {"requires_orchestrator": False, "routing_target": None,
                     "sub_agent": None,
                     "description": "NLQ Agent → direct (raw data query)"},
    "aggregation" : {"requires_orchestrator": False, "routing_target": None,
                     "sub_agent": None,
                     "description": "NLQ Agent → direct (computed metric)"},
    "comparison"  : {"requires_orchestrator": False, "routing_target": None,
                     "sub_agent": None,
                     "description": "NLQ Agent → direct (comparison)"},
    "explanation" : {"requires_orchestrator": False, "routing_target": None,
                     "sub_agent": None,
                     "description": "NLQ Agent → direct (qualitative analysis)"},

    # ── Orchestrateur → Agent Spécifique → Sector Predictive Model ──────
    "prediction"  : {"requires_orchestrator": True,
                     "routing_target": "USE_SECTOR_CONTEXT",
                     "sub_agent": "sector_prediction",
                     "description": "Orchestrator → {sector}_agent [sector_prediction]"},

    # ── Orchestrateur → Generic Predictive Agent (AutoML complet) ───────
    "anomaly"     : {"requires_orchestrator": True,
                     "routing_target": "generic_predictive_agent",
                     "sub_agent": None,
                     "description": "Orchestrator → Generic Predictive Agent (AutoML)"},

    # ── Orchestrateur → Agent Spécifique → Sector Explanation ───────────
    "sector_analysis": {"requires_orchestrator": True,
                        "routing_target": "USE_SECTOR_CONTEXT",
                        "sub_agent": "sector_explanation",
                        "description": "Orchestrator → {sector}_agent [sector_explanation]"},

    # ── Orchestrateur → Insight Agent ───────────────────────────────────
    "dashboard"   : {"requires_orchestrator": True,
                     "routing_target": "insight_agent",
                     "sub_agent": None,
                     "description": "Orchestrator → Insight Agent (Dashboard)"},
    "kpi_chart"   : {"requires_orchestrator": True,
                     "routing_target": "insight_agent",
                     "sub_agent": None,
                     "description": "Orchestrator → Insight Agent (KPI/Chart)"},
    "insight"     : {"requires_orchestrator": True,
                     "routing_target": "insight_agent",
                     "sub_agent": None,
                     "description": "Orchestrator → Insight Agent (Report/BI)"},
}

ORCHESTRATOR_INTENTS   = {i for i, c in ROUTING_TABLE.items() if c["requires_orchestrator"]}
NLQ_DIRECT_INTENTS     = {i for i, c in ROUTING_TABLE.items() if not c["requires_orchestrator"]}
SECTOR_DYNAMIC_INTENTS = {
    i for i, c in ROUTING_TABLE.items()
    if c.get("routing_target") == "USE_SECTOR_CONTEXT"
}


def resolve_routing_target(intent: str, sector_context: SectorContext) -> str:
    """
    Résout le routing_target final selon l'intent et le secteur.

    prediction/sector_analysis → routing depuis SectorContext (dynamique)
    anomaly/dashboard/…        → valeur statique dans ROUTING_TABLE
    """
    routing = ROUTING_TABLE.get(intent, ROUTING_TABLE["explanation"])
    if routing["routing_target"] == "USE_SECTOR_CONTEXT":
        return sector_context.routing_target
    return routing["routing_target"]


# ══════════════════════════════════════════════════════════════════
# MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════

class IntentClassification(BaseModel):
    """Résultat du nœud classify_intent."""
    intent               : str
    confidence           : float
    requires_orchestrator: bool
    routing_target       : Optional[str] = None
    sub_agent            : Optional[str] = None
    is_follow_up         : bool
    extracted_entities   : dict = Field(default_factory=dict)


class NLQResponse(BaseModel):
    """Réponse finale de la NLQ Layer."""
    answer               : str
    intent               : str
    query_type           : str
    generated_query      : Optional[str]  = None
    kpi_referenced       : Optional[str]  = None
    suggested_chart      : Optional[str]  = None
    requires_orchestrator: bool           = False
    routing_target       : Optional[str]  = None
    sub_agent            : Optional[str]  = None
    orchestrator_payload : Optional[dict] = None
    needs_more_data      : bool           = False


# ══════════════════════════════════════════════════════════════════
# ÉTAT DU GRAPH LANGGRAPH
# ══════════════════════════════════════════════════════════════════

class NLQAgentState(TypedDict):
    """
    État partagé entre les nœuds du NLQ Layer Graph.

    Muté séquentiellement :
      classify_intent  → remplit intent_result
      prepare_routing  → remplit nlq_response (chemin orchestrateur)
      generate_answer  → remplit nlq_response (chemin NLQ direct)
    """
    # Entrées
    user_id       : str
    question      : str
    sector_context: SectorContext
    data_profile  : Optional[dict]

    # Historique (injecté par NLQAgent depuis self._histories)
    history: list[dict]

    # Intermédiaires
    intent_result: Optional[IntentClassification]

    # Sortie finale
    nlq_response: Optional[NLQResponse]

    # Meta
    verbose: bool


# ══════════════════════════════════════════════════════════════════
# NŒUDS DU GRAPH
# ══════════════════════════════════════════════════════════════════

def _make_node_classify_intent(llm: ChatOpenAI):
    """Factory → Nœud : classify_intent."""

    def node_classify_intent(state: NLQAgentState) -> NLQAgentState:
        sector_context = state["sector_context"]
        question       = state["question"]
        history        = state["history"]

        # ── FIX 2 — lire data_profile pour injecter les colonnes ─────────────
        # Sans les colonnes dans le prompt, le LLM confond souvent
        # "aggregation" (colonne connue) et "explanation" (question vague)
        data_profile = state.get("data_profile") or {}

        kpi_list = ", ".join(k.name for k in sector_context.kpis)

        # ── FIX 2 — injecter les 3 derniers tours de conversation ────────────
        # Avant : seulement la dernière question via last_question (1 seul tour)
        # → is_follow_up souvent raté sur les questions de suivi implicites
        # Après : 3 tours complets → le LLM comprend le fil de la conversation
        history_section = ""
        if history:
            last_turns = history[-3:]
            history_section = "CONVERSATION HISTORY (last turns):\n"
            for i, turn in enumerate(last_turns, 1):
                history_section += f"  Q{i}: \"{turn['user']}\"\n"
                history_section += f"  A{i}: \"{turn['assistant'][:120]}...\"\n"
            history_section += "\n"

        # ── FIX 2 — injecter les colonnes disponibles du dataset ─────────────
        # Aide à distinguer sql (colonne citée explicitement)
        # vs aggregation (métrique calculée sans colonne précise)
        columns_hint = ""
        if data_profile.get("columns"):
            cols = data_profile["columns"][:10]  # max 10 pour ne pas surcharger
            columns_hint = f"AVAILABLE COLUMNS: {', '.join(cols)}\n\n"

        # R4 — langue de la question (info pour le classifieur)
        q_lang = detect_language(question)

        prompt = f"""You are the Intent Classifier of an analytics platform.
Classify the user's question to determine which agent handles it.
NOTE: User is writing in {q_lang}. Classify by semantic meaning regardless of language.

SECTOR : {sector_context.sector}
KPIs   : {kpi_list}

{history_section}{columns_hint}USER QUESTION: "{question}"

INTENTS — choose exactly one:

Handled directly by NLQ Agent:
  "sql"             → user wants raw records, filtered lists, direct lookups
  "aggregation"     → user wants a computed metric (avg, sum, count, max, min, %)
  "comparison"      → user wants to compare entities, routes, periods, segments
  "explanation"     → user wants qualitative analysis, explanation, why/how

Handled by Orchestrator → Generic Predictive Agent (AutoML Pipeline):
  "prediction"      → user wants forecast, future values, next period estimates
  "anomaly"         → user wants to detect outliers or abnormal patterns

Handled by Orchestrator → Sector Specific Agent (Prompt Builder → LLM):
  "sector_analysis" → user wants a deep comprehensive sector report

Handled by Orchestrator → Insight Agent (KPI + Chart + Power BI):
  "dashboard"       → user wants to generate or display a full dashboard
  "kpi_chart"       → user wants a specific chart or visualization
  "insight"         → user wants a full analytical report or Power BI export

RULES:
- Single number/metric      → "aggregation"
- List of records           → "sql"
- Two or more things vs     → "comparison"
- Why / How / Explain       → "explanation"
- Future / Forecast         → "prediction"
- Outlier / Anomaly         → "anomaly"
- Full sector report        → "sector_analysis"
- Build/show dashboard      → "dashboard"
- Create chart/graph        → "kpi_chart"
- Full report / export BI   → "insight"

FOLLOW-UP: is_follow_up=true if question uses implicit references (it, that, same...)
           or refers to something mentioned in CONVERSATION HISTORY above.

OUTPUT: valid JSON only, no markdown.

{{
  "intent"            : "one of the intents above",
  "confidence"        : 0.0,
  "is_follow_up"      : false,
  "extracted_entities": {{
    "metric"     : null,
    "time_period": null,
    "entity"     : null
  }}
}}"""

        raw = llm.invoke([HumanMessage(content=prompt)]).content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        try:
            data = json.loads(raw)
        except Exception:
            data = {"intent": "explanation", "confidence": 0.5,
                    "is_follow_up": False, "extracted_entities": {}}

        # ── FIX 1 — guard : intent ne peut jamais être hors ROUTING_TABLE ────
        # Avant : si LLM retourne "unknown", "general", "other" →
        #         intent="unknown" restait dans la réponse finale
        # Après : forcé à "explanation" si hors table → toujours valide
        intent = data.get("intent", "explanation")
        if intent not in ROUTING_TABLE:   # ← FIX 1
            intent = "explanation"        # ← FIX 1

        routing         = ROUTING_TABLE.get(intent, ROUTING_TABLE["explanation"])
        resolved_target = resolve_routing_target(intent, sector_context)

        intent_result = IntentClassification(
            intent                = intent,
            confidence            = data.get("confidence", 0.5),
            requires_orchestrator = routing["requires_orchestrator"],
            routing_target        = resolved_target,
            sub_agent             = routing.get("sub_agent"),
            is_follow_up          = data.get("is_follow_up", False),
            extracted_entities    = data.get("extracted_entities", {}),
        )

        if state.get("verbose"):
            if intent_result.requires_orchestrator:
                sub = f" [{intent_result.sub_agent}]" if intent_result.sub_agent else ""
                print(f"  [Node:classify_intent] 🔀 {intent} ({intent_result.confidence:.0%})"
                      f" → Orchestrator → {intent_result.routing_target}{sub}")
            else:
                print(f"  [Node:classify_intent] ✅ {intent} ({intent_result.confidence:.0%})"
                      f" → NLQ direct")

        return {**state, "intent_result": intent_result}

    return node_classify_intent


def node_prepare_routing(state: NLQAgentState) -> NLQAgentState:
    """
    Nœud : prepare_routing.
    Chemin Orchestrateur — construit le message et le payload.
    """
    intent         = state["intent_result"]
    sector_context = state["sector_context"]
    question       = state["question"]

    # Message lisible pour l'UI
    if intent.intent == "prediction" and intent.sub_agent == "sector_prediction":
        answer = (
            f"Prédiction sectorielle détectée pour le secteur {sector_context.sector}. "
            f"Routing vers {intent.routing_target} "
            f"(Sector Predictive Model pretrained → Sector Prediction Output)."
        )
    elif intent.intent == "sector_analysis" and intent.sub_agent == "sector_explanation":
        answer = (
            f"Analyse approfondie du secteur {sector_context.sector} demandée. "
            f"Routing vers {intent.routing_target} "
            f"(Sector Prompt Builder → LLM Call → Sector Explanation Output)."
        )
    else:
        answer = {
            "generic_predictive_agent": (
                "Détection d'anomalies ML demandée. "
                "Generic Predictive Agent : Dataset Profiling → ML Task Detection → AutoML."
            ),
            "insight_agent": (
                "Génération dashboard/rapport via l'Insight Agent : "
                "KPI/Chart Routing → Processing → Power BI → Insight Output."
            ),
        }.get(
            intent.routing_target,
            f"Routing vers {intent.routing_target} [sub_agent={intent.sub_agent}]."
        )

    # Payload Orchestrateur
    payload: dict = {
        "original_question" : question,
        "sector"            : sector_context.sector,
        "routing_target"    : intent.routing_target,
        "sub_agent"         : intent.sub_agent,
        "intent"            : intent.intent,
        "extracted_entities": intent.extracted_entities,
        "kpis"              : [k.name for k in sector_context.kpis],
    }

    if intent.intent == "prediction" and intent.sub_agent == "sector_prediction":
        payload["task_type"]          = "sector_prediction"
        payload["target_kpi"]         = (intent.extracted_entities.get("metric")
                                         or sector_context.kpis[0].name)
        payload["prediction_horizon"] = intent.extracted_entities.get("time_period", "next_period")
        payload["use_case"]           = sector_context.use_case

    elif intent.routing_target == "generic_predictive_agent":
        payload["task_type"]  = "anomaly_detection"
        payload["target_kpi"] = (intent.extracted_entities.get("metric")
                                 or sector_context.kpis[0].name)

    elif intent.intent == "sector_analysis" and intent.sub_agent == "sector_explanation":
        payload["task_type"]       = "sector_explanation"
        payload["use_case"]        = sector_context.use_case
        payload["dashboard_focus"] = sector_context.dashboard_focus

    elif intent.routing_target == "insight_agent":
        payload["output_type"]        = intent.intent
        payload["recommended_charts"] = sector_context.recommended_charts

    response = NLQResponse(
        answer                = answer,
        intent                = intent.intent,
        query_type            = intent.intent,
        requires_orchestrator = True,
        routing_target        = intent.routing_target,
        sub_agent             = intent.sub_agent,
        orchestrator_payload  = payload,
    )

    return {**state, "nlq_response": response}


def _make_node_generate_answer(llm: ChatOpenAI):
    """Factory → Nœud : generate_answer. Chemin NLQ direct."""

    def node_generate_answer(state: NLQAgentState) -> NLQAgentState:
        intent            = state["intent_result"]
        sector_context    = state["sector_context"]
        data_profile      = state.get("data_profile")
        history           = state["history"]
        question          = state["question"]

        # System prompt
        kpi_block = "\n".join(
            f"  - {k.name} ({k.unit}) : {k.description}"
            for k in sector_context.kpis
        )

        # ── FIX 3 — data_section enrichie avec column_stats + quality_score ──
        # Avant : seulement colonnes/types → SQL générique sans statistiques réelles
        # Après : mean/min/max injectés → SQL précis avec vraies valeurs du dataset
        data_section = ""
        if data_profile:
            cols      = data_profile.get("columns", [])
            rows      = data_profile.get("row_count", "unknown")
            num       = data_profile.get("numeric_columns", [])
            cat       = data_profile.get("categorical_columns", [])
            dt        = data_profile.get("datetime_columns", [])
            miss      = data_profile.get("missing_summary", {})
            col_stats = data_profile.get("column_stats", {})   # ← FIX 3
            quality   = data_profile.get("quality_score")      # ← FIX 3

            # Bloc stats — aide le LLM à écrire du SQL précis
            stats_lines = []
            for col, stats in col_stats.items():
                parts = []
                if "mean"     in stats: parts.append(f"mean={stats['mean']:.2f}")
                if "min"      in stats: parts.append(f"min={stats['min']}")
                if "max"      in stats: parts.append(f"max={stats['max']}")
                if "n_unique" in stats: parts.append(f"{stats['n_unique']} unique values")
                if parts:
                    stats_lines.append(f"    {col}: {', '.join(parts)}")
            stats_block  = "\n".join(stats_lines) if stats_lines else "    (no stats available)"
            quality_line = f"\n  Quality score : {quality:.1f}%" if quality else ""

            data_section = f"""
UPLOADED DATASET PROFILE (source: Data Prep Agent):
  Rows          : {rows}{quality_line}
  All columns   : {', '.join(cols)}
  Numeric       : {', '.join(num) or 'none'}
  Categorical   : {', '.join(cat) or 'none'}
  Datetime      : {', '.join(dt) or 'none'}
  Missing (%)   : {json.dumps(miss, ensure_ascii=False) if miss else 'none'}
  Column stats  :
{stats_block}
⚠ SQL: Use ONLY exact column names listed above. Prefer numeric columns for AVG/SUM/COUNT.
"""

        # ── Remarque encadrant R4 — Langue dynamique ─────────────────────────
        # La réponse est systématiquement dans la langue de la question courante.
        # Cette règle prime sur le profil CustomerAdapter (détection immédiate
        # vs historique) et garantit : FR→FR, AR→AR, EN→EN sans configuration.
        detected_lang    = detect_language(question)
        lang_instruction = (
            f"\nLANGUAGE RULE (mandatory — overrides all other instructions):\n"
            f"  The user asked in {detected_lang}.\n"
            f"  You MUST write your entire 'answer' field in {detected_lang}.\n"
            f"  Do NOT mix languages. Do NOT answer in English if the question was in French or Arabic.\n"
        )

        system_prompt = f"""You are a specialized analytics chatbot for the {sector_context.sector.upper()} sector.

CONTEXT:
  Sector    : {sector_context.sector}
  Use Case  : {sector_context.use_case}
  Dashboard : {sector_context.dashboard_focus}

AVAILABLE KPIs:
{kpi_block}

INTENT     : {intent.intent}
ENTITIES   : {json.dumps(intent.extracted_entities, ensure_ascii=False)}
FOLLOW-UP  : {intent.is_follow_up}
{data_section}{lang_instruction}
RULES:
1. Answer based on intent "{intent.intent}"
2. Generate SQL when intent is "sql" or "aggregation"
3. Reference exact KPI name when relevant
4. Suggest a chart type for metric answers
5. If follow-up=true → connect to previous exchange
6. Stay within the {sector_context.sector} domain

OUTPUT: valid JSON only, no markdown.

{{
  "answer"         : "response text",
  "intent"         : "{intent.intent}",
  "query_type"     : "{intent.intent}",
  "generated_query": "SQL or null",
  "kpi_referenced" : "KPI name or null",
  "suggested_chart": "chart type or null",
  "needs_more_data": false
}}"""

        # Messages avec historique complet
        messages = [SystemMessage(content=system_prompt)]
        for turn in history:
            messages.append(HumanMessage(content=turn["user"]))
            messages.append(AIMessage(content=turn["assistant"]))
        messages.append(HumanMessage(content=question))

        raw = llm.invoke(messages).content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        # ── FIX 4 — fallback NLQResponse avec tous les champs explicites ─────
        # Avant : fallback avec seulement answer/intent/query_type
        # → requires_orchestrator/routing_target/sub_agent absents
        # Après : tous les champs forcés explicitement
        try:
            data = json.loads(raw)
            data["intent"]                = intent.intent
            data["query_type"]            = intent.intent
            data["requires_orchestrator"] = False   # generate_answer = NLQ direct toujours
            data["routing_target"]        = None
            data["sub_agent"]             = None
            response = NLQResponse(**data)
        except Exception:
            response = NLQResponse(          # ← FIX 4
                answer                = raw.strip(),
                intent                = intent.intent,   # garanti depuis classify_intent
                query_type            = intent.intent,
                requires_orchestrator = False,           # NLQ direct → toujours False
                routing_target        = None,
                sub_agent             = None,
            )

        if state.get("verbose"):
            print(f"  [Node:generate_answer] ✅ intent={response.intent}")
            if response.generated_query:
                print(f"  SQL: {response.generated_query[:60]}...")

        return {**state, "nlq_response": response}

    return node_generate_answer


def _routing_condition(state: NLQAgentState) -> str:
    """
    Condition de branchement LangGraph.
    Retourne le nom du prochain nœud selon requires_orchestrator.
    """
    if state["intent_result"].requires_orchestrator:
        return "prepare_routing"
    return "generate_answer"


# ══════════════════════════════════════════════════════════════════
# NLQ AGENT — graph LangGraph
# ══════════════════════════════════════════════════════════════════

class NLQAgent:
    """
    NLQ Layer — implémentée comme un StateGraph LangGraph.

    Graph :
      classify_intent
          │
          ├── requires_orchestrator → prepare_routing → END
          └── NLQ direct            → generate_answer → END

    Memory Layer
    ------------
    L'historique est persisté dans Redis (illimité, survit aux redémarrages).
    Si Redis est indisponible → fallback automatique dict RAM (session courante).

    Variable d'environnement : REDIS_URL (défaut: redis://localhost:6379)

    Installation Redis
    ------------------
    1. Installer Redis :
           Windows  → https://github.com/tporadowski/redis/releases
           Linux    → sudo apt install redis-server && sudo service redis start
           Mac      → brew install redis && brew services start redis
    2. Installer redis-py :
           pip install redis
    3. Ajouter dans .env :
           REDIS_URL=redis://localhost:6379

    Parameters
    ----------
    openrouter_api_key : str
    verbose            : bool

    Examples
    --------
    >>> agent = NLQAgent(openrouter_api_key="sk-or-v1-...")
    >>> agent.using_redis          # True si Redis actif, False si RAM
    >>> result = agent.chat(
    ...     user_id="u1",
    ...     question="Quel est le retard moyen ?",
    ...     sector_context=transport_ctx,
    ... )
    >>> result.requires_orchestrator  # False → NLQ a répondu
    >>> result.routing_target         # None
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    MODEL               = "meta-llama/llama-3.1-8b-instruct"
    REDIS_KEY_PREFIX    = "history:"   # clé Redis : "history:{user_id}"

    def __init__(self, openrouter_api_key: str, verbose: bool = True):
        self.verbose = verbose

        # ── Memory Layer — Redis avec fallback RAM ────────────────────────────
        # Redis est la source de vérité pour l'historique des conversations.
        # Si Redis est indisponible (non installé ou éteint) → fallback dict RAM.
        # L'historique RAM est perdu au redémarrage ; Redis persiste indéfiniment.
        #
        # Variable d'environnement : REDIS_URL (défaut: redis://localhost:6379)
        # Exemple .env : REDIS_URL=redis://localhost:6379
        self._redis   : Optional[object]          = None   # client Redis ou None
        self._histories: dict[str, list[dict]]    = {}     # fallback RAM

        if _REDIS_AVAILABLE:
            try:
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                client    = redis_lib.from_url(redis_url, decode_responses=True)
                client.ping()                   # vérifie que Redis répond
                self._redis = client
                if self.verbose:
                    print(f"[NLQLayer] ✅ Redis connecté ({redis_url})")
            except Exception as e:
                self._redis = None
                if self.verbose:
                    print(f"[NLQLayer] ⚠️  Redis indisponible ({e}) → fallback RAM")
        else:
            if self.verbose:
                print("[NLQLayer] ⚠️  redis-py non installé → fallback RAM")
                print("[NLQLayer]    Pour activer Redis : pip install redis")

        self.llm = ChatOpenAI(
            model       = self.MODEL,
            temperature = 0.2,
            api_key     = openrouter_api_key,
            base_url    = self.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://dxc-pfe-analytics.local",
                "X-Title"     : "DXC Intelligence Analytics Platform",
            },
        )

        self.graph = self._build_graph()

    # ── Méthodes internes Memory Layer ───────────────────────────────────────

    def _get_history(self, user_id: str) -> list[dict]:
        """
        Lit l'historique d'un utilisateur.
        Redis → désérialise le JSON. Fallback → lit le dict RAM.
        """
        if self._redis:
            try:
                raw = self._redis.get(f"{self.REDIS_KEY_PREFIX}{user_id}")
                return json.loads(raw) if raw else []
            except Exception:
                pass   # Redis a planté en cours de route → fallback RAM
        return self._histories.get(user_id, [])

    def _append_history(self, user_id: str, turn: dict) -> None:
        """
        Ajoute un tour à l'historique.
        Redis → lit, append, réécrit (sans expiration — illimité).
        Fallback → append dans le dict RAM.
        """
        if self._redis:
            try:
                history = self._get_history(user_id)
                history.append(turn)
                self._redis.set(
                    f"{self.REDIS_KEY_PREFIX}{user_id}",
                    json.dumps(history, ensure_ascii=False),
                    # pas de ex= → pas d'expiration → illimité
                )
                return
            except Exception:
                pass   # Redis a planté → fallback RAM
        # Fallback RAM
        if user_id not in self._histories:
            self._histories[user_id] = []
        self._histories[user_id].append(turn)

    def _delete_history(self, user_id: str) -> bool:
        """
        Supprime l'historique d'un utilisateur.
        Retourne True si une session existait.
        """
        if self._redis:
            try:
                deleted = self._redis.delete(f"{self.REDIS_KEY_PREFIX}{user_id}")
                return deleted > 0
            except Exception:
                pass   # Redis a planté → fallback RAM
        if user_id in self._histories:
            del self._histories[user_id]
            return True
        return False

    def _count_sessions(self) -> int:
        """Nombre de sessions actives (clés history:* dans Redis ou dict RAM)."""
        if self._redis:
            try:
                return len(self._redis.keys(f"{self.REDIS_KEY_PREFIX}*"))
            except Exception:
                pass
        return len(self._histories)

    def _build_graph(self):
        """
        Construit et compile le NLQ Layer Graph.

        Nœuds :
          classify_intent  → Intent Classifier via LLM
          prepare_routing  → construit le payload Orchestrateur
          generate_answer  → NLQ Agent répond directement

        Branchement conditionnel après classify_intent :
          requires_orchestrator=True  → prepare_routing
          requires_orchestrator=False → generate_answer
        """
        builder = StateGraph(NLQAgentState)

        builder.add_node("classify_intent", _make_node_classify_intent(self.llm))
        builder.add_node("prepare_routing", node_prepare_routing)
        builder.add_node("generate_answer", _make_node_generate_answer(self.llm))

        builder.set_entry_point("classify_intent")

        builder.add_conditional_edges(
            "classify_intent",
            _routing_condition,
            {
                "prepare_routing": "prepare_routing",
                "generate_answer": "generate_answer",
            },
        )

        builder.add_edge("prepare_routing", END)
        builder.add_edge("generate_answer", END)

        return builder.compile()

    def chat(
        self,
        user_id       : str,
        question      : str,
        sector_context: SectorContext,
        data_profile  : Optional[dict] = None,
    ) -> NLQResponse:
        """
        Exécute le NLQ Layer Graph pour une question.

        Parameters
        ----------
        data_profile : dict, optional
            Dict plat fourni par l'Orchestrateur (déjà transformé) :
            { columns, numeric_columns, categorical_columns,
              datetime_columns, missing_summary, column_stats, quality_score, row_count }
            → utilisé pour générer du SQL avec les vrais noms de colonnes.

        Returns
        -------
        NLQResponse
            requires_orchestrator=False → answer contient la réponse directe
            requires_orchestrator=True  → routing_target + orchestrator_payload
        """
        history = self._get_history(user_id)   # ← Redis ou RAM

        initial_state: NLQAgentState = {
            "user_id"          : user_id,
            "question"         : question,
            "sector_context"   : sector_context,
            "data_profile"     : data_profile,
            "history"          : history,
            "intent_result"    : None,
            "nlq_response"     : None,
            "verbose"          : self.verbose,
        }

        final_state = self.graph.invoke(initial_state)
        result      = final_state["nlq_response"]

        # ── FIX 5 — sauvegarder l'historique pour TOUS les intents ───────────
        if result:
            self._append_history(user_id, {
                "user"     : question,
                "assistant": result.answer,
            })

            if self.verbose:
                orch = " [→ Orchestrateur]" if result.requires_orchestrator else ""
                print(f"  ✅ intent={result.intent}{orch} | history={self.history_length(user_id)}")

        return result

    def reset_conversation(self, user_id: str) -> bool:
        """Réinitialise l'historique d'un utilisateur. Retourne True si session existait."""
        cleared = self._delete_history(user_id)   # ← Redis ou RAM
        if cleared and self.verbose:
            print(f"[NLQLayer] Cleared '{user_id}'.")
        return cleared

    def history_length(self, user_id: str) -> int:
        return len(self._get_history(user_id))    # ← Redis ou RAM

    @property
    def active_sessions(self) -> int:
        return self._count_sessions()             # ← Redis ou RAM

    @property
    def using_redis(self) -> bool:
        """True si Redis est actif, False si fallback RAM."""
        return self._redis is not None