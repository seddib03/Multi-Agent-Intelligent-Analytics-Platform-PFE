"""
Context / Sector Detection Agent
==================================
PFE — DXC Technology | Intelligence Analytics Platform
Sprint 1 | Author: [Votre Nom]

Description
-----------
Ce module implémente le Context/Sector Agent, premier composant du pipeline
Multi-Agent. Il analyse l'objectif global de l'utilisateur et produit un
contexte structuré (secteur, KPIs, routing) pour l'Orchestrateur.

Responsabilités
---------------
1. Recevoir la query globale de l'utilisateur
   ex: "améliorer l'expérience des passagers de l'aéroport"

2. Accepter des metadata de colonnes (optionnel)
   Utile quand la query est ambiguë :
   "améliorer l'expérience client" + colonnes ["flight_id", "delay_minutes"]
   → le LLM peut déduire Transport avec haute confiance

3. Détecter automatiquement le secteur parmi :
   transport | finance | retail | manufacturing | public

4. Mapper les KPIs pertinents pour ce secteur et cette query

5. Produire un SectorContext structuré pour l'Orchestrateur

Stack
-----
- LangChain + OpenRouter (meta-llama/llama-3.1-8b-instruct)
- Pydantic pour la validation des sorties
- YAML pour la configuration des KPIs

Flux dans l'architecture
------------------------
  User Query + Metadata (optionnel)
          │
          ▼
  [Context/Sector Agent]   ← CE MODULE
          │
          ▼
  SectorContext
          │
          ▼
  Orchestrateur → Agent Sectoriel (Transport, Finance, ...)
"""

import os
import json
import yaml
from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


# ══════════════════════════════════════════════════════════
# SECTION 1 — MODÈLES DE DONNÉES
# ══════════════════════════════════════════════════════════

class ColumnMetadata(BaseModel):
    """
    Représente la description d'une colonne du dataset de l'utilisateur.

    Utilisée pour affiner la détection sectorielle quand la query est
    trop générique. Toutes les informations sont optionnelles sauf le nom.

    Attributs
    ---------
    name : str
        Nom exact de la colonne dans le dataset
    description : str, optional
        Description lisible de ce que contient la colonne
    sample_values : list[str], optional
        Quelques exemples de valeurs pour aider le LLM à comprendre le contenu

    Exemple
    -------
    >>> ColumnMetadata(
    ...     name="delay_minutes",
    ...     description="Retard du vol en minutes",
    ...     sample_values=["0", "15", "45", "120"]
    ... )
    """
    name: str
    description: Optional[str] = None
    sample_values: Optional[list[str]] = None


class KPI(BaseModel):
    """
    Représente un KPI sélectionné et priorisé pour le secteur détecté.

    Attributs
    ---------
    name : str
        Nom officiel du KPI (doit correspondre à kpi_config.yaml)
    description : str
        Explication courte de ce que mesure ce KPI
    unit : str
        Unité de mesure (%, minutes, MAD, score/5, etc.)
    priority : str
        Niveau de priorité par rapport à la query :
        - "high"   → directement mentionné dans la query
        - "medium" → impliqué par le contexte
        - "low"    → utile mais secondaire
    """
    name: str
    description: str
    unit: str
    priority: str


class SectorContext(BaseModel):
    """
    Sortie structurée du Context/Sector Agent.

    C'est l'objet transmis à l'Orchestrateur pour router
    la requête vers le bon agent sectoriel.

    Attributs
    ---------
    sector : str
        Secteur détecté parmi : transport, finance, retail,
        manufacturing, public
    confidence : float
        Score de confiance entre 0.0 et 1.0 :
        - >= 0.9  : secteur clairement identifié (avec ou sans metadata)
        - 0.7-0.9 : query claire mais sans metadata
        - < 0.7   : query ambiguë, metadata recommandée
    use_case : str
        Reformulation précise du use case identifié dans la query
    metadata_used : bool
        True si les metadata de colonnes ont influencé la décision
    kpis : list[KPI]
        Liste de 3 à 5 KPIs pertinents, triés par priorité décroissante
    dashboard_focus : str
        Titre/thème du dashboard global à générer
    recommended_charts : list[str]
        Types de visualisations recommandées pour ce secteur/use-case
    routing_target : str
        Identifiant de l'agent sectoriel cible, format : "{sector}_agent"
        ex: "transport_agent", "finance_agent"
    explanation : str
        Justification courte du raisonnement de détection (1-2 phrases)
    """
    sector: str
    confidence: float
    use_case: str
    metadata_used: bool
    kpis: list[KPI]
    dashboard_focus: str
    recommended_charts: list[str]
    routing_target: str
    explanation: str


# ══════════════════════════════════════════════════════════
# SECTION 2 — UTILITAIRES CONFIG
# ══════════════════════════════════════════════════════════

