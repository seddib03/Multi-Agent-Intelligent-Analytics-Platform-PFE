"""
main.py — FastAPI V3
"""
from __future__ import annotations
import logging, shutil, uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from agent.graph import agent_graph
from agent.state import build_initial_state
from config.settings import get_settings
from core.minio_client import MinioClient
from models.anomaly_report import CleaningAction, UserDecision

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app      = FastAPI(title="Data Preparation Agent V3", version="3.0.0")
settings = get_settings()


# ── Modèles Pydantic ──────────────────────────────────────────────────────────

class AnomalyDecision(BaseModel):
    anomaly_id:    str
    decision:      str
    chosen_action: Optional[str] = None
    params:        Optional[dict] = None

class ValidationRequest(BaseModel):
    decisions: list[AnomalyDecision]


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        MinioClient().initialize_buckets()
        logger.info("MinIO prêt — buckets bronze/silver/gold initialisés")
    except Exception as e:
        logger.error("MinIO non disponible : %s", e)


# ── POST /prepare ─────────────────────────────────────────────────────────────

@app.post("/prepare")
async def prepare(
    dataset:  UploadFile = File(...),
    metadata: UploadFile = File(...),
) -> JSONResponse:
    job_id  = str(uuid.uuid4())
    tmp_dir = settings.tmp_dir / job_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    dataset_path  = tmp_dir / dataset.filename
    metadata_path = tmp_dir / metadata.filename

    with open(dataset_path,  "wb") as f: shutil.copyfileobj(dataset.file,  f)
    with open(metadata_path, "wb") as f: shutil.copyfileobj(metadata.file, f)

    initial_state = build_initial_state(
        job_id=job_id,
        dataset_path=str(dataset_path),
        metadata_path=str(metadata_path),
    )

    config = {"configurable": {"thread_id": job_id}}
    try:
        state = agent_graph.invoke(initial_state, config=config)
    except Exception as e:
        logger.error("Erreur pipeline %s : %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    cleaning_plan  = state.get("cleaning_plan")
    quality_before = state.get("quality_before")

    return JSONResponse({
        "job_id":         job_id,
        "status":         "waiting_validation",
        "sector":         state.get("sector", "unknown"),
        "quality_before": quality_before if quality_before else {},
        "llm_summary":    state.get("llm_summary", ""),
        "plan":           cleaning_plan.to_dict() if cleaning_plan else {},
        "profiling_html": f"/jobs/{job_id}/profiling?sector={state.get('sector','unknown')}",
        "profiling_json": f"/jobs/{job_id}/profiling-json?sector={state.get('sector','unknown')}",
        "message":        f"Plan prêt. Validez via POST /jobs/{job_id}/validate",
    })


# ── GET /jobs/{job_id}/plan ───────────────────────────────────────────────────

@app.get("/jobs/{job_id}/plan")
async def get_plan(job_id: str) -> JSONResponse:
    config   = {"configurable": {"thread_id": job_id}}
    snapshot = _get_snapshot(job_id, config)
    state    = snapshot.values

    cleaning_plan = state.get("cleaning_plan")
    if not cleaning_plan:
        raise HTTPException(status_code=404, detail="Aucun plan trouvé")

    return JSONResponse({
        "job_id":         job_id,
        "status":         state.get("status"),
        "llm_summary":    state.get("llm_summary", ""),
        "plan":           cleaning_plan.to_dict(),
        "quality_before": state.get("quality_before") or {},
    })


# ── POST /jobs/{job_id}/validate ──────────────────────────────────────────────

@app.post("/jobs/{job_id}/validate")
async def validate_plan(job_id: str, payload: ValidationRequest) -> JSONResponse:
    config   = {"configurable": {"thread_id": job_id}}
    snapshot = _get_snapshot(job_id, config)
    state    = snapshot.values

    cleaning_plan = state.get("cleaning_plan")
    if not cleaning_plan:
        raise HTTPException(status_code=400, detail="Aucun plan à valider")

    decisions_map = {d.anomaly_id: d for d in payload.decisions}

    for anomaly in cleaning_plan.anomalies:
        if anomaly.anomaly_id not in decisions_map:
            raise HTTPException(status_code=400, detail=f"Décision manquante pour {anomaly.anomaly_id}")
        dec = decisions_map[anomaly.anomaly_id]

        try:
            anomaly.user_decision = UserDecision(dec.decision)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Décision invalide '{dec.decision}'")

        if dec.chosen_action:
            try:
                anomaly.chosen_action = CleaningAction(dec.chosen_action)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Action inconnue : {dec.chosen_action}")
        else:
            anomaly.chosen_action = anomaly.action_1

        if dec.params:
            anomaly.user_params = dec.params

    cleaning_plan.status = "validated"
    agent_graph.update_state(config, {"cleaning_plan": cleaning_plan}, as_node="strategy")

    try:
        final_state = agent_graph.invoke(None, config=config)
    except Exception as e:
        logger.error("Erreur reprise %s : %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    qb = final_state.get("quality_before") or {}
    qa = final_state.get("quality_after")  or {}
    qb_scores = qb.get("global_scores", {})
    qa_scores = qa.get("global_scores", {})

    return JSONResponse({
        "job_id":  job_id,
        "status":  final_state.get("status"),
        "sector":  final_state.get("sector"),
        "quality_comparison": {
            "before": {
                "global":       qb_scores.get("global"),
                "completeness": qb_scores.get("completeness"),
                "validity":     qb_scores.get("validity"),
                "uniqueness":   qb_scores.get("uniqueness"),
            },
            "after": {
                "global":       qa_scores.get("global"),
                "completeness": qa_scores.get("completeness"),
                "validity":     qa_scores.get("validity"),
                "uniqueness":   qa_scores.get("uniqueness"),
            },
            "gain": round(
                (qa_scores.get("global", 0) or 0) - (qb_scores.get("global", 0) or 0), 1
            ),
        },
        "quality_by_column": {
            "before": qb.get("columns", []),
            "after":  qa.get("columns", []),
        },
        "cleaning_log": final_state.get("cleaning_log", []),
        "paths": {
            "silver": final_state.get("silver_path"),
            "gold":   final_state.get("gold_path"),
        },
        "completed_at": final_state.get("completed_at"),
    })


# ── GET /jobs/{job_id}/status ─────────────────────────────────────────────────

@app.get("/jobs/{job_id}/status")
async def get_status(job_id: str) -> JSONResponse:
    config   = {"configurable": {"thread_id": job_id}}
    snapshot = _get_snapshot(job_id, config)
    state    = snapshot.values
    return JSONResponse({
        "job_id": job_id,
        "status": state.get("status"),
        "sector": state.get("sector"),
        "errors": state.get("errors", []),
    })


# ── GET /jobs/{job_id}/profiling ──────────────────────────────────────────────

@app.get("/jobs/{job_id}/profiling")
async def get_profiling_report(
    job_id: str,
    sector: str = "unknown",
):
    """
    Redirige vers le rapport HTML ydata-profiling dans MinIO Gold.
    Lit directement depuis MinIO — fonctionne après redémarrage.

    Exemple : GET /jobs/{id}/profiling?sector=assurance
    """
    try:
        url = MinioClient().get_presigned_url(
            job_id=job_id,
            sector=sector,
            filename="profiling_report.html",
            expires=3600,
        )
        return RedirectResponse(url=url)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Rapport HTML introuvable dans MinIO. "
                f"Vérifiez : gold / {sector} / {job_id} / profiling_report.html. "
                f"Erreur : {e}"
            ),
        )


