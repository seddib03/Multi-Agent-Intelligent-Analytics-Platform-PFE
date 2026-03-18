from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import pandas as pd

from agent.state import AgentState
from core.minio_client import MinioClient

logger = logging.getLogger(__name__)

# Supprimer les avertissements matplotlib répétitifs de ydata-profiling
logging.getLogger("matplotlib.category").setLevel(logging.WARNING)


def _load_df(df_dict: dict) -> pd.DataFrame:
    """Reconstruit un DataFrame Pandas depuis le dict sérialisé du state."""
    if df_dict is None:
        return pd.DataFrame()
    return pd.DataFrame(
        data=df_dict.get("data", []),
        columns=df_dict.get("columns", []),
    )


def profiling_node(state: AgentState) -> dict:
    logger.info(">>> NODE 2 : Profiling (ydata-profiling 4.18.1) — démarrage")

    df     = _load_df(state["raw_df"])
    job_id = state["job_id"]
    sector = state.get("sector", "unknown")
    minio  = MinioClient()

    html_minio        = None
    json_minio        = None
    profiling_summary = {}

    try:
        from ydata_profiling import ProfileReport

        logger.info(
            "Génération ProfileReport — %d lignes x %d colonnes",
            len(df), len(df.columns),
        )

        # ── Échantillonnage adaptatif pour les grands datasets ─────────────
        total_rows = len(df)
        if total_rows <= 10_000:
            df_to_profile = df
        else:
            sample_size = min(5000, total_rows)
            df_to_profile = df.sample(sample_size, random_state=42)
            logger.info(
                "Dataset volumineux (%d lignes) → profiling sur échantillon de %d lignes",
                total_rows, sample_size,
            )

        # ── Créer le ProfileReport ─────────────────────────────────────────
        profile = ProfileReport(
            df_to_profile,
            title=f"Data Profiling — {sector} | Job {job_id[:8]}",
            explorative=True,
            progress_bar=False,
        )

        # ── Export HTML → fichier temporaire → upload MinIO ───────────────
        tmp_dir  = Path(tempfile.gettempdir())
        html_tmp = tmp_dir / f"profiling_{job_id[:8]}.html"

        logger.info("Export HTML en cours...")
        profile.to_file(str(html_tmp))
        logger.info(
            "HTML généré : %.2f MB",
            html_tmp.stat().st_size / 1024 / 1024,
        )

        html_minio = minio.upload_gold_raw(
            job_id=job_id,
            sector=sector,
            raw_bytes=html_tmp.read_bytes(),
            filename="profiling_report.html",
            content_type="text/html",
        )
        html_tmp.unlink(missing_ok=True)
        logger.info("HTML uploadé MinIO : %s", html_minio)

        # ── Export JSON (optimisé via to_json()) ───────────────────────────
        logger.info("Export JSON en cours (mémoire)...")
        json_str = profile.to_json()
        profile_dict = json.loads(json_str)

        json_minio = minio.upload_gold(
            job_id=job_id,
            sector=sector,
            report=profile_dict,
            filename="profiling_report.json",
        )
        logger.info("JSON uploadé MinIO : %s", json_minio)

        # ── Extraire le résumé compact pour le state ───────────────────────
        profiling_summary = _extract_summary(profile_dict, df)
        logger.info(
            "Résumé extrait — %d colonnes | %d alertes | %d corrélations fortes",
            len(profiling_summary.get("columns", {})),
            len(profiling_summary.get("alerts", [])),
            len(profiling_summary.get("correlations", [])),
        )

    except ImportError:
        logger.warning(
            "ydata-profiling non installé — fallback basique Pandas.\n"
            "  → Installer : pip install ydata-profiling==4.18.1"
        )
        profiling_summary = _basic_profiling(df)

    except Exception as e:
        logger.error(
            "Erreur critique NODE 2 (ydata-profiling) : %s", e,
            exc_info=True,
        )
        # Fallback basique pour que le pipeline ne s'arrête pas
        profiling_summary = _basic_profiling(df)

    logger.info(
        "NODE 2 terminé — HTML: %s | JSON: %s",
        "✓ " + html_minio if html_minio else "✗ non généré",
        "✓ " + json_minio if json_minio else "✗ non généré",
    )

    from models.quality_report import _to_native
    return {
        "profiling_summary":   _to_native(profiling_summary),
        "profiling_html_path": html_minio,
        "profiling_json_path": json_minio,
    }


# ── Extraction du résumé compact ──────────────────────────────────────────────

