import asyncio
import time
from app.graph.state import OrchestratorState, DataPrepStatusEnum
from app.clients.data_prep_client import (
    call_prepare,
    call_get_status,
    call_get_data_profile
)

MAX_WAIT_SECONDS = 300   # 5 minutes max pour la validation utilisateur
POLL_INTERVAL    = 5     # vérifier le statut toutes les 5 secondes

def data_prep_node(state: OrchestratorState) -> OrchestratorState:
    """
    Node 3 of the LangGraph graph — Data Preparation Agent.

    Role: prepares and cleans data before analysis.

    Flow:
    1. If no CSV → skip (data already in Data Lake)
    2. Launches POST /prepare → job_id + anomalies plan
    3. Polling GET /jobs/{id}/status
       → "waiting_validation": waits for user validation in UI
       → "completed": continue
       → "failed": error, continue without data
    4. Retrieves data_profile via /profiling-json
       → will be passed to NLQ /chat to generate precise SQL
    """

    # ── Case 1: no CSV provided → skip ──────────────────────────
    if not state.csv_path:
        state.processing_steps.append(
            "data_prep_node → skipped (no CSV provided)"
        )
        return state

    # ── Case 2: CSV provided → launch pipeline ───────────────────
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    state = loop.run_until_complete(call_prepare(state))

    # If connection error → continue without prepared data
    if state.data_prep_status == DataPrepStatusEnum.FAILED:
        state.errors.append(
            "Data Prep Agent unavailable — continuing without prepared data"
        )
        return state

    # ── Polling — wait for job to complete ───────────────
    # The job pauses (waiting_validation) and waits
    # for the user to validate the cleaning plan in the UI.
    elapsed = 0
    while elapsed < MAX_WAIT_SECONDS:

        status_result  = loop.run_until_complete(
            call_get_status(state.data_prep_job_id)
        )
        current_status = status_result.get("status", "")

        if current_status == "completed":
            state.data_prep_status = DataPrepStatusEnum.COMPLETED
            state.data_prep_paths  = status_result.get("paths", {})
            break

        if current_status == "failed":
            state.data_prep_status = DataPrepStatusEnum.FAILED
            state.data_prep_error  = str(
                status_result.get("errors", [])
            )
            state.errors.append(
                f"Data Prep failed: {state.data_prep_error}"
            )
            return state

        # En attente validation → on logue et on attend
        state.data_prep_status = DataPrepStatusEnum.WAITING_VALIDATION
        state.processing_steps.append(
            f"data_prep_node → waiting_validation "
            f"({elapsed}s elapsed)"
        )
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    # ── Retrieve data_profile for NLQ Agent ───────────────
    if state.data_prep_status == DataPrepStatusEnum.COMPLETED:
        state = loop.run_until_complete(call_get_data_profile(state))
        state.processing_steps.append(
            f"data_prep_node → COMPLETED | "
            f"silver={state.data_prep_paths.get('silver', 'N/A')}"
        )
    else:
        # Timeout exceeded
        state.data_prep_status = DataPrepStatusEnum.FAILED
        state.errors.append(
            f"Data Prep timeout after {MAX_WAIT_SECONDS}s"
        )

    return state