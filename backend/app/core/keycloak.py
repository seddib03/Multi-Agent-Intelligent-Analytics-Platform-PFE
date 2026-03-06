from jose          import jwt, JWTError
from jose.backends import RSAKey
import httpx, json
from app.core.config import settings

# Cache des clés publiques Keycloak (JWKS)
_jwks_cache: dict = {}

async def _get_jwks() -> dict:
    """
    Récupérer les clés publiques Keycloak.
    Mises en cache pour éviter un appel HTTP à chaque requête.
    """
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache

    async with httpx.AsyncClient() as client:
        res = await client.get(settings.KEYCLOAK_JWKS_URL)
        res.raise_for_status()
        _jwks_cache = res.json()

    return _jwks_cache


async def verify_token(token: str) -> dict:
    """
    Valider un JWT Keycloak.
    Retourner le payload si valide, lever une exception sinon.
    """
    try:
        # Récupérer les clés publiques
        jwks = await _get_jwks()

        # Décoder sans vérification d'abord pour obtenir le kid
        header = jwt.get_unverified_header(token)
        kid    = header.get("kid")

        # Trouver la clé correspondante
        key = next(
            (k for k in jwks["keys"] if k["kid"] == kid),
            None
        )
        if not key:
            # Vider le cache et réessayer (rotation de clés)
            _jwks_cache.clear()
            jwks = await _get_jwks()
            key  = next(
                (k for k in jwks["keys"] if k["kid"] == kid),
                None
            )

        if not key:
            raise ValueError("Clé publique introuvable")

        # Valider et décoder le token
        payload = jwt.decode(
            token,
            key,
            algorithms = ["RS256"],
            audience   = settings.KEYCLOAK_CLIENT_ID,
        )
        return payload

    except JWTError as e:
        raise ValueError(f"Token invalide : {str(e)}")


async def get_userinfo(token: str) -> dict:
    """
    Récupérer les infos utilisateur depuis Keycloak.
    Appelé une fois après login pour sync avec Postgres.
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(
            settings.KEYCLOAK_USERINFO_URL,
            headers={"Authorization": f"Bearer {token}"}
        )
        res.raise_for_status()
        return res.json()


async def logout_keycloak(refresh_token: str) -> None:
    """
    Révoquer la session Keycloak côté serveur.
    """
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
            f"/protocol/openid-connect/logout",
            data={
                "client_id":     settings.KEYCLOAK_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "refresh_token": refresh_token,
            }
        )