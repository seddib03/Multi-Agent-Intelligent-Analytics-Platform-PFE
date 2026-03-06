# app/routers/users.py
from fastapi        import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy     import select, update

from app.core.database      import get_db
from app.dependencies       import get_current_user
from app.models.user        import User, Company, UserPreferences
from app.schemas.user       import UserResponse, UserUpdate, PreferencesUpdate, PreferencesResponse
from app.core.minio         import MinioService

import json, uuid
from datetime import datetime

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────
async def _build_user_response(
    db: AsyncSession, user: User
) -> dict:
    """Construire la réponse utilisateur complète."""

    # Company
    company = await db.get(Company, user.company_id)

    # Preferences
    result = await db.execute(
        select(UserPreferences).where(
            UserPreferences.user_id == user.id
        )
    )
    prefs = result.scalar_one_or_none()

    return {
        "id":           str(user.id),
        "email":        user.email,
        "first_name":   user.first_name,
        "last_name":    user.last_name,
        "company_name": company.name if company else "",
        "created_at":   str(user.created_at),
        "preferences": {
            "dark_mode":        prefs.dark_mode,
            "chart_style":      prefs.chart_style,
            "density":          prefs.density,
            "accent_theme":     prefs.accent_theme,
            "primary_color":    prefs.primary_color,
            "secondary_color":  prefs.secondary_color,
            "dashboard_layout": prefs.dashboard_layout,
            "visible_kpis":     json.loads(prefs.visible_kpis)
                                if isinstance(prefs.visible_kpis, str)
                                else prefs.visible_kpis or [],
        } if prefs else None
    }


# ── GET /api/users/me ────────────────────────────────────────
@router.get(
    "/me",
    response_model = UserResponse,
    summary        = "Récupérer le profil de l'utilisateur connecté",
)
async def get_me(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    db_user = await db.get(User, user["user_id"])
    if not db_user:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = "Utilisateur introuvable",
        )
    return await _build_user_response(db, db_user)


# ── PUT /api/users/me ────────────────────────────────────────
@router.put(
    "/me",
    response_model = UserResponse,
    summary        = "Modifier le profil",
)
async def update_me(
    body: UserUpdate,
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    db_user = await db.get(User, user["user_id"])
    if not db_user:
        raise HTTPException(404, "Utilisateur introuvable")

    # Vérifier unicité email si modifié
    if body.email and body.email != db_user.email:
        existing = await db.execute(
            select(User).where(User.email == body.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, "Email déjà utilisé")

    # Appliquer les modifications
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(db_user, field, value)

    await db.commit()
    await db.refresh(db_user)

    return await _build_user_response(db, db_user)


# ── PUT /api/users/me/preferences ───────────────────────────
@router.put(
    "/me/preferences",
    response_model = PreferencesResponse,
    summary        = "Sauvegarder les préférences dashboard",
)
async def update_preferences(
    body: PreferencesUpdate,
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    result = await db.execute(
        select(UserPreferences).where(
            UserPreferences.user_id == user["user_id"]
        )
    )
    prefs = result.scalar_one_or_none()

    # Créer si n'existe pas encore
    if not prefs:
        prefs = UserPreferences(
            id      = uuid.uuid4(),
            user_id = user["user_id"],
        )
        db.add(prefs)

    # Appliquer les modifications
    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        # visible_kpis → sérialiser en JSON string
        if field == "visible_kpis":
            setattr(prefs, field, json.dumps(value))
        else:
            setattr(prefs, field, value)

    await db.commit()
    await db.refresh(prefs)

    return {
        "dark_mode":        prefs.dark_mode,
        "chart_style":      prefs.chart_style,
        "density":          prefs.density,
        "accent_theme":     prefs.accent_theme,
        "primary_color":    prefs.primary_color,
        "secondary_color":  prefs.secondary_color,
        "dashboard_layout": prefs.dashboard_layout,
        "visible_kpis":     json.loads(prefs.visible_kpis)
                            if isinstance(prefs.visible_kpis, str)
                            else prefs.visible_kpis or [],
    }


# ── DELETE /api/users/me ─────────────────────────────────────
@router.delete(
    "/me",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Supprimer le compte et toutes les données",
)
async def delete_me(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    db_user = await db.get(User, user["user_id"])
    if not db_user:
        raise HTTPException(404, "Utilisateur introuvable")

    # 1. Cleanup MinIO — tous les fichiers de l'utilisateur
    await MinioService.delete_user_files(user["user_id"])

    # 2. Supprimer user (cascade → sessions + prefs + projets)
    await db.delete(db_user)
    await db.commit()