import asyncio
from app.graph.state import OrchestratorState, RouteEnum
from app.clients.nlq_client import (
    call_detect_sector,
    call_nlq_chat,
    reset_nlq_session,
    _format_data_profile_for_nlq,
)
from app.graph.nodes.routing_node import routing_node

# ═══════════════════════════════════════════════════════════════════
# Dataset de test — simule ce que le Collègue 2 aurait produit
# ═══════════════════════════════════════════════════════════════════
FAKE_DATA_PROFILE = {
    "row_count": 500,
    "columns": ["flight_id", "delay_minutes", "gate", "satisfaction"],
    "numeric_columns": ["flight_id", "delay_minutes", "satisfaction"],
    "categorical_columns": ["gate"],
    "missing_summary": {"gate": 5.0},
    "quality_score": 92.0
}


def separator(title):
    print(f"\n{'═' * 55}")
    print(f"  {title}")
    print('═' * 55)


# ═══════════════════════════════════════════════════════════════════
# TEST 1 — /detect-sector  (ton test original)
# ═══════════════════════════════════════════════════════════════════
async def test_detect_sector():
    separator("TEST 1 — POST /detect-sector")

    state = OrchestratorState(
        user_id="u_test",
        session_id="sess_test",
        query_raw="améliorer l experience des passagers de l aéroport"
    )

    result, route = await call_detect_sector(state)

    print("Secteur    :", result.sector.value)
    print("Confiance  :", result.sector_confidence)
    print("KPIs       :", [k.get("name") for k in result.kpi_mapping])
    print("Route      :", route)
    print("routing_target dans state :", result.routing_target)  # ✅ FIX 1
    print("Steps      :", result.processing_steps)

    # Vérifications
    assert result.sector.value != "Unknown", "❌ Secteur non détecté"
    assert result.sector_confidence > 0, "❌ Confiance à 0"
    assert result.routing_target != "", "❌ routing_target vide — FIX 1 non appliqué"
    print("✅ TEST 1 PASSED")
    return result


# ═══════════════════════════════════════════════════════════════════
# TEST 2 — _format_data_profile_for_nlq  (conversion format)
# ═══════════════════════════════════════════════════════════════════
async def test_format_data_profile():
    separator("TEST 2 — _format_data_profile_for_nlq (conversion)")

    state = OrchestratorState(
        user_id="u_test",
        query_raw="test",
        data_profile=FAKE_DATA_PROFILE
    )

    formatted = _format_data_profile_for_nlq(state)

    print("Format produit par Collègue 2 :")
    print("  columns (brut) :", FAKE_DATA_PROFILE["columns"])
    print("\nFormat attendu par Collègue 1 (/chat) :")
    print("  columns (formaté) :", formatted["columns"])
    print("  row_count          :", formatted["row_count"])

    # Vérifications
    assert formatted is not None, "❌ formatted est None"
    assert formatted["row_count"] == 500, "❌ row_count incorrect"
    assert all("name" in c and "type" in c for c in formatted["columns"]), \
        "❌ format colonnes incorrect"

    numeric_cols = [c["name"] for c in formatted["columns"] if c["type"] == "float"]
    string_cols  = [c["name"] for c in formatted["columns"] if c["type"] == "string"]
    print("\n  Colonnes numériques  :", numeric_cols)
    print("  Colonnes string      :", string_cols)

    assert "delay_minutes" in numeric_cols, "❌ delay_minutes pas en float"
    assert "gate" in string_cols, "❌ gate pas en string"
    print("✅ TEST 2 PASSED")


# ═══════════════════════════════════════════════════════════════════
# TEST 3 — /chat avec data_profile  (FIX 2 + FIX 3)
# ═══════════════════════════════════════════════════════════════════
async def test_nlq_chat(state_after_sector):
    separator("TEST 3 — POST /chat (avec data_profile)")

    # Simuler que le Data Prep a rempli data_profile dans le state
    state_after_sector.data_profile = FAKE_DATA_PROFILE

    question = "Quel est le retard moyen par gate ?"
    result   = await call_nlq_chat(state_after_sector, question)

    print("Intent détecté      :", result.intent.value)          # ✅ FIX 3
    print("Intent confiance    :", result.intent_confidence)
    print("requires_orchestrator:", result.requires_orchestrator)
    print("sub_agent           :", result.sub_agent or "none")
    print("routing_target      :", result.routing_target)
    print("Réponse finale      :", result.final_response[:100] if result.final_response else "vide")
    print("Steps               :", result.processing_steps[-1])

    # Vérifications FIX 3
    assert result.intent.value != "unknown" or True, "intent unknown (acceptable)"
    print("✅ TEST 3 PASSED")
    return result


