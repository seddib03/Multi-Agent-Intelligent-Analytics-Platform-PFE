from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from app.schemas.input_schema import UserQueryInput
from app.graph.orchestrator import build_orchestrator_graph
import shutil, uuid, json, os, tempfile
import nest_asyncio
nest_asyncio.apply()

app = FastAPI(
    title="Orchestrateur — Intelligent Analytics Platform",
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
    """
    Normalise la metadata au format attendu par le Collègue 2.

    Collègue 2 attend :
      {"columns": [{"column_name": "age", ...}, ...]}

    L'UI peut envoyer plusieurs formats :
      1. Liste directe  : [{"column_name": "age"}, ...]
      2. Liste (name)   : [{"name": "age"}, ...]
      3. Dict encapsulé : {"columns": [...]}
      4. Dict standard  : {"metadata_path": "...", ...}
    """
    if isinstance(metadata_parsed, list):
        # Normalise chaque colonne : "name" → "column_name"
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
            # Normalise "name" → "column_name" si nécessaire
            normalized_cols = []
            for col in cols:
                if "column_name" not in col and "name" in col:
                    col = {**col, "column_name": col["name"]}
                normalized_cols.append(col)
            return {**metadata_parsed, "columns": normalized_cols}
        return metadata_parsed

    return {}


def run_orchestrator(input_data: UserQueryInput) -> dict:
    initial_state = {
        "user_id":    input_data.user_id,
        "session_id": input_data.session_id,
        "query_raw":  input_data.query,
        "csv_path":   input_data.csv_path or "",
        "metadata":   input_data.metadata or {},
    }
    result = graph.invoke(initial_state)
    # result est un OrchestratorState — on le sérialise
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


@app.post("/analyze")
async def analyze(
    query_raw: str        = Form(...),
    dataset:   UploadFile = File(None),
    metadata:  str        = Form("{}")
):
    """
    Analyze endpoint — multipart/form-data :
    * query_raw (str, required)  : question en langage naturel
    * dataset   (file, optional) : fichier CSV
    * metadata  (str, optional)  : JSON string avec metadata colonnes
    """
    # ── Sauvegarde du CSV ──────────────────────────────────────────
    csv_path = None
    if dataset and dataset.filename:
        tmp_dir = os.path.join(tempfile.gettempdir(), "orchestrator")
        os.makedirs(tmp_dir, exist_ok=True)
        csv_path = os.path.join(tmp_dir, f"{uuid.uuid4()}_{dataset.filename}")
        with open(csv_path, "wb") as f:
            shutil.copyfileobj(dataset.file, f)

    # ── Parsing + normalisation metadata ──────────────────────────
    try:
        metadata_parsed = json.loads(metadata)
        metadata_dict   = _normalize_metadata(metadata_parsed)
    except json.JSONDecodeError:
        metadata_dict = {}

    # ── Lancement du graph ─────────────────────────────────────────
    result = run_orchestrator(UserQueryInput(
        user_id="demo_user",
        session_id=str(uuid.uuid4()),
        query=query_raw,
        csv_path=csv_path,
        metadata=metadata_dict,
    ))

    # ── Nettoyage CSV temporaire ───────────────────────────────────
    if csv_path and os.path.exists(csv_path):
        os.remove(csv_path)

    return result


@app.get("/health")
def health():
    return {"status": "ok", "graph": "ready"}