# ── GET /jobs/{job_id}/profiling-json ────────────────────────────────────────

@app.get("/jobs/{job_id}/profiling-json")
async def get_profiling_json(
    job_id: str,
    sector: str = "unknown",
) -> JSONResponse:
    """
    Retourne le résumé structuré du profiling.
    Tente de lire depuis le State d'abord, puis MinIO.
    """
    summary = None
    config  = {"configurable": {"thread_id": job_id}}
    
    try:
        # 1. Tenter depuis le State
        try:
            snapshot = agent_graph.get_state(config)
            if snapshot.values:
                summary = snapshot.values.get("profiling_summary")
                if summary:
                    logger.info("Résumé profiling récupéré depuis le State pour le job %s", job_id)
        except Exception as e:
            logger.warning("Échec lecture state pour profiling %s : %s", job_id, e)

        # 2. Tenter depuis MinIO si pas dans le state
        if not summary:
            try:
                full_json = MinioClient().download_gold_json(
                    job_id=job_id,
                    sector=sector,
                    filename="profiling_report.json",
                )
                summary = _extract_profiling_summary(full_json)
                logger.info("Résumé profiling récupéré depuis MinIO pour le job %s", job_id)
            except Exception as e:
                logger.warning("Échec lecture MinIO pour profiling %s : %s", job_id, e)
        
        if not summary:
            raise ValueError(f"Aucun résumé trouvé dans le State ou MinIO (secteur: {sector}).")

        return JSONResponse({
            "job_id":          job_id,
            "sector":          sector,
            "summary":         summary,
            "html_report_url": f"/jobs/{job_id}/profiling?sector={sector}",
        })
    except Exception as e:
        logger.error("Erreur globale profiling-json pour %s : %s", job_id, e)
        raise HTTPException(
            status_code=404,
            detail=(
                f"Résumé de profiling introuvable pour {job_id} (ni dans l'état, ni dans MinIO). "
                f"Vérifiez que le secteur '{sector}' est correct. Erreur : {e}"
            ),
        )


