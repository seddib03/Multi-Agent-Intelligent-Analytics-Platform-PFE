# LLMClient : wrapper pour appeler le LLM via OpenRouter de manière structurée et robuste.
from __future__ import annotations

import json
import logging
from typing import Optional, Union

from openai import OpenAI

from config.settings import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Client pour appeler le LLM via OpenRouter.

    Usage typique dans un node :

        client = LLMClient()

        # Pour une réponse JSON structurée
        result = client.call_structured(
            system_prompt="Tu es un expert data quality...",
            user_prompt="Analyse ce dataset : ...",
        )
        plan = result["plan_nettoyage"]  # dict parsé

        # Pour une réponse texte libre
        text = client.call_text(
            system_prompt="...",
            user_prompt="...",
        )
    """

    def __init__(self) -> None:
        """
        Initialise le client avec la configuration centralisée.

        On lit settings une seule fois à l'instanciation.
        → Pas de lecture .env à chaque appel API.
        """
        settings = get_settings()

        # Le SDK openai avec base_url OpenRouter
        # → Exactement comme OpenAI mais redirigé vers OpenRouter
        self._client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )

        self._model       = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_tokens  = settings.llm_max_tokens

        logger.info("LLMClient initialisé — modèle : %s", self._model)

    def call_structured(
        self,
        system_prompt: str,
        user_prompt:   str,
        context:       Optional[str] = None,
    ) -> dict:
        """
        Appelle le LLM et parse la réponse en JSON.

        À utiliser quand on a besoin d'une structure de données
        précise en réponse (plan de nettoyage, mapping dimensions...).

        COMMENT ÇA MARCHE :
            On dit au LLM dans le system_prompt de répondre
            UNIQUEMENT en JSON valide.
            Puis on parse la réponse avec json.loads().
            Si le LLM hallucine du texte autour du JSON,
            on le nettoie avant de parser.

        Args:
            system_prompt: Instructions pour le LLM
                           (son rôle, ce qu'on attend)
            user_prompt:   La question / données à analyser
            context:       Contexte additionnel optionnel
                           (ex: résultats dbt, profil dataset)

        Returns:
            Dict parsé depuis la réponse JSON du LLM.

        Raises:
            ValueError:  Si la réponse n'est pas du JSON valide
            RuntimeError: Si l'appel API échoue après retries
        """
        messages = self._build_messages(
            system_prompt, user_prompt, context
        )

        logger.info(
            "Appel LLM (structured) — modèle: %s | "
            "system: %d chars | user: %d chars",
            self._model,
            len(system_prompt),
            len(user_prompt),
        )

        raw_response = self._call_api(messages)

        # Parser la réponse JSON
        return self._parse_json_response(raw_response)

    def call_text(
        self,
        system_prompt: str,
        user_prompt:   str,
        context:       Optional[str] = None,
    ) -> str:
        """
        Appelle le LLM et retourne la réponse en texte libre.

        À utiliser quand on veut une analyse narrative
        (ex: commentaire sur les résultats de qualité).

        Args:
            system_prompt: Instructions pour le LLM
            user_prompt:   La question
            context:       Contexte additionnel optionnel

        Returns:
            Réponse textuelle du LLM.

        Raises:
            RuntimeError: Si l'appel API échoue
        """
        messages = self._build_messages(
            system_prompt, user_prompt, context
        )

        logger.info(
            "Appel LLM (text) — modèle: %s | "
            "system: %d chars | user: %d chars",
            self._model,
            len(system_prompt),
            len(user_prompt),
        )

        return self._call_api(messages)

    # ── Méthodes privées ─────────────────────────────────────────────────────

    def _build_messages(
        self,
        system_prompt: str,
        user_prompt:   str,
        context:       Optional[str],
    ) -> list[dict]:
        """
        Construit la liste de messages au format OpenAI.

        Format attendu par l'API :
            [
                {"role": "system", "content": "..."},
                {"role": "user",   "content": "..."},
            ]

        Le context est ajouté au user_prompt si présent.
        → Évite un 3ème message qui complexifie la conversation.

        Args:
            system_prompt: Rôle et instructions du LLM
            user_prompt:   Question principale
            context:       Données additionnelles (profiling, dbt...)

        Returns:
            Liste de messages formatés pour l'API.
        """
        # Construire le contenu user complet
        user_content = user_prompt
        if context:
            user_content = f"{user_prompt}\n\nCONTEXTE:\n{context}"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ]

    def _call_api(self, messages: list[dict]) -> str:
        """
        Exécute l'appel HTTP vers OpenRouter.

        Gère les erreurs et loggue le résultat.

        Args:
            messages: Liste de messages formatés

        Returns:
            Contenu texte de la réponse du LLM.

        Raises:
            RuntimeError: Si l'appel échoue (réseau, auth, quota)
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )

            # Extraire le texte de la réponse
            # response.choices[0].message.content
            # → Premier choix → message → texte
            content = response.choices[0].message.content

            # Logguer les tokens utilisés (pour suivre les coûts)
            usage = response.usage
            logger.info(
                "LLM réponse reçue — tokens: %d prompt + %d completion = %d total",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )

            return content

        except Exception as e:
            # Capturer TOUTES les exceptions et les convertir
            # en RuntimeError avec un message clair
            logger.error("Échec appel LLM : %s", str(e))
            raise RuntimeError(
                f"Appel LLM échoué (modèle: {self._model}) : {str(e)}"
            ) from e

    def _parse_json_response(self, raw_response: str) -> dict:
        """
        Parse la réponse JSON du LLM de façon robuste.

        PROBLÈME FRÉQUENT :
            Le LLM répond parfois avec du texte autour du JSON :
            "Voici le plan :\n```json\n{...}\n```\nJ'espère que ça aide."

            json.loads() échoue sur ce texte.
            Cette méthode nettoie la réponse avant de parser.

        STRATÉGIE DE NETTOYAGE :
            1. Chercher ```json ... ``` (markdown code block)
            2. Si non trouvé, chercher { ... } directement
            3. Si toujours rien, lever une erreur claire

        Args:
            raw_response: Texte brut retourné par le LLM

        Returns:
            Dict Python parsé depuis le JSON.

        Raises:
            ValueError: Si aucun JSON valide trouvé dans la réponse
        """
        # Tentative 1 : parser directement (cas idéal)
        try:
            return json.loads(raw_response.strip())
        except json.JSONDecodeError:
            pass

        # Tentative 2 : extraire depuis un bloc markdown ```json
        if "```json" in raw_response:
            start = raw_response.find("```json") + 7
            end   = raw_response.find("```", start)
            if end != -1:
                json_str = raw_response[start:end].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        # Tentative 3 : extraire la première paire { ... }
        start = raw_response.find("{")
        end   = raw_response.rfind("}") + 1
        if start != -1 and end > start:
            json_str = raw_response[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # Aucune tentative n'a fonctionné
        logger.error(
            "Impossible de parser la réponse LLM en JSON. "
            "Réponse brute : %s",
            raw_response[:500],  # Limiter le log à 500 chars
        )
        raise ValueError(
            "Le LLM n'a pas retourné un JSON valide. "
            f"Début de la réponse : {raw_response[:200]}"
        )