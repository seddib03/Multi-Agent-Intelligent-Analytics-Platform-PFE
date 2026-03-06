"""
NLQ Agent — Contextual Analytics Chatbot
==========================================
PFE — DXC Technology | Intelligence Analytics Platform
Sprint 1 | Author: [Votre Nom]

Description
-----------
Le NLQ (Natural Language Query) Agent est le chatbot analytique du pipeline.
Il est activé APRÈS l'affichage du dashboard global, quand l'utilisateur
veut approfondir une question spécifique sur ses données.

Important : le NLQ n'est PAS le point d'entrée du système.
C'est le Context/Sector Agent qui s'exécute en premier et produit
le SectorContext transmis au NLQ pour contextualiser ses réponses.

Responsabilités
---------------
1. Recevoir les questions spécifiques de l'utilisateur
   ex: "Quel est le taux de retard moyen ce mois ?"

2. Utiliser le SectorContext (produit par le Context/Sector Agent)
   pour répondre avec précision sectorielle :
   - Connaît les KPIs disponibles dans ce secteur
   - Utilise les bons termes métier (retard, vol, gate vs transaction, stock...)
   - Génère du SQL cohérent avec le schéma réel si un profil data est fourni

3. Maintenir l'historique de conversation (mémoire in-memory Sprint 1)
   pour permettre des questions de suivi :
   ex: "Et pour la route CMN-CDG spécifiquement ?" (fait référence à la question précédente)

4. Accepter un profil de données optionnel (du Data Prep Agent)
   pour générer des requêtes SQL avec les vrais noms de colonnes

Stack
-----
- LangChain + OpenRouter (meta-llama/llama-3.1-8b-instruct)
- Pydantic pour la validation des sorties

Flux dans l'architecture
------------------------
  [Context/Sector Agent] → SectorContext
                                │
  User specific question        │
          │                     ▼
          └──────────► [NLQ Agent]   ← CE MODULE
                            │
                            ▼
                    NLQResponse (réponse + SQL + KPI + chart)
"""

import os
import json
from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agents.context_sector_agent import SectorContext


# ══════════════════════════════════════════════════════════
# SECTION 1 — MODÈLE DE RÉPONSE
# ══════════════════════════════════════════════════════════

class NLQResponse(BaseModel):
    """
    Réponse structurée produite par le NLQ Agent pour chaque question.

    Attributs
    ---------
    answer : str
        Réponse en langage naturel, claire et orientée métier.
        C'est ce qui s'affiche à l'utilisateur dans le chatbot.

    query_type : str
        Classification du type de requête :
        - "sql"          → une requête SQL a été générée
        - "aggregation"  → calcu
        l d'agrégat (moyenne, somme, count...)
        - "prediction"   → question orientée prédiction/forecast
        - "explanation"  → explication ou analyse qualitative

    generated_query : str, optional
        Requête SQL ou analytique générée quand applicable.
        Utilise les noms de colonnes du DataProfile si disponible.

    kpi_referenced : str, optional
        Nom exact du KPI concerné par la question (doit correspondre
        à un KPI dans le SectorContext reçu).

    suggested_chart : str, optional
        Type de visualisation recommandé pour cette réponse.
        ex: "bar chart", "line chart", "KPI card"

    needs_more_data : bool
        True si la question ne peut pas être répondue complètement
        sans données supplémentaires (dataset non uploadé, etc.)
    """
    answer: str
    query_type: str
    generated_query: Optional[str] = None
    kpi_referenced: Optional[str] = None
    suggested_chart: Optional[str] = None
    needs_more_data: bool = False


# ══════════════════════════════════════════════════════════
# SECTION 2 — NLQ AGENT
# ══════════════════════════════════════════════════════════

