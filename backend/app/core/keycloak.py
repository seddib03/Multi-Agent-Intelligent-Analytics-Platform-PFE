from jose        import jwt, JWTError
import httpx
from app.core.config import settings

# ── Cache JWKS ───────────────────────────────────────────────
_jwks_cache: dict = {}


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    jwks_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient() as client:
        res = await client.get(jwks_url)
        res.raise_for_status()
        _jwks_cache = res.json()
    return _jwks_cache


async def verify_token(token: str) -> dict:
    """Valider JWT Keycloak → retourner payload."""
    try:
        jwks    = await _get_jwks()
        header  = jwt.get_unverified_header(token)
        kid     = header.get("kid")
        key     = next(
            (k for k in jwks["keys"] if k["kid"] == kid), None
        )
        if not key:
            _jwks_cache.clear()
            jwks = await _get_jwks()
            key  = next(
                (k for k in jwks["keys"] if k["kid"] == kid), None
            )
        if not key:
            raise ValueError("Clé publique introuvable")

        payload = jwt.decode(
            token, key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        expected_client_id = settings.KEYCLOAK_CLIENT_ID
        token_aud = payload.get("aud")
        token_azp = payload.get("azp")

        aud_matches = False
        if isinstance(token_aud, str):
            aud_matches = token_aud == expected_client_id
        elif isinstance(token_aud, list):
            aud_matches = expected_client_id in token_aud

        # Keycloak peut placer le client dans `azp` au lieu de `aud`.
        if not aud_matches and token_azp != expected_client_id:
            raise ValueError(
                "Token invalide : audience/client non autorise "
                f"(attendu={expected_client_id}, aud={token_aud}, azp={token_azp})"
            )

        return payload
    except JWTError as e:
        raise ValueError(f"Token invalide : {str(e)}")


async def _get_admin_token() -> str:
    """
    Obtenir un token admin pour appeler l'Admin API Keycloak.
    Utilisé uniquement pour le register.
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(
            settings.KEYCLOAK_TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     settings.KEYCLOAK_ADMIN_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
            }
        )
        res.raise_for_status()
        return res.json()["access_token"]


async def keycloak_register(
    email:      str,
    password:   str,
    first_name: str,
    last_name:  str,
    company:    str,
) -> None:
    """
    Créer un utilisateur dans Keycloak via l'Admin API.
    Appelé par AuthService.register()
    """
    admin_token = await _get_admin_token()

    async with httpx.AsyncClient() as client:
        res = await client.post(
            settings.KEYCLOAK_ADMIN_USERS_URL,
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type":  "application/json",
            },
            json={
                "username":  email,
                "email":     email,
                "firstName": first_name,
                "lastName":  last_name,
                "enabled":   True,
                "attributes": {
                    "company": [company]
                },
                "credentials": [{
                    "type":      "password",
                    "value":     password,
                    "temporary": False,
                }]
            }
        )
        # 409 → email déjà utilisé dans Keycloak
        if res.status_code == 409:
            from fastapi import HTTPException
            raise HTTPException(409, "Email déjà utilisé")

        res.raise_for_status()


async def keycloak_login(
    email:    str,
    password: str,
) -> dict:
    """
    Login direct email/password via Keycloak (Direct Access Grant).
    Retourne access_token + refresh_token.
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(
            settings.KEYCLOAK_TOKEN_URL,
            data={
                "grant_type":    "password",
                "client_id":     settings.KEYCLOAK_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "username":      email,
                "password":      password,
                "scope":         "openid profile email",
            }
        )
        if res.status_code == 401:
            from fastapi import HTTPException
            raise HTTPException(401, "Email ou mot de passe incorrect")

        res.raise_for_status()
        data = res.json()
        return {
            "access_token":  data["access_token"],
            "refresh_token": data["refresh_token"],
            "token_type":    "bearer",
            "expires_in":    data["expires_in"],
        }


async def keycloak_refresh(refresh_token: str) -> dict:
    """
    Rafraîchir le access_token via le refresh_token.
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(
            settings.KEYCLOAK_TOKEN_URL,
            data={
                "grant_type":    "refresh_token",
                "client_id":     settings.KEYCLOAK_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "refresh_token": refresh_token,
            }
        )
        if res.status_code in (400, 401):
            from fastapi import HTTPException
            raise HTTPException(401, "Refresh token invalide ou expiré")

        res.raise_for_status()
        data = res.json()
        return {
            "access_token":  data["access_token"],
            "refresh_token": data["refresh_token"],
            "token_type":    "bearer",
        }


async def keycloak_logout(refresh_token: str) -> None:
    """
    Révoquer la session Keycloak côté serveur.
    """
    async with httpx.AsyncClient() as client:
        await client.post(
            settings.KEYCLOAK_LOGOUT_URL,
            data={
                "client_id":     settings.KEYCLOAK_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "refresh_token": refresh_token,
            }
        )