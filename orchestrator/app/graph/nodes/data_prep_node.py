import time
import httpx
from app.graph.state import OrchestratorState, DataPrepStatusEnum
from app.clients.data_prep_client import (
    call_prepare,
    call_get_status,
    call_get_data_profile
)
from app.utils.async_utils import run_async

MAX_WAIT_SECONDS = 300   # 5 minutes max
POLL_INTERVAL    = 5     # vérifier toutes les 5 secondes


def data_prep_node(state: OrchestratorState) -> OrchestratorState:
    """
    Node 3 — Data Preparation Agent (Collègue 2).

    Flow:
    1. Si pas de CSV → skip
    2. Lance POST /prepare → job_id
    3. Polling GET /jobs/{id}/status
    4. Récupère data_profile via /profiling-json
    """

    # ── Cas 1 : pas de CSV → skip ──────────────────────────────────
    if not state.csv_path:
        state.processing_steps.append(
            "data_prep_node → skipped (no CSV provided)"
        )
        return state

    # ── Cas 2 : CSV fourni → lancer le pipeline ────────────────────
    try:
        state = run_async(call_prepare(state))
    except Exception as e:
        state.errors.append(
            f"Data Prep Agent unavailable — continuing without prepared data ({e})"
        )
        state.data_prep_status = DataPrepStatusEnum.FAILED
        state.processing_steps.append("data_prep_node → ERREUR connexion /prepare")
        return state

    if state.data_prep_status == DataPrepStatusEnum.FAILED:
        state.errors.append(
            "Data Prep Agent unavailable — continuing without prepared data"
        )
        return state

    # ── Polling — attendre la fin du job ──────────────────────────
    elapsed = 0
    while elapsed < MAX_WAIT_SECONDS:
        try:
            status_result = run_async(call_get_status(state.data_prep_job_id))
        except httpx.ReadError as e:
            # ✅ FIX : catch explicite du ReadError (service coupé mid-request)
            state.errors.append(
                f"Data Prep service disconnected during polling: {e}"
            )
            state.data_prep_status = DataPrepStatusEnum.FAILED
            break
        except httpx.ConnectError as e:
            state.errors.append(
                f"Data Prep service unreachable during polling: {e}"
            )
            state.data_prep_status = DataPrepStatusEnum.FAILED
            break
        except httpx.TimeoutException as e:
            state.errors.append(
                f"Data Prep polling timeout: {e}"
            )
            state.data_prep_status = DataPrepStatusEnum.FAILED
            break
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

        state.data_prep_status = DataPrepStatusEnum.WAITING_VALIDATION
        state.processing_steps.append(
            f"data_prep_node → waiting_validation ({elapsed}s elapsed)"
        )
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    # ── Récupération du data_profile ───────────────────────────────
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
            # Timeout atteint sans erreur explicite
            state.data_prep_status = DataPrepStatusEnum.FAILED
            state.errors.append(f"Data Prep timeout after {MAX_WAIT_SECONDS}s")

    return state