def _extract_summary(profile_dict: dict, df: pd.DataFrame) -> dict:
    """
    Extrait les métriques clés du JSON ydata-profiling.

    Produit un résumé léger (sans histogrammes ni samples complets)
    transmis au LLM dans strategy_node pour contextualiser le plan.

    Structure retournée :
    {
        "dataset": {
            "total_rows", "total_columns",
            "missing_pct", "duplicate_pct"
        },
        "columns": {
            "col_name": {
                "type", "null_count", "null_pct",
                "unique_count", "unique_pct",
                # si numérique :
                "mean", "std", "min", "max", "median",
                "skewness", "n_outliers", "is_skewed", "has_outliers",
                # si catégoriel :
                "top_values", "n_category",
            }
        },
        "alerts":       [{column, alert_type}],
        "correlations": [{col_a, col_b, pearson}],
    }
    """
    summary = {
        "dataset":      {},
        "columns":      {},
        "alerts":       [],
        "correlations": [],
    }

    # ── Stats globales ────────────────────────────────────────────────────
    table = profile_dict.get("table", {})
    summary["dataset"] = {
        "total_rows":          table.get("n",              len(df)),
        "total_columns":       table.get("n_var",          len(df.columns)),
        "total_missing_cells": table.get("n_cells_missing", 0),
        "missing_pct":         round(table.get("p_cells_missing", 0) * 100, 2),
        "total_duplicates":    table.get("n_duplicates",   0),
        "duplicate_pct":       round(table.get("p_duplicates",    0) * 100, 2),
    }

    # ── Stats par colonne ─────────────────────────────────────────────────
    variables = profile_dict.get("variables", {})
    for col_name, col_data in variables.items():
        col_type = col_data.get("type", "Unsupported")

        col_summary = {
            "type":         col_type,
            "null_count":   col_data.get("n_missing", 0),
            "null_pct":     round(col_data.get("p_missing",  0) * 100, 2),
            "unique_count": col_data.get("n_unique",  0),
            "unique_pct":   round(col_data.get("p_unique",   0) * 100, 2),
        }

        # Colonnes numériques
        if col_type in ("Numeric", "Real", "Integer"):
            skewness = col_data.get("skewness") or 0
            outliers = col_data.get("n_outliers") or 0
            col_summary.update({
                "mean":         round(col_data.get("mean") or 0, 4),
                "std":          round(col_data.get("std")  or 0, 4),
                "min":          col_data.get("min"),
                "max":          col_data.get("max"),
                "median":       col_data.get("50%"),
                "skewness":     round(skewness, 3),
                "n_outliers":   outliers,
                "is_skewed":    abs(skewness) > 1,
                "has_outliers": outliers > 0,
            })

        # Colonnes catégorielles / texte
        elif col_type in ("Categorical", "Text", "Boolean"):
            vc       = col_data.get("value_counts_without_nan", {})
            top_vals = sorted(vc.items(), key=lambda x: x[1], reverse=True)[:5]
            col_summary.update({
                "top_values": [{"value": k, "count": v} for k, v in top_vals],
                "n_category": len(vc),
            })

        # Colonnes date
        elif col_type == "DateTime":
            col_summary.update({
                "min_date": str(col_data.get("min", "")),
                "max_date": str(col_data.get("max", "")),
            })

        summary["columns"][col_name] = col_summary

    # ── Alertes ydata ─────────────────────────────────────────────────────
    for alert in profile_dict.get("alerts", []):
        if isinstance(alert, dict):
            summary["alerts"].append({
                "column":     alert.get("column_name", ""),
                "alert_type": alert.get("alert_type",  ""),
            })
        elif isinstance(alert, str):
            summary["alerts"].append({"description": alert})

    # ── Corrélations fortes Pearson (>= 0.85) ─────────────────────────────
    corr_data = (
        profile_dict
        .get("correlations", {})
        .get("pearson", {})
        .get("data", {})
    )
    seen      = set()
    high_corr = []

    if isinstance(corr_data, dict):
        for col_a, row in corr_data.items():
            if not isinstance(row, dict):
                continue
            for col_b, val in row.items():
                key = tuple(sorted([col_a, col_b]))
                if col_a != col_b and abs(val) >= 0.85 and key not in seen:
                    seen.add(key)
                    high_corr.append({
                        "col_a":   col_a,
                        "col_b":   col_b,
                        "pearson": round(val, 3),
                    })

    summary["correlations"] = high_corr[:10]

    return summary


# ── Fallback basique (sans ydata-profiling) ───────────────────────────────────

def _basic_profiling(df: pd.DataFrame) -> dict:
    """
    Profiling basique avec Pandas natif.
    Utilisé si ydata-profiling n'est pas installé ou échoue.
    Produit un résumé dans le même format que _extract_summary.
    """
    total   = len(df)
    n_cells = total * len(df.columns)

    summary = {
        "dataset": {
            "total_rows":          total,
            "total_columns":       len(df.columns),
            "total_missing_cells": int(df.isna().sum().sum()),
            "missing_pct":         round(df.isna().sum().sum() / max(1, n_cells) * 100, 2),
            "total_duplicates":    int(df.duplicated().sum()),
            "duplicate_pct":       round(df.duplicated().sum() / max(1, total) * 100, 2),
        },
        "columns":      {},
        "alerts":       [],
        "correlations": [],
    }

    for col in df.columns:
        s          = df[col]
        null_count = int(s.isna().sum())
        non_null   = total - null_count

        col_info = {
            "type":         "string",
            "null_count":   null_count,
            "null_pct":     round(null_count / max(1, total) * 100, 2),
            "unique_count": int(s.nunique()),
            "unique_pct":   round(s.nunique() / max(1, total) * 100, 2),
        }

        # Tenter conversion numérique
        numeric = pd.to_numeric(s, errors="coerce")
        if non_null > 0 and numeric.notna().sum() / non_null >= 0.8:
            col_info["type"]   = "Numeric"
            col_info["mean"]   = round(float(numeric.mean()),   4)
            col_info["std"]    = round(float(numeric.std()),    4)
            col_info["min"]    = float(numeric.min())
            col_info["max"]    = float(numeric.max())
            col_info["median"] = float(numeric.median())

        summary["columns"][col] = col_info

        # Alerte si > 20% nulls
        if null_count / max(1, total) > 0.2:
            summary["alerts"].append({
                "column":     col,
                "alert_type": "HIGH_MISSING",
                "description": f"{round(null_count/total*100,1)}% de valeurs manquantes",
            })

    return summary