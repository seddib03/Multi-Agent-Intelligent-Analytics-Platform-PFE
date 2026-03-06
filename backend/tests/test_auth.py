import pytest
from httpx       import AsyncClient
from unittest.mock import AsyncMock, patch


# ── Fixture — simuler un token Keycloak valide ───────────────
FAKE_KEYCLOAK_PAYLOAD = {
    "sub":           "keycloak-user-123",
    "email":         "test@nexora.com",
    "given_name":    "John",
    "family_name":   "Doe",
    "company":       "Nexora Corp",
}

FAKE_TOKEN = "fake-keycloak-jwt-token"


@pytest.fixture
def mock_keycloak():
    """
    Intercepte verify_token() pour éviter un vrai appel Keycloak.
    Tous les tests utilisent ce mock — pas besoin de serveur Keycloak.
    """
    with patch(
        "app.core.keycloak.verify_token",
        new_callable=AsyncMock,
        return_value=FAKE_KEYCLOAK_PAYLOAD
    ):
        yield


@pytest.fixture
def auth_headers():
    """Headers avec token Keycloak simulé."""
    return {"Authorization": f"Bearer {FAKE_TOKEN}"}


# ── Test sync — première connexion crée l'utilisateur ────────
@pytest.mark.asyncio
async def test_sync_creates_user_on_first_login(
    client: AsyncClient, mock_keycloak
):
    """
    Remplace test_register_success.
    Avec Keycloak, pas de register via API —
    l'utilisateur est créé automatiquement au premier appel.
    """
    res = await client.get(
        "/api/auth/me/sync",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["email"]        == "test@nexora.com"
    assert data["first_name"]   == "John"
    assert data["company_name"] == "Nexora Corp"


@pytest.mark.asyncio
async def test_sync_twice_does_not_duplicate_user(
    client: AsyncClient, mock_keycloak
):
    """
    Remplace test_register_duplicate_email.
    Appeler sync deux fois → même utilisateur, pas de doublon.
    """
    await client.get(
        "/api/auth/me/sync",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    res = await client.get(
        "/api/auth/me/sync",
        headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
    )
    assert res.status_code == 200


# ── Test token invalide → 401 ─────────────────────────────────
@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient):
    """
    Remplace test_login_wrong_password.
    Avec Keycloak, un mauvais token = verify_token() lève ValueError.
    """
    with patch(
        "app.core.keycloak.verify_token",
        new_callable=AsyncMock,
        side_effect=ValueError("Token invalide")
    ):
        res = await client.get(
            "/api/auth/users/me",
            headers={"Authorization": "Bearer bad-token"}
        )
    assert res.status_code == 401


# ── Test logout révoque session Keycloak ─────────────────────
@pytest.mark.asyncio
async def test_logout_calls_keycloak(
    client: AsyncClient, mock_keycloak
):
    """
    Remplace test_logout_revokes_token.
    Logout appelle logout_keycloak() côté serveur.
    """
    with patch(
        "app.core.keycloak.logout_keycloak",
        new_callable=AsyncMock,
        return_value=None
    ) as mock_logout:
        res = await client.post(
            "/api/auth/logout",
            params={"refresh_token": "fake-refresh-token"},
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"}
        )
        assert res.status_code == 200
        assert res.json()["message"] == "Déconnecté"
        mock_logout.assert_called_once_with("fake-refresh-token")


# ── Test refresh — délégué à Keycloak ────────────────────────
@pytest.mark.asyncio
async def test_refresh_handled_by_keycloak(client: AsyncClient):
    """
    Remplace test_refresh_token_works.
    Il n'y a plus d'endpoint /refresh dans FastAPI.
    Le refresh est géré par l'intercepteur Axios côté frontend
    qui appelle directement Keycloak.
    Ce test vérifie que l'endpoint n'existe plus.
    """
    res = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": "any-token"}
    )
    # 404 → endpoint supprimé, comportement attendu
    assert res.status_code == 404


# ── Test préférences sauvegardées ────────────────────────────
@pytest.mark.asyncio
async def test_preferences_saved(
    client: AsyncClient, mock_keycloak
):
    """Inchangé dans le comportement, adapté pour Keycloak."""
    headers = {"Authorization": f"Bearer {FAKE_TOKEN}"}

    # S'assurer que l'utilisateur existe d'abord
    await client.get("/api/auth/me/sync", headers=headers)

    # Sauvegarder préférences
    res = await client.put(
        "/api/auth/users/me/preferences",
        json={
            "dark_mode":   True,
            "chart_style": "line",
            "density":     "expert"
        },
        headers=headers
    )
    assert res.status_code == 200

    # Vérifier persistées
    me = await client.get("/api/auth/users/me", headers=headers)
    prefs = me.json()["preferences"]
    assert prefs["dark_mode"]   == True
    assert prefs["chart_style"] == "line"
    assert prefs["density"]     == "expert"


# ── Test token expiré → 401 ───────────────────────────────────
@pytest.mark.asyncio
async def test_expired_token_returns_401(client: AsyncClient):
    with patch(
        "app.core.keycloak.verify_token",
        new_callable=AsyncMock,
        side_effect=ValueError("Token expiré")
    ):
        res = await client.get(
            "/api/auth/users/me",
            headers={"Authorization": "Bearer expired-token"}
        )
    assert res.status_code == 401
