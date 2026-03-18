"""
Customer Adapter — Profiling + Behavior Collection + Adaptation
================================================================
PFE — DXC Technology | Intelligence Analytics Platform
Sprint 2

Architecture
------------
Ce module est structuré en 3 couches explicites :

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    CUSTOMER ADAPTER                                  │
    │                                                                     │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │  COUCHE 1 — USER PROFILING                                  │   │
    │  │  Qui est l'utilisateur ?                                    │   │
    │  │  • Langue préférée (fr / ar / en) — détectée automatique   │   │
    │  │  • Niveau technique (debutant / intermediaire / expert)     │   │
    │  │  • Style de réponse préféré (court / detaille)              │   │
    │  │  • Secteur métier (transport / finance / retail...)         │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    │                          │                                          │
    │                          ▼                                          │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │  COUCHE 2 — USER BEHAVIOR COLLECTION                        │   │
    │  │  Que fait l'utilisateur ?                                   │   │
    │  │  • KPIs les plus consultés (compteur par KPI)               │   │
    │  │  • Intents utilisés (sql / aggregation / comparison...)     │   │
    │  │  • Fréquence des sessions (nb questions / session)          │   │
    │  │  • Patterns temporels (heure d'activité)                    │   │
    │  │  • Séquences de questions (enchaînements fréquents)         │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    │                          │                                          │
    │                          ▼                                          │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │  COUCHE 3 — INTERACTION ADAPTATION                          │   │
    │  │  Comment adapter la réponse ?                               │   │
    │  │  • Prompt context injecté dans le LLM                       │   │
    │  │  • Règles langue / niveau / style                           │   │
    │  │  • Mise en avant des KPIs fréquents                         │   │
    │  │  • Suggestions de suivi basées sur les séquences            │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────┘

Flux NLQAgent.chat()
--------------------
    AVANT le LLM :
        process_before_chat(user_id, question, sector)
            └─► get_profile()   [COUCHE 1]
            └─► get_behavior()  [COUCHE 2]
            └─► build_prompt_context(profile, behavior)  [COUCHE 3]
                    └─► injecté dans le system prompt

    APRÈS le LLM :
        process_after_chat(user_id, intent, kpi_referenced, ...)
            └─► update_profile()    [COUCHE 1] — langue / niveau / style
            └─► collect_behavior()  [COUCHE 2] — KPIs / intents / temps

Persistance Redis
-----------------
    "profile:{user_id}"   → UserProfile  (langue, niveau, style, secteur)
    "behavior:{user_id}"  → UserBehavior (kpi_counts, intent_counts, sessions...)
    Expiration : illimitée (cohérent avec Memory Layer history:{user_id})
    Fallback   : dict RAM si Redis indisponible

Usage
-----
    >>> adapter = CustomerAdapter(redis_client=r)
    >>> profile, behavior, ctx = adapter.process_before_chat(
    ...     "user_001", question="retard moyen ?", sector="transport"
    ... )
    >>> # ... appel LLM avec ctx injecté dans le prompt ...
    >>> adapter.process_after_chat(
    ...     "user_001", intent="aggregation", kpi_referenced="Retard Moyen"
    ... )
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════════
# COUCHE 1 — USER PROFILING
# Qui est l'utilisateur ?
# ══════════════════════════════════════════════════════════════════════════════

class UserProfile(BaseModel):
    """
    COUCHE 1 — USER PROFILING

    Capture l'identité et les préférences stables de l'utilisateur.
    Évolue lentement (lissage sur plusieurs questions).

    Persisté : Redis "profile:{user_id}"
    """
    user_id             : str
    langue              : str       = "fr"            # fr | ar | en
    niveau              : str       = "intermediaire" # debutant | intermediaire | expert
    style               : str       = "detaille"      # court | detaille
    secteur             : str       = ""              # transport | finance | retail | ...
    display_preferences : list[str] = Field(default_factory=list)
    # Visualisations préférées — déduit des suggested_chart retournés par le LLM
    # Valeurs : "bar_chart" | "line_chart" | "pie_chart" | "table" | "kpi_card"
    created_at          : str       = ""
    updated_at          : str       = ""

    @property
    def is_new(self) -> bool:
        return self.updated_at == ""

    @property
    def preferred_chart(self):
        """Type de visualisation le plus souvent utilisé par cet utilisateur."""
        if not self.display_preferences:
            return None
        from collections import Counter
        counts = Counter(self.display_preferences)
        return counts.most_common(1)[0][0]


class UserBehavior(BaseModel):
    """
    COUCHE 2 — USER BEHAVIOR COLLECTION

    Capture les habitudes et comportements observés de l'utilisateur.
    Mis à jour à chaque interaction.

    Persisté : Redis "behavior:{user_id}"
    """
    user_id     : str

    # Compteurs KPIs  — ex: {"Retard Moyen": 12, "On-Time Performance": 7}
    kpi_counts  : dict[str, int] = Field(default_factory=dict)

    # Compteurs intents — ex: {"aggregation": 15, "sql": 8, "comparison": 4}
    intent_counts : dict[str, int] = Field(default_factory=dict)

    # Fréquence sessions
    total_questions             : int   = 0
    total_sessions              : int   = 0
    avg_questions_per_session   : float = 0.0

    # Séquences d'intents — ex: {"aggregation→comparison": 5}
    intent_sequences : dict[str, int] = Field(default_factory=dict)
    last_intent      : str            = ""

    first_seen : str = ""
    last_seen  : str = ""

    @property
    def top_kpis(self) -> list[str]:
        """Top 5 KPIs les plus consultés."""
        sorted_kpis = sorted(self.kpi_counts.items(), key=lambda x: x[1], reverse=True)
        return [k for k, _ in sorted_kpis[:5]]

    @property
    def dominant_intent(self) -> Optional[str]:
        if not self.intent_counts:
            return None
        return max(self.intent_counts, key=self.intent_counts.get)

    @property
    def confidence(self) -> str:
        if self.total_questions < 3:  return "low"
        if self.total_questions < 10: return "medium"
        return "high"


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION AUTOMATIQUE — Langue / Niveau / Style
# Utilisé par COUCHE 1 — User Profiling
# ══════════════════════════════════════════════════════════════════════════════

_AR_KEYWORDS = [
    "ما هو", "كيف", "أظهر", "قائمة", "متوسط", "مجموع", "عدد",
    "تحليل", "توقع", "شذوذ", "هل", "ما", "من", "أين"
]
_EN_KEYWORDS = [
    "what is", "how many", "show me", "list", "average", "sum", "count",
    "predict", "forecast", "anomaly", "which", "where", "when", "who",
    "give me", "display"
]
_FR_KEYWORDS = [
    "quel", "quelle", "combien", "montre", "liste", "moyenne", "somme",
    "prédire", "prévoir", "anomalie", "comment", "pourquoi", "où",
    "donne", "affiche", "calcule", "compare", "quels"
]
_EXPERT_KEYWORDS = [
    "sql", "select", "where", "join", "group by", "having",
    "agrégation", "agrégat", "corrélation", "variance", "écart-type",
    "percentile", "quantile", "outlier", "clustering", "regression",
    "accuracy", "precision", "recall", "f1", "roc", "auc",
    "pipeline", "feature", "hyperparameter", "cross-validation", "p-value"
]
_BEGINNER_KEYWORDS = [
    "c'est quoi", "qu'est-ce que", "explique", "je comprends pas",
    "comment ça marche", "tu peux m'expliquer", "simple", "basique"
]


def _detect_langue(text: str) -> Optional[str]:
    t = text.lower()
    ar_score = sum(1 for kw in _AR_KEYWORDS if kw in t)
    en_score = sum(1 for kw in _EN_KEYWORDS if kw in t)
    fr_score = sum(1 for kw in _FR_KEYWORDS if kw in t)
    if re.search(r'[\u0600-\u06FF]', text):
        ar_score += 5
    scores = {"ar": ar_score, "en": en_score, "fr": fr_score}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def _detect_niveau(text: str) -> Optional[str]:
    t = text.lower()
    expert_hits   = sum(1 for kw in _EXPERT_KEYWORDS   if kw in t)
    beginner_hits = sum(1 for kw in _BEGINNER_KEYWORDS if kw in t)
    if expert_hits >= 2:   return "expert"
    if expert_hits == 1:   return "intermediaire"
    if beginner_hits >= 1: return "debutant"
    return None


def _detect_style(text: str, history_lengths: list[int]) -> Optional[str]:
    word_count = len(text.split())
    if word_count > 15:
        return "detaille"
    if history_lengths and sum(history_lengths) / len(history_lengths) < 7:
        return "court"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER ADAPTER — classe principale
# Orchestre les 3 couches
# ══════════════════════════════════════════════════════════════════════════════

class CustomerAdapter:
    """
    Orchestre les 3 couches du Customer Adapter.

    Couche 1 — User Profiling          : get_profile()   / update_profile()
    Couche 2 — User Behavior Collection: get_behavior()  / collect_behavior()
    Couche 3 — Interaction Adaptation  : build_prompt_context()

    API principale (appelée par NLQAgent) :
        process_before_chat()  — charge profil + behavior + construit le contexte
        process_after_chat()   — met à jour profil + collecte le comportement

    Parameters
    ----------
    redis_client : redis.Redis | None
        Partagé avec Memory Layer (même client Redis que NLQAgent._redis).
        Si None → fallback dict RAM.

    Redis keys
    ----------
    "profile:{user_id}"   → UserProfile  (JSON, illimité)
    "behavior:{user_id}"  → UserBehavior (JSON, illimité)
    """

    PROFILE_PREFIX  = "profile:"
    BEHAVIOR_PREFIX = "behavior:"

    def __init__(self, redis_client=None, verbose: bool = True):
        self._redis  = redis_client
        self.verbose = verbose
        self._ram_profiles  : dict[str, dict] = {}
        self._ram_behaviors : dict[str, dict] = {}

        if self.verbose:
            store = "Redis" if self._redis else "RAM (fallback)"
            print(f"[CustomerAdapter] ✅ Initialisé — store={store}")

    # ══════════════════════════════════════════════════════════════════════════
    # COUCHE 1 — USER PROFILING
    # ══════════════════════════════════════════════════════════════════════════

    def get_profile(self, user_id: str) -> UserProfile:
        """COUCHE 1 — Charge le profil utilisateur (Redis → RAM → défaut)."""
        key = f"{self.PROFILE_PREFIX}{user_id}"
        if self._redis:
            try:
                raw = self._redis.get(key)
                if raw:
                    return UserProfile(**json.loads(raw))
            except Exception as e:
                if self.verbose:
                    print(f"[CustomerAdapter] ⚠️  Redis profile get: {e}")
        if user_id in self._ram_profiles:
            return UserProfile(**self._ram_profiles[user_id])
        return UserProfile(user_id=user_id)

    def update_profile(
        self,
        user_id         : str,
        question        : str           = "",
        sector          : str           = "",
        suggested_chart : Optional[str] = None,
        history         : list          = None,
    ) -> UserProfile:
        """
        COUCHE 1 — Met à jour le profil utilisateur.

        Détecte automatiquement depuis la question :
          langue (FR/AR/EN), niveau (expert/débutant), style (court/détaillé).
        Lissage appliqué pour éviter les changements brusques.
        Met à jour display_preferences si suggested_chart est fourni.
        """
        profile = self.get_profile(user_id)
        history = history or []
        now     = datetime.now(timezone.utc).isoformat()

        if profile.is_new:
            profile.created_at = now
        profile.updated_at = now

        if sector:
            profile.secteur = sector

        # Préférences d'affichage — déduit du suggested_chart retourné par le LLM
        if suggested_chart:
            normalized = suggested_chart.lower().replace(" ", "_").replace("-", "_")
            # Normalisation vers valeurs canoniques
            chart_map = {
                "bar"     : "bar_chart",  "bar_chart" : "bar_chart",
                "line"    : "line_chart", "line_chart": "line_chart",
                "pie"     : "pie_chart",  "pie_chart" : "pie_chart",
                "table"   : "table",      "tableau"   : "table",
                "kpi"     : "kpi_card",   "kpi_card"  : "kpi_card",
                "scatter" : "scatter",    "histogram" : "histogram",
            }
            canonical = chart_map.get(normalized, normalized)
            profile.display_preferences.append(canonical)
            # Garder uniquement les 20 dernières entrées (fenêtre glissante)
            profile.display_preferences = profile.display_preferences[-20:]

        if question:
            # Langue avec lissage
            detected_lang = _detect_langue(question)
            if detected_lang:
                if len(history) < 2:
                    profile.langue = detected_lang
                else:
                    lang_history = [_detect_langue(t.get("user", "")) for t in history[-3:]]
                    if lang_history.count(detected_lang) >= 2:
                        profile.langue = detected_lang

            # Niveau avec lissage
            detected_niveau = _detect_niveau(question)
            if detected_niveau:
                if detected_niveau == "expert":
                    profile.niveau = "expert"
                elif detected_niveau == "debutant" and profile.niveau != "expert":
                    profile.niveau = "debutant"
                elif detected_niveau == "intermediaire" and profile.niveau == "debutant":
                    profile.niveau = "intermediaire"

            # Style
            q_lengths = [len(t.get("user", "").split()) for t in history[-10:]]
            detected_style = _detect_style(question, q_lengths)
            if detected_style:
                profile.style = detected_style

        self._save_profile(profile)

        if self.verbose:
            print(
                f"  [Profiling]  👤 user='{user_id}' | "
                f"lang={profile.langue} | niveau={profile.niveau} | "
                f"style={profile.style} | secteur={profile.secteur or 'N/A'}"
            )
        return profile

    def _save_profile(self, profile: UserProfile) -> None:
        key = f"{self.PROFILE_PREFIX}{profile.user_id}"
        data = profile.model_dump()
        if self._redis:
            try:
                self._redis.set(key, json.dumps(data, ensure_ascii=False))
                return
            except Exception as e:
                if self.verbose:
                    print(f"[CustomerAdapter] ⚠️  Redis profile save: {e}")
        self._ram_profiles[profile.user_id] = data

    def delete_profile(self, user_id: str) -> bool:
        key = f"{self.PROFILE_PREFIX}{user_id}"
        if self._redis:
            try:
                return self._redis.delete(key) > 0
            except Exception:
                pass
        if user_id in self._ram_profiles:
            del self._ram_profiles[user_id]
            return True
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # COUCHE 2 — USER BEHAVIOR COLLECTION
    # ══════════════════════════════════════════════════════════════════════════

    def get_behavior(self, user_id: str) -> UserBehavior:
        """COUCHE 2 — Charge les données comportementales (Redis → RAM → défaut)."""
        key = f"{self.BEHAVIOR_PREFIX}{user_id}"
        if self._redis:
            try:
                raw = self._redis.get(key)
                if raw:
                    return UserBehavior(**json.loads(raw))
            except Exception as e:
                if self.verbose:
                    print(f"[CustomerAdapter] ⚠️  Redis behavior get: {e}")
        if user_id in self._ram_behaviors:
            return UserBehavior(**self._ram_behaviors[user_id])
        return UserBehavior(user_id=user_id)

    def collect_behavior(
        self,
        user_id         : str,
        intent          : str           = "",
        kpi_referenced  : Optional[str] = None,
        suggested_chart : Optional[str] = None,
        question        : str           = "",
        is_new_session  : bool          = False,
    ) -> UserBehavior:
        """
        COUCHE 2 — Collecte le comportement observé après une interaction.

        Collecte et met à jour :
          • kpi_counts          — KPIs consultés (kpi_counts[kpi] += 1)
          • intent_counts       — intents utilisés (intent_counts[intent] += 1)
          • intent_sequences    — enchaînements ("aggregation→comparison" += 1)
          • total_questions     — compteur global
          • total_sessions      — si is_new_session=True
        Note : suggested_chart est transmis à update_profile() via process_after_chat()
               pour mettre à jour display_preferences (COUCHE 1 — User Profiling).
        """
        behavior = self.get_behavior(user_id)
        now      = datetime.now(timezone.utc)

        if not behavior.first_seen:
            behavior.first_seen = now.isoformat()
        behavior.last_seen = now.isoformat()

        # Total questions
        behavior.total_questions += 1

        # Sessions
        if is_new_session:
            behavior.total_sessions += 1

        # Intent
        if intent:
            behavior.intent_counts[intent] = behavior.intent_counts.get(intent, 0) + 1

        # KPI
        if kpi_referenced:
            behavior.kpi_counts[kpi_referenced] = (
                behavior.kpi_counts.get(kpi_referenced, 0) + 1
            )

        # Séquence d'intents  "intent_précédent→intent_courant"
        if intent and behavior.last_intent:
            seq_key = f"{behavior.last_intent}→{intent}"
            behavior.intent_sequences[seq_key] = (
                behavior.intent_sequences.get(seq_key, 0) + 1
            )
        if intent:
            behavior.last_intent = intent

        # Avg questions/session
        if behavior.total_sessions > 0:
            behavior.avg_questions_per_session = round(
                behavior.total_questions / behavior.total_sessions, 2
            )

        self._save_behavior(behavior)

        if self.verbose:
            print(
                f"  [Behavior]   📊 user='{user_id}' | "
                f"intent={intent or 'N/A'} | kpi={kpi_referenced or 'N/A'} | "
                f"total_q={behavior.total_questions} | "
                f"top_kpis={behavior.top_kpis[:2]}"
            )
        return behavior

    def _save_behavior(self, behavior: UserBehavior) -> None:
        key = f"{self.BEHAVIOR_PREFIX}{behavior.user_id}"
        data = behavior.model_dump()
        if self._redis:
            try:
                self._redis.set(key, json.dumps(data, ensure_ascii=False))
                return
            except Exception as e:
                if self.verbose:
                    print(f"[CustomerAdapter] ⚠️  Redis behavior save: {e}")
        self._ram_behaviors[behavior.user_id] = data

    def delete_behavior(self, user_id: str) -> bool:
        key = f"{self.BEHAVIOR_PREFIX}{user_id}"
        if self._redis:
            try:
                return self._redis.delete(key) > 0
            except Exception:
                pass
        if user_id in self._ram_behaviors:
            del self._ram_behaviors[user_id]
            return True
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # COUCHE 3 — INTERACTION ADAPTATION
    # ══════════════════════════════════════════════════════════════════════════

    def build_prompt_context(
        self,
        profile  : UserProfile,
        behavior : UserBehavior,
    ) -> str:
        """
        COUCHE 3 — Construit le bloc de contexte à injecter dans le system prompt.

        Combine profil (COUCHE 1) + comportement (COUCHE 2) pour adapter :
          • la langue de la réponse
          • le niveau de détail technique
          • le style (court / détaillé)
          • les KPIs à mettre en avant
          • les suggestions de suivi (basées sur les séquences d'intents)
        """
        if behavior.confidence == "low":
            return self._build_minimal_context(profile)
        return self._build_full_context(profile, behavior)

    def _build_minimal_context(self, profile: UserProfile) -> str:
        """Contexte minimal — utilisateur peu connu (< 3 questions)."""
        lang_map = {"fr": "French", "ar": "Arabic", "en": "English"}
        lang = lang_map.get(profile.langue, "French")
        return (
            f"\nUSER ADAPTATION (early stage — adapt progressively):\n"
            f"  Language : {lang} — respond in this language\n"
            f"  Style    : {profile.style}\n"
        )

    def _build_full_context(
        self,
        profile  : UserProfile,
        behavior : UserBehavior,
    ) -> str:
        """Contexte complet — profil établi (≥ 3 questions)."""
        lang_map = {"fr": "French", "ar": "Arabic", "en": "English"}
        lang = lang_map.get(profile.langue, "French")

        niveau_rules = {
            "debutant": (
                "- Use simple vocabulary, avoid jargon\n"
                "- Explain SQL queries step by step\n"
                "- Add a plain-language explanation of each metric"
            ),
            "intermediaire": (
                "- Balance accuracy and readability\n"
                "- Show SQL without over-explaining\n"
                "- Reference KPI names directly"
            ),
            "expert": (
                "- Be concise and technical — no hand-holding\n"
                "- Raw SQL, no simplification\n"
                "- Use statistical vocabulary when relevant"
            ),
        }
        style_rules = {
            "court": (
                "- Keep answers to 2-4 sentences max\n"
                "- Lead with the key number immediately\n"
                "- No preamble"
            ),
            "detaille": (
                "- Provide full context and interpretation\n"
                "- Include reasoning behind the insight\n"
                "- Suggest a follow-up question if relevant"
            ),
        }

        # KPIs fréquents
        kpis_section = ""
        if behavior.top_kpis:
            kpis_section = (
                f"  Frequent KPIs  : {', '.join(behavior.top_kpis)}\n"
                f"  → Prioritize these KPIs in your answer\n"
            )

        # Préférences d'affichage
        chart_hint = ""
        if profile.preferred_chart:
            chart_hint = (
                f"  Preferred chart: {profile.preferred_chart}\n"
                f"  → Suggest this chart type when proposing visualizations\n"
            )

        # Suggestion de suivi basée sur les séquences comportementales
        followup_hint = ""
        if behavior.intent_sequences and behavior.dominant_intent:
            dom = behavior.dominant_intent
            next_intents = {
                seq.split("→")[1]: count
                for seq, count in behavior.intent_sequences.items()
                if seq.startswith(f"{dom}→")
            }
            if next_intents:
                likely_next = max(next_intents, key=next_intents.get)
                next_labels = {
                    "sql"        : "raw records",
                    "aggregation": "a computed metric",
                    "comparison" : "a comparison",
                    "explanation": "an explanation",
                    "prediction" : "a forecast",
                }
                followup_hint = (
                    f"  Behavior pattern: after '{dom}' this user often asks for "
                    f"{next_labels.get(likely_next, likely_next)}\n"
                    f"  → Proactively suggest a follow-up if relevant\n"
                )

        n_rules = niveau_rules.get(profile.niveau, niveau_rules["intermediaire"])
        s_rules = style_rules.get(profile.style,   style_rules["detaille"])

        return (
            f"\nUSER ADAPTATION (confidence={behavior.confidence}):\n"
            f"  Language       : {lang}\n"
            f"  Technical level: {profile.niveau}\n"
            f"  Response style : {profile.style}\n"
            f"  Sector         : {profile.secteur or 'unknown'}\n"
            f"{kpis_section}"
            f"{chart_hint}"
            f"{followup_hint}"
            f"\nADAPTATION RULES — apply strictly:\n"
            f"LANGUAGE: Respond in {lang}\n"
            f"LEVEL ({profile.niveau}):\n"
            f"{n_rules}\n"
            f"STYLE ({profile.style}):\n"
            f"{s_rules}\n"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # API PRINCIPALE — appelée par NLQAgent.chat()
    # ══════════════════════════════════════════════════════════════════════════

    def process_before_chat(
        self,
        user_id  : str,
        question : str,
        sector   : str  = "",
        history  : list = None,
    ) -> tuple:
        """
        Appelé AVANT le LLM dans NLQAgent.chat().

        COUCHE 1 → get_profile()
        COUCHE 2 → get_behavior()
        COUCHE 3 → build_prompt_context(profile, behavior)

        Returns
        -------
        (UserProfile, UserBehavior, str)  ← (profil, comportement, contexte prompt)
        """
        profile  = self.get_profile(user_id)
        behavior = self.get_behavior(user_id)
        context  = self.build_prompt_context(profile, behavior)
        return profile, behavior, context

    def process_after_chat(
        self,
        user_id         : str,
        question        : str,
        intent          : str           = "",
        kpi_referenced  : Optional[str] = None,
        suggested_chart : Optional[str] = None,
        sector          : str           = "",
        history         : list          = None,
        is_new_session  : bool          = False,
    ) -> None:
        """
        Appelé APRÈS le LLM dans NLQAgent.chat().

        COUCHE 1 → update_profile()   — langue / niveau / style / secteur / display_preferences
        COUCHE 2 → collect_behavior() — KPIs / intents / fréquence / séquences
        """
        self.update_profile(
            user_id         = user_id,
            question        = question,
            sector          = sector,
            suggested_chart = suggested_chart,
            history         = history,
        )
        self.collect_behavior(
            user_id         = user_id,
            intent          = intent,
            kpi_referenced  = kpi_referenced,
            suggested_chart = suggested_chart,
            question        = question,
            is_new_session  = is_new_session,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def full_summary(self, user_id: str) -> dict:
        """Résumé complet des 3 couches — utilisé par GET /profile/{user_id}."""
        profile  = self.get_profile(user_id)
        behavior = self.get_behavior(user_id)
        return {
            "profiling": {
                "user_id"             : profile.user_id,
                "langue"              : profile.langue,
                "niveau"              : profile.niveau,
                "style"               : profile.style,
                "secteur"             : profile.secteur,
                "preferred_chart"     : profile.preferred_chart,
                "display_preferences" : profile.display_preferences,
                "created_at"          : profile.created_at,
                "updated_at"          : profile.updated_at,
            },
            "behavior": {
                "total_questions"           : behavior.total_questions,
                "total_sessions"            : behavior.total_sessions,
                "avg_questions_per_session" : behavior.avg_questions_per_session,
                "top_kpis"                  : behavior.top_kpis,
                "dominant_intent"           : behavior.dominant_intent,
                "intent_counts"             : behavior.intent_counts,
                "kpi_counts"                : behavior.kpi_counts,
                "top_sequences"             : dict(
                    sorted(behavior.intent_sequences.items(),
                           key=lambda x: x[1], reverse=True)[:5]
                ),
                "confidence"                : behavior.confidence,
                "first_seen"                : behavior.first_seen,
                "last_seen"                 : behavior.last_seen,
            },
        }

    def delete_all(self, user_id: str) -> dict:
        """Supprime profil + comportement d'un utilisateur."""
        return {
            "profile_deleted" : self.delete_profile(user_id),
            "behavior_deleted": self.delete_behavior(user_id),
        }

    @property
    def active_users(self) -> int:
        if self._redis:
            try:
                return len(self._redis.keys(f"{self.PROFILE_PREFIX}*"))
            except Exception:
                pass
        return len(self._ram_profiles)


# ── Alias rétrocompatibilité ───────────────────────────────────────────────────
# nlq_agent.py importe CustomerProfile — on garde la compatibilité
CustomerProfile = UserProfile