"""
main.py
────────
API FastAPI V2 avec interface web pour la validation humaine.

ENDPOINTS :
    POST /prepare              → Lancer le pipeline (upload dataset + metadata)
    GET  /jobs/{job_id}/plan   → Récupérer le plan proposé par le LLM
    POST /jobs/{job_id}/validate → Valider / modifier / rejeter le plan
    GET  /jobs/{job_id}/status → Statut du job et résultats
    GET  /history/{sector}     → Historique des runs
    GET  /health               → Santé de l'API

HUMAN-IN-THE-LOOP AVEC LANGGRAPH :
    1. POST /prepare lance le graph jusqu'à strategy_node
       → Le graph s'interrompt avant cleaning_node
       → Retourne job_id + plan proposé

    2. GET /jobs/{job_id}/plan affiche le plan à l'user

    3. POST /jobs/{job_id}/validate reçoit les décisions de l'user
       → Met à jour le cleaning_plan dans le state
       → Reprend le graph depuis cleaning_node

    4. GET /jobs/{job_id}/status retourne les résultats finaux

THREAD_ID LANGGRAPH :
    LangGraph utilise un thread_id pour retrouver
    l'état sauvegardé entre les 2 appels.
    On utilise le job_id comme thread_id.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.graph import agent_graph
from agent.state import build_initial_state
from config.settings import get_settings
from core.storage_manager import StorageManager
from models.cleaning_plan import UserDecision

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Data Preparation Agent V2",
    description=(
        "Agent intelligent de préparation de données "
        "avec LLM + Human-in-the-Loop"
    ),
    version="2.0.0",
)

settings = get_settings()


# ── Modèles Pydantic pour les requêtes ────────────────────────────────────────

class ActionDecision(BaseModel):
    """
    Décision de l'user pour une action du plan.

    Exemple JSON envoyé par l'user :
        {
          "action_id": "action_1",
          "decision": "approved"
        }
    """
    action_id:     str
    decision:      str  # "approved", "modified", "rejected"
    modifications: Optional[dict] = None


class ValidationRequest(BaseModel):
    """
    Corps de la requête POST /jobs/{job_id}/validate.

    L'user envoie ses décisions pour toutes les actions du plan.
    """
    decisions: list[ActionDecision]


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """
    Initialisation au démarrage :
        - Créer les dossiers de stockage
        - Initialiser le Gold Layer DuckDB
    """
    logger.info("Démarrage Data Preparation Agent V2")

    # Créer les dossiers nécessaires
    for directory in [
        settings.bronze_dir,
        settings.silver_dir,
        settings.gold_db_path.parent,
        settings.tmp_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    # Initialiser le Gold Layer
    storage = StorageManager()
    storage.initialize_gold_layer()

    logger.info("Initialisation terminée — API prête sur port %d", settings.api_port)


# ── ENDPOINT 1 : Lancer le pipeline ──────────────────────────────────────────

@app.post("/prepare")
async def prepare(
    dataset:  UploadFile = File(..., description="Fichier de données"),
    metadata: UploadFile = File(..., description="Fichier metadata JSON"),
) -> JSONResponse:
    """
    Lance le pipeline de préparation de données.

    Le pipeline s'exécute jusqu'à strategy_node puis s'interrompt
    pour attendre la validation humaine du plan de nettoyage.

    Returns:
        job_id, status="waiting_validation", plan proposé par le LLM
    """
    job_id = str(uuid.uuid4())
    logger.info("Nouveau job démarré : %s", job_id)

    # ── Sauvegarder les fichiers uploadés en tmp ──────────────────────────────
    tmp_dir = settings.tmp_dir / job_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    dataset_path  = tmp_dir / dataset.filename
    metadata_path = tmp_dir / metadata.filename

    with open(dataset_path, "wb") as f:
        shutil.copyfileobj(dataset.file, f)

    with open(metadata_path, "wb") as f:
        shutil.copyfileobj(metadata.file, f)

    # ── Construire l'état initial ─────────────────────────────────────────────
    initial_state = build_initial_state(
        job_id=job_id,
        dataset_path=str(dataset_path),
        metadata_path=str(metadata_path),
    )

    # ── Lancer le graph ───────────────────────────────────────────────────────
    # config = {"configurable": {"thread_id": job_id}}
    # → LangGraph utilise thread_id pour sauvegarder/retrouver l'état
    config = {"configurable": {"thread_id": job_id}}

    try:
        # Le graph s'exécute jusqu'à l'interruption (avant cleaning_node)
        final_state = agent_graph.invoke(initial_state, config=config)

    except Exception as e:
        logger.error("Erreur pipeline job %s : %s", job_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

    # ── Construire la réponse ─────────────────────────────────────────────────
    cleaning_plan = final_state.get("cleaning_plan")

    return JSONResponse({
        "job_id":          job_id,
        "status":          "waiting_validation",
        "sector":          final_state.get("sector", "unknown"),
        "profiling_summary": (
            final_state["profiling_report"].build_llm_summary()
            if final_state.get("profiling_report") else ""
        ),
        "llm_analysis":    final_state.get("llm_analysis", ""),
        "plan":            cleaning_plan.to_dict() if cleaning_plan else {},
        "message": (
            "Plan de nettoyage proposé. "
            f"Validez via POST /jobs/{job_id}/validate "
            f"ou consultez l'interface web à GET /"
        ),
    })


# ── ENDPOINT 2 : Récupérer le plan ───────────────────────────────────────────

@app.get("/jobs/{job_id}/plan")
async def get_plan(job_id: str) -> JSONResponse:
    """
    Retourne le plan de nettoyage proposé pour un job.
    """
    config = {"configurable": {"thread_id": job_id}}

    try:
        # Récupérer l'état sauvegardé par le checkpointer
        current_state = agent_graph.get_state(config)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} introuvable",
        )

    if not current_state.values:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun état trouvé pour le job {job_id}",
        )

    state         = current_state.values
    cleaning_plan = state.get("cleaning_plan")

    if not cleaning_plan:
        raise HTTPException(
            status_code=404,
            detail="Aucun plan de nettoyage trouvé pour ce job",
        )

    return JSONResponse({
        "job_id":         job_id,
        "status":         state.get("status", "unknown"),
        "llm_analysis":   state.get("llm_analysis", ""),
        "plan":           cleaning_plan.to_dict(),
    })


# ── ENDPOINT 3 : Valider le plan ─────────────────────────────────────────────

@app.post("/jobs/{job_id}/validate")
async def validate_plan(
    job_id:  str,
    payload: ValidationRequest,
) -> JSONResponse:
    """
    Reçoit les décisions de l'user et reprend le pipeline.

    L'user envoie une décision pour chaque action du plan.
    Le graph reprend depuis cleaning_node et s'exécute
    jusqu'à la fin (evaluation → delivery).

    Args:
        job_id:  ID du job à reprendre
        payload: Décisions de l'user pour chaque action

    Returns:
        Résultats complets du pipeline (score, rapport, logs)
    """
    config = {"configurable": {"thread_id": job_id}}

    # ── Récupérer l'état sauvegardé ───────────────────────────────────────────
    try:
        current_state_snapshot = agent_graph.get_state(config)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} introuvable",
        )

    state         = dict(current_state_snapshot.values)
    cleaning_plan = state.get("cleaning_plan")

    if not cleaning_plan:
        raise HTTPException(
            status_code=400,
            detail="Aucun plan à valider pour ce job",
        )

    # ── Appliquer les décisions de l'user ────────────────────────────────────
    decisions_map = {d.action_id: d for d in payload.decisions}

    for action in cleaning_plan.actions:
        if action.action_id in decisions_map:
            decision_obj = decisions_map[action.action_id]

            # Convertir la string en enum UserDecision
            try:
                action.user_decision    = UserDecision(decision_obj.decision)
                action.user_modifications = decision_obj.modifications
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Décision invalide '{decision_obj.decision}'. "
                        f"Valeurs acceptées : approved, modified, rejected"
                    ),
                )

    if not cleaning_plan.is_fully_validated:
        missing = [
            a.action_id for a in cleaning_plan.actions
            if a.user_decision is None
        ]
        raise HTTPException(
            status_code=400,
            detail=f"Actions sans décision : {missing}",
        )

    cleaning_plan.status = "validated"

    # ── Mettre à jour le state et reprendre le graph ──────────────────────────
    # update_state() modifie l'état sauvegardé dans le checkpointer
    agent_graph.update_state(
        config,
        {"cleaning_plan": cleaning_plan},
        as_node="strategy",  # Indiquer depuis quel node on met à jour
    )

    # Reprendre l'exécution depuis cleaning_node
    try:
        final_state = agent_graph.invoke(None, config=config)
    except Exception as e:
        logger.error("Erreur reprise pipeline %s : %s", job_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

    # ── Construire la réponse finale ──────────────────────────────────────────
    dimensions_after = final_state.get("dimensions_after")

    return JSONResponse({
        "job_id":   job_id,
        "status":   final_state.get("status", "unknown"),
        "sector":   final_state.get("sector", "unknown"),

        "quality_dimensions": (
            dimensions_after.to_dict()
            if dimensions_after else {}
        ),

        "llm_evaluation": final_state.get("llm_evaluation", ""),

        "before_after": {
            "before": final_state.get("profile_before", {}),
            "after":  final_state.get("profile_after", {}),
        },

        "cleaning_log": final_state.get("cleaning_log", []),

        "paths": {
            "bronze": final_state.get("bronze_path", ""),
            "silver": final_state.get("silver_path", ""),
        },

        "started_at":   final_state.get("started_at", ""),
        "completed_at": final_state.get("completed_at", ""),
    })


# ── ENDPOINT 4 : Statut d'un job ──────────────────────────────────────────────

@app.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str) -> JSONResponse:
    """Retourne le statut courant d'un job."""
    config = {"configurable": {"thread_id": job_id}}

    try:
        snapshot = agent_graph.get_state(config)
        state    = snapshot.values
    except Exception:
        raise HTTPException(status_code=404, detail=f"Job {job_id} introuvable")

    return JSONResponse({
        "job_id": job_id,
        "status": state.get("status", "unknown"),
        "sector": state.get("sector", "unknown"),
        "errors": state.get("errors", []),
    })


# ── ENDPOINT 5 : Historique ───────────────────────────────────────────────────

@app.get("/history/{sector}")
async def get_history(sector: str) -> JSONResponse:
    """Retourne l'historique des 50 derniers runs pour un secteur."""
    storage = StorageManager()
    history = storage.get_sector_history(sector)
    return JSONResponse({"sector": sector, "runs": history})


# ── ENDPOINT 6 : Health ───────────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    """Vérification basique que l'API tourne."""
    return JSONResponse({"status": "ok", "version": "2.0.0"})
