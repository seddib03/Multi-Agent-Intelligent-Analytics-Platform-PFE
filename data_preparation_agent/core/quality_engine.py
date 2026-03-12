"""
Moteur de calcul des qualités dbt + DuckDB.

5 DIMENSIONS :
    Completeness → not_null
    Validity     → is_type, date_format, regex_pattern, accepted_values
    Uniqueness   → unique (colonne) + row_not_duplicate (table)
    Accuracy     → in_range
    Consistency  → business rules (via LLM)
"""
from __future__ import annotations
import glob
import json
import shutil
import logging
import os
import subprocess
import yaml
import duckdb
from pathlib import Path
from typing import Optional

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


def generate_dbt_schema(
    metadata: list[ColumnMeta],
    out_path: str,
    business_rule_tests: Optional[list] = None,
):
    """
    Génère dynamiquement dbt_project/models/_sources.yml avec tous les tests.
    
    Inclut :
    - Tests column-level classiques (not_null, unique, is_type, etc.)
    - Tests table-level (row_not_duplicate)
    - Tests business rules (column-level et table-level)
    """
    columns_yaml = []
    table_tests = []
    seen_table_tests = set()  # pour dédupliquer les tests table-level
    # ── Test de duplication de lignes (table-level, dim: uniqueness) ──
    table_tests.append("row_not_duplicate")
    seen_table_tests.add("row_not_duplicate")
    
    for meta in metadata:
        tests = []
        
        if not meta.nullable:
            tests.append("not_null")
        if meta.identifier:
            tests.append("unique")
        # Macros custom : paramètres passés DIRECTEMENT (pas sous "arguments")
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
    
    # ── Injecter les tests business rules ──
    if business_rule_tests:
        for br_test in business_rule_tests:
            if br_test.is_table_level:
                # Test table-level — dédupliquer par nom de macro
                test_key = br_test.macro_name or str(br_test.schema_entry)
                if test_key in seen_table_tests:
                    logger.warning(
                        "Test table-level dupliqué ignoré : '%s'", test_key
                    )
                    continue
                seen_table_tests.add(test_key)
                if isinstance(br_test.schema_entry, dict):
                    table_tests.append(br_test.schema_entry)
                elif isinstance(br_test.schema_entry, str):
                    table_tests.append(br_test.schema_entry)
            elif br_test.target_column:
                # Test column-level
                col_entry = None
                for col_yaml in columns_yaml:
                    if col_yaml["name"] == br_test.target_column:
                        col_entry = col_yaml
                        break
                
                if col_entry is None:
                    col_entry = {"name": br_test.target_column, "tests": []}
                    columns_yaml.append(col_entry)
                
                if isinstance(br_test.schema_entry, dict):
                    col_entry["tests"].append(br_test.schema_entry)
                elif isinstance(br_test.schema_entry, str):
                    col_entry["tests"].append(br_test.schema_entry)
    
    # Construire le YAML
    table_config = {
        "name": "raw_data",
        "columns": columns_yaml,
    }
    
    # Ajouter les tests table-level s'il y en a
    if table_tests:
        table_config["tests"] = table_tests
            
    schema_yaml = {
        "version": 2,
        "sources": [
            {
                "name": "staging",
                "schema": "main",
                "tables": [table_config]
            }
        ]
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(schema_yaml, f, sort_keys=False)
    
    logger.info("Schema dbt généré : %s", out_path)
    # logger.debug("Contenu du schema :\n%s", yaml.dump(schema_yaml, sort_keys=False))


def compute_quality_report(
    metadata: list[ColumnMeta],
    label:    str,
    sector:   str,
    job_id:   str,
    duckdb_path: str,
    business_rules: Optional[list[str]] = None,
    precomputed_br_tests: Optional[list] = None,
) -> tuple[QualityReport, list]:
    """
    Calcule le QualityReport via dbt test.

    Args:
        metadata:             Colonnes de la table
        label:                "AVANT" ou "APRES"
        sector:               Secteur metier
        job_id:               ID du job
        duckdb_path:          Chemin de la base DuckDB
        business_rules:       Regles metier (langage naturel) - declenche l'appel LLM
        precomputed_br_tests: BusinessRuleTest deja generes (ex: rescoring) - evite le LLM
    """

    settings = get_settings()
    dbt_dir = settings.dbt_project_dir
    models_dir = dbt_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # -- Nettoyage des anciens schemas --
    for stale in glob.glob(str(models_dir / "_sources_*.yml")):
        Path(stale).unlink(missing_ok=True)
        logger.debug("Ancien schema supprime : %s", stale)

    # -- Traiter les business rules via LLM (seulement si pas de tests pre-calcules) --
    business_rule_tests = []
    if precomputed_br_tests is not None:
        # Rescoring : reutiliser les BusinessRuleTest deja generes - pas de LLM
        from core.business_rules_engine import BusinessRuleTest
        for br_dict in precomputed_br_tests:
            try:
                business_rule_tests.append(BusinessRuleTest(
                    rule_text=br_dict.get("rule_text", ""),
                    dimension=br_dict.get("dimension", "validity"),
                    test_type=br_dict.get("test_type", "existing"),
                    macro_name=br_dict.get("macro_name", ""),
                    schema_entry=br_dict.get("schema_entry"),
                    target_column=br_dict.get("target_column"),
                    is_table_level=br_dict.get("is_table_level", False),
                    macro_sql=br_dict.get("macro_sql"),
                ))
            except Exception as e:
                logger.warning("Impossible de reconstruire BusinessRuleTest : %s", e)
        logger.info(
            "Rescoring : %d business rule tests reutilises (pas d'appel LLM)",
            len(business_rule_tests),
        )
    elif business_rules:
        try:
            from core.business_rules_engine import process_business_rules
            business_rule_tests = process_business_rules(
                business_rules=business_rules,
                metadata=metadata,
                macros_dir=str(dbt_dir / "macros"),
            )
            logger.info(
                "%d business rules traduites en tests dbt",
                len(business_rule_tests),
            )
        except Exception as e:
            logger.error("Erreur traitement business rules : %s", e)


    # ── Générer le schema dbt ──
    schema_path = str(models_dir / "_sources_current.yml")
    generate_dbt_schema(metadata, schema_path, business_rule_tests)
    
    # Environnement — injecter le chemin DuckDB pour profiles.yml
    env = os.environ.copy()
    env["DBT_DUCKDB_PATH"] = duckdb_path

    # ── Nettoyer le répertoire target pour éviter les caches stales ──
    # Le partial_parse.msgpack d'un run précédent (avec un autre DuckDB)
    # peut amener dbt-duckdb à réutiliser une connexion obsolète
    # et écrire les audit tables dans le mauvais fichier DuckDB.
    target_dir = dbt_dir / "target"
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
        logger.debug("Répertoire target nettoyé : %s", target_dir)
    
    # dbt test --store-failures --no-partial-parse
    logger.info("Lancement de dbt test pour le job %s...", job_id)
    cmd = [
        "dbt", "test",
        "--store-failures",
        "--no-partial-parse",
        "--project-dir",  str(dbt_dir),
        "--profiles-dir", str(dbt_dir),
        "--select", "source:staging.raw_data",
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("dbt test a retourné un code non-zéro (%d)", result.returncode)
    if result.stderr:
        logger.debug("dbt stderr:\n%s", result.stderr[-2000:])
    if result.stdout:
        logger.debug("dbt stdout:\n%s", result.stdout[-2000:])

    # Récupérer le nombre total de lignes
    with duckdb.connect(duckdb_path) as conn:
        total_rows = int(conn.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0])
        
    report = QualityReport(label=label, sector=sector, job_id=job_id, total_rows=total_rows)
    
    run_results_path = dbt_dir / "target" / "run_results.json"
    manifest_path    = dbt_dir / "target" / "manifest.json"
    
    if not (run_results_path.exists() and manifest_path.exists()):
        logger.warning("run_results.json ou manifest.json absent — QualityReport vide retourné")
        Path(schema_path).unlink(missing_ok=True)
        return report, business_rule_tests

    with open(run_results_path) as f:
        run_results = json.load(f)
    with open(manifest_path) as f:
        manifest = json.load(f)
        
    test_results = run_results.get("results", [])
    
    # ── Lire les failure tables depuis DuckDB ──
    available_failure_tables: dict[str, str] = {}
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

    # ── Construire un index des business rules par macro_name pour le dispatching ──
    br_dimension_map = {}
    for br_test in business_rule_tests:
        br_dimension_map[br_test.macro_name] = br_test.dimension

    col_failures: dict[str, dict] = {}
    table_level_failures: dict[str, dict] = {}  # pour les tests table-level

    for test in test_results:
        node_id = test.get("unique_id", "")
        node    = manifest.get("nodes", {}).get(node_id, {})
        col_name = node.get("column_name")
        
        test_type      = node.get("test_metadata", {}).get("name")
        failures_count = test.get("failures") or 0

        failed_rows    = []
        sample_invalid = []

        if failures_count > 0:
            relation_name = node.get("relation_name", "")
            raw_table_name = relation_name.replace('"', '').split('.')[-1]
            qualified_name = available_failure_tables.get(raw_table_name.lower())

            if qualified_name:
                try:
                    with duckdb.connect(duckdb_path, read_only=True) as conn:
                        logger.info("Lecture des échecs depuis %s", qualified_name)

                        # Introspection : quelles colonnes sont dans la failure table ?
                        avail_cols_raw = conn.execute(
                            f"SELECT column_name FROM information_schema.columns "
                            f"WHERE table_schema || '.' || table_name = "
                            f"replace(replace({qualified_name!r}, '\"', ''), '.', '.')"
                        ).fetchall()
                        # Fallback plus robuste : PRAGMA
                        if not avail_cols_raw:
                            avail_cols_raw = conn.execute(
                                f"PRAGMA table_info({qualified_name})"
                            ).fetchall()
                            avail_cols = {str(r[1]).lower() for r in avail_cols_raw}
                        else:
                            avail_cols = {str(r[0]).lower() for r in avail_cols_raw}

                        has_row_id = "__row_id" in avail_cols
                        has_col = col_name and col_name.lower() in avail_cols
                        
                        # dbt aliases techniques pour tests natifs
                        dbt_aliases = ["value_field", "unique_field"]
                        found_alias = next((a for a in dbt_aliases if a in avail_cols), None)

                        if has_row_id:
                            # Cas standard : on a l'ID de ligne (soit dbt-native on_fail, soit macro custom)
                            if has_col:
                                res = conn.execute(
                                    f'SELECT __row_id, "{col_name}" FROM {qualified_name} LIMIT 2000'
                                ).fetchall()
                                failed_rows    = [int(r[0]) for r in res]
                                sample_invalid = [r[1] for r in res[:5] if r[1] is not None]
                            elif found_alias:
                                res = conn.execute(
                                    f'SELECT __row_id, "{found_alias}" FROM {qualified_name} LIMIT 2000'
                                ).fetchall()
                                failed_rows    = [int(r[0]) for r in res]
                                sample_invalid = [r[1] for r in res[:5] if r[1] is not None]
                            else:
                                res = conn.execute(
                                    f'SELECT __row_id FROM {qualified_name} LIMIT 2000'
                                ).fetchall()
                                failed_rows = [int(r[0]) for r in res]
                        elif has_col or found_alias:
                            # Fallback pour tests natifs dbt (unique, accepted_values) qui n'ont pas __row_id
                            # On joint avec raw_data pour retrouver les IDs originaux
                            effective_col = col_name if has_col else found_alias
                            logger.info("Récupération des __row_id par join pour %s (via %s)", col_name, effective_col)
                            try:
                                res = conn.execute(
                                    f'SELECT __row_id, "{col_name}" FROM raw_data '
                                    f'WHERE "{col_name}" IN (SELECT "{effective_col}" FROM {qualified_name}) '
                                    f'LIMIT 2000'
                                ).fetchall()
                                failed_rows    = [int(r[0]) for r in res]
                                sample_invalid = [r[1] for r in res[:5] if r[1] is not None]
                            except Exception as e:
                                logger.warning("Echec du join pour retrouver les IDs (%s): %s", effective_col, e)
                                # Dernier recours : juste les valeurs
                                res = conn.execute(
                                    f'SELECT "{effective_col}" FROM {qualified_name} LIMIT 50'
                                ).fetchall()
                                sample_invalid = [r[0] for r in res if r[0] is not None]
                        else:
                            # Table avec colonnes inconnues
                            logger.debug(
                                "Table %s — colonnes: %s (pas de __row_id ni %s)",
                                qualified_name, avail_cols, col_name,
                            )
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

        # ── Dispatcher par type de test ──
        
        # Test table-level (row_not_duplicate ou business rules table-level)
        if not col_name:
            if test_type == "row_not_duplicate":
                table_level_failures["row_not_duplicate"] = {
                    "count": failures_count,
                    "rows": failed_rows,
                    "dimension": "uniqueness",
                }
            elif test_type in br_dimension_map:
                table_level_failures[test_type] = {
                    "count": failures_count,
                    "rows": failed_rows,
                    "dimension": br_dimension_map[test_type],
                }
            continue

        # Initialiser le dict de la colonne si besoin
        if col_name not in col_failures:
            col_failures[col_name] = {
                "not_null":         {"count": 0, "rows": []},
                "unique":           {"count": 0, "rows": [], "samples": []},
                "type_errors":      {"count": 0, "rows": [], "samples": []},
                "range_errors":     {"count": 0, "rows": [], "samples": []},
                "enum_errors":      {"count": 0, "rows": [], "samples": []},
                "pattern_errors":   {"count": 0, "rows": [], "samples": []},
                "date_errors":      {"count": 0, "rows": [], "samples": []},
                "br_errors":         {},  # business rules errors par dimension
            }

        # Tests classiques
        if test_type == "not_null":
            col_failures[col_name]["not_null"]["count"] += failures_count
            col_failures[col_name]["not_null"]["rows"].extend(failed_rows)
        elif test_type == "unique":
            col_failures[col_name]["unique"]["count"] += failures_count
            col_failures[col_name]["unique"]["rows"].extend(failed_rows)
            col_failures[col_name]["unique"]["samples"].extend(sample_invalid)
        elif test_type in br_dimension_map:
            # Business rule test au niveau colonne
            dimension = br_dimension_map[test_type]
            if dimension not in col_failures[col_name]["br_errors"]:
                col_failures[col_name]["br_errors"][dimension] = {
                    "count": 0, "rows": [], "samples": [], "tests": []
                }
            col_failures[col_name]["br_errors"][dimension]["count"] += failures_count
            col_failures[col_name]["br_errors"][dimension]["rows"].extend(failed_rows)
            col_failures[col_name]["br_errors"][dimension]["samples"].extend(sample_invalid)
            col_failures[col_name]["br_errors"][dimension]["tests"].append(test_type)
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

    # ── Score de duplication de lignes (table-level) ──
    dup_info = table_level_failures.get("row_not_duplicate")
    if dup_info:
        dup_count = dup_info["count"]
        report.row_duplication_score = float(round(
            (total_rows - dup_count) / total_rows * 100, 1
        )) if total_rows > 0 else 100.0
        report.row_duplication_detail = {
            "duplicate_row_count": int(dup_count),
            "total_rows": int(total_rows),
            "duplicate_rows": [r for r in dup_info["rows"][:500]],
        }
    else:
        report.row_duplication_score = 100.0

    # ── Autres Business Rules table-level ──
    for tl_test_type, tl_info in table_level_failures.items():
        if tl_test_type == "row_not_duplicate":
            continue
        report.table_level_business_rules.append({
            "test_type": tl_test_type,
            "dimension": tl_info.get("dimension", "consistency"),
            "count": int(tl_info.get("count", 0)),
            "rows": [r for r in tl_info.get("rows", [])][:500]
        })

    # ── Construire les ColumnQualityScore ──
    _empty_failures = {
        "not_null":       {"count": 0, "rows": []},
        "unique":         {"count": 0, "rows": [], "samples": []},
        "type_errors":    {"count": 0, "rows": [], "samples": []},
        "range_errors":   {"count": 0, "rows": [], "samples": []},
        "enum_errors":    {"count": 0, "rows": [], "samples": []},
        "pattern_errors": {"count": 0, "rows": [], "samples": []},
        "date_errors":    {"count": 0, "rows": [], "samples": []},
        "br_errors":      {},
    }

    for col_meta in metadata:
        col_name = col_meta.column_name
        f        = col_failures.get(col_name, _empty_failures)
        score    = ColumnQualityScore(column_name=col_name, business_name=col_meta.business_name)

        # ── COMPLETENESS ──
        if not col_meta.nullable:
            null_c = f["not_null"]["count"]
            score.completeness = float(round((total_rows - null_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
            score.completeness_detail = {
                "null_count": int(null_c),
                "total":      int(total_rows),
                "null_rows":  f["not_null"]["rows"][:500],
            }

        # ── UNIQUENESS (column-level) ──
        if col_meta.identifier:
            uniq_c = f["unique"]["count"]
            score.uniqueness = float(round((total_rows - uniq_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
            score.uniqueness_detail = {
                "duplicate_count":  int(uniq_c),
                "total_non_null":   int(total_rows - f["not_null"]["count"]),
                "duplicate_rows":   f["unique"]["rows"][:500],
                "duplicate_values": f["unique"]["samples"],
            }

        # ── VALIDITY (type, enum, pattern, date — SANS in_range) ──
        has_validity = (
            col_meta.type in ("int", "float", "date")
            or col_meta.has_enum
            or col_meta.has_pattern
        )
        if has_validity:
            val_c = sum(
                f[k]["count"]
                for k in ["type_errors", "enum_errors", "pattern_errors", "date_errors"]
            )
            score.validity = float(round((total_rows - val_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
            
            validity_detail = {"invalid_count": int(val_c)}
            for k in ["type_errors", "enum_errors", "pattern_errors", "date_errors"]:
                if f[k]["count"] > 0:
                    validity_detail[k]              = f[k]["rows"][:500]
                    validity_detail[k + "_samples"] = f[k]["samples"][:5]
            score.validity_detail = validity_detail

        # ── ACCURACY (in_range uniquement) ──
        if col_meta.has_range:
            range_c = f["range_errors"]["count"]
            score.accuracy = float(round((total_rows - range_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
            score.accuracy_detail = {
                "out_of_range_count": int(range_c),
                "total": int(total_rows),
                "out_of_range_rows":[r for r in f["range_errors"]["rows"][:500]],
                "out_of_range_samples": f["range_errors"]["samples"][:5],
            }

        # ── CONSISTENCY + autres dimensions via business rules ──
        br_errors = f.get("br_errors", {})
        
        # Business rules marquées "consistency"
        if "consistency" in br_errors:
            cons_c = br_errors["consistency"]["count"]
            score.consistency = float(round((total_rows - cons_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
            score.consistency_detail = {
                "inconsistent_count": int(cons_c),
                "inconsistent_rows": br_errors["consistency"]["rows"][:500],
                "inconsistent_samples": br_errors["consistency"]["samples"][:5],
                "failed_tests": br_errors["consistency"].get("tests", []),
            }
        
        # Business rules marquées "accuracy" (en plus de in_range)
        if "accuracy" in br_errors:
            br_acc_c = br_errors["accuracy"]["count"]
            if score.accuracy is not None:
                # Combiner avec in_range
                total_acc_errors = f["range_errors"]["count"] + br_acc_c
                score.accuracy = float(round((total_rows - total_acc_errors) / total_rows * 100, 1)) if total_rows > 0 else 100.0
                score.accuracy_detail["br_accuracy_errors"] = br_acc_c
                score.accuracy_detail["br_accuracy_rows"] = br_errors["accuracy"]["rows"][:500]
            else:
                score.accuracy = float(round((total_rows - br_acc_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0
                score.accuracy_detail = {
                    "out_of_range_count": int(br_acc_c),
                    "out_of_range_rows": br_errors["accuracy"]["rows"][:500],
                    "out_of_range_samples": br_errors["accuracy"]["samples"][:5],
                    "failed_tests": br_errors["accuracy"].get("tests", []),
                }
        
        # Business rules touchant d'autres dimensions (validity, completeness, uniqueness)
        for dim in ["validity", "completeness", "uniqueness"]:
            if dim in br_errors:
                br_dim_c = br_errors[dim]["count"]
                current_score = getattr(score, dim)
                if current_score is not None:
                    # Recalculer en ajoutant les erreurs BR
                    detail = getattr(score, f"{dim}_detail")
                    existing_errors = detail.get("invalid_count", detail.get("null_count", detail.get("duplicate_count", 0)))
                    total_errors = existing_errors + br_dim_c
                    setattr(score, dim, float(round((total_rows - total_errors) / total_rows * 100, 1)) if total_rows > 0 else 100.0)
                    detail[f"br_{dim}_errors"] = br_dim_c
                    detail[f"br_{dim}_rows"] = br_errors[dim]["rows"][:500]
                else:
                    setattr(score, dim, float(round((total_rows - br_dim_c) / total_rows * 100, 1)) if total_rows > 0 else 100.0)
                    setattr(score, f"{dim}_detail", {
                        "br_error_count": int(br_dim_c),
                        "br_error_rows": br_errors[dim]["rows"][:500],
                        "failed_tests": br_errors[dim].get("tests", []),
                    })

        report.columns.append(score)

    # ── Traiter les business rules table-level pour consistency ──
    table_consistency_failures = {
        k: v for k, v in table_level_failures.items()
        if k != "row_not_duplicate" and v.get("dimension") == "consistency"
    }
    if table_consistency_failures:
        # Créer une entrée globale consistency si pas déjà couvert par les colonnes
        total_table_cons_errors = sum(v["count"] for v in table_consistency_failures.values())
        logger.info(
            "Business rules table-level consistency : %d erreurs",
            total_table_cons_errors,
        )

    # Nettoyage du fichier schema temporaire
    Path(schema_path).unlink(missing_ok=True)
    return report, business_rule_tests