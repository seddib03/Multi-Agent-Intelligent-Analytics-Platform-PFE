"""
Moteur de calcul des qualites dbt + DuckDB.
"""
from __future__ import annotations
import glob
import json
import logging
import os
import subprocess
import yaml
import duckdb
from pathlib import Path

from config.settings import get_settings
from models.metadata_schema import ColumnMeta
from models.quality_report import ColumnQualityScore, QualityReport

logger = logging.getLogger(__name__)

DATE_FORMAT_MAP = {
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD-MM-YYYY": "%d-%m-%Y",
    "MM-DD-YYYY": "%m-%d-%Y",
    "YYYY/MM/DD": "%Y/%m/%d",
}

def _normalize_date_format_for_duckdb(format_str: str) -> str:
    if not format_str:
        return "%Y-%m-%d"
    if format_str in DATE_FORMAT_MAP:
        return DATE_FORMAT_MAP[format_str]
    return format_str

def generate_dbt_schema(metadata: list[ColumnMeta], out_path: str):
    """
    Génère dynamiquement dbt_project/models/_sources.yml avec tous les tests.
    """
    columns_yaml = []
    
    for meta in metadata:
        tests = []
        
        if not meta.nullable:
            tests.append("not_null")
        if meta.identifier:
            tests.append("unique")
        # Macros custom : paramètres passés DIRECTEMENT (pas sous "arguments")
        # "arguments:" est réservé aux tests natifs dbt.
        # Le warning MissingArgumentsPropertyInGenericTestDeprecation
        # ne concerne pas les macros custom → on l'ignore.
        if meta.type in ("int", "float"):
            dk_type = "integer" if meta.type == "int" else "double"
            tests.append({"is_type": {"type_str": dk_type}})
        elif meta.type == "date":
            fmt = _normalize_date_format_for_duckdb(meta.format)
            tests.append({"date_format": {"format_str": fmt}})
        if meta.type in ("int", "float") and meta.has_range:
            tests.append({
                "in_range": {
                    "min_value": meta.min if meta.min is not None else "None",
                    "max_value": meta.max if meta.max is not None else "None",
                }
            })
        if meta.type == "string" and meta.has_enum:
            tests.append({"accepted_values": {"values": meta.enum}})
        if meta.type == "string" and meta.has_pattern:
            tests.append({"regex_pattern": {"pattern": meta.pattern}})
            
        if len(tests) > 0:
            columns_yaml.append({
                "name": meta.column_name,
                "tests": tests
            })
            
    schema_yaml = {
        "version": 2,
        "sources": [
            {
                "name": "staging",
                "schema": "main",
                "tables": [
                    {
                        "name": "raw_data",
                        "columns": columns_yaml
                    }
                ]
            }
        ]
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(schema_yaml, f, sort_keys=False)

def compute_quality_report(
    metadata: list[ColumnMeta],
    label:    str,
    sector:   str,
    job_id:   str,
    duckdb_path: str,
) -> QualityReport:

    settings = get_settings()
    dbt_dir = settings.dbt_project_dir
    models_dir = dbt_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # ── FIX BUG 1 : supprimer TOUS les anciens _sources_*.yml avant d'en créer un ──
    # Sans ce nettoyage, dbt trouve plusieurs fois la même source "staging.raw_data"
    # et lève "Compilation Error: dbt found two sources with the name staging_raw_data"
    for stale in glob.glob(str(models_dir / "_sources_*.yml")):
        Path(stale).unlink(missing_ok=True)
        logger.debug("Ancien schema supprimé : %s", stale)

    # Toujours utiliser le même nom de fichier fixe pour éviter toute accumulation
    schema_path = str(models_dir / "_sources_current.yml")
    generate_dbt_schema(metadata, schema_path)
    
    # Environnement — injecter le chemin DuckDB pour profiles.yml
    env = os.environ.copy()
    env["DBT_DUCKDB_PATH"] = duckdb_path
    
    # dbt test --store-failures
    logger.info("Lancement de dbt test pour le job %s...", job_id)
    cmd = [
        "dbt", "test",
        "--store-failures",
        "--project-dir",  str(dbt_dir),
        "--profiles-dir", str(dbt_dir),
        "--select", "source:staging.raw_data",
    ]
    subprocess.run(cmd, env=env, capture_output=True, text=True)

    # Récupérer le nombre total de lignes
    with duckdb.connect(duckdb_path) as conn:
        total_rows = int(conn.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0])
        
    report = QualityReport(label=label, sector=sector, job_id=job_id, total_rows=total_rows)
    
    run_results_path = dbt_dir / "target" / "run_results.json"
    manifest_path    = dbt_dir / "target" / "manifest.json"
    
    if not (run_results_path.exists() and manifest_path.exists()):
        logger.warning("run_results.json ou manifest.json absent — QualityReport vide retourné")
        Path(schema_path).unlink(missing_ok=True)
        return report

    with open(run_results_path) as f:
        run_results = json.load(f)
    with open(manifest_path) as f:
        manifest = json.load(f)
        
    test_results = run_results.get("results", [])
    
    # ── FIX BUG 2 : lire les failure tables depuis le BON fichier DuckDB ───────────
    #
    # PROBLÈME ORIGINAL :
    #   dbt-duckdb crée les failure tables dans le fichier DuckDB configuré dans
    #   profiles.yml (DBT_DUCKDB_PATH = ton duckdb_path).
    #   Mais le relation_name dans manifest.json est formaté :
    #       "db"."main_dbt_test__audit"."nom_table"
    #   Or DuckDB ne comprend pas le préfixe "db" → "Table does not exist"
    #
    # FIX :
    #   On se connecte directement à duckdb_path et on interroge le schéma
    #   dbt_test__audit (sans le préfixe "db") via information_schema.
    #   On liste les tables disponibles une fois, puis on fait le matching
    #   par nom de table uniquement (la partie finale du relation_name).

    # Lister toutes les failure tables disponibles dans duckdb_path
    available_failure_tables: dict[str, str] = {}  # nom_table_lower → schema.table
    try:
        with duckdb.connect(duckdb_path, read_only=True) as conn:
            rows = conn.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema LIKE '%audit%'
                   OR table_schema LIKE '%test%'
            """).fetchall()
            for schema_name, table_name in rows:
                available_failure_tables[table_name.lower()] = f'"{schema_name}"."{table_name}"'
        logger.debug(
            "%d failure table(s) trouvée(s) dans DuckDB : %s",
            len(available_failure_tables),
            list(available_failure_tables.keys())[:5],
        )
    except Exception as e:
        logger.warning("Impossible de lister les failure tables : %s", e)

    col_failures: dict[str, dict] = {}

    for test in test_results:
        node_id = test.get("unique_id", "")
        node    = manifest.get("nodes", {}).get(node_id, {})
        col_name = node.get("column_name")
        if not col_name:
            continue
        
        test_type      = node.get("test_metadata", {}).get("name")
        failures_count = test.get("failures") or 0

        failed_rows    = []
        sample_invalid = []

        if failures_count > 0:
            relation_name = node.get("relation_name", "")

            # Extraire uniquement le nom de la table (dernière partie du relation_name)
            # "db"."main_dbt_test__audit"."source_not_null_..." → "source_not_null_..."
            raw_table_name = relation_name.replace('"', '').split('.')[-1]

            # Chercher dans les tables disponibles par correspondance exacte
            qualified_name = available_failure_tables.get(raw_table_name.lower())

            if qualified_name:
                try:
                    with duckdb.connect(duckdb_path, read_only=True) as conn:
                        logger.info("Lecture des échecs depuis %s", qualified_name)
                        res = conn.execute(
                            f'SELECT __row_id, "{col_name}" FROM {qualified_name} LIMIT 2000'
                        ).fetchall()
                        failed_rows    = [int(r[0]) for r in res]
                        sample_invalid = [r[1] for r in res[:5] if r[1] is not None]
                except Exception as e:
                    logger.error(
                        "Impossible de lire %s : %s", qualified_name, e
                    )
            else:
                logger.warning(
                    "Failure table '%s' introuvable dans DuckDB. "
                    "Tables disponibles : %s",
                    raw_table_name,
                    list(available_failure_tables.keys())[:10],
                )

        # Initialiser le dict de la colonne si besoin
        if col_name not in col_failures:
            col_failures[col_name] = {
                "not_null":     {"count": 0, "rows": []},
                "unique":       {"count": 0, "rows": [], "samples": []},
                "type_errors":  {"count": 0, "rows": [], "samples": []},
                "range_errors": {"count": 0, "rows": [], "samples": []},
                "enum_errors":  {"count": 0, "rows": [], "samples": []},
                "pattern_errors": {"count": 0, "rows": [], "samples": []},
                "date_errors":  {"count": 0, "rows": [], "samples": []},
            }

        # Dispatcher par type de test
        if test_type == "not_null":
            col_failures[col_name]["not_null"]["count"] += failures_count
            col_failures[col_name]["not_null"]["rows"].extend(failed_rows)
        elif test_type == "unique":
            col_failures[col_name]["unique"]["count"] += failures_count
            col_failures[col_name]["unique"]["rows"].extend(failed_rows)
            col_failures[col_name]["unique"]["samples"].extend(sample_invalid)
        else:
            key_map = {
                "in_range":        "range_errors",
                "accepted_values": "enum_errors",
                "regex_pattern":   "pattern_errors",
                "date_format":     "date_errors",
                "is_type":         "type_errors",
            }
            target_key = key_map.get(test_type, "type_errors")
            col_failures[col_name][target_key]["count"] += failures_count
            col_failures[col_name][target_key]["rows"].extend(failed_rows)
            col_failures[col_name][target_key]["samples"].extend(sample_invalid)

    # Construire les ColumnQualityScore
    _empty_failures = {
        "not_null":       {"count": 0, "rows": []},
        "unique":         {"count": 0, "rows": [], "samples": []},
        "type_errors":    {"count": 0, "rows": [], "samples": []},
        "range_errors":   {"count": 0, "rows": [], "samples": []},
        "enum_errors":    {"count": 0, "rows": [], "samples": []},
        "pattern_errors": {"count": 0, "rows": [], "samples": []},
        "date_errors":    {"count": 0, "rows": [], "samples": []},
    }

    for col_meta in metadata:
        col_name = col_meta.column_name
        f        = col_failures.get(col_name, _empty_failures)
        score    = ColumnQualityScore(column_name=col_name, business_name=col_meta.business_name)

        if not col_meta.nullable:
            null_c = f["not_null"]["count"]
            score.completeness = float(round((total_rows - null_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
            score.completeness_detail = {
                "null_count": int(null_c),
                "total":      int(total_rows),
                "null_rows":  f["not_null"]["rows"][:500],
            }

        if col_meta.identifier:
            uniq_c = f["unique"]["count"]
            score.uniqueness = float(round((total_rows - uniq_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
            score.uniqueness_detail = {
                "duplicate_count":  int(uniq_c),
                "total_non_null":   int(total_rows - f["not_null"]["count"]),
                "duplicate_rows":   f["unique"]["rows"][:500],
                "duplicate_values": f["unique"]["samples"],
            }

        has_validity = (
            col_meta.type in ("int", "float", "date")
            or col_meta.has_enum
            or col_meta.has_pattern
            or col_meta.has_range
        )
        if has_validity:
            val_c = sum(
                f[k]["count"]
                for k in ["type_errors", "range_errors", "enum_errors", "pattern_errors", "date_errors"]
            )
            score.validity = float(round((total_rows - val_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
            
            validity_detail = {"invalid_count": int(val_c)}
            for k in ["type_errors", "range_errors", "enum_errors", "pattern_errors", "date_errors"]:
                if f[k]["count"] > 0:
                    validity_detail[k]              = f[k]["rows"][:500]
                    validity_detail[k + "_samples"] = f[k]["samples"][:5]
            score.validity_detail = validity_detail

        report.columns.append(score)

    # Nettoyage du fichier schema temporaire
    Path(schema_path).unlink(missing_ok=True)
    return report