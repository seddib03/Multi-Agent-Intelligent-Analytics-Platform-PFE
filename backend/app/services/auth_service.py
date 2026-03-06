from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy              import select
from fastapi                 import HTTPException
from app.models.user         import User, Company, UserPreferences
import uuid


class AuthService:

    # ── Sync utilisateur à la première connexion Keycloak ────
    @staticmethod
    async def sync_or_create(
        db:          AsyncSession,
        keycloak_id: str,
        email:       str,
        first_name:  str,
        last_name:   str,
        company_name: str,
    ) -> dict:
        """
        Appelé par get_current_user() à chaque requête.
        Crée l'utilisateur en Postgres si première connexion.
        """
        # Chercher par keycloak_id
        result = await db.execute(
            select(User).where(User.keycloak_id == keycloak_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # Première connexion → créer company si nouvelle
            company_result = await db.execute(
                select(Company).where(Company.name == company_name)
            )
            company = company_result.scalar_one_or_none()
            if not company:
                company = Company(
                    id   = uuid.uuid4(),
                    name = company_name or "Default"
                )
                db.add(company)
                await db.flush()

            # Créer utilisateur
            user = User(
                id          = uuid.uuid4(),
                keycloak_id = keycloak_id,
                email       = email,
                first_name  = first_name,
                last_name   = last_name,
                company_id  = company.id,
            )
            db.add(user)
            await db.flush()

            # Créer préférences par défaut
            prefs = UserPreferences(
                id      = uuid.uuid4(),
                user_id = user.id,
            )
            db.add(prefs)
            await db.commit()
            await db.refresh(user)

        return {
            "user_id":    str(user.id),
            "keycloak_id": keycloak_id,
            "email":      user.email,
            "company_id": str(user.company_id),
        }

    # ── GET me ───────────────────────────────────────────────
    @staticmethod
    async def get_me(db: AsyncSession, user_id: str) -> dict:
        user    = await db.get(User, user_id)
        if not user:
            raise HTTPException(404, "Utilisateur introuvable")

        company = await db.get(Company, user.company_id)
        result  = await db.execute(
            select(UserPreferences).where(
                UserPreferences.user_id == user_id
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
                "visible_kpis":     prefs.visible_kpis,
            } if prefs else {}
        }

    # ── UPDATE preferences ───────────────────────────────────
    @staticmethod
    async def update_preferences(
        db: AsyncSession, user_id: str, data
    ) -> dict:
        result = await db.execute(
            select(UserPreferences).where(
                UserPreferences.user_id == user_id
            )
        )
        prefs = result.scalar_one_or_none()

        if not prefs:
            prefs = UserPreferences(
                id      = uuid.uuid4(),
                user_id = user_id
            )
            db.add(prefs)

        for field, value in data.model_dump(
            exclude_none=True
        ).items():
            setattr(prefs, field, value)

        await db.commit()
        return {"message": "Préférences sauvegardées"}

    # ── DELETE me ────────────────────────────────────────────
    @staticmethod
    async def delete_me(db: AsyncSession, user_id: str) -> None:
        from app.services.minio_service import MinioService
        await MinioService.delete_user_files(user_id)
        user = await db.get(User, user_id)
        if user:
            await db.delete(user)
            await db.commit()