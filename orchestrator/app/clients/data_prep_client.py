import httpx
import os
import json
from dotenv import load_dotenv
from app.graph.state import OrchestratorState, DataPrepStatusEnum

load_dotenv()
DATA_PREP_API_URL = os.getenv("DATA_PREP_API_URL", "http://localhost:8001")

async def call_prepare(
    state: OrchestratorState
) -> OrchestratorState:
    """
    Calls POST /prepare
    Launches the Data Prep pipeline (Nodes 1 to 5).
    Automatically stops awaiting user validation.

    Input  : csv_path + metadata from State
    Output : job_id + quality_before + anomalies plan
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(state.csv_path, "rb") as f:
                response = await client.post(
                    f"{DATA_PREP_API_URL}/prepare",
                    files={"dataset": f},
                    data={"metadata": json.dumps(state.metadata)}
                )
                result = response.json()
                state.data_prep_job_id = result.get("job_id", "")
                state.data_prep_status = DataPrepStatusEnum(
                    result.get("status", "not_started")
        )
                state.data_prep_quality = result.get(
                    "quality_before", {}
                ).get("global_scores", {})

                state.processing_steps.append(
                    f"data_prep → job_id={state.data_prep_job_id} | "
                    f"status={state.data_prep_status.value} | "
                    f"quality={state.data_prep_quality.get('global', 0):.0%}"
        )
    except httpx.ConnectError:
        state.data_prep_error = " Data Prep API unavailable"
        state.data_prep_status = DataPrepStatusEnum.FAILED
        state.processing_steps.append(
            "data_prep → API connection ERROR"
        )

    return state

async def call_get_status(job_id: str) -> dict:
    """
    Calls GET /jobs/{job_id}/status
    Checks if pipeline is completed or awaiting validation.

    Returns : {"job_id": "...", "status": "completed", "errors": []}
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{DATA_PREP_API_URL}/jobs/{job_id}/status"
        )
        return response.json()


async def call_get_data_profile(
    state: OrchestratorState
) -> OrchestratorState:
    """
    Calls GET /jobs/{job_id}/profiling-json
    Retrieves the statistical profile of the cleaned dataset.

    This profile is then passed to the NLQ Agent via POST /chat
    so it generates SQL with the actual column names.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{DATA_PREP_API_URL}/jobs/"
                f"{state.data_prep_job_id}/profiling-json"
            )
            profiling = response.json()

        summary      = profiling.get("summary", {})
        columns_info = summary.get("columns", {})

        # Format in the format expected by the NLQ Agent /chat
        state.data_profile = {
            "row_count": summary.get(
                "dataset", {}
            ).get("total_rows", 0),
            "columns": list(columns_info.keys()),
            "numeric_columns": [
                col for col, info in columns_info.items()
                if info.get("type") == "Numeric"
            ],
            "categorical_columns": [
                col for col, info in columns_info.items()
                if info.get("type") == "Categorical"
            ],
            "missing_summary": {
                col: info.get("missing_pct", 0)
                for col, info in columns_info.items()
                if info.get("missing_pct", 0) > 0
            },
            "quality_score": state.data_prep_quality.get(
                "global", 0
            ) * 100
        }

        state.processing_steps.append(
            f"data_profile → "
            f"{state.data_profile['row_count']} rows | "
            f"{len(state.data_profile['columns'])} columns"
        )

    except Exception as e:
        state.errors.append(f"Profiling error: {str(e)}")

    return state
                