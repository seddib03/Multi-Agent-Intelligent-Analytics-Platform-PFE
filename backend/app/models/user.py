from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid

class Company(Base):
    __tablename__ = "companies"

    id         = Column(UUID(as_uuid=True), primary_key=True,
                        default=uuid.uuid4)
    name       = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True),
                        server_default="now()")

    users = relationship("User", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True,
                           default=uuid.uuid4)
    email         = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name    = Column(String, nullable=False)
    last_name     = Column(String, nullable=False)
    company_id    = Column(UUID(as_uuid=True),
                           ForeignKey("companies.id"),
                           nullable=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True),
                           server_default="now()")
    last_login_at = Column(DateTime(timezone=True),
                           nullable=True)

    company     = relationship("Company", back_populates="users")
    sessions    = relationship("AuthSession",
                               back_populates="user",
                               cascade="all, delete-orphan")
    preferences = relationship("UserPreferences",
                               back_populates="user",
                               uselist=False,
                               cascade="all, delete-orphan")
    projects    = relationship("Project",
                               back_populates="user",
                               cascade="all, delete-orphan")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id            = Column(UUID(as_uuid=True), primary_key=True,
                           default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True),
                           ForeignKey("users.id", ondelete="CASCADE"),
                           nullable=False)
    refresh_token = Column(String, unique=True, nullable=False)
    user_agent    = Column(String, nullable=True)
    ip_address    = Column(String, nullable=True)
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    is_revoked    = Column(Boolean, default=False)
    created_at    = Column(DateTime(timezone=True),
                           server_default="now()")

    user = relationship("User", back_populates="sessions")


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id               = Column(UUID(as_uuid=True), primary_key=True,
                              default=uuid.uuid4)
    user_id          = Column(UUID(as_uuid=True),
                              ForeignKey("users.id", ondelete="CASCADE"),
                              unique=True, nullable=False)
    dark_mode        = Column(Boolean, default=False)
    chart_style      = Column(String, default="bar")
    density          = Column(String, default="standard")
    accent_theme     = Column(String, default="royal-melon")
    primary_color    = Column(String, default="#004AAC")
    secondary_color  = Column(String, default="#FF7E51")
    dashboard_layout = Column(String, default="grid")
    visible_kpis     = Column(String, default="[]")  # JSON string
    updated_at       = Column(DateTime(timezone=True),
                              onupdate="now()")

    user = relationship("User", back_populates="preferences")