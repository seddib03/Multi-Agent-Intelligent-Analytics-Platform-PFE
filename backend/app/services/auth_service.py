# app/services/auth_service.py
from sqlalchemy.ext.asyncio  import AsyncSession
from sqlalchemy               import select
from fastapi                  import HTTPException
from app.models.user          import User, Company, UserPreferences
from app.schemas.auth         import RegisterRequest, LoginRequest
from app.core.keycloak        import (
    keycloak_register, keycloak_login,
    keycloak_refresh, keycloak_logout,
    verify_token,
)
import uuid


class AuthService:

    # ── Register ─────────────────────────────────────────────
    @staticmethod
    async def register(
        db:   AsyncSession,
        data: RegisterRequest,
    ) -> dict:
        """
        1. Créer l'utilisateur dans Keycloak
        2. Login automatique pour obtenir les tokens
        3. Créer l'utilisateur dans Postgres
        """
        # 1. Créer dans Keycloak (lève 409 si email existe)
        await keycloak_register(
            email      = data.email,
            password   = data.password,
            first_name = data.first_name,
            last_name  = data.last_name,
            company    = data.company_name,
        )

        # 2. Login automatique
        tokens = await keycloak_login(data.email, data.password)

        # 3. Décoder le token pour obtenir le keycloak_id
        payload = await verify_token(tokens["access_token"])
        keycloak_id = payload["sub"]

        # 4. Créer company + user + prefs dans Postgres
        company_result = await db.execute(
            select(Company).where(Company.name == data.company_name)
        )
        company = company_result.scalar_one_or_none()
        if not company:
            company = Company(
                id   = uuid.uuid4(),
                name = data.company_name,
            )
            db.add(company)
            await db.flush()

        user = User(
            id          = uuid.uuid4(),
            keycloak_id = keycloak_id,
            email       = data.email,
            first_name  = data.first_name,
            last_name   = data.last_name,
            company_id  = company.id,
        )
        db.add(user)
        await db.flush()

        prefs = UserPreferences(
            id      = uuid.uuid4(),
            user_id = user.id,
        )
        db.add(prefs)
        await db.commit()

        return {
            **tokens,
            "user": {
                "id":           str(user.id),
                "email":        user.email,
                "first_name":   user.first_name,
                "last_name":    user.last_name,
                "company_name": company.name,
                "created_at":   str(user.created_at),
            }
        }

    # ── Login ────────────────────────────────────────────────
    @staticmethod
    async def login(
        db:   AsyncSession,
        data: LoginRequest,
    ) -> dict:
        """
        1. Login via Keycloak (Direct Access Grant)
        2. Sync user dans Postgres si besoin
        3. Retourner tokens + profil
        """
        # 1. Login Keycloak → tokens
        tokens = await keycloak_login(data.email, data.password)

        # 2. Décoder pour obtenir keycloak_id
        payload     = await verify_token(tokens["access_token"])
        keycloak_id = payload["sub"]

        # 3. Sync Postgres
        result = await db.execute(
            select(User).where(User.keycloak_id == keycloak_id)
        )
        user = result.scalar_one_or_none()

        # Créer si première connexion (ex: user créé dans Keycloak
        # directement par un admin)
        if not user:
            company_name = payload.get("company", "Default")
            company_res  = await db.execute(
                select(Company).where(Company.name == company_name)
            )
            company = company_res.scalar_one_or_none()
            if not company:
                company = Company(id=uuid.uuid4(), name=company_name)
                db.add(company)
                await db.flush()

            user = User(
                id          = uuid.uuid4(),
                keycloak_id = keycloak_id,
                email       = data.email,
                first_name  = payload.get("given_name", ""),
                last_name   = payload.get("family_name", ""),
                company_id  = company.id,
            )
            db.add(user)
            await db.flush()

            prefs = UserPreferences(
                id=uuid.uuid4(), user_id=user.id
            )
            db.add(prefs)
            await db.commit()
            await db.refresh(user)

        company = await db.get(Company, user.company_id)

        return {
            **tokens,
            "user": {
                "id":           str(user.id),
                "email":        user.email,
                "first_name":   user.first_name,
                "last_name":    user.last_name,
                "company_name": company.name,
                "created_at":   str(user.created_at),
            }
        }

    # ── Refresh ──────────────────────────────────────────────
    @staticmethod
    async def refresh(refresh_token: str) -> dict:
        """Déléguer le refresh à Keycloak."""
        return await keycloak_refresh(refresh_token)

    # ── Logout ───────────────────────────────────────────────
    @staticmethod
    async def logout(refresh_token: str) -> None:
        """Révoquer la session dans Keycloak."""
        await keycloak_logout(refresh_token)

    # ── Get me ───────────────────────────────────────────────
    @staticmethod
    async def get_me(db: AsyncSession, user_id: str) -> dict:
        user = await db.get(User, user_id)
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

    # ── Update preferences ───────────────────────────────────
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
                id=uuid.uuid4(), user_id=user_id
            )
            db.add(prefs)

        for field, value in data.model_dump(
            exclude_none=True
        ).items():
            setattr(prefs, field, value)

        await db.commit()
        return {"message": "Préférences sauvegardées"}

    # ── Delete me ────────────────────────────────────────────
    @staticmethod
    async def delete_me(db: AsyncSession, user_id: str) -> None:
        from app.services.minio_service import MinioService
        await MinioService.delete_user_files(user_id)
        user = await db.get(User, user_id)
        if user:
            await db.delete(user)
            await db.commit()