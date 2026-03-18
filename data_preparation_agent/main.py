"""
main.py — FastAPI V4 (Import + Check Quality)
"""
from __future__ import annotations
import dataclasses, json, logging, shutil, uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from agent.graph import import_graph, agent_graph
from agent.state import build_import_state
from config.settings import get_settings
from core.minio_client import MinioClient
from models.anomaly_report import CleaningAction, UserDecision
from models.metadata_schema import parse_metadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app      = FastAPI(title="Data Preparation Agent V4", version="4.0.0")
settings = get_settings()


# ── Modèles Pydantic ──────────────────────────────────────────────────────────

class AnomalyDecision(BaseModel):
    anomaly_id:    str
    decision:      str
    chosen_action: Optional[str] = None
    params:        Optional[dict] = None

class ValidationRequest(BaseModel):
    decisions: list[AnomalyDecision]

from datetime import datetime, date

def _serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} non sérialisable")

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        MinioClient().initialize_buckets()
        logger.info("MinIO prêt — buckets bronze/silver/gold initialisés")
    except Exception as e:
        logger.error("MinIO non disponible : %s", e)


# ── POST /import ──────────────────────────────────────────────────────────────
# Étape 1 : Import léger — ingestion + profiling uniquement.
# L'utilisateur envoie son dataset brut (CSV). Pas de metadata.
# Retourne profiling_summary pour le NLQ agent.