def load_kpi_config(config_path: str = "config/kpi_config.yaml") -> dict:
    """
    Charge la configuration des KPIs par secteur depuis le fichier YAML.

    Le fichier YAML est la source de vérité pour les KPIs.
    Modifier kpi_config.yaml suffit pour ajouter/modifier des KPIs
    sans toucher au code de l'agent.

    Parameters
    ----------
    config_path : str
        Chemin vers le fichier kpi_config.yaml

    Returns
    -------
    dict
        Dictionnaire avec la clé "sectors" contenant les 5 secteurs
    """
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_kpi_config_for_prompt(config: dict) -> str:
    """
    Transforme la config YAML en texte structuré pour injection dans le prompt LLM.

    Le LLM ne lit pas le YAML directement — on le convertit en texte
    clair et hiérarchique pour qu'il puisse choisir les bons KPIs.

    Parameters
    ----------
    config : dict
        Config chargée par load_kpi_config()

    Returns
    -------
    str
        Texte formaté listant tous les secteurs et leurs KPIs disponibles
    """
    lines = []
    for sector, data in config["sectors"].items():
        lines.append(f"\nSECTOR: {sector.upper()}")
        lines.append(f"  Dashboard focus: {data['dashboard_focus']}")
        lines.append("  Available KPIs:")
        for kpi in data["kpis"]:
            lines.append(f"    - {kpi['name']} ({kpi['unit']}): {kpi['description']}")
    return "\n".join(lines)


