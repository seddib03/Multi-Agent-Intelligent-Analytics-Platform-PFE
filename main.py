"""
main.py — FastAPI V3
━━━━━━━━━━━━━━━━━━━━
ENDPOINTS :
    POST /prepare                    → lancer le pipeline
    GET  /jobs/{job_id}/plan         → récupérer le plan proposé
    POST /jobs/{job_id}/validate     → valider le plan et exécuter
    GET  /jobs/{job_id}/status       → statut + résultats
    GET  /jobs/{job_id}/quality      → scores qualité AVANT/APRÈS
    GET  /health                     → santé API
"""
from __future__ import annotations
import logging, shutil, uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
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
    decision:      str          # approved | modified | rejected
    chosen_action: Optional[str] = None   # action choisie parmi action_1/2/3
    params:        Optional[dict] = None  # paramètres modifiés

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
    """
    Lance le pipeline jusqu'à strategy_node.
    Retourne le plan de nettoyage proposé (règles + LLM).
    """
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
        "job_id":  job_id,
        "status":  "waiting_validation",
        "sector":  state.get("sector", "unknown"),

        # Scores qualité AVANT
        "quality_before": quality_before if quality_before else {},

        # Résumé LLM
        "llm_summary": state.get("llm_summary", ""),

        # Plan complet avec anomalies + actions proposées
        "plan": cleaning_plan.to_dict() if cleaning_plan else {},

        "message": f"Plan prêt. Validez via POST /jobs/{job_id}/validate",
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
        "job_id":       job_id,
        "status":       state.get("status"),
        "llm_summary":  state.get("llm_summary",""),
        "plan":         cleaning_plan.to_dict(),
        "quality_before": state.get("quality_before") or {},
    })


# ── POST /jobs/{job_id}/validate ──────────────────────────────────────────────

@app.post("/jobs/{job_id}/validate")
async def validate_plan(job_id: str, payload: ValidationRequest) -> JSONResponse:
    """
    Reçoit les décisions de l'user sur chaque anomalie.
    Reprend le graph depuis cleaning_node.
    Retourne les scores AVANT / APRÈS.
    """
    config   = {"configurable": {"thread_id": job_id}}
    snapshot = _get_snapshot(job_id, config)
    state    = snapshot.values

    cleaning_plan = state.get("cleaning_plan")
    if not cleaning_plan:
        raise HTTPException(status_code=400, detail="Aucun plan à valider")

    # ── Appliquer les décisions ───────────────────────────────────────────
    decisions_map = {d.anomaly_id: d for d in payload.decisions}

    for anomaly in cleaning_plan.anomalies:
        if anomaly.anomaly_id not in decisions_map:
            raise HTTPException(
                status_code=400,
                detail=f"Décision manquante pour {anomaly.anomaly_id}",
            )
        dec = decisions_map[anomaly.anomaly_id]

        try:
            anomaly.user_decision = UserDecision(dec.decision)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Décision invalide '{dec.decision}'. Valeurs: approved|modified|rejected",
            )

        # Action choisie par l'user (action_1, action_2 ou action_3)
        if dec.chosen_action:
            try:
                anomaly.chosen_action = CleaningAction(dec.chosen_action)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Action inconnue : {dec.chosen_action}",
                )
        else:
            # Par défaut : action_1 (conservative)
            anomaly.chosen_action = anomaly.action_1

        if dec.params:
            anomaly.user_params = dec.params

    cleaning_plan.status = "validated"

    # ── Mettre à jour le state et reprendre ──────────────────────────────
    agent_graph.update_state(config, {"cleaning_plan": cleaning_plan}, as_node="strategy")

    try:
        final_state = agent_graph.invoke(None, config=config)
    except Exception as e:
        logger.error("Erreur reprise %s : %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    qb = final_state.get("quality_before") or {}
    qa = final_state.get("quality_after") or {}

    qb_scores = qb.get("global_scores", {})
    qa_scores = qa.get("global_scores", {})

    return JSONResponse({
        "job_id":  job_id,
        "status":  final_state.get("status"),
        "sector":  final_state.get("sector"),

        # Comparaison AVANT / APRÈS
        "quality_comparison": {
            "before": {
                "global":        qb_scores.get("global"),
                "completeness":  qb_scores.get("completeness"),
                "validity":      qb_scores.get("validity"),
                "uniqueness":    qb_scores.get("uniqueness"),
            },
            "after": {
                "global":        qa_scores.get("global"),
                "completeness":  qa_scores.get("completeness"),
                "validity":      qa_scores.get("validity"),
                "uniqueness":    qa_scores.get("uniqueness"),
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


