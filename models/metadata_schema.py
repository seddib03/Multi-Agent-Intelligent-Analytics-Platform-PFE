# models/metadata_schema.py

# Standard library
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

# Third-party
from pydantic import BaseModel, field_validator, model_validator


# ─── Énumérations ────────────────────────────────────────────────────────────


class ColumnRole(str, Enum):
    """Rôles possibles pour une colonne dans le dataset.

    Le rôle est le champ le plus important — il détermine
    quelle stratégie de nettoyage sera appliquée dans
    le cleaning_node.

    Values:
        METRIC:     Colonne numérique mesurable.
                    Stratégie : imputation médiane, détection outliers.
                    Exemples  : revenue, quantity, premium.
        DIMENSION:  Colonne catégorielle de regroupement.
                    Stratégie : imputation mode, trim, uppercase.
                    Exemples  : store_id, gender, category.
        IDENTIFIER: Colonne identifiant unique une ligne.
                    Stratégie : détection doublons, drop si null.
                    Exemples  : transaction_id, contract_id.
        TEMPORAL:   Colonne date ou datetime.
                    Stratégie : parsing date, cohérence temporelle.
                    Exemples  : sale_date, created_at, date_effet.
    """

    METRIC     = "metric"
    DIMENSION  = "dimension"
    IDENTIFIER = "identifier"
    TEMPORAL   = "temporal_key"


class ColumnType(str, Enum):
    """Types de données possibles pour une colonne.

    Values:
        STRING:  Texte, catégories, codes identifiants.
        FLOAT:   Nombre décimal (prix, taux, pourcentage).
        INT:     Nombre entier (quantité, âge, nombre de jours).
        DATE:    Date ou datetime (avec date_format optionnel).
        BOOLEAN: Valeur booléenne (actif/inactif, oui/non).
    """

    STRING  = "string"
    FLOAT   = "float"
    INT     = "int"
    DATE    = "date"
    BOOLEAN = "boolean"


# ─── Modèle d'une colonne ────────────────────────────────────────────────────


class ColumnMetadata(BaseModel):
    """Contrat d'une colonne avec schema hybride.

    Attributes:
        name:          Nom exact de la colonne dans le dataset.
        type:          Type de données attendu.
        role:          Rôle déterminant la stratégie de nettoyage.
        nullable:      True si la colonne accepte des valeurs nulles.
        range:         Plage valide pour colonnes numériques.
                       Format : {"min": 0, "max": 1000000}
        pattern:       Regex pour valider les strings.
                       Exemple : "^STR-[0-9]{4}$"
        date_format:   Format strftime si type == DATE.
                       Exemple : "%Y-%m-%d"
        business_rule: Règle métier en langage naturel.
                       Exemple : "date_debut < date_fin"
        extensions:    Champs libres spécifiques au secteur.
                       Exemple : {"unit": "USD"}
    """

    # Ces 4 champs sont TOUJOURS requis peu importe le secteur
    name:     str
    type:     ColumnType
    role:     ColumnRole
    nullable: bool = True

    # Optionnels mais validés par Pydantic si présents
    range:          Optional[dict] = None
    pattern:        Optional[str]  = None
    date_format:    Optional[str]  = None
    business_rule:  Optional[str]  = None

    # Pour le moment — c'est un champ libre pour les besoins spécifiques
    extensions: dict[str, Any] = {}

    # ── Validators Couche 2 ───────────────────────────────────────────

    @field_validator("range")
    @classmethod
    def validate_range_structure(
        cls,
        range_value: Optional[dict],
    ) -> Optional[dict]:
        """Valide la structure du champ range si présent.

        Vérifie que :
            - min et max sont présents
            - min est strictement inférieur à max

        Args:
            range_value: Valeur du champ range.

        Returns:
            range_value inchangé si valide, None si absent.

        Raises:
            ValueError: Si structure invalide.
        """
        if range_value is None:
            return range_value

        if "min" not in range_value or "max" not in range_value:
            raise ValueError(
                "range doit contenir les clés 'min' et 'max'"
            )

        if range_value["min"] >= range_value["max"]:
            raise ValueError(
                f"range['min'] ({range_value['min']}) doit être "
                f"strictement inférieur à range['max'] ({range_value['max']})"
            )

        return range_value

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, name_value: str) -> str:
        """Valide que le nom de colonne est non vide et sans espaces.

        Un nom avec espaces causerait des problèmes dans les
        requêtes SQL dbt et les accès Polars.

        Args:
            name_value: Valeur du champ name.

        Returns:
            name_value en minuscules et strippé.

        Raises:
            ValueError: Si nom vide ou contient des espaces.
        """
        name_stripped = name_value.strip()

        if not name_stripped:
            raise ValueError("Le nom de colonne ne peut pas être vide")

        if " " in name_stripped:
            raise ValueError(
                f"Le nom de colonne '{name_stripped}' ne peut pas "
                f"contenir d'espaces. Utilisez _ à la place."
            )

        return name_stripped


# ─── Modèle principal ────────────────────────────────────────────────────────


