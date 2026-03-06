from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.schemas.auth import (RegisterRequest, LoginRequest,
                               RefreshRequest, UserUpdate,
                               PreferencesUpdate)
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    return await AuthService.register(db, body)

@router.post("/login")
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    return await AuthService.login(db, body)

@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    return await AuthService.refresh(db, body.refresh_token)

@router.post("/logout")
async def logout(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    await AuthService.logout(db, body.refresh_token)
    return {"message": "Déconnecté"}

@router.get("/users/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    return await AuthService.get_me(db, user["user_id"])

@router.put("/users/me")
async def update_me(
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    return await AuthService.update_me(db, user["user_id"], body)

@router.put("/users/me/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    return await AuthService.update_preferences(
        db, user["user_id"], body
    )

@router.delete("/users/me", status_code=204)
async def delete_me(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    await AuthService.delete_me(db, user["user_id"])