from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Valider le JWT et retourner le payload.
    Injecté dans tous les endpoints protégés.
    """
    token   = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Token invalide ou expiré",
            headers     = {"WWW-Authenticate": "Bearer"},
        )

    # Vérifier que l'utilisateur existe toujours en base
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(
        select(User).where(
            User.id        == payload["user_id"],
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Utilisateur introuvable ou désactivé",
            headers     = {"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id":    str(user.id),
        "email":      user.email,
        "company_id": str(user.company_id),
    }


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """
    Version optionnelle — retourne None si pas de token.
    Utilisé pour les routes accessibles connecté OU non.
    """
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def get_internal_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> None:
    """
    Auth par API Key pour les routes /api/internal/*.
    Utilisé par les agents (NLQ, Data, Insight, Orchestrateur).
    """
    from app.core.config import settings

    if credentials.credentials != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "API Key invalide",
        )