from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime, timedelta
from app.models.user import User, Company, AuthSession, UserPreferences
from app.schemas.auth import RegisterRequest, LoginRequest
from app.core.security import (hash_password, verify_password,
                                create_access_token, create_refresh_token)
import uuid

class AuthService:

    @staticmethod
    async def register(db: AsyncSession,
                       data: RegisterRequest) -> dict:

        # Vérifier email unique
        existing = await db.execute(
            select(User).where(User.email == data.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, "Email déjà utilisé")

        # Créer ou récupérer la company
        company_result = await db.execute(
            select(Company).where(Company.name == data.company_name)
        )
        company = company_result.scalar_one_or_none()
        if not company:
            company = Company(
                id   = uuid.uuid4(),
                name = data.company_name
            )
            db.add(company)
            await db.flush()  # obtenir l'id avant commit

        # Créer l'utilisateur
        user = User(
            id            = uuid.uuid4(),
            email         = data.email,
            password_hash = hash_password(data.password),
            first_name    = data.first_name,
            last_name     = data.last_name,
            company_id    = company.id,
        )
        db.add(user)
        await db.flush()

        # Créer les préférences par défaut
        prefs = UserPreferences(
            id      = uuid.uuid4(),
            user_id = user.id
        )
        db.add(prefs)

        # Créer la session
        refresh_token = create_refresh_token()
        session = AuthSession(
            id            = uuid.uuid4(),
            user_id       = user.id,
            refresh_token = refresh_token,
            expires_at    = datetime.utcnow() + timedelta(days=30)
        )
        db.add(session)
        await db.commit()

        access_token = create_access_token(
            str(user.id), user.email
        )

        return {
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "token_type":    "bearer",
            "user": {
                "id":           str(user.id),
                "email":        user.email,
                "first_name":   user.first_name,
                "last_name":    user.last_name,
                "company_name": company.name,
                "created_at":   str(user.created_at),
            }
        }

    @staticmethod
    async def login(db: AsyncSession,
                    data: LoginRequest) -> dict:

        # Trouver l'utilisateur
        result = await db.execute(
            select(User).where(User.email == data.email)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(
            data.password, user.password_hash
        ):
            raise HTTPException(401, "Email ou mot de passe incorrect")

        if not user.is_active:
            raise HTTPException(403, "Compte désactivé")

        # Récupérer la company
        company = await db.get(Company, user.company_id)

        # Mettre à jour last_login
        user.last_login_at = datetime.utcnow()

        # Créer nouvelle session
        refresh_token = create_refresh_token()
        session = AuthSession(
            id            = uuid.uuid4(),
            user_id       = user.id,
            refresh_token = refresh_token,
            expires_at    = datetime.utcnow() + timedelta(days=30)
        )
        db.add(session)
        await db.commit()

        access_token = create_access_token(
            str(user.id), user.email
        )

        return {
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "token_type":    "bearer",
            "user": {
                "id":           str(user.id),
                "email":        user.email,
                "first_name":   user.first_name,
                "last_name":    user.last_name,
                "company_name": company.name,
                "created_at":   str(user.created_at),
            }
        }

    @staticmethod
    async def refresh(db: AsyncSession,
                      refresh_token: str) -> dict:

        result = await db.execute(
            select(AuthSession).where(
                AuthSession.refresh_token == refresh_token,
                AuthSession.is_revoked    == False,
                AuthSession.expires_at    > datetime.utcnow()
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(401, "Refresh token invalide ou expiré")

        user = await db.get(User, session.user_id)

        access_token = create_access_token(
            str(user.id), user.email
        )
        return {
            "access_token": access_token,
            "token_type":   "bearer"
        }

    @staticmethod
    async def logout(db: AsyncSession,
                     refresh_token: str) -> None:

        result = await db.execute(
            select(AuthSession).where(
                AuthSession.refresh_token == refresh_token
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.is_revoked = True
            await db.commit()

    @staticmethod
    async def get_me(db: AsyncSession,
                     user_id: str) -> dict:
        user    = await db.get(User, user_id)
        company = await db.get(Company, user.company_id)
        prefs   = await db.execute(
            select(UserPreferences).where(
                UserPreferences.user_id == user_id
            )
        )
        prefs = prefs.scalar_one_or_none()

        return {
            "id":           str(user.id),
            "email":        user.email,
            "first_name":   user.first_name,
            "last_name":    user.last_name,
            "company_name": company.name,
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

    @staticmethod
    async def update_preferences(db: AsyncSession,
                                  user_id: str,
                                  data) -> dict:
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

    @staticmethod
    async def delete_me(db: AsyncSession,
                        user_id: str) -> None:
        from app.services.minio_service import MinioService
        # Cleanup MinIO
        await MinioService.delete_user_files(user_id)
        # Supprimer user (cascade supprime sessions + prefs)
        user = await db.get(User, user_id)
        await db.delete(user)
        await db.commit()