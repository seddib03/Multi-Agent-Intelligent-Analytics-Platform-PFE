# core/dbt_runner.py

# Standard library
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

# Third-party
import polars as pl


logger = logging.getLogger(__name__)


# ─── Constantes ──────────────────────────────────────────────────────────────

DBT_PROJECT_PATH = os.getenv("DBT_PROJECT_PATH", "DataQuality")
SILVER_PATH      = os.getenv("SILVER_PATH", "storage/silver")


# ─── Fonction publique principale ────────────────────────────────────────────


def save_clean_dataset(
    clean_df: pl.DataFrame,
    sector: str,
) -> str:
    """Sauvegarde le DataFrame nettoyé en Parquet dans le Silver layer.

    Cette fonction DOIT être appelée AVANT generate_dbt_artifacts()
    car dbt lit ce fichier Parquet comme source.

    Args:
        clean_df: DataFrame Polars nettoyé.
        sector:   Secteur pour organiser le stockage.

    Returns:
        Chemin absolu du fichier Parquet sauvegardé.
    """
    sector_dir = os.path.join(SILVER_PATH, sector)
    os.makedirs(sector_dir, exist_ok=True)

    silver_path = os.path.abspath(
        os.path.join(sector_dir, "clean_dataset.parquet")
    )

    clean_df.write_parquet(silver_path)

    logger.info(
        "Dataset nettoyé sauvegardé Silver : %s (%d lignes)",
        silver_path,
        clean_df.height,
    )

    return silver_path


def run_dbt_tests(model_name: str) -> list[dict]:
    """Exécute dbt run puis dbt test et retourne les résultats.

    Ordre d'exécution :
        1. dbt run   → crée le staging model dans DuckDB
        2. dbt test  → exécute tous les tests du schema.yml
        3. parse     → lit run_results.json et retourne les résultats

    Args:
        model_name: Nom du model dbt à exécuter et tester.

    Returns:
        Liste des résultats de tests avec status pass/fail.

    Raises:
        RuntimeError: Si dbt run échoue (model non créé).
    """
    # Étape 1 : dbt run — créer le staging model
    _run_dbt_command(["dbt", "run", "--select", model_name])

    # Étape 2 : dbt test — lancer les tests
    # On ne bloque pas sur le returncode car dbt retourne
    # un code non-zéro quand des tests échouent (c'est normal)
    _run_dbt_command(
        ["dbt", "test", "--select", model_name],
        fail_on_error=False,
    )

    # Étape 3 : parser les résultats
    test_results = _parse_dbt_results()

    logger.info(
        "dbt terminé — %d tests | %d passés | %d échoués",
        len(test_results),
        sum(1 for t in test_results if t["status"] == "pass"),
        sum(1 for t in test_results if t["status"] == "fail"),
    )

    return test_results


# ─── Fonctions privées ───────────────────────────────────────────────────────


def _run_dbt_command(
    command: list[str],
    fail_on_error: bool = True,
) -> subprocess.CompletedProcess:
    """Exécute une commande dbt dans le répertoire du projet dbt.

    Args:
        command:       Arguments de la commande dbt.
        fail_on_error: Si True, lève RuntimeError si returncode != 0.

    Returns:
        Résultat du subprocess.

    Raises:
        RuntimeError: Si fail_on_error=True et returncode != 0.
    """
    logger.info("Exécution : %s", " ".join(command))

    result = subprocess.run(
        command,
        cwd=os.path.abspath(DBT_PROJECT_PATH),
        capture_output=True,
        text=True,
    )

    # Toujours logger la sortie dbt pour le débogage
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                logger.info("dbt | %s", line)

    if result.returncode != 0:
        if fail_on_error:
            raise RuntimeError(
                f"dbt échoué (code {result.returncode}) : "
                f"{result.stdout[-300:]}"
            )
        else:
            logger.warning(
                "dbt retourne code %d (tests échoués attendus)",
                result.returncode,
            )

    return result


