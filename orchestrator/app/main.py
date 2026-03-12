from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from app.schemas.input_schema import UserQueryInput
from app.graph.orchestrator import build_orchestrator_graph
import shutil, uuid, json, os, tempfile

app = FastAPI(
    title="Orchestrateur — Intelligent Analytics Platform",
    version="1.0.0"
)

# Permettre à l'UI de l'appeler
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Construire le graph une seule fois au démarrage
graph = build_orchestrator_graph()


def run_orchestrator(input_data: UserQueryInput) -> dict:
    """Lance le graph LangGraph et retourne le state final."""
    initial_state = {
        "user_id":    input_data.user_id,
        "session_id": input_data.session_id,
        "query_raw":  input_data.query_raw,
        "csv_path":   input_data.csv_path or "",
        "metadata":   input_data.metadata or {},
    }
    final_state = graph.invoke(initial_state)
    return final_state


@app.post("/analyze")
async def analyze(
    query_raw: str        = Form(...),
    dataset:   UploadFile = File(None),
    metadata:  str        = Form("{}")
):
    # ✅ Compatible Windows ET Linux (tempfile.gettempdir())
    csv_path = None
    if dataset and dataset.filename:
        tmp_dir = os.path.join(tempfile.gettempdir(), "orchestrator")
        os.makedirs(tmp_dir, exist_ok=True)
        csv_path = os.path.join(tmp_dir, f"{uuid.uuid4()}_{dataset.filename}")
        with open(csv_path, "wb") as f:
            shutil.copyfileobj(dataset.file, f)

    try:
        metadata_dict = json.loads(metadata)
    except json.JSONDecodeError:
        metadata_dict = {}

    result = run_orchestrator(UserQueryInput(
        user_id="demo_user",
        session_id=str(uuid.uuid4()),
        query_raw=query_raw,
        csv_path=csv_path,
        metadata=metadata_dict,
    ))

    if csv_path and os.path.exists(csv_path):
        os.remove(csv_path)

    return result


@app.get("/health")
def health():
    return {"status": "ok", "graph": "ready"}

