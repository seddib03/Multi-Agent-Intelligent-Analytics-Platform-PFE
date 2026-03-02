# core/dbt_generator.py

# Standard library
from __future__ import annotations

import logging
import os
from pathlib import Path

# Third-party
import yaml

# Local
from models.metadata_schema import ColumnType, DatasetMetadata


logger = logging.getLogger(__name__)


# ─── Constantes ──────────────────────────────────────────────────────────────

# Chemin du projet dbt
DBT_PROJECT_PATH = os.getenv("DBT_PROJECT_PATH", "DataQuality")

# Dossier où on génère les models staging
DBT_STAGING_PATH = os.path.join(DBT_PROJECT_PATH, "models", "staging")

# Seuils de pondération pour le quality score
# Certains tests sont plus critiques que d'autres
TEST_WEIGHTS = {
    "not_null":          3,  # critique — donnée manquante
    "unique":            3,  # critique — doublon
    "accepted_range":    2,  # important — valeur hors plage
    "regex_match":       2,  # important — format invalide
    "date_not_in_future":1,  # mineur — date future
}


# ─── Fonction publique principale ────────────────────────────────────────────


def generate_dbt_artifacts(
    metadata: DatasetMetadata,
    cleaned_data_path: str,
) -> dict:
    """Génère tous les fichiers dbt nécessaires à la validation qualité.

    Génère 2 fichiers dans DataQuality/models/staging/ :
        1. stg_{sector}.sql    : staging model SQL
        2. schema.yml          : tests dbt par colonne

    Args:
        metadata:          DatasetMetadata validé par Pydantic.
        cleaned_data_path: Chemin vers le fichier Parquet nettoyé.
                           Utilisé comme source dans le staging model.

    Returns:
        Dictionnaire avec les chemins des fichiers générés et
        la liste des tests qui seront exécutés.
    """
    # Créer le dossier staging s'il n'existe pas
    os.makedirs(DBT_STAGING_PATH, exist_ok=True)

    sector       = metadata.sector
    model_name   = f"stg_{sector}_dataset"

    # Générer les 2 fichiers
    sql_path  = _generate_staging_model(
        metadata, model_name, cleaned_data_path
    )
    yaml_path = _generate_schema_yml(metadata, model_name)

    # Construire la liste des tests générés pour le rapport
    tests_generated = _list_generated_tests(metadata)

    logger.info(
        "Artifacts dbt générés — model : %s | tests : %d",
        model_name,
        len(tests_generated),
    )

    return {
        "model_name":      model_name,
        "sql_path":        sql_path,
        "yaml_path":       yaml_path,
        "tests_generated": tests_generated,
    }


# ─── Générateurs privés ──────────────────────────────────────────────────────




def _generate_staging_model(
    metadata: DatasetMetadata,
    model_name: str,
    source_path: str,
) -> str:
    """Génère le fichier SQL du staging model.

    Le chemin source_path doit être ABSOLU pour que DuckDB
    le retrouve correctement depuis le répertoire dbt.

    Args:
        metadata:    DatasetMetadata avec les types de colonnes.
        model_name:  Nom du model dbt.
        source_path: Chemin ABSOLU vers le Parquet nettoyé.

    Returns:
        Chemin du fichier SQL généré.
    """
    # S'assurer que le chemin est absolu
    # DuckDB dans dbt résout les chemins depuis DataQuality/
    # Un chemin absolu évite toute ambiguïté
    absolute_source = os.path.abspath(source_path)

    select_clauses = []
    for col in metadata.columns:
        sql_cast = _get_sql_cast(col.name, col.type)
        select_clauses.append(f"    {sql_cast}")

    select_block = ",\n".join(select_clauses)

    # Échapper les backslash Windows dans le chemin
    # DuckDB sur Windows accepte les / mais pas les \ dans SQL
    safe_path = absolute_source.replace("\\", "/")

    sql_content = f"""-- Auto-généré par dbt_generator.py
-- Secteur  : {metadata.sector}
-- Version  : {metadata.version}
-- Ne pas modifier manuellement

WITH source AS (
    SELECT *
    FROM read_parquet('{safe_path}')
),

staged AS (
    SELECT
{select_block}
    FROM source
)

SELECT * FROM staged
"""

    sql_path = os.path.join(DBT_STAGING_PATH, f"{model_name}.sql")

    with open(sql_path, "w", encoding="utf-8") as sql_file:
        sql_file.write(sql_content)

    logger.info("Staging model généré : %s", sql_path)
    logger.info("Source Parquet : %s", safe_path)

    return sql_path

