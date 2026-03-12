from fastapi                 import APIRouter, Depends, status
from sqlalchemy.ext.asyncio  import AsyncSession

from app.core.database       import get_db
from app.dependencies        import get_current_user
from app.models.user         import User
from app.schemas.auth        import (
    RegisterRequest, LoginRequest,
    RefreshRequest, UserUpdate, PreferencesUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter()


# ── POST /api/auth/register ──────────────────────────────────
@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    db:   AsyncSession = Depends(get_db),
):
    return await AuthService.register(db, body)


# ── POST /api/auth/login ─────────────────────────────────────
@router.post("/login")
async def login(
    body: LoginRequest,
    db:   AsyncSession = Depends(get_db),
):
    return await AuthService.login(db, body)


# ── POST /api/auth/refresh ───────────────────────────────────
@router.post("/refresh")
async def refresh(body: RefreshRequest):
    return await AuthService.refresh(body.refresh_token)


# ── POST /api/auth/logout ────────────────────────────────────
@router.post("/logout")
async def logout(body: RefreshRequest):
    await AuthService.logout(body.refresh_token)
    return {"message": "Déconnecté"}


# ── GET /api/auth/users/me ───────────────────────────────────
@router.get("/users/me")
async def get_me(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    return await AuthService.get_me(db, user.id)


# ── PUT /api/auth/users/me ───────────────────────────────────
@router.put("/users/me")
async def update_me(
    body: UserUpdate,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    from app.services.user_service import UserService
    return await UserService.update_me(db, user.id, body)


# ── PUT /api/auth/users/me/preferences ──────────────────────
@router.put("/users/me/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    return await AuthService.update_preferences(
        db, user.id, body
    )


# ── DELETE /api/auth/users/me ────────────────────────────────
@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    await AuthService.delete_me(db, user.id)