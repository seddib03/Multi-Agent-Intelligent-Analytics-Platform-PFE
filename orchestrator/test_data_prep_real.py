"""
Test réel — Data Preparation Agent (nouveau flux Sprint 2)
Lance ce test depuis le dossier orchestrator/ :
    python -m pytest tests/test_data_prep_real.py -v -s
ou directement :
    python tests/test_data_prep_real.py
"""
import asyncio
import httpx
import os
import json
import pytest
from app.graph.state import OrchestratorState, DataPrepStatusEnum
from app.clients.data_prep_client import (
    call_import,
    call_prepare_v2,
    call_get_status,
    call_get_data_profile,
    call_validate,
)

DATA_PREP_URL = os.getenv("DATA_PREP_API_URL", "http://127.0.0.1:8001")
TEST_CSV      = "test_flights.csv"

TEST_METADATA = {
    "table_name": "flights",
    "columns": [
        {"column_name": "flight_id",         "type": "int",    "nullable": False, "unique": True},
        {"column_name": "delay_minutes",      "type": "float",  "min_val": 0, "max_val": 500},
        {"column_name": "gate",               "type": "string", "nullable": True},
        {"column_name": "satisfaction_score", "type": "float",  "min_val": 0, "max_val": 5},
        {"column_name": "route",              "type": "string", "nullable": False},
        {"column_name": "passenger_count",    "type": "int",    "min_val": 0},
        {"column_name": "departure_date",     "type": "date"},
        {"column_name": "status",             "type": "string", "nullable": False}
    ],
    "business_rules": [
        "delay_minutes must be >= 0",
        "satisfaction_score must be <= 5"
    ]
}


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
    print(f"✅ CSV créé : {TEST_CSV}")


async def run_test():
    print("\n" + "=" * 60)
    print("  TEST RÉEL — Data Preparation Agent (nouveau flux)")
    print("=" * 60)

    create_test_csv()

    state = OrchestratorState(
        user_id="u_test",
        session_id="sess_test",
        query_raw="améliorer l expérience des passagers",
        csv_path=TEST_CSV,
        metadata=TEST_METADATA
    )

    # ── Étape 1 : POST /import ─────────────────────────────────────
    print("\n── Étape 1 : POST /import (CSV uniquement) ──")
    state = await call_import(state)

    if state.data_prep_status == DataPrepStatusEnum.FAILED:
        print(f"❌ Échec /import : {state.errors}")
        print("→ Vérifier que http://127.0.0.1:8001 est lancé")
        return False

    print(f"✅ job_id  : {state.data_prep_job_id}")
    print(f"✅ status  : {state.data_prep_status.value}")

    # ── Étape 2 : POST /prepare/{job_id} ──────────────────────────
    print("\n── Étape 2 : POST /prepare/{job_id} (metadata + règles) ──")
    state = await call_prepare_v2(state)

    if state.data_prep_status == DataPrepStatusEnum.FAILED:
        print(f"❌ Échec /prepare : {state.errors}")
        return False

    print(f"✅ status  : {state.data_prep_status.value}")
    print(f"✅ quality : {state.data_prep_quality}")

    # ── Étape 3 : Récupérer le plan d'anomalies ───────────────────
    print("\n── Étape 3 : Récupération du plan d'anomalies ──")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{DATA_PREP_URL}/jobs/{state.data_prep_job_id}/plan"
        )
        plan_response = r.json()

    plan      = plan_response.get("plan", {})
    anomalies = plan.get("anomalies", [])
    print(f"Anomalies détectées : {len(anomalies)}")

    for a in anomalies:
        recommended_key = a.get("recommended_action", "action_1")
        proposed        = a.get("proposed_actions", {})
        action_detail   = proposed.get(recommended_key, {})
        print(
            f"  → {a.get('anomaly_id')} | "
            f"col: {a.get('column_name')} | "
            f"type: {a.get('anomaly_type')} | "
            f"action: {action_detail.get('action', 'flag_only')}"
        )

    # ── Étape 4 : Validation (simulée — normalement faite par l'UI) ──
    print("\n── Étape 4 : Validation (simulée par le test) ──")
    print("ℹ️  En production : l'UI appelle /validate après confirmation utilisateur")

    decisions = []
    for anomaly in anomalies:
        anomaly_id      = anomaly.get("anomaly_id")
        recommended_key = anomaly.get("recommended_action", "action_1")
        proposed        = anomaly.get("proposed_actions", {})
        action_detail   = proposed.get(recommended_key, {})
        chosen_action   = action_detail.get("action", "flag_only")
        decisions.append({
            "anomaly_id":    anomaly_id,
            "decision":      "approved",
            "chosen_action": chosen_action,
            "params":        {}
        })
        print(f"  → {anomaly_id} | {chosen_action}")

    if not decisions:
        print("ℹ️  Aucune anomalie — validation vide")

    # Appel direct HTTP (pas via call_validate) pour voir la réponse brute
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{DATA_PREP_URL}/jobs/{state.data_prep_job_id}/validate",
            json={"decisions": decisions}
        )
        validate_result = r.json()
        print(f"HTTP validate : {r.status_code}")
        print(f"Réponse brute : {json.dumps(validate_result, indent=2)[:500]}")

    # Accepte tout status 200 comme succès
    if r.status_code == 200:
        state.data_prep_status = DataPrepStatusEnum.COMPLETED
        state.data_prep_paths  = validate_result.get("paths", {})
        print(f"✅ validate OK | silver : {state.data_prep_paths.get('silver', 'N/A')}")
    else:
        print(f"⚠️  Validate HTTP {r.status_code}")
        return False

    # ── Étape 5 : data_profile pour NLQ ───────────────────────────
    print("\n── Étape 5 : Récupération data_profile ──")
    state = await call_get_data_profile(state)

    if state.data_profile:
        print(f"✅ row_count           : {state.data_profile.get('row_count')}")
        print(f"✅ columns             : {state.data_profile.get('columns')}")
        print(f"✅ numeric_columns     : {state.data_profile.get('numeric_columns')}")
        print(f"✅ categorical_columns : {state.data_profile.get('categorical_columns')}")
        print(f"✅ quality_score       : {state.data_profile.get('quality_score')}")
    else:
        print("⚠️  data_profile vide")

    # ── Résumé ─────────────────────────────────────────────────────
    print("\n── Processing Steps ──")
    for step in state.processing_steps:
        print(f"  → {step}")

    print("\n" + "=" * 60)
    print("  ✅ Test Data Prep Agent terminé avec succès !")
    print("=" * 60)
    return True


# ── pytest ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_data_prep_full_pipeline():
    result = await run_test()
    assert result is True


# ── run direct ─────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    finally:
        if os.path.exists(TEST_CSV):
            os.remove(TEST_CSV)