"""
Sector Detection Agent — LangGraph
====================================
PFE — DXC Technology | Intelligence Analytics Platform
Sprint 1

Architecture LangGraph
-----------------------
Ce module implémente le bloc "Sector Detection Agent" comme un
StateGraph LangGraph à 3 nœuds :

    ┌─────────────────────────────────────────────────────────┐
    │               Sector Detection Graph                    │
    │                                                         │
    │  [load_context] → [detect_sector] → [map_kpis]          │
    │                                                         │
    │  Nœud 1 : load_context   — prépare le prompt            │
    │  Nœud 2 : detect_sector  — appel LLM, parse JSON        │
    │  Nœud 3 : map_kpis       — valide KPIs contre YAML      │
    └─────────────────────────────────────────────────────────┘

Pourquoi LangGraph ?
--------------------
- Chaque étape est un nœud typé → testable et observable isolément
- L'état (SectorAgentState) est partagé et muté entre les nœuds
- Prêt pour l'Orchestrateur multi-agent (Sprint 2) : le graph s'intègre
  comme un sous-graph dans le graph global via add_node / compile()
- Transitions conditionnelles possibles (ex: retry si confidence < 0.5)

Flux dans le pipeline global
-----------------------------
    User Query (+ colonnes optionnelles)
            │
            ▼
    [Sector Detection Graph]   ← CE MODULE
            │  SectorContext { sector, kpis, kpi_thresholds, routing_target }
            ▼
    [Orchestrateur Graph]      ← Sprint 2 (opérationnel)
            │
            ▼
    [Agent Sectoriel Graph]    ← Sprint 3

Changements Sprint 2
---------------------
    - SectorContext : ajout kpi_thresholds (seuils rouge/orange/vert par KPI)
    - node_map_kpis : lit thresholds + direction depuis kpi_config.yaml
    - kpi_config.yaml : ajout thresholds + direction pour les 5 secteurs
    - Consommé par Insight Agent (Sprint 5) et Frontend (Panel 3)
      pour afficher les zones colorées sans hardcoder les seuils
"""

import json
import yaml
from typing import Optional, TypedDict, Annotated
from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from langgraph.graph import StateGraph, END


# ══════════════════════════════════════════════════════════════════
# MODÈLES PYDANTIC — partagés avec l'Orchestrateur
# ══════════════════════════════════════════════════════════════════

class ColumnMetadata(BaseModel):
    """
    Description d'une colonne du dataset uploadé par l'utilisateur.
    Passée en option pour lever l'ambiguïté sectorielle.
    """
    name          : str
    description   : Optional[str]       = None
    sample_values : Optional[list[str]] = None


class KPI(BaseModel):
    """KPI sélectionné et priorisé par le Sector KPI Mapping."""
    name       : str
    description: str
    unit       : str
    priority   : str  # "high" | "medium" | "low"


class SectorContext(BaseModel):
    """
    Sortie du Sector Detection Agent — consommée par l'Orchestrateur.

    Champs clés
    -----------
    sector          : secteur détecté
    confidence      : 0.9+ clair | 0.7–0.9 probable | <0.7 ambigu
    routing_target  : "{sector}_agent" — utilisé par l'Orchestrateur
    kpis            : 3–5 KPIs priorisés
    kpi_thresholds  : seuils rouge/orange/vert par KPI — Sprint 2
                      Consommé par Insight Agent (Sprint 5) + Frontend (Panel 3)
                      Format :
                      {
                        "On-Time Performance": {
                          "red": 70, "orange": 85,
                          "direction": "higher_is_better"
                        },
                        "Average Delay": {
                          "red": 40, "orange": 25,
                          "direction": "lower_is_better"
                        }
                      }
    """
    sector            : str
    confidence        : float
    use_case          : str
    metadata_used     : bool
    kpis              : list[KPI]
    dashboard_focus   : str
    recommended_charts: list[str]
    routing_target    : str
    explanation       : str
    # ── Sprint 2 ──────────────────────────────────────────────────────
    kpi_thresholds    : dict = {}
    # { kpi_name: { "red": val, "orange": val, "direction": str } }
    # ── Sprint 3 — Sector override ────────────────────────────────
    is_overridden     : bool = False
    # True si l'utilisateur a choisi manuellement le secteur via POST /sector/override
    # → court-circuite la détection LLM, confidence forcée à 1.0


