import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    res = await client.post("/api/auth/register", json={
        "email":        "test@nexora.com",
        "password":     "Test1234!",
        "first_name":   "John",
        "last_name":    "Doe",
        "company_name": "Nexora Corp"
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token"  in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "test@nexora.com"
    assert data["user"]["company_name"] == "Nexora Corp"

@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "email": "dup@nexora.com", "password": "Test1234!",
        "first_name": "A", "last_name": "B",
        "company_name": "Corp"
    }
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    res = await client.post("/api/auth/login", json={
        "email":    "test@nexora.com",
        "password": "WrongPassword"
    })
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_refresh_token_works(client: AsyncClient):
    # Register d'abord
    reg = await client.post("/api/auth/register", json={
        "email": "refresh@nexora.com", "password": "Test1234!",
        "first_name": "R", "last_name": "T",
        "company_name": "RefreshCorp"
    })
    refresh_token = reg.json()["refresh_token"]

    res = await client.post("/api/auth/refresh",
                            json={"refresh_token": refresh_token})
    assert res.status_code == 200
    assert "access_token" in res.json()

@pytest.mark.asyncio
async def test_logout_revokes_token(client: AsyncClient):
    reg = await client.post("/api/auth/register", json={
        "email": "logout@nexora.com", "password": "Test1234!",
        "first_name": "L", "last_name": "O",
        "company_name": "LogoutCorp"
    })
    refresh_token = reg.json()["refresh_token"]

    # Logout
    await client.post("/api/auth/logout",
                      json={"refresh_token": refresh_token})

    # Refresh doit échouer
    res = await client.post("/api/auth/refresh",
                            json={"refresh_token": refresh_token})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_preferences_saved(client: AsyncClient,
                                  auth_headers: dict):
    res = await client.put(
        "/api/users/me/preferences",
        json={"dark_mode": True, "chart_style": "line",
              "density": "expert"},
        headers=auth_headers
    )
    assert res.status_code == 200

    # Vérifier persisté
    me = await client.get("/api/users/me", headers=auth_headers)
    prefs = me.json()["preferences"]
    assert prefs["dark_mode"]   == True
    assert prefs["chart_style"] == "line"
    assert prefs["density"]     == "expert"