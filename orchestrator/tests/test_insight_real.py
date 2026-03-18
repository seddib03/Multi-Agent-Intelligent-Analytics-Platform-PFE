"""
test_insight_real.py
Test réel end-to-end avec l'API du Collègue 3 (Insight Agent).
Requiert que l'API soit lancée sur http://127.0.0.1:8002

Lancement : python tests/test_insight_real.py
"""
import asyncio
import httpx
import json

INSIGHT_API_URL = "http://127.0.0.1:8002"


async def test_health():
    """Vérifie que l'API est bien lancée."""
    print("\n=== Test 1 — Health Check ===")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{INSIGHT_API_URL}/")
    print(f"Status : {response.status_code}")
    assert response.status_code == 200, "❌ API non disponible"
    print("✅ API opérationnelle")


async def test_generate_dashboard_insurance():
    """Test principal — dataset insurance."""
    print("\n=== Test 2 — Generate Dashboard (Insurance) ===")

    payload = {
        "sector_context": {
            "sector": "Insurance",
            "context": "Customer and premium analytics",
            "recommended_kpis": [
                "Total Premium Amount",
                "Average Client Age",
                "Unique Clients"
            ],
            "recommended_charts": ["line", "bar", "bar"],
            "dashboard_focus": "Insurance Analytics Dashboard"
        },
        "dataset_path": "insurance_data.csv",   # chemin local chez le Collègue 3
        "metadata_path": "metadata_insurance.json",
        "user_query": None
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{INSIGHT_API_URL}/generate-dashboard",
            json=payload
        )

    print(f"Status : {response.status_code}")
    result = response.json()
    print(f"Réponse complète :\n{json.dumps(result, indent=2, ensure_ascii=False)}")

    assert response.status_code == 200, f"❌ Erreur : {result}"
    assert result.get("status") == "success", f"❌ status != success : {result}"

    # Vérifications sur la réponse
    assert "kpis" in result,     "❌ Champ 'kpis' manquant"
    assert "charts" in result,   "❌ Champ 'charts' manquant"
    assert "insights" in result, "❌ Champ 'insights' manquant"
    assert "template" in result, "❌ Champ 'template' manquant"
    assert len(result["kpis"]) > 0,     "❌ Aucun KPI retourné"
    assert len(result["charts"]) > 0,   "❌ Aucun graphique retourné"
    assert len(result["insights"]) > 0, "❌ Aucun insight retourné"

    print(f"\n✅ Template sélectionné : {result['template']}")
    print(f"✅ {len(result['kpis'])} KPIs générés :")
    for kpi in result["kpis"]:
        print(f"   - {kpi.get('name')} = {kpi.get('value')}")
    print(f"✅ {len(result['charts'])} graphiques générés")
    print(f"✅ {len(result['insights'])} insights générés")


async def test_generate_dashboard_specific_query():
    """Test avec user_query — mode spécifique."""
    print("\n=== Test 3 — Generate Dashboard (mode spécifique) ===")

    payload = {
        "sector_context": {
            "sector": "Insurance",
            "context": "Premium analysis",
            "recommended_kpis": ["Total Premium Amount"],
            "recommended_charts": ["line"],
            "dashboard_focus": "Premium Evolution"
        },
        "dataset_path": "insurance_data.csv",
        "metadata_path": "metadata_insurance.json",
        "user_query": "Analyse l'évolution des primes par année"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{INSIGHT_API_URL}/generate-dashboard",
            json=payload
        )

    result = response.json()
    print(f"Status : {response.status_code}")
    print(f"Dashboard mode : {result.get('dashboard_mode')}")

    assert response.status_code == 200
    assert result.get("dashboard_mode") == "specific", \
        f"❌ Mode attendu 'specific', reçu '{result.get('dashboard_mode')}'"
    print("✅ Mode spécifique activé correctement")


async def main():
    print("=" * 60)
    print("TEST RÉEL — Insight Agent (Collègue 3)")
    print(f"API : {INSIGHT_API_URL}")
    print("=" * 60)

    try:
        await test_health()
        await test_generate_dashboard_insurance()
        await test_generate_dashboard_specific_query()

        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS PASSENT — Insight Agent opérationnel !")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ ÉCHEC : {e}")
    except httpx.ConnectError:
        print("\n❌ CONNEXION IMPOSSIBLE — l'API du Collègue 3 est-elle lancée ?")
        print(f"   → Lance : python -m uvicorn api:app --reload --port 8002")
        print(f"   → Dans le dossier : insight_agent/")


if __name__ == "__main__":
    asyncio.run(main())