def format_metadata_for_prompt(columns: list[ColumnMetadata]) -> str:
    """
    Formate les metadata des colonnes en texte lisible pour le LLM.

    Cette section est ajoutée au prompt seulement si des metadata
    sont fournies. Elle permet au LLM de lever l'ambiguïté sectorielle
    en analysant le schéma réel du dataset de l'utilisateur.

    Parameters
    ----------
    columns : list[ColumnMetadata]
        Liste des colonnes à formater

    Returns
    -------
    str
        Texte formaté avec nom, description et valeurs exemples
    """
    lines = ["USER DATASET COLUMNS:"]
    for col in columns:
        line = f"  - {col.name}"
        if col.description:
            line += f" : {col.description}"
        if col.sample_values:
            line += f" (examples: {', '.join(col.sample_values[:4])})"
        lines.append(line)
    lines.append(
        "NOTE: These columns strongly indicate the business sector. "
        "Prioritize them over the query text if they conflict."
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# SECTION 3 — CONTEXT/SECTOR AGENT
# ══════════════════════════════════════════════════════════

class ContextSectorAgent:
    """
    Agent de détection sectorielle et de mapping KPI.

    Utilise un LLM via OpenRouter (Llama 3.1 8B, gratuit) pour :
    1. Analyser la query globale de l'utilisateur
    2. Identifier le secteur business parmi 5 options
    3. Sélectionner et prioriser les KPIs adaptés depuis kpi_config.yaml
    4. Produire un SectorContext structuré pour l'Orchestrateur

    OpenRouter vs OpenAI direct
    ---------------------------
    OpenRouter expose une API compatible OpenAI.
    On utilise ChatOpenAI avec base_url=OpenRouter et le modèle Llama 3.1.
    Avantage : modèle gratuit, pas de coût par requête.

    Parameters
    ----------
    openrouter_api_key : str
        Clé API OpenRouter (https://openrouter.ai/keys)
    config_path : str
        Chemin vers kpi_config.yaml
    verbose : bool
        Affiche les logs détaillés pendant l'exécution

    Examples
    --------
    >>> agent = ContextSectorAgent(api_key="sk-or-v1-...")
    >>> ctx = agent.detect("améliorer l'expérience des passagers de l'aéroport")
    >>> print(ctx.sector)      # "transport"
    >>> print(ctx.confidence)  # 0.95
    >>> print(ctx.kpis[0].name) # "On-Time Performance"
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    MODEL = "meta-llama/llama-3.1-8b-instruct"

    def __init__(
        self,
        openrouter_api_key: str,
        config_path: str = "config/kpi_config.yaml",
        verbose: bool = True
    ):
        self.verbose = verbose

        # Chargement de la config KPI
        self.config = load_kpi_config(config_path)
        self.kpi_reference = format_kpi_config_for_prompt(self.config)

        # Initialisation du LLM via OpenRouter
        # ChatOpenAI accepte n'importe quelle API compatible OpenAI
        self.llm = ChatOpenAI(
            model=self.MODEL,
            temperature=0,          # 0 = déterministe, pas de variation
            api_key=openrouter_api_key,
            base_url=self.OPENROUTER_BASE_URL,
            default_headers={
                # Headers recommandés par OpenRouter pour identifier l'app
                "HTTP-Referer": "https://dxc-pfe-analytics.local",
                "X-Title": "DXC Intelligence Analytics Platform"
            }
        )

    # ──────────────────────────────────────────────────
    # Méthode privée : construction du prompt
    # ──────────────────────────────────────────────────

    def _build_prompt(
        self,
        user_query: str,
        column_metadata: Optional[list[ColumnMetadata]]
    ) -> str:
        """
        Construit le prompt complet envoyé au LLM.

        Le prompt est construit dynamiquement :
        - La section KPI reference est toujours présente
        - La section metadata est ajoutée seulement si des colonnes sont fournies

        Le prompt demande une sortie JSON stricte pour permettre
        un parsing fiable sans dépendre du format exact de la réponse.

        Parameters
        ----------
        user_query : str
            Objectif global de l'utilisateur
        column_metadata : list[ColumnMetadata] | None
            Metadata des colonnes du dataset (optionnel)

        Returns
        -------
        str
            Prompt complet prêt à envoyer au LLM
        """
        # Section metadata — ajoutée seulement si fournie
        metadata_section = ""
        if column_metadata:
            metadata_section = f"\n{format_metadata_for_prompt(column_metadata)}\n"

        return f"""You are the Context/Sector Detection Agent of an enterprise \
multi-sector AI analytics platform built by DXC Technology.

Your task: analyze the user's business objective and return a structured JSON context.

AVAILABLE SECTORS AND KPIs:
{self.kpi_reference}

SELECTION RULES:
- Select exactly 3 to 5 KPIs, sorted from most to least relevant
- priority field: "high" if directly mentioned, "medium" if implied, "low" if general
- confidence: 0.9+ if sector is very clear, 0.7-0.9 if clear, below 0.7 if ambiguous
- metadata_used: true only if column metadata was provided AND changed your decision
- routing_target format must be: "transport_agent", "finance_agent", etc.
- explanation: 1 to 2 sentences justifying your sector choice

OUTPUT FORMAT: Respond ONLY with a valid JSON object. No markdown, no explanation outside JSON.

User objective: {user_query}
{metadata_section}
Return this exact JSON structure:
{{
  "sector": "transport|finance|retail|manufacturing|public",
  "confidence": 0.0,
  "use_case": "specific use case description",
  "metadata_used": false,
  "kpis": [
    {{"name": "", "description": "", "unit": "", "priority": "high|medium|low"}}
  ],
  "dashboard_focus": "",
  "recommended_charts": [""],
  "routing_target": "sector_agent",
  "explanation": ""
}}"""

    # ──────────────────────────────────────────────────
    # Méthode privée : parsing de la réponse LLM
    # ──────────────────────────────────────────────────

    def _parse_response(self, raw_content: str) -> SectorContext:
        """
        Parse la réponse JSON du LLM en objet SectorContext.

        Llama 3.1 peut parfois encadrer sa réponse JSON avec des
        backticks markdown (```json ... ```). Cette méthode nettoie
        ces artefacts avant le parsing.

        Parameters
        ----------
        raw_content : str
            Contenu brut retourné par le LLM

        Returns
        -------
        SectorContext
            Objet validé par Pydantic

        Raises
        ------
        ValueError
            Si le LLM n'a pas retourné un JSON valide après nettoyage
        """
        content = raw_content.strip()

        # Nettoyage des backticks markdown si présents
        if content.startswith("```"):
            parts = content.split("```")
            # Format: ```json\n{...}\n``` → on prend la partie du milieu
            content = parts[1]
            if content.startswith("json"):
                content = content[4:]

        try:
            data = json.loads(content.strip())
            return SectorContext(**data)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON.\n"
                f"Raw response: {raw_content[:300]}\n"
                f"Parse error: {e}"
            )
        except Exception as e:
            raise ValueError(
                f"JSON valid but doesn't match SectorContext schema.\n"
                f"Error: {e}"
            )

    # ──────────────────────────────────────────────────
    # Méthode publique principale
    # ──────────────────────────────────────────────────

    def detect(
        self,
        user_query: str,
        column_metadata: Optional[list[ColumnMetadata]] = None
    ) -> SectorContext:
        """
        Détecte le secteur et produit le contexte enrichi.

        C'est le point d'entrée principal de l'agent.
        Peut être appelé avec ou sans metadata de colonnes.

        Parameters
        ----------
        user_query : str
            Objectif global de l'utilisateur en langage naturel.
            Exemples :
            - "améliorer l'expérience des passagers de l'aéroport"
            - "analyser la performance financière et réduire les risques"
            - "améliorer l'expérience client" (ambiguë → fournir metadata)

        column_metadata : list[ColumnMetadata], optional
            Liste des colonnes du dataset de l'utilisateur.
            Recommandé quand la query est générique pour lever l'ambiguïté.
            Exemple: [ColumnMetadata(name="flight_id"), ColumnMetadata(name="delay_minutes")]

        Returns
        -------
        SectorContext
            Contexte structuré contenant secteur, KPIs, routing info.
            Transmis à l'Orchestrateur pour continuer le pipeline.

        Raises
        ------
        ValueError
            Si le LLM retourne une réponse non parseable.

        Examples
        --------
        >>> # Cas 1 : query précise, sans metadata
        >>> ctx = agent.detect("améliorer l'expérience des passagers de l'aéroport")
        >>> ctx.sector       # "transport"
        >>> ctx.confidence   # 0.95

        >>> # Cas 2 : query ambiguë avec metadata
        >>> meta = [ColumnMetadata(name="flight_id"), ColumnMetadata(name="delay_minutes")]
        >>> ctx = agent.detect("améliorer l'expérience client", column_metadata=meta)
        >>> ctx.metadata_used  # True
        """
        if self.verbose:
            print(f"\n{'═'*60}")
            print(f"[ContextSectorAgent] Detecting sector...")
            print(f"  Query    : '{user_query}'")
            if column_metadata:
                names = [c.name for c in column_metadata]
                print(f"  Metadata : {len(names)} columns → {names[:6]}")
            else:
                print(f"  Metadata : none")
            print(f"{'═'*60}")

        # Construction du prompt et appel LLM
        prompt = self._build_prompt(user_query, column_metadata)
        raw_response = self.llm.invoke([HumanMessage(content=prompt)])

        # Parsing de la réponse
        result = self._parse_response(raw_response.content)

        if self.verbose:
            self._print_result(result)

        return result

    # ──────────────────────────────────────────────────
    # Méthodes raccourcis (helpers)
    # ──────────────────────────────────────────────────

    def detect_from_dict(
        self,
        user_query: str,
        columns: dict
    ) -> SectorContext:
        """
        Raccourci : fournit les metadata sous forme de dict simple.

        Pratique pour passer rapidement quelques colonnes sans
        créer des objets ColumnMetadata manuellement.

        Parameters
        ----------
        user_query : str
            Objectif global de l'utilisateur
        columns : dict
            Dictionnaire {nom_colonne: description}.
            La description peut être une chaîne vide "".

        Returns
        -------
        SectorContext

        Examples
        --------
        >>> ctx = agent.detect_from_dict(
        ...     "améliorer l'expérience client",
        ...     {
        ...         "flight_id":     "identifiant unique du vol",
        ...         "delay_minutes": "retard en minutes",
        ...         "gate":          "porte d'embarquement"
        ...     }
        ... )
        """
        metadata = [
            ColumnMetadata(name=name, description=desc or None)
            for name, desc in columns.items()
        ]
        return self.detect(user_query, column_metadata=metadata)

    def detect_from_dataframe_columns(
        self,
        user_query: str,
        df_columns: list
    ) -> SectorContext:
        """
        Raccourci : passe directement la liste des colonnes d'un DataFrame.

        Typiquement utilisé après l'upload CSV par le Data Prep Agent :
            profile = data_prep_agent.analyze(df)
            ctx = sector_agent.detect_from_dataframe_columns(query, profile.columns)

        Parameters
        ----------
        user_query : str
            Objectif global de l'utilisateur
        df_columns : list
            Liste des noms de colonnes, ex: df.columns.tolist()

        Returns
        -------
        SectorContext

        Examples
        --------
        >>> ctx = agent.detect_from_dataframe_columns(
        ...     "améliorer l'expérience client",
        ...     ["flight_id", "delay_minutes", "gate", "passenger_count"]
        ... )
        """
        metadata = [ColumnMetadata(name=str(col)) for col in df_columns]
        return self.detect(user_query, column_metadata=metadata)

    # ──────────────────────────────────────────────────
    # Affichage console
    # ──────────────────────────────────────────────────

    def _print_result(self, result: SectorContext):
        """Affiche le résultat de façon lisible dans la console."""
        print(f"\n  ✅ Sector    : {result.sector.upper()} ({result.confidence:.0%} confidence)")
        print(f"  📋 Use Case  : {result.use_case}")
        print(f"  🔗 Metadata  : {'used ✓' if result.metadata_used else 'not used'}")
        print(f"  🎯 Routing   : {result.routing_target}")
        print(f"  📊 KPIs ({len(result.kpis)}):")
        for kpi in result.kpis:
            icon = "🔴" if kpi.priority == "high" else "🟡" if kpi.priority == "medium" else "⚪"
            print(f"     {icon} [{kpi.priority:<6}] {kpi.name} ({kpi.unit})")
        print(f"  💬 Reasoning : {result.explanation}")