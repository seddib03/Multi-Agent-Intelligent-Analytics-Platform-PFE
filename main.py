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
    GET  /                     → Interface web de validation

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
from fastapi.responses import HTMLResponse, JSONResponse
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


# ── ENDPOINT 7 : Interface web ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def web_interface() -> HTMLResponse:
    """
    Interface web pour uploader un dataset et valider le plan.

    Page HTML simple avec :
        1. Formulaire d'upload (dataset + metadata)
        2. Affichage du plan LLM
        3. Boutons Approuver / Rejeter par action
        4. Affichage des résultats finaux
    """
    html = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Preparation Agent V2</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; color: #1a3c5e; }

        .header { background: #1a3c5e; color: white; padding: 24px 40px; }
        .header h1 { font-size: 1.8rem; }
        .header p  { opacity: 0.7; margin-top: 4px; }

        .container { max-width: 900px; margin: 32px auto; padding: 0 20px; }

        .card { background: white; border-radius: 12px; padding: 28px;
                box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 24px; }
        .card h2 { font-size: 1.2rem; color: #1a3c5e; margin-bottom: 16px;
                   border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }

        input[type="file"] { width: 100%; padding: 10px; border: 2px dashed #cbd5e0;
                              border-radius: 8px; margin-bottom: 12px; cursor: pointer; }
        button { background: #2563eb; color: white; border: none; padding: 12px 24px;
                 border-radius: 8px; cursor: pointer; font-size: 1rem; font-weight: 600; }
        button:hover { background: #1d4ed8; }
        button.approve { background: #16a34a; }
        button.reject  { background: #dc2626; }
        button.approve:hover { background: #15803d; }
        button.reject:hover  { background: #b91c1c; }

        .action-card { border: 1px solid #e2e8f0; border-radius: 8px;
                       padding: 16px; margin-bottom: 12px; }
        .action-card .severity-BLOCKING { border-left: 4px solid #dc2626; }
        .action-card .severity-MAJOR    { border-left: 4px solid #d97706; }
        .action-card .severity-MINOR    { border-left: 4px solid #2563eb; }
        .action-header { display: flex; justify-content: space-between;
                         align-items: center; margin-bottom: 8px; }
        .badge { padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;
                 font-weight: 600; }
        .badge.BLOCKING { background: #fecaca; color: #dc2626; }
        .badge.MAJOR    { background: #fde68a; color: #d97706; }
        .badge.MINOR    { background: #bfdbfe; color: #2563eb; }
        .action-btns    { display: flex; gap: 8px; margin-top: 10px; }
        .action-btns button { padding: 6px 16px; font-size: 0.85rem; }

        .score-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
        .score-box  { text-align: center; padding: 16px; border-radius: 8px;
                      background: #eff6ff; }
        .score-box .value { font-size: 1.8rem; font-weight: 700; color: #1a3c5e; }
        .score-box .label { font-size: 0.75rem; color: #64748b; margin-top: 4px; }

        .llm-box { background: #f8fafc; border-left: 4px solid #2563eb;
                   padding: 16px; border-radius: 0 8px 8px 0; font-style: italic;
                   color: #334155; line-height: 1.6; }

        #status-bar { padding: 12px 20px; border-radius: 8px; margin-bottom: 16px;
                      font-weight: 600; display: none; }
        .status-info    { background: #bfdbfe; color: #1e40af; }
        .status-success { background: #bbf7d0; color: #166534; }
        .status-error   { background: #fecaca; color: #dc2626; }

        .hidden { display: none; }
        .loader { text-align: center; padding: 20px; color: #64748b; }
    </style>
</head>
<body>

<div class="header">
    <h1>🤖 Data Preparation Agent V2</h1>
    <p>LLM-powered · Human-in-the-Loop · 5 Quality Dimensions</p>
</div>

<div class="container">

    <div id="status-bar"></div>

    <!-- ÉTAPE 1 : Upload -->
    <div class="card" id="upload-section">
        <h2>📁 Étape 1 — Charger le dataset</h2>
        <div>
            <label>Dataset (CSV, Excel, JSON, Parquet)</label>
            <input type="file" id="dataset-file" accept=".csv,.xlsx,.json,.parquet">
        </div>
        <div>
            <label>Metadata (JSON)</label>
            <input type="file" id="metadata-file" accept=".json">
        </div>
        <button onclick="launchPipeline()">🚀 Analyser et Proposer un Plan</button>
    </div>

    <!-- ÉTAPE 2 : Plan LLM -->
    <div class="card hidden" id="plan-section">
        <h2>🧠 Étape 2 — Plan proposé par le LLM</h2>
        <div class="llm-box" id="llm-analysis"></div>
        <br>
        <div id="actions-list"></div>
        <br>
        <button onclick="submitValidation()" style="width:100%; padding:16px;">
            ✅ Valider le plan et exécuter le nettoyage
        </button>
    </div>

    <!-- ÉTAPE 3 : Résultats -->
    <div class="card hidden" id="results-section">
        <h2>📊 Étape 3 — Résultats de qualité</h2>
        <div class="llm-box" id="llm-evaluation"></div>
        <br>
        <div class="score-grid" id="scores-grid"></div>
    </div>

</div>

<script>
let currentJobId = null;
let currentPlan  = null;
// Stocke la décision de l'user pour chaque action
let userDecisions = {};

// ── Lancer le pipeline ─────────────────────────────────────────────────────
async function launchPipeline() {
    const datasetFile  = document.getElementById('dataset-file').files[0];
    const metadataFile = document.getElementById('metadata-file').files[0];

    if (!datasetFile || !metadataFile) {
        showStatus('Veuillez sélectionner les 2 fichiers.', 'error');
        return;
    }

    showStatus('🔄 Analyse en cours... (profiling + LLM)', 'info');

    const formData = new FormData();
    formData.append('dataset',  datasetFile);
    formData.append('metadata', metadataFile);

    try {
        const response = await fetch('/prepare', { method: 'POST', body: formData });
        const data     = await response.json();

        if (!response.ok) {
            showStatus('Erreur : ' + (data.detail || 'Erreur serveur'), 'error');
            return;
        }

        currentJobId = data.job_id;
        currentPlan  = data.plan;

        displayPlan(data.plan, data.llm_analysis);
        showStatus(
            '✓ Analyse terminée. Revoyez le plan et validez chaque action.',
            'info'
        );

    } catch (err) {
        showStatus('Erreur réseau : ' + err.message, 'error');
    }
}

// ── Afficher le plan LLM ───────────────────────────────────────────────────
function displayPlan(plan, llmAnalysis) {
    document.getElementById('llm-analysis').textContent = llmAnalysis;

    const actionsList = document.getElementById('actions-list');
    actionsList.innerHTML = '';
    userDecisions = {};

    plan.actions.forEach(action => {
        // Décision par défaut : approuvé
        userDecisions[action.action_id] = 'approved';

        const lignes = action.lignes_concernees.length > 0
            ? `Lignes : ${action.lignes_concernees.join(', ')}`
            : 'Toute la colonne';

        const div = document.createElement('div');
        div.className = `action-card severity-${action.severite}`;
        div.innerHTML = `
            <div class="action-header">
                <strong>${action.colonne}</strong>
                <span class="badge ${action.severite}">${action.severite}</span>
            </div>
            <div style="color:#64748b; font-size:0.85rem; margin-bottom:4px;">
                ${lignes} · Dimension: ${action.dimension}
            </div>
            <div><strong>Problème :</strong> ${action.probleme}</div>
            <div><strong>Action :</strong> <code>${action.action}</code></div>
            <div><strong>Justification :</strong> ${action.justification}</div>
            <div class="action-btns">
                <button class="approve" id="btn-approve-${action.action_id}"
                    onclick="setDecision('${action.action_id}', 'approved')">
                    ✓ Approuver
                </button>
                <button class="reject" id="btn-reject-${action.action_id}"
                    onclick="setDecision('${action.action_id}', 'rejected')">
                    ✗ Rejeter
                </button>
            </div>
        `;
        actionsList.appendChild(div);
    });

    document.getElementById('plan-section').classList.remove('hidden');
}

// ── Gérer les décisions ────────────────────────────────────────────────────
function setDecision(actionId, decision) {
    userDecisions[actionId] = decision;

    // Feedback visuel
    const approveBtn = document.getElementById(`btn-approve-${actionId}`);
    const rejectBtn  = document.getElementById(`btn-reject-${actionId}`);

    if (decision === 'approved') {
        approveBtn.style.opacity = '1';
        rejectBtn.style.opacity  = '0.4';
    } else {
        approveBtn.style.opacity = '0.4';
        rejectBtn.style.opacity  = '1';
    }
}

// ── Soumettre la validation ────────────────────────────────────────────────
async function submitValidation() {
    if (!currentJobId) return;

    showStatus('🔄 Exécution du nettoyage en cours...', 'info');

    const decisions = Object.entries(userDecisions).map(([action_id, decision]) => ({
        action_id,
        decision,
    }));

    try {
        const response = await fetch(`/jobs/${currentJobId}/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ decisions }),
        });

        const data = await response.json();

        if (!response.ok) {
            showStatus('Erreur : ' + (data.detail || 'Erreur serveur'), 'error');
            return;
        }

        displayResults(data);
        showStatus('✅ Pipeline terminé avec succès !', 'success');

    } catch (err) {
        showStatus('Erreur réseau : ' + err.message, 'error');
    }
}

// ── Afficher les résultats ─────────────────────────────────────────────────
function displayResults(data) {
    document.getElementById('llm-evaluation').textContent =
        data.llm_evaluation || 'Analyse disponible dans le rapport JSON.';

    const grid     = document.getElementById('scores-grid');
    const dims     = data.quality_dimensions?.dimensions || {};
    const dimNames = ['completeness', 'uniqueness', 'validity',
                      'consistency', 'accuracy'];

    grid.innerHTML = dimNames.map(name => {
        const d     = dims[name] || {};
        const score = d.score ?? 0;
        const color = score >= 90 ? '#16a34a' : score >= 70 ? '#d97706' : '#dc2626';
        return `
            <div class="score-box">
                <div class="value" style="color:${color}">${score.toFixed(1)}%</div>
                <div class="label">${name.charAt(0).toUpperCase() + name.slice(1)}</div>
            </div>
        `;
    }).join('');

    // Score global
    const globalScore = data.quality_dimensions?.global_score ?? 0;
    grid.innerHTML += `
        <div class="score-box" style="background:#1a3c5e; color:white; grid-column: span 5;">
            <div class="value" style="color:white">${globalScore.toFixed(1)}%</div>
            <div class="label" style="color:#93c5fd">Score Global Pondéré</div>
        </div>
    `;

    document.getElementById('results-section').classList.remove('hidden');
}

// ── Helper affichage statut ────────────────────────────────────────────────
function showStatus(message, type) {
    const bar       = document.getElementById('status-bar');
    bar.textContent = message;
    bar.className   = `status-${type}`;
    bar.style.display = 'block';
}
</script>

</body>
</html>
    """
    return HTMLResponse(content=html)