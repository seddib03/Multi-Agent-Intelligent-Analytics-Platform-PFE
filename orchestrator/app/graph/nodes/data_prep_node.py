import time
from app.graph.state import OrchestratorState, DataPrepStatusEnum
from app.clients.data_prep_client import (
    call_import,
    call_prepare_v2,
    call_get_status,
    call_get_data_profile
)
from app.utils.async_utils import run_async

MAX_WAIT_SECONDS = 300
POLL_INTERVAL    = 5


def data_prep_node(state: OrchestratorState) -> OrchestratorState:
    """
    Node 3 — Data Preparation Agent (Collègue 2).

    Flux en 2 étapes (restructuration Sprint 2) :
    1. POST /import          → CSV uniquement → job_id + profiling disponible
    2. POST /prepare/{id}    → metadata + règles métier → anomalies + plan LLM
    3. Polling /status       → waiting_validation (Human-in-the-Loop côté UI)
    4. GET /profiling-json   → data_profile pour NLQ Agent
    """

    # ── Pas de CSV → skip ─────────────────────────────────────────
    if not state.csv_path:
        state.processing_steps.append("data_prep_node → skipped (no CSV)")
        return state

    # ── Étape 1 : Import CSV ───────────────────────────────────────
    try:
        state = run_async(call_import(state))
    except Exception as e:
        state.errors.append(f"Data Prep /import error: {e}")
        state.data_prep_status = DataPrepStatusEnum.FAILED
        state.processing_steps.append("data_prep_node → ERREUR /import")
        return state

    if state.data_prep_status == DataPrepStatusEnum.FAILED:
        state.errors.append("Data Prep /import failed — continuing without prep")
        return state

    # ── Étape 2 : Qualité + metadata ──────────────────────────────
    # Seulement si la metadata est disponible
    if state.metadata:
        try:
            state = run_async(call_prepare_v2(state))
        except Exception as e:
            state.errors.append(f"Data Prep /prepare error: {e}")
            # On continue — le CSV brut est déjà disponible via /import
            state.processing_steps.append(
                "data_prep_node → /prepare échoué, CSV brut disponible"
            )

    if state.data_prep_status == DataPrepStatusEnum.FAILED:
        state.errors.append("Data Prep /prepare failed — continuing without prep")
        return state

    # ── Étape 3 : Polling — attendre fin du job ───────────────────
    # Le job se met en waiting_validation si des anomalies sont détectées
    # L'UI doit appeler /validate pour débloquer
    elapsed = 0
    while elapsed < MAX_WAIT_SECONDS:
        try:
            status_result = run_async(call_get_status(state.data_prep_job_id))
        except Exception as e:
            state.errors.append(f"Data Prep polling error: {e}")
            state.data_prep_status = DataPrepStatusEnum.FAILED
            break

        current_status = status_result.get("status", "")

        if current_status == "completed":
            state.data_prep_status = DataPrepStatusEnum.COMPLETED
            state.data_prep_paths  = status_result.get("paths", {})
            break

        if current_status == "failed":
            state.data_prep_status = DataPrepStatusEnum.FAILED
            state.data_prep_error  = str(status_result.get("errors", []))
            state.errors.append(f"Data Prep failed: {state.data_prep_error}")
            return state

        # waiting_validation ou running → on attend
        state.data_prep_status = DataPrepStatusEnum.WAITING_VALIDATION
        state.processing_steps.append(
            f"data_prep_node → {current_status} ({elapsed}s elapsed)"
        )
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    # ── Étape 4 : Récupération du data_profile ────────────────────
    if state.data_prep_status == DataPrepStatusEnum.COMPLETED:
        try:
            state = run_async(call_get_data_profile(state))
        except Exception as e:
            state.errors.append(f"Data Prep profiling error: {e}")

        state.processing_steps.append(
            f"data_prep_node → COMPLETED | "
            f"silver={state.data_prep_paths.get('silver', 'N/A')}"
        )
    else:
        if state.data_prep_status != DataPrepStatusEnum.FAILED:
            state.data_prep_status = DataPrepStatusEnum.FAILED
            state.errors.append(f"Data Prep timeout after {MAX_WAIT_SECONDS}s")

    return state