# Secteurs disponibles — source de vérité pour le sector override
AVAILABLE_SECTORS: list[str] = ["transport", "finance", "retail", "manufacturing", "public"]


# ══════════════════════════════════════════════════════════════════
# ÉTAT DU GRAPH LANGGRAPH
# ══════════════════════════════════════════════════════════════════

class SectorAgentState(TypedDict):
    """
    État partagé entre les nœuds du Sector Detection Graph.

    Muté séquentiellement par chaque nœud :
      load_context   → remplit prompt, user_query, columns
      detect_sector  → remplit llm_raw, llm_data
      map_kpis       → remplit sector_context (sortie finale)
    """
    # Entrées
    user_query : str
    columns    : Optional[list[ColumnMetadata]]

    # Intermédiaires
    prompt     : str
    llm_raw    : str
    llm_data   : dict

    # Config injectée (non mutée)
    kpi_config_text: str
    kpi_config_dict: dict

    # Sortie finale
    sector_context: Optional[SectorContext]

    # Meta
    error  : Optional[str]
    verbose: bool


# ══════════════════════════════════════════════════════════════════
# UTILITAIRES CONFIG
# ══════════════════════════════════════════════════════════════════

def load_kpi_config(config_path: str = "config/kpi_config.yaml") -> dict:
    """Charge kpi_config.yaml — source de vérité pour tous les KPIs."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_kpi_config_for_prompt(config: dict) -> str:
    """Convertit la config YAML en texte injecté dans le prompt LLM."""
    lines = []
    for sector, data in config["sectors"].items():
        lines.append(f"\nSECTOR: {sector.upper()}")
        lines.append(f"  Dashboard focus : {data['dashboard_focus']}")
        lines.append("  Available KPIs  :")
        for kpi in data["kpis"]:
            lines.append(f"    - {kpi['name']} ({kpi['unit']}): {kpi['description']}")
    return "\n".join(lines)


def format_columns_for_prompt(columns: list[ColumnMetadata]) -> str:
    """Formate les colonnes du dataset pour lever l'ambiguïté sectorielle."""
    lines = ["USER DATASET COLUMNS (use these to disambiguate the sector):"]
    for col in columns:
        line = f"  - {col.name}"
        if col.description:
            line += f" : {col.description}"
        if col.sample_values:
            line += f" (ex: {', '.join(col.sample_values[:3])})"
        lines.append(line)
    lines.append(
        "\nNOTE: These column names are strong indicators of the sector. "
        "Prioritize them over the query text if they conflict."
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# NŒUDS DU GRAPH
# ══════════════════════════════════════════════════════════════════

def node_load_context(state: SectorAgentState) -> SectorAgentState:
    """
    Nœud 1 — Prépare le prompt LLM.

    Injecte :
    - La config KPI complète (tous secteurs)
    - Les colonnes du dataset si fournies
    - La query utilisateur
    """
    columns_section = (
        f"\n{format_columns_for_prompt(state['columns'])}\n"
        if state.get("columns") else ""
    )

    prompt = f"""You are the Sector Detection Agent of an enterprise multi-sector \
AI analytics platform built by DXC Technology.

TASK: Analyze the user's business objective and return a structured JSON context
that will be used by the Orchestrator to route to the correct sector agent.

AVAILABLE SECTORS AND KPIs:
{state['kpi_config_text']}

RULES:
- Detect ONE sector among: transport, finance, retail, manufacturing, public
- Select 3 to 5 KPIs sorted by relevance (most relevant first)
- priority: "high" if directly mentioned | "medium" if implied | "low" if general
- confidence: >=0.9 if sector very clear | 0.7-0.9 if probable | <0.7 if ambiguous
- metadata_used: true ONLY if columns were provided AND changed your sector decision
- routing_target: must follow the pattern "{{sector}}_agent"
- explanation: 1-2 sentences justifying the sector choice

OUTPUT: Respond ONLY with a valid JSON object. No markdown, no text outside JSON.

User objective: {state['user_query']}
{columns_section}
Expected JSON:
{{
  "sector": "transport|finance|retail|manufacturing|public",
  "confidence": 0.0,
  "use_case": "precise description of the detected use case",
  "metadata_used": false,
  "kpis": [
    {{"name": "KPI name", "description": "what it measures", "unit": "unit", "priority": "high|medium|low"}}
  ],
  "dashboard_focus": "dashboard theme title",
  "recommended_charts": ["chart type 1", "chart type 2"],
  "routing_target": "sector_agent",
  "explanation": "1-2 sentence justification"
}}"""

    return {**state, "prompt": prompt}


def _make_node_detect_sector(llm: ChatOpenAI):
    """
    Factory → Nœud 2 : appelle le LLM et parse le JSON.
    Le LLM est injecté par closure pour garder les nœuds purs.
    """
    def node_detect_sector(state: SectorAgentState) -> SectorAgentState:
        if state.get("verbose"):
            print("  [Node:detect_sector] Calling LLM...")

        raw = llm.invoke([HumanMessage(content=state["prompt"])]).content.strip()

        # Nettoyage backticks markdown
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip()

        try:
            data = json.loads(raw)
            return {**state, "llm_raw": raw, "llm_data": data, "error": None}
        except json.JSONDecodeError as e:
            error_msg = f"[detect_sector] Invalid JSON: {e} | Preview: {raw[:200]}"
            return {**state, "llm_raw": raw, "llm_data": {}, "error": error_msg}

    return node_detect_sector


def node_map_kpis(state: SectorAgentState) -> SectorAgentState:
    """
    Nœud 3 — Sector KPI Mapping.
    Valide les KPIs du LLM contre kpi_config.yaml et construit SectorContext.
    """
    if state.get("error"):
        return state

    data   = state["llm_data"]
    sector = data.get("sector", "")

    # Index des KPIs de référence pour ce secteur
    ref_kpis: dict[str, dict] = {}
    config = state.get("kpi_config_dict", {})
    if sector in config.get("sectors", {}):
        for kpi in config["sectors"][sector]["kpis"]:
            ref_kpis[kpi["name"].lower()] = kpi

    validated = []
    for item in data.get("kpis", []):
        ref = ref_kpis.get(item.get("name", "").lower())
        if ref:
            validated.append(KPI(
                name        = ref["name"],
                description = ref["description"],
                unit        = ref["unit"],
                priority    = item.get("priority", "medium"),
            ))
        else:
            try:
                validated.append(KPI(**item))
            except Exception:
                pass

    data["kpis"] = [k.model_dump() for k in validated]

    # ── Sprint 2 — extraire kpi_thresholds depuis kpi_config.yaml ────────────
    # Parcourt TOUS les KPIs du secteur pour que le Frontend/Insight Agent
    # ait les seuils complets disponibles (pas seulement les KPIs sélectionnés).
    kpi_thresholds: dict = {}
    if sector in config.get("sectors", {}):
        for kpi in config["sectors"][sector]["kpis"]:
            if "thresholds" in kpi:
                kpi_thresholds[kpi["name"]] = {
                    "red"      : kpi["thresholds"].get("red"),
                    "orange"   : kpi["thresholds"].get("orange"),
                    "direction": kpi.get("direction", "higher_is_better"),
                    "unit"     : kpi.get("unit", ""),
                }
    data["kpi_thresholds"] = kpi_thresholds
    # ─────────────────────────────────────────────────────────────────────────

    try:
        ctx = SectorContext(**data)
    except Exception as e:
        return {**state, "error": f"[map_kpis] SectorContext build error: {e}"}

    if state.get("verbose"):
        print(f"  [Node:map_kpis] ✅ {ctx.sector.upper()} ({ctx.confidence:.0%}) → {ctx.routing_target}")
        if kpi_thresholds:
            print(f"  [Node:map_kpis] 📊 Thresholds: {len(kpi_thresholds)} KPIs configurés")

    return {**state, "sector_context": ctx}


# ══════════════════════════════════════════════════════════════════
# CONTEXT SECTOR AGENT — graph LangGraph
# ══════════════════════════════════════════════════════════════════

class ContextSectorAgent:
    """
    Sector Detection Agent — implémenté comme un StateGraph LangGraph.

    Graph : load_context → detect_sector → map_kpis → END

    Chaque nœud est testable isolément.
    Le graph compilé s'intègre dans l'Orchestrateur multi-agent (Sprint 2)
    via orchestrator_graph.add_node("sector_detection", self.graph).

    Parameters
    ----------
    openrouter_api_key : str
    config_path        : str   chemin vers kpi_config.yaml
    verbose            : bool

    Examples
    --------
    >>> agent = ContextSectorAgent(openrouter_api_key="sk-or-v1-...")
    >>> ctx = agent.detect("améliorer l'expérience des passagers de l'aéroport")
    >>> ctx.sector           # "transport"
    >>> ctx.routing_target   # "transport_agent"
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    MODEL               = "meta-llama/llama-3.1-8b-instruct"

    def __init__(
        self,
        openrouter_api_key: str,
        config_path       : str  = "config/kpi_config.yaml",
        verbose           : bool = True,
    ):
        self.verbose    = verbose
        self.config     = load_kpi_config(config_path)
        self.config_text= format_kpi_config_for_prompt(self.config)

        # LLM via OpenRouter
        self.llm = ChatOpenAI(
            model       = self.MODEL,
            temperature = 0,
            api_key     = openrouter_api_key,
            base_url    = self.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://dxc-pfe-analytics.local",
                "X-Title"     : "DXC Intelligence Analytics Platform",
            },
        )

        # Construction du StateGraph
        self.graph = self._build_graph()

    def _build_graph(self):
        """
        Construit et compile le StateGraph LangGraph.

        Nœuds :
          load_context  → prépare le prompt
          detect_sector → appelle le LLM, parse JSON
          map_kpis      → valide KPIs contre YAML, produit SectorContext
        """
        builder = StateGraph(SectorAgentState)

        builder.add_node("load_context",   node_load_context)
        builder.add_node("detect_sector",  _make_node_detect_sector(self.llm))
        builder.add_node("map_kpis",       node_map_kpis)

        builder.set_entry_point("load_context")
        builder.add_edge("load_context",  "detect_sector")
        builder.add_edge("detect_sector", "map_kpis")
        builder.add_edge("map_kpis",      END)

        return builder.compile()

    def detect(
        self,
        user_query: str,
        columns   : Optional[list[ColumnMetadata]] = None,
    ) -> SectorContext:
        """
        Exécute le graph et retourne le SectorContext.

        Parameters
        ----------
        user_query : str
            Objectif global de l'utilisateur.
        columns    : list[ColumnMetadata], optional
            Colonnes du dataset pour lever l'ambiguïté.

        Returns
        -------
        SectorContext

        Raises
        ------
        ValueError  Si le LLM retourne un JSON invalide ou incomplet.
        """
        if self.verbose:
            sep = "═" * 60
            print(f"\n{sep}")
            print(f"[ContextSectorAgent] Detecting sector...")
            print(f"  Query   : '{user_query}'")
            if columns:
                print(f"  Columns : {len(columns)} → {[c.name for c in columns[:5]]}")
            print(sep)

        # État initial
        initial_state: SectorAgentState = {
            "user_query"     : user_query,
            "columns"        : columns,
            "prompt"         : "",
            "llm_raw"        : "",
            "llm_data"       : {},
            "kpi_config_text": self.config_text,
            "kpi_config_dict": self.config,
            "sector_context" : None,
            "error"          : None,
            "verbose"        : self.verbose,
        }

        # Exécution du graph
        final_state = self.graph.invoke(initial_state)

        if final_state.get("error"):
            raise ValueError(final_state["error"])

        ctx = final_state["sector_context"]
        if ctx is None:
            raise ValueError("[ContextSectorAgent] Graph produced no SectorContext.")

        if self.verbose:
            self._log_result(ctx)

        return ctx

    def detect_from_dict(self, user_query: str, columns: dict) -> SectorContext:
        """Raccourci : colonnes sous forme {nom: description}."""
        meta = [
            ColumnMetadata(name=name, description=desc or None)
            for name, desc in columns.items()
        ]
        return self.detect(user_query, columns=meta)

    def detect_from_dataframe(self, user_query: str, df_columns: list) -> SectorContext:
        """Raccourci : passe directement df.columns.tolist()."""
        meta = [ColumnMetadata(name=str(c)) for c in df_columns]
        return self.detect(user_query, columns=meta)

    def _log_result(self, r: SectorContext) -> None:
        print(f"\n  ✅ Sector    : {r.sector.upper()} ({r.confidence:.0%} confidence)")
        print(f"  📋 Use Case  : {r.use_case}")
        print(f"  🔗 Metadata  : {'used ✓' if r.metadata_used else 'not used'}")
        print(f"  🎯 Routing   : {r.routing_target}")
        print(f"  📊 KPIs ({len(r.kpis)}):")
        for kpi in r.kpis:
            icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(kpi.priority, "⚪")
            thresh = r.kpi_thresholds.get(kpi.name, {})
            t_str  = (f" | 🟠≥{thresh['orange']} 🔴{'≤' if thresh['direction']=='lower_is_better' else '≤'}{thresh['red']}"
                      if thresh else "")
            print(f"       {icon} [{kpi.priority:<6}] {kpi.name} ({kpi.unit}){t_str}")
        print(f"  💬 Reason    : {r.explanation}")
        if r.kpi_thresholds:
            print(f"  🎚 Thresholds: {len(r.kpi_thresholds)} KPIs configurés (rouge/orange/vert)")


    def override_sector(
        self,
        user_query   : str,
        sector       : str,
        columns      : Optional[list["ColumnMetadata"]] = None,
    ) -> SectorContext:
        """
        Remarque encadrant R1 — Sector Override.

        Permet à l'utilisateur de corriger la détection automatique.
        Le secteur est forcé ; seuls les KPIs sont détectés via le graph normal.

        Parameters
        ----------
        user_query : str  — query originale de l'utilisateur
        sector     : str  — secteur choisi manuellement (doit être dans AVAILABLE_SECTORS)
        columns    : list[ColumnMetadata], optional

        Returns
        -------
        SectorContext avec is_overridden=True et confidence=1.0

        Raises
        ------
        ValueError si sector n'est pas dans AVAILABLE_SECTORS
        """
        if sector not in AVAILABLE_SECTORS:
            raise ValueError(
                f"Secteur '{sector}' invalide. "
                f"Secteurs disponibles : {AVAILABLE_SECTORS}"
            )

        # On détecte normalement (pour obtenir les KPIs et le dashboard_focus)
        # puis on force le secteur et confidence=1.0
        enriched_query = (
            f"[SECTOR OVERRIDE: {sector}] {user_query} "
            f"(focus strictly on {sector} sector KPIs)"
        )
        ctx = self.detect(enriched_query, columns=columns)

        # Force le secteur et routing_target
        return SectorContext(
            sector             = sector,
            confidence         = 1.0,
            use_case           = ctx.use_case,
            metadata_used      = ctx.metadata_used,
            kpis               = ctx.kpis,
            dashboard_focus    = ctx.dashboard_focus,
            recommended_charts = ctx.recommended_charts,
            routing_target     = f"{sector}_agent",
            explanation        = (
                f"Secteur '{sector}' sélectionné manuellement par l'utilisateur. "
                f"Détection automatique remplacée."
            ),
            kpi_thresholds     = ctx.kpi_thresholds,
            is_overridden      = True,
        )


# Alias rétrocompatibilité (ancienne codebase utilisait SectorDetectionAgent)
SectorDetectionAgent = ContextSectorAgent
