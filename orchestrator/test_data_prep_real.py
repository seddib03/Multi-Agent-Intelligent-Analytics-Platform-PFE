import asyncio
import httpx
import os
from app.graph.state import OrchestratorState, DataPrepStatusEnum
from app.clients.data_prep_client import (
    call_prepare,
    call_get_data_profile
)

TEST_CSV = "test_flights.csv"

TEST_METADATA = {
    "table_name": "flights",
    "columns": [
        {"column_name": "flight_id",          "type": "int",
         "nullable": False, "unique": True},
        {"column_name": "delay_minutes",      "type": "float",
         "min_val": 0, "max_val": 500},
        {"column_name": "gate",               "type": "string",
         "nullable": True},
        {"column_name": "satisfaction_score", "type": "float",
         "min_val": 0, "max_val": 5},
        {"column_name": "route",              "type": "string",
         "nullable": False},
        {"column_name": "passenger_count",    "type": "int",
         "min_val": 0},
        {"column_name": "departure_date",     "type": "date"},
        {"column_name": "status",             "type": "string",
         "nullable": False}
    ],
    "business_rules": [
        "delay_minutes must be >= 0",
        "satisfaction_score must be <= 5"
    ]
}

DATA_PREP_URL = "http://127.0.0.1:8001"


def create_test_csv():
    content = """flight_id,delay_minutes,gate,satisfaction_score,route,passenger_count,departure_date,status
1,15,A1,4.2,CMN-CDG,180,2026-01-15,on_time
2,0,B2,4.8,CMN-MAD,150,2026-01-15,on_time
3,-5,C3,3.1,CMN-LHR,200,2026-01-16,on_time
4,120,A1,2.5,CMN-CDG,175,2026-01-16,delayed
5,45,,4.0,CMN-MAD,160,2026-01-17,delayed
6,999,B2,5.1,CMN-LHR,190,2026-01-17,delayed
"""
    with open(TEST_CSV, "w") as f:
        f.write(content)
    print(f"✅ CSV de test créé : {TEST_CSV}")


async def test():
    print("=" * 55)
    print("  TEST RÉEL — Data Preparation Agent")
    print("=" * 55)

    create_test_csv()

    state = OrchestratorState(
        user_id="u_test",
        session_id="sess_test",
        query_raw="améliorer l expérience des passagers",
        csv_path=TEST_CSV,
        metadata=TEST_METADATA
    )

    # ── Étape 1 : POST /prepare ───────────────────────────────────
    print("\n── Étape 1 : POST /prepare ──")
    state = await call_prepare(state)

    if state.data_prep_status == DataPrepStatusEnum.FAILED:
        print(f"❌ Échec : {state.data_prep_error}")
        print("   → Vérifier que http://127.0.0.1:8001 est lancé")
        print("   → Vérifier que MinIO Docker tourne")
        return

    print(f"✅ job_id  : {state.data_prep_job_id}")
    print(f"✅ status  : {state.data_prep_status.value}")
    print(f"✅ quality : {state.data_prep_quality}")

    # ── Étape 2 : Récupérer le plan d'anomalies ───────────────────
    print("\n── Étape 2 : Récupération du plan d'anomalies ──")
    async with httpx.AsyncClient(timeout=30.0) as client:
        plan_response = await client.get(
            f"{DATA_PREP_URL}/jobs/{state.data_prep_job_id}/plan"
        )
        plan = plan_response.json()

    anomalies = plan.get("anomalies", [])
    print(f"Anomalies détectées : {len(anomalies)}")
    for a in anomalies:
        print(f"  → {a.get('anomaly_id')} | "
              f"colonne: {a.get('column_name')} | "
              f"type: {a.get('anomaly_type')}")

    # ── Étape 3 : Validation automatique ─────────────────────────
    print("\n── Étape 3 : Validation automatique ──")
    decisions = []
    for anomaly in anomalies:
        actions = anomaly.get("proposed_actions", {})
        # Choisir action_2 (modérée) si disponible, sinon action_1
        chosen = actions.get("action_2", actions.get("action_1", {}))
        decisions.append({
            "anomaly_id":    anomaly["anomaly_id"],
            "decision":      "approved",
            "chosen_action": chosen.get("action", "flag_only"),
            "params":        {}
        })

    if not decisions:
        print("ℹ️  Aucune anomalie détectée — données déjà propres ✅")

    async with httpx.AsyncClient(timeout=60.0) as client:
        validate_response = await client.post(
            f"{DATA_PREP_URL}/jobs/{state.data_prep_job_id}/validate",
            json={"decisions": decisions}
        )
        validate_result = validate_response.json()

    print(f"HTTP validate : {validate_response.status_code}")
    print(f"status        : {validate_result.get('status')}")

    quality_comp = validate_result.get("quality_comparison", {})
    if quality_comp:
        print(f"quality avant : {quality_comp.get('before', {}).get('global', 'N/A')}")
        print(f"quality après : {quality_comp.get('after',  {}).get('global', 'N/A')}")
        print(f"gain          : {quality_comp.get('gain',   'N/A')}")

    if validate_result.get("status") in ["completed", "success"]:
        state.data_prep_status = DataPrepStatusEnum.COMPLETED
        state.data_prep_paths  = validate_result.get("paths", {})
        print(f"✅ silver : {state.data_prep_paths.get('silver', 'N/A')}")
        print(f"✅ gold   : {state.data_prep_paths.get('gold',   'N/A')}")
    else:
        print(f"⚠️  Statut inattendu : {validate_result.get('status')}")
        print(f"   Détail : {validate_result}")
        return

    # ── Étape 4 : GET /profiling-json ─────────────────────────────
    print("\n── Étape 4 : Récupération data_profile ──")
    state = await call_get_data_profile(state)

    if state.data_profile:
        print(f"✅ row_count          : {state.data_profile.get('row_count')}")
        print(f"✅ columns            : {state.data_profile.get('columns')}")
        print(f"✅ numeric_columns    : {state.data_profile.get('numeric_columns')}")
        print(f"✅ categorical_columns: {state.data_profile.get('categorical_columns')}")
        print(f"✅ missing_summary    : {state.data_profile.get('missing_summary')}")
        print(f"✅ quality_score      : {state.data_profile.get('quality_score')}")
    else:
        print("⚠️  data_profile vide — vérifier /profiling-json")

    # ── Résumé ────────────────────────────────────────────────────
    print("\n── Processing Steps ──")
    for step in state.processing_steps:
        print(f"  → {step}")

    # Nettoyage
    if os.path.exists(TEST_CSV):
        os.remove(TEST_CSV)

    print("\n" + "=" * 55)
    print("  ✅ Test Data Prep Agent terminé avec succès !")
    print("=" * 55)


asyncio.run(test())