class DatasetMetadata(BaseModel):
    """Contrat complet du dataset — schema hybride.

    Structure :
        Core fixe    : sector, version, columns
        Config libre : sector_config (spécifique au secteur)

    Le sector_config permet à chaque secteur d'ajouter
    des paramètres globaux sans modifier le schema.

    Attributes:
        sector:        Secteur métier du dataset.
                       Exemples : retail, finance, transport,
                       healthcare, manufacturing.
        version:       Version du metadata pour la traçabilité.
        columns:       Liste des colonnes avec leurs contrats.
        sector_config: Configuration libre spécifique au secteur.
                       Exemples : {"currency": "USD"} pour retail,
                       {"regulateur": "ACPR"} pour finance.

    Example:
        Retail :
        {
            "sector": "retail",
            "columns": [...],
            "sector_config": {"currency": "USD", "fiscal_year": "calendar"}
        }

    """

    # ── Core obligatoire ──────────────────────────────────────────────
    sector:  str
    version: str = "1.0"
    columns: list[ColumnMetadata]

    # ── Config libre par secteur ──────────────────────────────────────
    sector_config: dict[str, Any] = {}

    # ── Validators ────────────────────────────────────────────────────

    @field_validator("sector")
    @classmethod
    def validate_sector_format(cls, sector_value: str) -> str:
        """Valide et normalise le nom du secteur.

        Le secteur est utilisé pour organiser le stockage
        Bronze/Silver/Gold — il doit être propre.

        Args:
            sector_value: Valeur du champ sector.

        Returns:
            Secteur en minuscules et strippé.

        Raises:
            ValueError: Si secteur vide.
        """
        sector_stripped = sector_value.strip().lower()

        if not sector_stripped:
            raise ValueError("Le secteur ne peut pas être vide")

        return sector_stripped

    @model_validator(mode="after")
    def validate_global_rules(self) -> DatasetMetadata:
        """Valide les règles globales sur l'ensemble des colonnes.

        Règles vérifiées :
            1. Au moins une colonne identifier
            2. Aucun nom de colonne en double
            3. range défini uniquement sur float ou int

        Returns:
            self inchangé si toutes les règles passent.

        Raises:
            ValueError: Si une règle est violée.
        """
        roles = [col.role for col in self.columns]
        names = [col.name for col in self.columns]

        # Règle 1 : au moins un identifier
        if ColumnRole.IDENTIFIER not in roles:
            raise ValueError(
                "Le metadata doit contenir au moins une colonne "
                "avec role='identifier' pour identifier les doublons"
            )

        # Règle 2 : pas de doublons dans les noms de colonnes
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(
                f"Noms de colonnes en double détectés : {duplicates}"
            )

        # Règle 3 : range uniquement sur colonnes numériques
        for col in self.columns:
            if col.range is not None and col.type not in (
                ColumnType.FLOAT,
                ColumnType.INT,
            ):
                raise ValueError(
                    f"Colonne '{col.name}' : range ne peut être "
                    f"défini que sur float/int, pas sur {col.type.value}"
                )

        return self

    # ── Méthodes utilitaires ──────────────────────────────────────────

    def get_columns_by_role(
        self,
        role: ColumnRole,
    ) -> list[ColumnMetadata]:
        """Retourne toutes les colonnes ayant le rôle demandé.

        Utilisée par cleaning_node et quality_node pour
        récupérer dynamiquement les colonnes à traiter
        selon leur rôle.

        Args:
            role: Le rôle recherché.

        Returns:
            Liste des ColumnMetadata correspondant au rôle.
            Liste vide si aucune colonne n'a ce rôle.

        Example:
            >>> metrics = metadata.get_columns_by_role(ColumnRole.METRIC)
            >>> [col.name for col in metrics]
            ['revenue', 'quantity']
        """
        return [col for col in self.columns if col.role == role]

    def get_column_names(self) -> list[str]:
        """Retourne la liste de tous les noms de colonnes déclarés.

        Returns:
            Liste des noms de colonnes dans l'ordre de déclaration.
        """
        return [col.name for col in self.columns]

    def get_column_by_name(
        self,
        name: str,
    ) -> Optional[ColumnMetadata]:
        """Retourne la ColumnMetadata d'une colonne par son nom.

        Utilisée quand on a besoin des détails d'une colonne
        spécifique (range, pattern, extensions...).

        Args:
            name: Nom de la colonne recherchée.

        Returns:
            ColumnMetadata si trouvée, None sinon.
        """
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def get_required_columns(self) -> list[str]:
        """Retourne les colonnes obligatoires (nullable=False).

        Utilisée par quality_node pour les tests not_null dbt.

        Returns:
            Liste des noms de colonnes non nullable.
        """
        return [
            col.name
            for col in self.columns
            if not col.nullable
        ]

    def has_extensions(self) -> bool:
        """Vérifie si au moins une colonne a des extensions.

        Returns:
            True si au moins une colonne a des extensions.
        """
        return any(col.extensions for col in self.columns)
