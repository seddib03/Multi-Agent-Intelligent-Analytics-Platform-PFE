from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from app.schemas.input_schema import UserQueryInput
from app.graph.orchestrator import build_orchestrator_graph
from app.graph.state import OrchestratorState
import shutil, uuid, json, os, tempfile

app = FastAPI(
    title="Orchestrateur - Intelligent Analytics Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = build_orchestrator_graph()


def _normalize_metadata(metadata_parsed) -> dict:
    if isinstance(metadata_parsed, list):
        normalized_cols = []
        for col in metadata_parsed:
            if isinstance(col, dict):
                if "column_name" not in col and "name" in col:
                    col = {**col, "column_name": col["name"]}
                normalized_cols.append(col)
        return {"columns": normalized_cols}

    if isinstance(metadata_parsed, dict):
        cols = metadata_parsed.get("columns", [])
        if cols and isinstance(cols[0], dict):
            normalized_cols = []
            for col in cols:
                if "column_name" not in col and "name" in col:
                    col = {**col, "column_name": col["name"]}
                normalized_cols.append(col)
            return {**metadata_parsed, "columns": normalized_cols}
        return metadata_parsed

    return {}


def run_orchestrator(input_data: UserQueryInput) -> dict:
    initial_state = OrchestratorState(
        user_id=input_data.user_id,
        session_id=input_data.session_id,
        query_raw=input_data.query,
        csv_path=input_data.csv_path or "",
        metadata=input_data.metadata or {},
    )

    result = graph.invoke(initial_state)

    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    return {}


@app.post("/analyze")
async def analyze(
    query_raw:  str        = Form(...),
    dataset:    UploadFile = File(None),
    metadata:   str        = Form("{}"),
    csv_path:   str        = Form(""),   # chemin serveur persisté
):
    resolved_csv_path = None

    # Priorité 1 : chemin serveur fourni par le frontend (persisté dans Zustand)
    if csv_path and os.path.exists(csv_path):
        resolved_csv_path = csv_path
        print(f"[INFO] Using persisted csv_path: {resolved_csv_path}", flush=True)

    # Priorité 2 : fichier uploadé directement
    elif dataset and dataset.filename:
        tmp_dir = os.path.join(tempfile.gettempdir(), "orchestrator")
        os.makedirs(tmp_dir, exist_ok=True)
        resolved_csv_path = os.path.join(tmp_dir, f"{uuid.uuid4()}_{dataset.filename}")
        with open(resolved_csv_path, "wb") as f:
            shutil.copyfileobj(dataset.file, f)
        print(f"[INFO] CSV uploaded and saved to: {resolved_csv_path}", flush=True)

    else:
        print("[WARN] No CSV provided", flush=True)

    try:
        metadata_parsed = json.loads(metadata)
        metadata_dict   = _normalize_metadata(metadata_parsed)
    except json.JSONDecodeError:
        metadata_dict = {}

    result = run_orchestrator(UserQueryInput(
        user_id="demo_user",
        session_id=str(uuid.uuid4()),
        query=query_raw,
        csv_path=resolved_csv_path,
        metadata=metadata_dict,
    ))

    # Nettoyage uniquement si fichier uploadé (pas le fichier persisté)
    if resolved_csv_path and resolved_csv_path != csv_path:
        if os.path.exists(resolved_csv_path):
            os.remove(resolved_csv_path)

    return result


@app.get("/health")
def health():
    return {"status": "ok", "graph": "ready"}