def _parse_dbt_results() -> list[dict]:
    """Parse le fichier run_results.json généré par dbt test.

    dbt génère ce fichier dans DataQuality/target/
    après chaque exécution.

    Returns:
        Liste des résultats par test avec :
            test_name, column, status, failures, message
    """
    results_path = (
        Path(DBT_PROJECT_PATH) / "target" / "run_results.json"
    )

    if not results_path.exists():
        raise FileNotFoundError(
            f"run_results.json introuvable : {results_path}. "
            f"Vérifier que dbt test s'est bien exécuté."
        )

    with open(results_path, encoding="utf-8") as results_file:
        raw = json.load(results_file)

    test_results = []

    for result in raw.get("results", []):
        unique_id = result.get("unique_id", "")

        # Ignorer les résultats de dbt run (models)
        # On veut seulement les résultats de dbt test
        if not unique_id.startswith("test."):
            continue

        test_name = _extract_test_name(unique_id)
        column    = _extract_column_name(unique_id)

        # dbt retourne "pass", "fail", "warn", "error"
        raw_status = result.get("status", "unknown")
        status     = "pass" if raw_status == "pass" else "fail"

        test_results.append({
            "test_name": test_name,
            "column":    column,
            "status":    status,
            "failures":  result.get("failures") or 0,
            "message":   result.get("message") or "",
        })

    return test_results


def _extract_test_name(unique_id: str) -> str:
    """Extrait le nom du test depuis l'unique_id dbt.

    Format unique_id dbt :
        test.data_quality.not_null_stg_retail_revenue.abc123

    Args:
        unique_id: Identifiant unique dbt du test.

    Returns:
        Nom du test (ex: "not_null", "unique", "accepted_range").
    """
    # La 3ème partie : "not_null_stg_retail_revenue"
    parts = unique_id.split(".")
    if len(parts) < 3:
        return "unknown"

    test_part = parts[2]

    # Mapper les préfixes connus vers les noms de tests
    known_tests = [
        "not_null",
        "unique",
        "accepted_range",
        "regex_match",
        "date_not_in_future",
    ]

    for test_name in known_tests:
        if test_part.startswith(test_name):
            return test_name

    return test_part.split("_")[0]


def _extract_column_name(unique_id: str) -> str:
    """Extrait le nom de la colonne depuis l'unique_id dbt.

    Exemples d'unique_id dbt :
        test.data_quality.not_null_stg_retail_dataset_revenue.hash
        test.data_quality.accepted_range_stg_retail_dataset_revenue__1000000__0.hash
        test.data_quality.regex_match_stg_retail_dataset_store_id___STR_0_9_4_.hash

    Stratégie :
        1. Supprimer le préfixe du test connu
        2. Supprimer le nom du model (stg_retail_dataset)
        3. Ce qui reste = nom de la colonne

    Args:
        unique_id: Identifiant unique dbt.

    Returns:
        Nom de la colonne concernée.
    """
    parts = unique_id.split(".")
    if len(parts) < 3:
        return "unknown"

    # Partie centrale : "not_null_stg_retail_dataset_revenue"
    test_part = parts[2]

    # Préfixes de tests connus à supprimer
    known_prefixes = [
        "not_null_",
        "unique_",
        "accepted_range_",
        "regex_match_",
        "date_not_in_future_",
    ]

    # Supprimer le préfixe du test
    remainder = test_part
    for prefix in known_prefixes:
        if test_part.startswith(prefix):
            remainder = test_part[len(prefix):]
            break

    # Supprimer le nom du model "stg_{sector}_dataset_"
    # Le model commence toujours par "stg_"
    model_prefix_idx = remainder.find("stg_")
    if model_prefix_idx != -1:
        after_stg = remainder[model_prefix_idx:]
        # Trouver la fin du nom du model
        # Format : stg_retail_dataset_revenue → colonne = revenue
        # On cherche le 3ème underscore après "stg"
        parts_after_stg = after_stg.split("_")
        # stg(0) + sector(1) + dataset(2) + colonne(3...)
        if len(parts_after_stg) > 3:
            # Reconstruire le nom de colonne
            # S'arrêter avant les paramètres (__)
            col_parts = []
            for part in parts_after_stg[3:]:
                # Les paramètres dbt commencent par "--" dans l'id
                if part == "" or part.startswith("-"):
                    break
                col_parts.append(part)
            if col_parts:
                return "_".join(col_parts)

    return remainder