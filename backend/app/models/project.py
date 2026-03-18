import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    CREATED              = "CREATED"
    DATA_UPLOADED        = "DATA_UPLOADED"
    METADATA_CONFIGURED  = "METADATA_CONFIGURED"
    TRAINING             = "TRAINING"
    READY                = "READY"
    FAILED               = "FAILED"
    ARCHIVED             = "ARCHIVED"


class Project(Base):
    __tablename__ = "projects"

    id:                 Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:               Mapped[str]             = mapped_column(String(255), nullable=False)
    description:        Mapped[str | None]      = mapped_column(Text, nullable=True)
    use_case:           Mapped[str | None]      = mapped_column(Text, nullable=True)
    detected_sector:    Mapped[str | None]      = mapped_column(String(100), nullable=True)
    visual_preferences: Mapped[str | None]      = mapped_column(Text, nullable=True)    # JSON string
    status:             Mapped[ProjectStatus]   = mapped_column(Enum(ProjectStatus), nullable=False, default=ProjectStatus.CREATED)
    business_rules:     Mapped[str | None]      = mapped_column(Text, nullable=True)
    owner_id:           Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at:         Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at:         Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner:    Mapped["User"]          = relationship("User", back_populates="projects")
    datasets: Mapped[list["Dataset"]] = relationship("Dataset", back_populates="project", cascade="all, delete-orphan")