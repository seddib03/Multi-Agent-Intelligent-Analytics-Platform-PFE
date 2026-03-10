"""
NLQ Layer — LangGraph
======================
PFE — DXC Technology | Intelligence Analytics Platform
Sprint 1

Architecture LangGraph
-----------------------
Ce module implémente le bloc "NLQ Layer" comme un StateGraph LangGraph
à 4 nœuds :

    ┌─────────────────────────────────────────────────────────────┐
    │                     NLQ Layer Graph                         │
    │                                                             │
    │  [load_history]                                             │
    │       │                                                     │
    │       ▼                                                     │
    │  [classify_intent]                                          │
    │       │                                                     │
    │       ├── requires_orchestrator=True ──► [prepare_routing]  │
    │       │                                       │             │
    │       └── requires_orchestrator=False ─► [generate_answer]  │
    │                                               │             │
    │                                              END            │
    └─────────────────────────────────────────────────────────────┘

Pourquoi LangGraph ?
--------------------
- Le branchement conditionnel (NLQ direct vs Orchestrateur) est
  exprimé naturellement via add_conditional_edges()
- L'état (NLQAgentState) inclut l'historique complet → pas de state
  externe nécessaire
- Prêt pour Sprint 2 : le graph NLQ s'intègre comme sub-graph dans
  l'Orchestrateur via orchestrator_graph.add_node("nlq", nlq_graph)
- Chaque nœud est testable isolément

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
from typing import Optional, TypedDict
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from langgraph.graph import StateGraph, END

from agents.context_sector_agent import SectorContext


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

ORCHESTRATOR_INTENTS  = {i for i, c in ROUTING_TABLE.items() if c["requires_orchestrator"]}
NLQ_DIRECT_INTENTS    = {i for i, c in ROUTING_TABLE.items() if not c["requires_orchestrator"]}
SECTOR_DYNAMIC_INTENTS= {
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
      load_history     → remplit history
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

        kpi_list      = ", ".join(k.name for k in sector_context.kpis)
        last_question = (
            f'Previous question: "{history[-1]["user"]}"'
            if history else ""
        )

        prompt = f"""You are the Intent Classifier of an analytics platform.
Classify the user's question to determine which agent handles it.

SECTOR : {sector_context.sector}
KPIs   : {kpi_list}
{last_question}

USER QUESTION: "{question}"

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

FOLLOW-UP: is_follow_up=true if question uses implicit references.

OUTPUT: valid JSON only, no markdown.

{{
  "intent"            : "one of the intents above",
  "confidence"        : 0.0,
  "is_follow_up"      : false,
  "extracted_entities": {{}}
}}"""

        raw = llm.invoke([HumanMessage(content=prompt)]).content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        try:
            data = json.loads(raw)
        except Exception:
            data = {"intent": "explanation", "confidence": 0.5,
                    "is_follow_up": False, "extracted_entities": {}}

        intent  = data.get("intent", "explanation")
        routing = ROUTING_TABLE.get(intent, ROUTING_TABLE["explanation"])
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
        intent         = state["intent_result"]
        sector_context = state["sector_context"]
        data_profile   = state.get("data_profile")
        history        = state["history"]
        question       = state["question"]

        # System prompt
        kpi_block = "\n".join(
            f"  - {k.name} ({k.unit}) : {k.description}"
            for k in sector_context.kpis
        )
        data_section = ""
        if data_profile:
            cols = data_profile.get("columns", [])
            rows = data_profile.get("row_count", "unknown")
            num  = data_profile.get("numeric_columns", [])
            cat  = data_profile.get("categorical_columns", [])
            dt   = data_profile.get("datetime_columns", [])
            miss = data_profile.get("missing_summary", {})
            data_section = f"""
UPLOADED DATASET PROFILE:
  Rows         : {rows}
  All columns  : {', '.join(cols)}
  Numeric      : {', '.join(num)}
  Categorical  : {', '.join(cat)}
  Datetime     : {', '.join(dt)}
  Missing      : {json.dumps(miss, ensure_ascii=False)}
⚠ SQL: Use ONLY exact column names listed above.
"""

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
{data_section}
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

        # Messages avec historique
        messages = [SystemMessage(content=system_prompt)]
        for turn in history:
            messages.append(HumanMessage(content=turn["user"]))
            messages.append(AIMessage(content=turn["assistant"]))
        messages.append(HumanMessage(content=question))

        raw = llm.invoke(messages).content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        try:
            data = json.loads(raw)
            data["intent"]                = intent.intent
            data["query_type"]            = intent.intent
            data["requires_orchestrator"] = False
            data["routing_target"]        = None
            response = NLQResponse(**data)
        except Exception:
            response = NLQResponse(
                answer     = raw.strip(),
                intent     = intent.intent,
                query_type = intent.intent,
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
      load_history → classify_intent
                          │
                          ├── requires_orchestrator → prepare_routing → END
                          └── NLQ direct            → generate_answer → END

    L'historique des conversations est géré en mémoire (dict user_id → list).
    Sprint 3 : migrer vers Redis pour la persistance multi-instance.

    Parameters
    ----------
    openrouter_api_key : str
    verbose            : bool

    Examples
    --------
    >>> agent = NLQAgent(openrouter_api_key="sk-or-v1-...")
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

    def __init__(self, openrouter_api_key: str, verbose: bool = True):
        self.verbose    = verbose
        self._histories : dict[str, list[dict]] = {}

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

        # Branchement conditionnel LangGraph
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

        Returns
        -------
        NLQResponse
            requires_orchestrator=False → answer contient la réponse directe
            requires_orchestrator=True  → routing_target + orchestrator_payload
        """
        history = self._histories.get(user_id, [])

        if self.verbose:
            print(f"\n{'─'*60}")
            print(f"[NLQLayer] user='{user_id}' | history={len(history)} | q='{question}'")

        initial_state: NLQAgentState = {
            "user_id"       : user_id,
            "question"      : question,
            "sector_context": sector_context,
            "data_profile"  : data_profile,
            "history"       : history,
            "intent_result" : None,
            "nlq_response"  : None,
            "verbose"       : self.verbose,
        }

        final_state = self.graph.invoke(initial_state)
        result      = final_state["nlq_response"]

        # Sauvegarde historique uniquement pour les réponses NLQ directes
        if result and not result.requires_orchestrator:
            if user_id not in self._histories:
                self._histories[user_id] = []
            self._histories[user_id].append({
                "user"     : question,
                "assistant": result.answer,
            })
            if self.verbose:
                print(f"  ✅ NLQ direct | history={self.history_length(user_id)}")

        return result

    def reset_conversation(self, user_id: str) -> bool:
        """Réinitialise l'historique d'un utilisateur. Retourne True si session existait."""
        if user_id in self._histories:
            del self._histories[user_id]
            if self.verbose:
                print(f"[NLQLayer] Cleared '{user_id}'.")
            return True
        return False

    def history_length(self, user_id: str) -> int:
        return len(self._histories.get(user_id, []))

    @property
    def active_sessions(self) -> int:
        return len(self._histories)
