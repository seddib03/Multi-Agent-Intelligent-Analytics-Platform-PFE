import asyncio
import json
import os
from app.graph.state import OrchestratorState, DataPrepStatusEnum
from app.clients.data_prep_client import (
    call_prepare,
    call_get_status,
    call_get_data_profile
)

# ── Créer un CSV de test minimal ──────────────────────────────────
TEST_CSV = "test_flights.csv"
TEST_METADATA = {
    "table_name": "flights",
    "columns": [
        {"name": "flight_id",    "type": "integer", "nullable": False, "unique": True},
        {"name": "delay_minutes","type": "float",   "min_val": 0, "max_val": 500},
        {"name": "gate",         "type": "string",  "nullable": True},
        {"name": "satisfaction", "type": "float",   "min_val": 0, "max_val": 5}
    ],
    "business_rules": ["delay_minutes must be >= 0"]
}

def create_test_csv():
    content = """flight_id,delay_minutes,gate,satisfaction
1,15,A1,4.2
2,0,B2,4.8
3,-5,C3,3.1
4,120,A1,2.5
5,45,,4.0
6,999,B2,5.1
"""
    with open(TEST_CSV, "w") as f:
        f.write(content)
    print(f"✅ CSV de test créé : {TEST_CSV}")


async def test():
    create_test_csv()

    state = OrchestratorState(
        user_id="u_test",
        session_id="sess_test",
        query_raw="améliorer l expérience des passagers",
        csv_path=TEST_CSV,
        metadata=TEST_METADATA
    )

    # ── Étape 1 : POST /prepare ───────────────────────────────────
    print("\n── Étape 1 : Lancement POST /prepare ──")
    state = await call_prepare(state)
    print(f"job_id  : {state.data_prep_job_id}")
    print(f"status  : {state.data_prep_status.value}")
    print(f"quality : {state.data_prep_quality}")

    if state.data_prep_status == DataPrepStatusEnum.FAILED:
        print("❌ Échec — vérifier que l'API et MinIO sont lancés")
        return

    # ── Étape 2 : Polling GET /jobs/{id}/status ───────────────────
    print("\n── Étape 2 : Polling statut ──")
    print("⏸  En attente de validation utilisateur...")
    print(f"👉 Va sur http://localhost:8000/docs")
    print(f"   POST /jobs/{state.data_prep_job_id}/validate")
    print("""   Body: {
     "decisions": [
       {"anomaly_id": "anom_001", "decision": "approved",
        "chosen_action": "clip_range", "params": {}}
     ]
   }""")
    print("\nAppuie sur Entrée une fois la validation faite...")
    input()

    status_result = await call_get_status(state.data_prep_job_id)
    print(f"status après validation : {status_result.get('status')}")

    if status_result.get("status") == "completed":
        state.data_prep_status = DataPrepStatusEnum.COMPLETED
        state.data_prep_paths  = status_result.get("paths", {})

    # ── Étape 3 : GET /profiling-json ─────────────────────────────
    print("\n── Étape 3 : Récupération data_profile ──")
    state = await call_get_data_profile(state)
    print(f"row_count         : {state.data_profile.get('row_count')}")
    print(f"columns           : {state.data_profile.get('columns')}")
    print(f"numeric_columns   : {state.data_profile.get('numeric_columns')}")
    print(f"quality_score     : {state.data_profile.get('quality_score')}")
    print(f"\nSteps : {state.processing_steps}")

    # Nettoyage
    os.remove(TEST_CSV)
    print("\n✅ Test réel Data Prep Agent terminé !")


asyncio.run(test())