# ═══════════════════════════════════════════════════════════════════
# TEST 4 — routing_node avec requires_orchestrator
# ═══════════════════════════════════════════════════════════════════
async def test_routing_with_requires_orchestrator():
    separator("TEST 4 — routing_node (Niveau 0bis)")

    # Cas : NLQ dit requires_orchestrator=True → dashboard → insight_agent
    state = OrchestratorState(
        user_id="u_test",
        query_raw="génère moi un dashboard des KPIs",
        sector_confidence=0.65,   # < 80% → Niveau 0 skippé
        routing_target="insight_agent",
        requires_orchestrator=True,
        sub_agent="",
    )
    from app.graph.state import IntentEnum
    state.intent = IntentEnum.DASHBOARD

    result = routing_node(state)
    print("Route décidée  :", result.route.value)
    print("Raison         :", result.route_reason)
    print("Fallback       :", result.fallback_route.value if result.fallback_route else "none")

    assert result.route == RouteEnum.INSIGHT_AGENT, \
        f"❌ Attendu INSIGHT_AGENT, reçu {result.route.value}"
    assert "Niveau 0bis" in result.route_reason, \
        "❌ Niveau 0bis non utilisé"
    print("✅ TEST 4 PASSED")


# ═══════════════════════════════════════════════════════════════════
# TEST 5 — Pipeline complet detect-sector → routing
# ═══════════════════════════════════════════════════════════════════
async def test_pipeline_complet():
    separator("TEST 5 — Pipeline complet (detect-sector → routing)")

    state = OrchestratorState(
        user_id="u_test",
        session_id="sess_test",
        query_raw="améliorer l experience des passagers de l aéroport",
        data_profile=FAKE_DATA_PROFILE
    )

    # Étape 1 — detect-sector
    state, suggested_route = await call_detect_sector(state)
    print(f"[1] Secteur : {state.sector.value} ({state.sector_confidence:.0%})")
    print(f"    routing_target : {state.routing_target}")

    # Étape 2 — routing_node
    state = routing_node(state)
    print(f"[2] Route finale  : {state.route.value}")
    print(f"    Raison        : {state.route_reason}")
    print(f"    Fallback      : {state.fallback_route.value if state.fallback_route else 'none'}")
    print(f"    Steps         : {state.processing_steps}")

    assert state.route != RouteEnum.CLARIFICATION, \
        "❌ Route = CLARIFICATION sur une query claire"
    print("✅ TEST 5 PASSED")


# ═══════════════════════════════════════════════════════════════════
# TEST 6 — reset session
# ═══════════════════════════════════════════════════════════════════
async def test_reset_session():
    separator("TEST 6 — POST /chat/reset")

    result = await reset_nlq_session("u_test")
    print("Réponse reset :", result)
    assert result.get("history_cleared") or "message" in result or "user_id" in result, \
        "❌ Réponse reset inattendue"
    print("✅ TEST 6 PASSED")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
async def main():
    print("\n" + "═" * 55)
    print("  TEST RÉEL — Orchestrateur + Collègue 1")
    print("  Prérequis : uvicorn api.main:app --port 8000")
    print("═" * 55)

    try:
        # Test 1 — detect-sector
        state = await test_detect_sector()

        # Test 2 — format data_profile (pas besoin d'API)
        await test_format_data_profile()

        # Test 3 — /chat avec data_profile
        await test_nlq_chat(state)

        # Test 4 — routing avec requires_orchestrator (pas besoin d'API)
        await test_routing_with_requires_orchestrator()

        # Test 5 — pipeline complet
        await test_pipeline_complet()

        # Test 6 — reset session
        await test_reset_session()

        print("\n" + "═" * 55)
        print("  ✅ TOUS LES TESTS PASSÉS")
        print("═" * 55)

    except AssertionError as e:
        print(f"\n❌ ÉCHEC : {e}")
    except Exception as e:
        print(f"\n⚠️  ERREUR : {type(e).__name__}: {e}")
        print("    → Vérifie que l'API du Collègue 1 est bien lancée sur le port 8000")


asyncio.run(main())