class NLQAgent:
    """
    Chatbot analytique contextuel (OpenRouter / Llama 3.1 8B).

    Contrairement à un chatbot générique, cet agent est spécialisé
    par secteur grâce au SectorContext injecté dynamiquement dans
    le system prompt à chaque échange.

    Pourquoi le contexte sectoriel est-il critique ?
    ------------------------------------------------
    Sans contexte :
      Q: "Montre-moi les retards"
      → réponse générique, SQL incorrect, mauvais noms de colonnes

    Avec SectorContext (transport, KPIs: Average Delay, ...):
      Q: "Montre-moi les retards"
      → SQL précis sur delay_minutes, référence au KPI "Average Delay",
         suggestion de visualisation adaptée (histogram)

    Mémoire de conversation (Sprint 1)
    ------------------------------------
    L'historique est stocké en mémoire Python (liste de dict).
    À chaque appel, tout l'historique est injecté dans les messages
    pour que le LLM puisse répondre aux questions de suivi.

    Exemple :
      Tour 1: "Quel est le taux de retard moyen ?"  → "12 minutes en moyenne"
      Tour 2: "Et pour la route CMN-CDG ?"          → le LLM sait que "ça" = taux de retard

    Parameters
    ----------
    openrouter_api_key : str
        Clé API OpenRouter
    verbose : bool
        Affiche les logs de chaque échange

    Examples
    --------
    >>> nlq = NLQAgent(api_key="sk-or-v1-...")
    >>> response = nlq.chat("Quel est le taux de retard ?", sector_context)
    >>> print(response.answer)
    >>> print(response.generated_query)
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    MODEL = "meta-llama/llama-3.1-8b-instruct"

    def __init__(self, openrouter_api_key: str, verbose: bool = True):
        self.verbose = verbose

        # Historique de conversation (in-memory, Sprint 1)
        # Format: [{"user": "question", "assistant": "réponse"}, ...]
        self.conversation_history: list[dict] = []

        # LLM via OpenRouter
        self.llm = ChatOpenAI(
            model=self.MODEL,
            temperature=0.2,        # légèrement créatif pour les réponses textuelles
            api_key=openrouter_api_key,
            base_url=self.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://dxc-pfe-analytics.local",
                "X-Title": "DXC Intelligence Analytics Platform"
            }
        )

    # ──────────────────────────────────────────────────
    # Méthode privée : construction du system prompt
    # ──────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        sector_context: SectorContext,
        data_profile: Optional[dict]
    ) -> str:
        """
        Construit le system prompt du chatbot injecté avec le contexte sectoriel.

        C'est ici que la spécialisation se produit : le LLM reçoit
        dans ses instructions le secteur détecté, les KPIs disponibles,
        et si disponible le schéma réel du dataset.

        Parameters
        ----------
        sector_context : SectorContext
            Contexte produit par le ContextSectorAgent
        data_profile : dict, optional
            Profil du dataset produit par le DataPrepAgent.
            Contient les noms réels des colonnes pour générer du SQL précis.
            Clés attendues : "columns", "row_count", "numeric_columns",
                             "categorical_columns", "missing_summary"

        Returns
        -------
        str
            System prompt complet et contextualisé
        """
        # Formatage des KPIs disponibles
        kpi_block = "\n".join([
            f"  - {kpi.name} ({kpi.unit}): {kpi.description}"
            for kpi in sector_context.kpis
        ])

        # Section data profile — injectée seulement si le Data Prep Agent a fourni des données
        data_section = ""
        if data_profile:
            cols = data_profile.get("columns", [])
            rows = data_profile.get("row_count", "unknown")
            missing = data_profile.get("missing_summary", {})
            numeric = data_profile.get("numeric_columns", [])
            categorical = data_profile.get("categorical_columns", [])

            data_section = f"""
UPLOADED DATASET PROFILE:
  Total rows        : {rows}
  All columns       : {', '.join(cols)}
  Numeric columns   : {', '.join(numeric)}
  Categorical cols  : {', '.join(categorical)}
  Columns w/ missing: {json.dumps(missing, ensure_ascii=False)}

IMPORTANT: When generating SQL, use ONLY the exact column names listed above.
"""

        return f"""You are an analytics chatbot specialized in the {sector_context.sector.upper()} sector.

CURRENT CONTEXT:
  Sector      : {sector_context.sector}
  Use Case    : {sector_context.use_case}
  Dashboard   : {sector_context.dashboard_focus}

AVAILABLE KPIs FOR THIS SECTOR:
{kpi_block}
{data_section}
RESPONSE RULES:
1. Answer the user's question using the sector context above
2. When the question relates to a KPI, reference it by its exact name
3. If the question calls for data retrieval, generate a SQL query
4. Suggest a relevant chart type when the answer involves metrics
5. If you cannot answer completely without more data, set needs_more_data to true
6. Stay strictly within the {sector_context.sector} sector domain

Respond ONLY with valid JSON. No markdown fences, no text outside the JSON.

