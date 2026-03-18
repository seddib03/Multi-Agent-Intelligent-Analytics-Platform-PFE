import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.keycloak import verify_token
from app.models.user import User, UserPreferences, Company

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    1. Valider le token JWT auprès de Keycloak
    2. Synchroniser l'utilisateur dans Postgres si première connexion
    3. Retourner l'objet User SQLAlchemy
    """
    token = credentials.credentials

    try:
        payload = await verify_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    keycloak_id = payload.get("sub")
    email       = payload.get("email", "")
    first_name  = payload.get("given_name", "")
    last_name   = payload.get("family_name", "")
    company     = payload.get("company", "")

    result = await db.execute(
        select(User).where(User.keycloak_id == keycloak_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = await _create_user_from_keycloak(
            db, keycloak_id, email, first_name, last_name, company
        )

    return user   # ← retourne l'objet User, pas un dict


async def _create_user_from_keycloak(
    db:           AsyncSession,
    keycloak_id:  str,
    email:        str,
    first_name:   str,
    last_name:    str,
    company_name: str,
) -> User:
    # Créer ou récupérer la company
    result = await db.execute(
        select(Company).where(Company.name == company_name)
    )
    company = result.scalar_one_or_none()
    if not company:
        company = Company(id=uuid.uuid4(), name=company_name or "Default")
        db.add(company)
        await db.flush()

    # Créer l'utilisateur
    user = User(
        id=uuid.uuid4(),
        keycloak_id=keycloak_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        company_id=company.id,
    )
    db.add(user)

    # Créer les préférences par défaut
    prefs = UserPreferences(
        id=uuid.uuid4(),
        user_id=user.id,
    )
    db.add(prefs)

    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def get_internal_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> None:
    from app.core.config import settings
    if credentials.credentials != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key invalide",
        )