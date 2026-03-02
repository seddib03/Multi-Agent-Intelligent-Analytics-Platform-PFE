# core/metadata_parser.py

# Standard library
from __future__ import annotations

import json
import logging
from pathlib import Path

# Local
from models.metadata_schema import ColumnRole, DatasetMetadata


logger = logging.getLogger(__name__)


# ─── Fonction publique principale ────────────────────────────────────────────


def parse_metadata(metadata_path: str) -> tuple[DatasetMetadata, dict]:
    """Lit, valide et transforme le fichier metadata en plan d'action.

    Étapes :
        1. Lire le fichier JSON
        2. Valider avec Pydantic (schema hybride)
        3. Construire le action_plan enrichi

    Args:
        metadata_path: Chemin vers le fichier metadata JSON.

    Returns:
        Tuple (DatasetMetadata validé, action_plan dict).

    Raises:
        FileNotFoundError: Si fichier introuvable.
        ValueError: Si JSON invalide ou schema non respecté.
    """
    logger.info("Parsing metadata : %s", metadata_path)

    raw_data = _read_json_file(metadata_path)

    try:
        metadata = DatasetMetadata.model_validate(raw_data)
    except Exception as error:
        raise ValueError(f"Metadata invalide : {error}") from error

    logger.info(
        "Metadata valide — secteur : %s | colonnes : %d | "
        "extensions présentes : %s",
        metadata.sector,
        len(metadata.columns),
        metadata.has_extensions(),
    )

    action_plan = _build_action_plan(metadata)

    return metadata, action_plan


def validate_schema_matching(
    dataset_columns: list[str],
    metadata: DatasetMetadata,
) -> dict:
    """Vérifie la cohérence entre colonnes du dataset et metadata.

    Deux types de problèmes :
        Bloquant : colonne déclarée dans metadata mais absente
                   du dataset → pipeline arrêté
        Warning  : colonne présente dans dataset mais non déclarée
                   dans metadata → loggué, pipeline continue

    Args:
        dataset_columns: Colonnes présentes dans le dataset chargé.
        metadata:        DatasetMetadata validé.

    Returns:
        {
            "is_valid":        bool,
            "missing_columns": list,  ← bloquant si non vide
            "extra_columns":   list   ← warning seulement
        }
    """
    expected = set(metadata.get_column_names())
    actual   = set(dataset_columns)

    missing_columns = sorted(expected - actual)
    extra_columns   = sorted(actual - expected)

    if missing_columns:
        logger.error(
            "Colonnes manquantes dans le dataset : %s", missing_columns
        )

    if extra_columns:
        logger.warning(
            "Colonnes non déclarées dans le metadata "
            "(ignorées par le pipeline) : %s",
            extra_columns,
        )

    return {
        "is_valid":        len(missing_columns) == 0,
        "missing_columns": missing_columns,
        "extra_columns":   extra_columns,
    }


# ─── Fonctions privées ───────────────────────────────────────────────────────


def _read_json_file(file_path: str) -> dict:
    """Lit un fichier JSON et retourne son contenu.

    Args:
        file_path: Chemin vers le fichier JSON.

    Returns:
        Contenu sous forme de dictionnaire.

    Raises:
        FileNotFoundError: Si fichier introuvable.
        ValueError: Si contenu JSON invalide.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier metadata introuvable : {file_path}"
        )

    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"JSON invalide dans {file_path} : {error}"
        ) from error


def _build_action_plan(metadata: DatasetMetadata) -> dict:
    """Construit le plan d'action enrichi depuis le metadata validé.

    Le plan d'action est calculé UNE SEULE FOIS à l'ingestion.
    Tous les nodes suivants le lisent directement sans
    re-parser le metadata.

    Contenu du plan d'action :
        Colonnes par rôle       → utilisées par cleaning_node
        Colonnes required       → utilisées par quality_node
        Extensions par colonne  → utilisées par agents en aval
        Sector config           → utilisée par aggregation_node

    Args:
        metadata: DatasetMetadata validé par Pydantic.

    Returns:
        Dictionnaire complet prêt à l'emploi pour les nodes.
    """
    # ── Colonnes par rôle ─────────────────────────────────────────────
    metric_cols     = metadata.get_columns_by_role(ColumnRole.METRIC)
    dimension_cols  = metadata.get_columns_by_role(ColumnRole.DIMENSION)
    identifier_cols = metadata.get_columns_by_role(ColumnRole.IDENTIFIER)
    temporal_cols   = metadata.get_columns_by_role(ColumnRole.TEMPORAL)

    # ── Extensions par colonne ────────────────────────────────────────
    # On ne collecte que les colonnes qui ont des extensions
    # pour ne pas alourdir le plan d'action inutilement
    extensions_map = {
        col.name: col.extensions
        for col in metadata.columns
        if col.extensions
    }

    # ── Colonnes avec règles spéciales ────────────────────────────────
    # Utilisées par quality_node pour générer les bons tests dbt
    columns_with_range = {
        col.name: col.range
        for col in metadata.columns
        if col.range is not None
    }

    columns_with_pattern = {
        col.name: col.pattern
        for col in metadata.columns
        if col.pattern is not None
    }

    columns_with_date_format = {
        col.name: col.date_format
        for col in metadata.columns
        if col.date_format is not None
    }

    columns_with_business_rule = {
        col.name: col.business_rule
        for col in metadata.columns
        if col.business_rule is not None
    }

    action_plan = {

        # ── Pour cleaning_node ────────────────────────────────────────
        "metric_columns":     [col.name for col in metric_cols],
        "dimension_columns":  [col.name for col in dimension_cols],
        "identifier_columns": [col.name for col in identifier_cols],
        "temporal_columns":   [col.name for col in temporal_cols],

        # ── Pour quality_node ─────────────────────────────────────────
        "required_columns":          metadata.get_required_columns(),
        "columns_with_range":        columns_with_range,
        "columns_with_pattern":      columns_with_pattern,
        "columns_with_date_format":  columns_with_date_format,
        "columns_with_business_rule": columns_with_business_rule,

        # ── Pour tous les nodes ───────────────────────────────────────
        "all_column_names": metadata.get_column_names(),
        "sector":           metadata.sector,

        # ── Extensions libres (agents en aval + LLM post-MVP) ─────────
        "extensions_map":  extensions_map,
        "sector_config":   metadata.sector_config,
    }

    logger.info(
        "Action plan — metrics : %s | dimensions : %s | "
        "identifiers : %s | temporels : %s | "
        "avec range : %s | avec pattern : %s",
        action_plan["metric_columns"],
        action_plan["dimension_columns"],
        action_plan["identifier_columns"],
        action_plan["temporal_columns"],
        list(columns_with_range.keys()),
        list(columns_with_pattern.keys()),
    )

    return action_plan