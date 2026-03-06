from fastapi                 import APIRouter, Depends, status
from sqlalchemy.ext.asyncio  import AsyncSession

from app.core.database       import get_db
from app.core.keycloak       import logout_keycloak
from app.dependencies        import get_current_user
from app.schemas.user        import UserUpdate, PreferencesUpdate
from app.services.auth_service import AuthService

router = APIRouter()


# ── POST /api/auth/logout ────────────────────────────────────
@router.post("/logout")
async def logout(
    refresh_token: str,
    user: dict = Depends(get_current_user),
):
    await logout_keycloak(refresh_token)
    return {"message": "Déconnecté"}


# ── GET /api/auth/me/sync ────────────────────────────────────
@router.get("/me/sync")
async def sync_user(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    """Appelé par le frontend après chaque login Keycloak."""
    return await AuthService.get_me(db, user["user_id"])


# ── GET /api/auth/users/me ───────────────────────────────────
@router.get("/users/me")
async def get_me(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    return await AuthService.get_me(db, user["user_id"])


# ── PUT /api/auth/users/me ───────────────────────────────────
@router.put("/users/me")
async def update_me(
    body: UserUpdate,
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    from app.services.user_service import UserService
    return await UserService.update_me(db, user["user_id"], body)


# ── PUT /api/auth/users/me/preferences ──────────────────────
@router.put("/users/me/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    return await AuthService.update_preferences(
        db, user["user_id"], body
    )


# ── DELETE /api/auth/users/me ────────────────────────────────
@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    await AuthService.delete_me(db, user["user_id"])