# ── GET /health ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    try:
        MinioClient().initialize_buckets()
        minio_ok = True
    except Exception:
        minio_ok = False
    return JSONResponse({
        "status":  "ok",
        "version": "3.0.0",
        "minio":   "ok" if minio_ok else "unreachable",
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_snapshot(job_id: str, config: dict):
    try:
        snapshot = agent_graph.get_state(config)
        if not snapshot.values:
            raise HTTPException(status_code=404, detail=f"Job {job_id} introuvable")
        return snapshot
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail=f"Job {job_id} introuvable")


def _extract_profiling_summary(profile_dict: dict) -> dict:
    """
    Extrait les métriques clés du JSON brut ydata-profiling.

    Le JSON brut contient des histogrammes base64 et samples complets
    qui rendent la réponse API illisible (5-20 MB).
    Cette fonction retourne uniquement ce qui est exploitable :
        - Stats globales du dataset
        - Par colonne : type, nulls, uniques, stats numériques, top valeurs
        - Alertes ydata (HIGH_MISSING, SKEWED, HIGH_CARDINALITY...)
        - Corrélations fortes (Pearson >= 0.85)
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
        "total_rows":          table.get("n", 0),
        "total_columns":       table.get("n_var", 0),
        "total_missing_cells": table.get("n_cells_missing", 0),
        "missing_pct":         round((table.get("p_cells_missing") or 0) * 100, 2),
        "total_duplicates":    table.get("n_duplicates", 0),
        "duplicate_pct":       round((table.get("p_duplicates") or 0) * 100, 2),
    }

    # ── Stats par colonne ─────────────────────────────────────────────────
    for col_name, col_data in profile_dict.get("variables", {}).items():
        col_type = col_data.get("type", "Unknown")

        col_info = {
            "type":         col_type,
            "null_count":   col_data.get("n_missing", 0),
            "null_pct":     round((col_data.get("p_missing")  or 0) * 100, 2),
            "unique_count": col_data.get("n_unique", 0),
            "unique_pct":   round((col_data.get("p_unique")   or 0) * 100, 2),
        }

        # Numérique
        if col_type in ("Numeric", "Real", "Integer"):
            skewness = col_data.get("skewness") or 0
            outliers = col_data.get("n_outliers") or 0
            col_info.update({
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

        # Catégoriel
        elif col_type in ("Categorical", "Text", "Boolean"):
            vc       = col_data.get("value_counts_without_nan", {})
            top_vals = sorted(vc.items(), key=lambda x: x[1], reverse=True)[:5]
            col_info.update({
                "top_values": [{"value": k, "count": v} for k, v in top_vals],
                "n_category": len(vc),
            })

        # Date
        elif col_type == "DateTime":
            col_info.update({
                "min_date": str(col_data.get("min", "")),
                "max_date": str(col_data.get("max", "")),
            })

        summary["columns"][col_name] = col_info

    # ── Alertes ydata ─────────────────────────────────────────────────────
    for alert in profile_dict.get("alerts", []):
        if isinstance(alert, dict):
            summary["alerts"].append({
                "column":     alert.get("column_name", ""),
                "alert_type": alert.get("alert_type",  ""),
            })
        elif isinstance(alert, str):
            summary["alerts"].append({"description": alert})

    # ── Corrélations fortes (Pearson >= 0.85) ─────────────────────────────
    corr_data = (
        profile_dict
        .get("correlations", {})
        .get("pearson", {})
        .get("data", {})
    )
    seen = set()
    if isinstance(corr_data, dict):
        for col_a, row in corr_data.items():
            if not isinstance(row, dict):
                continue
            for col_b, val in row.items():
                key = tuple(sorted([col_a, col_b]))
                if col_a != col_b and abs(val or 0) >= 0.85 and key not in seen:
                    seen.add(key)
                    summary["correlations"].append({
                        "col_a":   col_a,
                        "col_b":   col_b,
                        "pearson": round(val, 3),
                    })

    summary["correlations"] = summary["correlations"][:10]
    return summary