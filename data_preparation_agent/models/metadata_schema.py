from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Types reconnus dans le metadata
VALID_TYPES = {"int", "float", "string", "date", "bool"}


@dataclass
class ColumnMeta:
    """
    Metadata d'une colonne — correspond à une ligne du formulaire UI.

    Tous les champs optionnels sont None si non remplis dans le formulaire.
    Le quality_engine adapte ses règles selon ce qui est fourni.
    """

    # Nom exact de la colonne dans le dataset (obligatoire)
    column_name: str

    # Nom métier lisible (pour les rapports)
    business_name: str

    # Type de données attendu
    type: str  # "int", "float", "string", "date", "bool"

    # La colonne peut-elle contenir des nulls ?
    nullable: bool = True

    # Est-ce un identifiant unique ? (vérifié pour Uniqueness)
    identifier: bool = False

    # Pattern regex à respecter (pour les strings)
    pattern: Optional[str] = None

    # Valeur minimale (pour int/float)
    min: Optional[float] = None

    # Valeur maximale (pour int/float)
    max: Optional[float] = None

    # Format de date (ex: "MM/DD/YYYY", "%Y-%m-%d")
    format: Optional[str] = None

    # Liste de valeurs valides (pour les colonnes catégorielles)
    enum: Optional[list[str]] = None

    # Description métier (affichée dans le rapport)
    description: Optional[str] = None

    def __post_init__(self) -> None:
        """Validation basique après initialisation."""
        if self.type not in VALID_TYPES:
            raise ValueError(
                f"Type '{self.type}' non reconnu pour la colonne "
                f"'{self.column_name}'. Types valides : {VALID_TYPES}"
            )

    @property
    def has_range(self) -> bool:
        """True si min ou max est défini."""
        return self.min is not None or self.max is not None

    @property
    def has_enum(self) -> bool:
        """True si une liste de valeurs valides est définie."""
        return self.enum is not None and len(self.enum) > 0

    @property
    def has_pattern(self) -> bool:
        """True si un pattern regex est défini."""
        return self.pattern is not None and self.pattern.strip() != ""

    @property
    def has_date_format(self) -> bool:
        """True si un format de date est spécifié."""
        return self.format is not None and self.format.strip() != ""


def parse_metadata(raw: list[dict]) -> list[ColumnMeta]:
    """
    Convertit la liste JSON du formulaire en liste de ColumnMeta.

    Gère les champs manquants avec des valeurs par défaut.
    Loggue un warning si un champ obligatoire est absent.

    Args:
        raw: Liste de dicts depuis le JSON metadata

    Returns:
        Liste de ColumnMeta validés.

    Raises:
        ValueError: Si column_name ou type est absent.
    """
    import logging
    logger = logging.getLogger(__name__)

    result = []
    for i, col_dict in enumerate(raw):
        if "column_name" not in col_dict:
            raise ValueError(
                f"Colonne #{i} : champ 'column_name' obligatoire manquant"
            )
        if "type" not in col_dict:
            raise ValueError(
                f"Colonne '{col_dict['column_name']}' : champ 'type' obligatoire manquant"
            )

        # Normaliser le type en minuscules
        col_dict["type"] = str(col_dict["type"]).lower().strip()

        # Construire le ColumnMeta avec les champs disponibles
        meta = ColumnMeta(
            column_name=col_dict["column_name"],
            business_name=col_dict.get("business_name", col_dict["column_name"]),
            type=col_dict["type"],
            nullable=bool(col_dict.get("nullable", True)),
            identifier=bool(col_dict.get("identifier", False)),
            pattern=col_dict.get("pattern"),
            min=float(col_dict["min"]) if col_dict.get("min") is not None else None,
            max=float(col_dict["max"]) if col_dict.get("max") is not None else None,
            format=col_dict.get("format"),
            enum=col_dict.get("enum"),
            description=col_dict.get("description"),
        )
        result.append(meta)

    logger.info("Metadata parsé — %d colonnes", len(result))
    return result