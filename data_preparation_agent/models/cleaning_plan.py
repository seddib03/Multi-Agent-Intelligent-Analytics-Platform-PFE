"""
models/cleaning_plan.py
────────────────────────
Structure de données pour le plan de nettoyage proposé par le LLM.

POURQUOI CE MODÈLE :
    Le LLM retourne du texte JSON.
    Sans structure explicite, n'importe quoi peut arriver.
    Ce modèle garantit que le plan a exactement les champs
    attendus par cleaning_node pour exécuter les actions.

    Flux :
        strategy_node  →  LLM génère JSON  →  CleaningPlan
        user valide CleaningPlan
        cleaning_node lit CleaningPlan et exécute les actions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CleaningAction(str, Enum):
    """
    Actions de nettoyage que cleaning_node sait exécuter.

    POURQUOI UNE ENUM :
        Le LLM pourrait retourner "drop_null" ou "remove_null"
        ou "delete_null_rows"... tous différents, même effet.
        L'Enum force une liste fermée d'actions reconnues.
        Si le LLM retourne une action inconnue → erreur claire.
    """

    # Suppression de lignes
    DROP_NULL_IDENTIFIER  = "drop_null_identifier"
    DROP_DUPLICATES       = "drop_duplicates"

    # Imputation
    IMPUTE_MEDIAN         = "impute_median"
    IMPUTE_MODE           = "impute_mode"
    IMPUTE_CONSTANT       = "impute_constant"

    # Correction de type
    CAST_TO_FLOAT         = "cast_to_float"
    CAST_TO_INT           = "cast_to_int"
    CAST_TO_STRING        = "cast_to_string"
    PARSE_DATE            = "parse_date"

    # Normalisation texte
    TRIM_WHITESPACE       = "trim_whitespace"
    TO_UPPERCASE          = "to_uppercase"
    TO_LOWERCASE          = "to_lowercase"

    # Correction de cohérence
    FIX_DATE_ORDER        = "fix_date_order"

    # Signalement sans modification
    FLAG_OUTLIER          = "flag_outlier"
    LOG_RANGE_VIOLATION   = "log_range_violation"


class UserDecision(str, Enum):
    """
    Décisions possibles de l'utilisateur sur une action.

    APPROVED → Exécuter l'action telle quelle
    MODIFIED → Exécuter avec les modifications de l'user
    REJECTED → Ne pas exécuter cette action
    """

    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


@dataclass
class ActionItem:
    """
    Une action de nettoyage sur une colonne et/ou une ligne.

    Exemple :
        ActionItem(
            action_id="action_1",
            colonne="prime_annuelle",
            lignes_concernees=[7, 12],
            dimension="completeness",
            probleme="2 valeurs nulles",
            action=CleaningAction.IMPUTE_MEDIAN,
            justification="Médiane robuste aux outliers présents",
            severite="MAJOR",
            parametre={"valeur_imputation": 1650.0}
        )
    """

    # Identifiant unique de l'action (pour que l'user puisse
    # approuver/rejeter individuellement)
    action_id: str

    # Colonne concernée
    colonne: str

    # Numéros de lignes exactes concernées (1-indexed)
    # [] = toute la colonne (ex: cast_to_float)
    lignes_concernees: list[int]

    # Dimension de qualité que cette action améliore
    dimension: str

    # Description claire du problème détecté
    probleme: str

    # Action à exécuter
    action: CleaningAction

    # Explication de POURQUOI cette action est proposée
    # C'est ce que l'user lit pour décider d'approuver ou non
    justification: str

    # Niveau de sévérité du problème
    severite: str  # "BLOCKING", "MAJOR", "MINOR"

    # Paramètres optionnels selon l'action
    # Ex: {"valeur_imputation": 1650.0} pour IMPUTE_CONSTANT
    #     {"format": "%Y-%m-%d"} pour PARSE_DATE
    parametre: dict = field(default_factory=dict)

    # Décision de l'utilisateur (rempli après validation)
    user_decision: Optional[UserDecision] = None

    # Modifications apportées par l'user (si MODIFIED)
    user_modifications: Optional[dict] = None


@dataclass
class CleaningPlan:
    """
    Plan complet de nettoyage proposé par le LLM.

    Cycle de vie :
        1. strategy_node crée CleaningPlan avec status="proposed"
        2. L'user reçoit le plan via l'API
        3. L'user approuve/modifie/rejette chaque action
        4. status passe à "validated"
        5. cleaning_node exécute les actions validées

    Exemple d'usage :
        plan = CleaningPlan(...)

        # Actions approuvées uniquement
        for action in plan.approved_actions:
            execute(action)
    """

    # Identifiant unique lié au job
    plan_id: str

    # Secteur concerné
    sector: str

    # Actions proposées par le LLM
    actions: list[ActionItem]

    # Analyse textuelle du LLM (ce qu'il a compris du dataset)
    llm_analysis: str

    # Risques identifiés par le LLM
    # Ex: ["prime_annuelle=75000 peut être contrat VIP légitime"]
    risques: list[str] = field(default_factory=list)

    # Statut du plan dans son cycle de vie
    # "proposed"  → LLM a proposé, user n'a pas encore répondu
    # "validated" → User a répondu à toutes les actions
    # "executed"  → cleaning_node a exécuté le plan
    status: str = "proposed"

    @property
    def approved_actions(self) -> list[ActionItem]:
        """
        Filtre les actions approuvées ou modifiées par l'user.

        Exclut les actions rejetées.
        Une action sans décision user n'est PAS exécutée
        (sécurité : on ne fait rien sans validation explicite).
        """
        return [
            action for action in self.actions
            if action.user_decision in (
                UserDecision.APPROVED,
                UserDecision.MODIFIED,
            )
        ]

    @property
    def is_fully_validated(self) -> bool:
        """
        Vérifie que l'user a répondu à TOUTES les actions.

        cleaning_node ne peut pas démarrer si ce n'est pas le cas.
        → Empêche d'exécuter un plan partiellement validé.
        """
        return all(
            action.user_decision is not None
            for action in self.actions
        )

    def to_dict(self) -> dict:
        """
        Sérialise le plan pour l'API et l'interface web.
        """
        return {
            "plan_id":      self.plan_id,
            "sector":       self.sector,
            "status":       self.status,
            "llm_analysis": self.llm_analysis,
            "risques":      self.risques,
            "actions": [
                {
                    "action_id":          a.action_id,
                    "colonne":            a.colonne,
                    "lignes_concernees":  a.lignes_concernees,
                    "dimension":          a.dimension,
                    "probleme":           a.probleme,
                    "action":             a.action.value,
                    "justification":      a.justification,
                    "severite":           a.severite,
                    "parametre":          a.parametre,
                    "user_decision":      a.user_decision.value
                                          if a.user_decision else None,
                }
                for a in self.actions
            ],
        }