@app.post("/import")
async def import_dataset(
    dataset: UploadFile = File(...),
    sector:  str        = Form("unknown"),
) -> JSONResponse:
    job_id  = str(uuid.uuid4())
    tmp_dir = settings.tmp_dir / job_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = tmp_dir / dataset.filename
    with open(dataset_path, "wb") as f:
        shutil.copyfileobj(dataset.file, f)

    initial_state = build_import_state(
        job_id=job_id,
        dataset_path=str(dataset_path),
        sector=sector,
    )

    config = {"configurable": {"thread_id": f"import_{job_id}"}}
    try:
        state = import_graph.invoke(initial_state, config=config)
    except Exception as e:
        logger.error("Erreur import %s : %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    sector = state.get("sector", "unknown")

    return JSONResponse({
        "job_id":            job_id,
        "status":            "imported",
        "sector":            sector,
        "profiling_html":    f"/jobs/{job_id}/profiling?sector={sector}",
        "profiling_json":    f"/jobs/{job_id}/profiling-json?sector={sector}",
        "raw_data_path":     state.get("bronze_path"),
        "message":           f"Import OK. Lancez le check qualité via POST /prepare/{job_id}",
    })


# ── POST /prepare/{job_id} ───────────────────────────────────────────────────
# Étape 2 : Check Quality — l'utilisateur fournit les règles (metadata JSON).
# Reprend le job existant (même DuckDB, même Bronze) et lance NODE 3 → 8.

@app.post("/prepare/{job_id}")
async def prepare(
    job_id:   str,
    metadata: UploadFile = File(...),
) -> JSONResponse:
    # ── 1. Lire le state existant depuis l'import_graph ───────────────────
    config_import = {"configurable": {"thread_id": f"import_{job_id}"}}
    try:
        snapshot = import_graph.get_state(config_import)
        if not snapshot or not snapshot.values:
            raise ValueError("State vide")
        existing_state = snapshot.values
    except Exception as e:
        logger.error("Job %s introuvable : %s", job_id, e)
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} introuvable. Avez-vous fait POST /import d'abord ?",
        )

    if existing_state.get("status") != "imported":
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} n'est pas en état 'imported' (état actuel: {existing_state.get('status')})",
        )

    # ── 2. Parser le metadata JSON uploadé ────────────────────────────────
    tmp_dir = settings.tmp_dir / job_id
    metadata_path = tmp_dir / metadata.filename
    with open(metadata_path, "wb") as f:
        shutil.copyfileobj(metadata.file, f)

    with open(metadata_path, encoding="utf-8") as f:
        raw_meta = json.load(f)

    # Extraire colonnes, secteur, business_rules
    if isinstance(raw_meta, list):
        meta_list = raw_meta
    elif isinstance(raw_meta, dict) and "columns" in raw_meta:
        meta_list = raw_meta["columns"]
    else:
        meta_list = raw_meta

    parsed_metadata = parse_metadata(meta_list)
    meta_dicts = [dataclasses.asdict(m) for m in parsed_metadata]

    sector = "unknown"
    business_rules = []
    if isinstance(raw_meta, dict):
        sector = raw_meta.get("sector", raw_meta.get("secteur", "unknown"))
        business_rules = raw_meta.get("business_rules", [])

    # ── 3. Construire le state pour le prep graph ─────────────────────────
    prep_state = {
        **existing_state,
        "metadata":       meta_dicts,
        "business_rules": business_rules,
        "sector":         sector,
        "metadata_path":  str(metadata_path),
        "status":         "running",
    }

    # ── 4. Lancer le prep graph (NODE 3 → NODE 5, interrupt avant cleaning)
    try:
        config_agent = {"configurable": {"thread_id": f"agent_{job_id}"}}
        state = agent_graph.invoke(prep_state, config=config_agent)
    except Exception as e:
        logger.error("Erreur pipeline prep %s : %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    cleaning_plan = state.get("cleaning_plan")
    qb_dict       = state.get("quality_before")

    if qb_dict:
        from models.quality_report import QualityReport
        qb_dict = QualityReport.from_dict(qb_dict).to_dict(apply_offsets=True)

    return JSONResponse({
        "job_id":         job_id,
        "status":         "waiting_validation",
        "sector":         state.get("sector", "unknown"),
        "quality_before": qb_dict if qb_dict else {},
        "plan":           cleaning_plan.to_dict(apply_offsets=True) if cleaning_plan else {},
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
        "plan":           cleaning_plan.to_dict(),
        "quality_before": state.get("quality_before") or {},
    })


# ── POST /jobs/{job_id}/validate ──────────────────────────────────────────────

@app.post("/jobs/{job_id}/validate")
async def validate_plan(job_id: str, payload: ValidationRequest) -> JSONResponse:
    config_agent = {"configurable": {"thread_id": f"agent_{job_id}"}}
    config_import = {"configurable": {"thread_id": f"import_{job_id}"}}
    
    snapshot = _get_snapshot(job_id, config_agent)
    state    = snapshot.values

    cleaning_plan = state.get("cleaning_plan")
    if not cleaning_plan:
        raise HTTPException(status_code=400, detail="Aucun plan à valider")

    # ── Récupérer raw_df depuis import_graph ──────────────────────────────
    # raw_df est dans import_graph (thread import_{job_id})
    # pas dans agent_graph
    raw_df = state.get("raw_df")
    if not raw_df or not raw_df.get("columns"):
        # Fallback : lire depuis import_graph
        try:
            import_snapshot = import_graph.get_state(config_import)
            if import_snapshot and import_snapshot.values:
                raw_df = import_snapshot.values.get("raw_df")
                logger.info("raw_df récupéré depuis import_graph pour validate")
        except Exception as e:
            logger.error("Impossible de récupérer raw_df depuis import_graph : %s", e)

    if not raw_df or not raw_df.get("columns"):
        raise HTTPException(
            status_code=400,
            detail="raw_df introuvable — relancez POST /import"
        )

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
    agent_graph.update_state(
        config_agent, 
        {
            "cleaning_plan": cleaning_plan,
            "raw_df": raw_df,
        }, 
        as_node="strategy"
    )
    try:
        final_state = agent_graph.invoke(None, config=config_agent)
    except Exception as e:
        logger.error("Erreur reprise %s : %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    # Appliquer les offsets aux rapports qualité pour l'affichage final
    from models.quality_report import QualityReport
    qb_dict = final_state.get("quality_before")
    qa_dict = final_state.get("quality_after")
    
    if qb_dict: qb_dict = QualityReport.from_dict(qb_dict).to_dict(apply_offsets=True)
    if qa_dict: qa_dict = QualityReport.from_dict(qa_dict).to_dict(apply_offsets=True)
    
    qb_scores = qb_dict.get("global_scores", {}) if qb_dict else {}
    qa_scores = qa_dict.get("global_scores", {}) if qa_dict else {}

    response_data = {
        "job_id":  job_id,
        "status":  final_state.get("status"),
        "sector":  final_state.get("sector"),
        "quality_comparison": {
            "before": {
                "global":       qb_scores.get("global"),
                "completeness": qb_scores.get("completeness"),
                "validity":     qb_scores.get("validity"),
                "uniqueness":   qb_scores.get("uniqueness"),
                "accuracy":     qb_scores.get("accuracy"),
                "consistency":  qb_scores.get("consistency"),
            },
            "after": {
                "global":       qa_scores.get("global"),
                "completeness": qa_scores.get("completeness"),
                "validity":     qa_scores.get("validity"),
                "uniqueness":   qa_scores.get("uniqueness"),
                "accuracy":     qa_scores.get("accuracy"),
                "consistency":  qa_scores.get("consistency"),
            },
            "gain": round(
                (qa_scores.get("global", 0) or 0) - (qb_scores.get("global", 0) or 0), 1
            ),
        },
        "quality_by_column": {
            "before": qb_dict.get("columns", []) if qb_dict else [],
            "after":  qa_dict.get("columns", []) if qa_dict else [],
        },
        "cleaning_log": final_state.get("cleaning_log", []),
        "paths": {
            "silver": final_state.get("silver_path"),
            "gold":   final_state.get("gold_path"),
        },
    }
    return JSONResponse(content=json.loads(json.dumps(response_data, default=_serial)))

# ── GET /jobs/{job_id}/status ─────────────────────────────────────────────────

@app.get("/jobs/{job_id}/status")
async def get_status(job_id: str) -> JSONResponse:
    config   = {"configurable": {"thread_id": f"agent_{job_id}"}}
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
    config_import  = {"configurable": {"thread_id": f"import_{job_id}"}}
    config_agent   = {"configurable": {"thread_id": f"agent_{job_id}"}}

    try:
        # 1. Tenter depuis le State (import_graph ou agent_graph)
        try:
            snapshot = import_graph.get_state(config_import)
            if snapshot and snapshot.values:
                summary = snapshot.values.get("profiling_summary")
            if not summary:
                snapshot = agent_graph.get_state(config_agent)
                if snapshot and snapshot.values:
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
        "version": "4.0.0",
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