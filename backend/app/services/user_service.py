# app/services/user_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy              import select
from fastapi                 import HTTPException, status

from app.models.user   import User, Company, UserPreferences
from app.schemas.user  import UserUpdate, PreferencesUpdate
from app.core.minio    import MinioService

import json, uuid
from datetime import datetime


class UserService:

    # ── Helper interne ───────────────────────────────────────
    @staticmethod
    async def _get_user_or_404(
        db: AsyncSession, user_id: str
    ) -> User:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail      = "Utilisateur introuvable",
            )
        return user

    @staticmethod
    async def _get_company(
        db: AsyncSession, company_id: str
    ) -> Company:
        return await db.get(Company, company_id)

    @staticmethod
    async def _get_preferences(
        db: AsyncSession, user_id: str
    ) -> UserPreferences | None:
        result = await db.execute(
            select(UserPreferences).where(
                UserPreferences.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _serialize_preferences(prefs: UserPreferences | None) -> dict | None:
        if not prefs:
            return None
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

    @staticmethod
    async def _build_response(
        db: AsyncSession, user: User
    ) -> dict:
        company = await UserService._get_company(db, user.company_id)
        prefs   = await UserService._get_preferences(db, str(user.id))

        return {
            "id":           str(user.id),
            "email":        user.email,
            "first_name":   user.first_name,
            "last_name":    user.last_name,
            "company_name": company.name if company else "",
            "created_at":   str(user.created_at),
            "preferences":  UserService._serialize_preferences(prefs),
        }

    # ── GET me ───────────────────────────────────────────────
    @staticmethod
    async def get_me(
        db: AsyncSession, user_id: str
    ) -> dict:
        user = await UserService._get_user_or_404(db, user_id)
        return await UserService._build_response(db, user)

    # ── PUT me ───────────────────────────────────────────────
    @staticmethod
    async def update_me(
        db:      AsyncSession,
        user_id: str,
        data:    UserUpdate,
    ) -> dict:
        user = await UserService._get_user_or_404(db, user_id)

        # Vérifier unicité email si modifié
        if data.email and data.email != user.email:
            existing = await db.execute(
                select(User).where(User.email == data.email)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code = status.HTTP_409_CONFLICT,
                    detail      = "Email déjà utilisé",
                )

        # Appliquer les modifications
        for field, value in data.model_dump(
            exclude_none=True
        ).items():
            setattr(user, field, value)

        await db.commit()
        await db.refresh(user)

        return await UserService._build_response(db, user)

    # ── PUT preferences ──────────────────────────────────────
    @staticmethod
    async def update_preferences(
        db:      AsyncSession,
        user_id: str,
        data:    PreferencesUpdate,
    ) -> dict:

        prefs = await UserService._get_preferences(db, user_id)

        # Créer si n'existe pas encore
        if not prefs:
            prefs = UserPreferences(
                id      = uuid.uuid4(),
                user_id = user_id,
            )
            db.add(prefs)

        # Appliquer les modifications
        for field, value in data.model_dump(
            exclude_none=True
        ).items():
            if field == "visible_kpis":
                # Sérialiser en JSON string pour stockage
                setattr(prefs, field, json.dumps(value))
            else:
                setattr(prefs, field, value)

        await db.commit()
        await db.refresh(prefs)

        return UserService._serialize_preferences(prefs)

    # ── DELETE me ────────────────────────────────────────────
    @staticmethod
    async def delete_me(
        db:      AsyncSession,
        user_id: str,
    ) -> None:
        user = await UserService._get_user_or_404(db, user_id)

        # 1. Cleanup MinIO — tous les fichiers de l'utilisateur
        await MinioService.delete_user_files(user_id)

        # 2. Supprimer user
        #    cascade → sessions + preferences + projets
        await db.delete(user)
        await db.commit()