def _generate_schema_yml(
    metadata: DatasetMetadata,
    model_name: str,
) -> str:
    """Génère le fichier schema.yml avec les tests dbt par colonne.

    Pour chaque colonne du metadata, génère les tests
    appropriés selon ses règles :
        - not_null    si nullable == False
        - unique      si role == identifier
        - accepted_range si range défini
        - regex_match    si pattern défini
        - date_not_in_future si type == date

    Args:
        metadata:   DatasetMetadata avec les règles par colonne.
        model_name: Nom du model dbt à tester.

    Returns:
        Chemin du fichier schema.yml généré.
    """
    columns_config = []

    for col in metadata.columns:
        col_tests = _build_column_tests(col)

        col_config = {
            "name":        col.name,
            "description": (
                f"Colonne {col.role.value} — type {col.type.value}"
            ),
        }

        if col_tests:
            col_config["tests"] = col_tests

        columns_config.append(col_config)

    # Structure complète du schema.yml
    schema_content = {
        "version": 2,
        "models": [
            {
                "name":        model_name,
                "description": (
                    f"Staging model pour le secteur {metadata.sector}. "
                    f"Auto-généré par le Data Preparation Agent."
                ),
                "columns": columns_config,
            }
        ],
    }

    yaml_path = os.path.join(DBT_STAGING_PATH, "schema.yml")

    with open(yaml_path, "w", encoding="utf-8") as yaml_file:
        yaml.dump(
            schema_content,
            yaml_file,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    logger.info("Schema.yml généré : %s", yaml_path)
    return yaml_path


def _build_column_tests(col) -> list:
    """Construit la liste des tests dbt pour une colonne.

    Applique les règles suivantes :
        not_null      → si col.nullable == False
        unique        → si col.role == identifier
        accepted_range → si col.range défini
        regex_match   → si col.pattern défini
        date_not_in_future → si col.type == date

    Args:
        col: ColumnMetadata avec les règles de la colonne.

    Returns:
        Liste des tests dbt pour cette colonne.
        Liste vide si aucun test applicable.
    """
    tests = []

    # Test not_null → colonne obligatoire
    if not col.nullable:
        tests.append("not_null")

    # Test unique → colonne identifiant
    if col.role.value == "identifier":
        tests.append("unique")

    # Test accepted_range → plage de valeurs
    if col.range is not None:
        tests.append({
            "accepted_range": {
                "min_value": col.range["min"],
                "max_value": col.range["max"],
            }
        })

    # Test regex_match → format attendu
    if col.pattern is not None:
        tests.append({
            "regex_match": {
                "pattern": col.pattern,
            }
        })

    # Test date_not_in_future → cohérence temporelle
    if col.type == ColumnType.DATE:
        tests.append("date_not_in_future")

    return tests


def _get_sql_cast(col_name: str, col_type: ColumnType) -> str:
    """Retourne la clause SQL de cast pour une colonne.

    Mappe les types du metadata vers les types SQL DuckDB.

    Args:
        col_name: Nom de la colonne.
        col_type: Type défini dans le metadata.

    Returns:
        Clause SQL de cast (ex: "CAST(revenue AS DOUBLE) AS revenue").
    """
    type_mapping = {
        ColumnType.STRING:  f"CAST({col_name} AS VARCHAR)  AS {col_name}",
        ColumnType.FLOAT:   f"CAST({col_name} AS DOUBLE)   AS {col_name}",
        ColumnType.INT:     f"CAST({col_name} AS INTEGER)  AS {col_name}",
        ColumnType.DATE:    f"CAST({col_name} AS DATE)     AS {col_name}",
        ColumnType.BOOLEAN: f"CAST({col_name} AS BOOLEAN)  AS {col_name}",
    }
    return type_mapping.get(col_type, f"{col_name}")


def _list_generated_tests(metadata: DatasetMetadata) -> list[dict]:
    """Liste tous les tests qui seront générés.

    Utilisé pour construire le rapport de qualité
    avant même d'exécuter dbt.

    Args:
        metadata: DatasetMetadata.

    Returns:
        Liste de dicts décrivant chaque test généré.
    """
    tests = []

    for col in metadata.columns:
        col_tests = _build_column_tests(col)

        for test in col_tests:
            test_name = test if isinstance(test, str) else list(test.keys())[0]
            tests.append({
                "column":  col.name,
                "test":    test_name,
                "weight":  TEST_WEIGHTS.get(test_name, 1),
            })

    return tests
