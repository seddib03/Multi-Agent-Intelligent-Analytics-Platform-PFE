import pytest
from httpx        import AsyncClient
from unittest.mock import AsyncMock, patch


# ── Mocks Keycloak ───────────────────────────────────────────
FAKE_TOKENS = {
    "access_token":  "fake-access-token",
    "refresh_token": "fake-refresh-token",
    "token_type":    "bearer",
    "expires_in":    900,
}

FAKE_PAYLOAD = {
    "sub":         "keycloak-uid-123",
    "email":       "test@dxc.com",
    "given_name":  "test",
    "family_name": "test",
    "company":     "Nexora Corp",
}


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    with patch("app.core.keycloak.keycloak_register",
               new_callable=AsyncMock, return_value=None), \
         patch("app.core.keycloak.keycloak_login",
               new_callable=AsyncMock, return_value=FAKE_TOKENS), \
         patch("app.core.keycloak.verify_token",
               new_callable=AsyncMock, return_value=FAKE_PAYLOAD):

        res = await client.post("/api/auth/register", json={
            "email":        "test@dxc.com",
            "password":     "Test1234!",
            "first_name":   "test",
            "last_name":    "test",
            "company_name": "Nexora Corp",
        })
    assert res.status_code == 201
    data = res.json()
    assert "access_token"           in data
    assert "refresh_token"          in data
    assert data["user"]["email"]        == "test@dxc.com"
    assert data["user"]["company_name"] == "Nexora Corp"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    from fastapi import HTTPException
    with patch("app.core.keycloak.keycloak_register",
               new_callable=AsyncMock,
               side_effect=HTTPException(409, "Email déjà utilisé")):

        res = await client.post("/api/auth/register", json={
            "email":        "mary@dxc.com",
            "password":     "Test1234!",
            "first_name":   "Mary",
            "last_name":    "Ame",
            "company_name": "DXC Technology",
        })
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    with patch("app.core.keycloak.keycloak_login",
               new_callable=AsyncMock, return_value=FAKE_TOKENS), \
         patch("app.core.keycloak.verify_token",
               new_callable=AsyncMock, return_value=FAKE_PAYLOAD):

        res = await client.post("/api/auth/login", json={
            "email":    "test@nexora.com",
            "password": "Test1234!",
        })
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    with patch("app.core.keycloak.keycloak_login",
               new_callable=AsyncMock,
               side_effect=HTTPException(401, "Email ou mot de passe incorrect")):

        res = await client.post("/api/auth/login", json={
            "email":    "test@nexora.com",
            "password": "WrongPassword",
        })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_works(client: AsyncClient):
    with patch("app.core.keycloak.keycloak_refresh",
               new_callable=AsyncMock, return_value={
                   "access_token":  "new-access-token",
                   "refresh_token": "new-refresh-token",
                   "token_type":    "bearer",
               }):
        res = await client.post("/api/auth/refresh",
                                json={"refresh_token": "valid-refresh"})
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient):
    with patch("app.core.keycloak.keycloak_logout",
               new_callable=AsyncMock, return_value=None):
        res = await client.post("/api/auth/logout",
                                json={"refresh_token": "valid-refresh"})
    assert res.status_code == 200
    assert res.json()["message"] == "Déconnecté"


@pytest.mark.asyncio
async def test_preferences_saved(client: AsyncClient):
    headers = {"Authorization": "Bearer fake-token"}

    with patch("app.core.keycloak.verify_token",
               new_callable=AsyncMock, return_value=FAKE_PAYLOAD), \
         patch("app.core.keycloak.keycloak_login",
               new_callable=AsyncMock, return_value=FAKE_TOKENS):

        # Login d'abord pour créer le user en base
        await client.post("/api/auth/login", json={
            "email": "pref@dxc.com", "password": "Test1234!"
        })

        # Sauvegarder préférences
        res = await client.put(
            "/api/auth/users/me/preferences",
            json={"dark_mode": True, "chart_style": "line",
                  "density": "expert"},
            headers=headers,
        )
        assert res.status_code == 200

        # Vérifier persistées
        me = await client.get("/api/auth/users/me", headers=headers)
        prefs = me.json()["preferences"]
        assert prefs["dark_mode"]   == True
        assert prefs["chart_style"] == "line"
        assert prefs["density"]     == "expert"