JSON Schema:
{{
  "answer": "natural language response for the user",
  "query_type": "sql|aggregation|prediction|explanation",
  "generated_query": "SQL string or null",
  "kpi_referenced": "exact KPI name or null",
  "suggested_chart": "chart type description or null",
  "needs_more_data": false
}}"""

    # ──────────────────────────────────────────────────
    # Méthode privée : parsing de la réponse
    # ──────────────────────────────────────────────────

    def _parse_response(self, raw_content: str) -> NLQResponse:
        """
        Parse la réponse JSON du LLM en objet NLQResponse.

        Gère le nettoyage des backticks markdown que Llama peut ajouter.
        En cas d'échec du parsing JSON, retourne une NLQResponse dégradée
        avec le contenu brut comme réponse textuelle (fallback).

        Parameters
        ----------
        raw_content : str
            Contenu brut de la réponse LLM

        Returns
        -------
        NLQResponse
            Objet validé, jamais None (fallback si nécessaire)
        """
        content = raw_content.strip()

        # Nettoyage des backticks markdown
        if content.startswith("```"):
            parts = content.split("```")
            content = parts[1]
            if content.startswith("json"):
                content = content[4:]

        try:
            return NLQResponse(**json.loads(content.strip()))
        except Exception:
            # Fallback : retourner la réponse brute comme texte
            return NLQResponse(
                answer=raw_content.strip(),
                query_type="explanation"
            )

    # ──────────────────────────────────────────────────
    # Méthode publique principale
    # ──────────────────────────────────────────────────

    def chat(
        self,
        user_question: str,
        sector_context: SectorContext,
        data_profile: Optional[dict] = None
    ) -> NLQResponse:
        """
        Répond à une question spécifique de l'utilisateur.

        Chaque appel :
        1. Construit le system prompt avec le SectorContext
        2. Injecte l'historique complet de conversation
        3. Appelle le LLM avec la nouvelle question
        4. Parse et valide la réponse JSON
        5. Sauvegarde l'échange dans l'historique

        Parameters
        ----------
        user_question : str
            Question spécifique de l'utilisateur après le dashboard global.
            Exemples :
            - "Quel est le taux de retard moyen ce mois ?"
            - "Compare la satisfaction entre les routes"
            - "Quels vols ont les pires scores de ponctualité ?"

        sector_context : SectorContext
            Contexte produit par le ContextSectorAgent.
            Doit être le même objet pour toute la durée de la session.

        data_profile : dict, optional
            Profil du dataset produit par le DataPrepAgent.
            Si fourni, le NLQ génère du SQL avec les vrais noms de colonnes.
            Si absent, le SQL utilise des noms génériques cohérents avec le secteur.

        Returns
        -------
        NLQResponse
            Réponse structurée avec texte, SQL optionnel, KPI et chart.

        Examples
        --------
        >>> response = nlq.chat("Quel est le taux de retard moyen ?", ctx)
        >>> print(response.answer)
        >>> print(response.generated_query)
        >>> print(response.kpi_referenced)    # "Average Delay"
        >>> print(response.suggested_chart)   # "KPI card with trend"
        """
        if self.verbose:
            print(f"\n{'─'*60}")
            print(f"[NLQAgent] Question: '{user_question}'")
            print(f"  Sector: {sector_context.sector} | "
                  f"History: {len(self.conversation_history)} turns | "
                  f"Data profile: {'yes' if data_profile else 'no'}")

        # Construction du system prompt contextualisé
        system_prompt = self._build_system_prompt(sector_context, data_profile)

        # Construction des messages avec historique
        messages = [SystemMessage(content=system_prompt)]

        # Injection de l'historique pour permettre les questions de suivi
        for turn in self.conversation_history:
            messages.append(HumanMessage(content=turn["user"]))
            messages.append(AIMessage(content=turn["assistant"]))

        # Question courante
        messages.append(HumanMessage(content=user_question))

        # Appel LLM
        raw_response = self.llm.invoke(messages)

        # Parsing
        result = self._parse_response(raw_response.content)

        # Sauvegarde dans l'historique
        self.conversation_history.append({
            "user": user_question,
            "assistant": result.answer
        })

        if self.verbose:
            print(f"  ✅ Answer  : {result.answer[:100]}...")
            print(f"  🔍 Type    : {result.query_type}")
            if result.generated_query:
                print(f"  📝 SQL     : {result.generated_query[:80]}...")
            if result.kpi_referenced:
                print(f"  📊 KPI     : {result.kpi_referenced}")
            if result.suggested_chart:
                print(f"  📈 Chart   : {result.suggested_chart}")

        return result

    # ──────────────────────────────────────────────────
    # Gestion de la mémoire
    # ──────────────────────────────────────────────────

    def reset_conversation(self):
        """
        Réinitialise l'historique de conversation.

        À appeler quand l'utilisateur commence une nouvelle session
        ou change de sujet de façon significative.
        """
        self.conversation_history = []
        if self.verbose:
            print("[NLQAgent] Conversation history cleared.")

    @property
    def history_length(self) -> int:
        """Retourne le nombre de tours de conversation en cours."""
        return len(self.conversation_history)