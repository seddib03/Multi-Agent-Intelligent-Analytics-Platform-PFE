import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id:                    Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id:            Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    original_filename:     Mapped[str]         = mapped_column(String(255), nullable=False)
    # path on local filesystem where the uploaded file was saved
    file_path:              Mapped[str]         = mapped_column(String(500), nullable=False)
    # optional processed version path
    processed_path:         Mapped[str | None]  = mapped_column(String(500), nullable=True)
    file_format:           Mapped[str]         = mapped_column(String(20), nullable=False)   # csv | xlsx | json
    file_size_bytes:       Mapped[int]         = mapped_column(Integer, nullable=False)
    row_count:             Mapped[int | None]  = mapped_column(Integer, nullable=True)
    column_count:          Mapped[int | None]  = mapped_column(Integer, nullable=True)
    quality_score:         Mapped[float | None]= mapped_column(Float, nullable=True)
    quality_report:        Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at:            Mapped[datetime]    = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at:            Mapped[datetime]    = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project: Mapped["Project"]              = relationship("Project", back_populates="datasets")
    columns: Mapped[list["DatasetColumn"]]  = relationship("DatasetColumn", back_populates="dataset", cascade="all, delete-orphan")


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"

    id:             Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id:     Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    original_name:  Mapped[str]          = mapped_column(String(255), nullable=False)
    business_name:  Mapped[str | None]   = mapped_column(String(255), nullable=True)
    description:    Mapped[str | None]   = mapped_column(Text, nullable=True)
    detected_type:  Mapped[str]          = mapped_column(String(50), nullable=False)   # numeric | categorical | datetime | text | boolean
    business_type:  Mapped[str | None]   = mapped_column(String(50), nullable=True)
    null_percent:   Mapped[float | None] = mapped_column(Float, nullable=True)
    unique_count:   Mapped[int | None]   = mapped_column(Integer, nullable=True)
    sample_values:  Mapped[dict | None]  = mapped_column(JSONB, nullable=True)
    stats:          Mapped[dict | None]  = mapped_column(JSONB, nullable=True)
    extra_metadata: Mapped[dict | None]  = mapped_column(JSONB, nullable=True)
    column_order:   Mapped[int]          = mapped_column(Integer, nullable=False, default=0)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="columns")

    def _extra_metadata_value(self, *keys: str):
        metadata = self.extra_metadata or {}
        for key in keys:
            if key in metadata:
                return metadata[key]
        return None

    @property
    def semantic_type(self):
        return self.business_type

    @property
    def pattern(self):
        return self._extra_metadata_value("pattern")

    @property
    def nullable(self):
        return self._extra_metadata_value("nullable")

    @property
    def min(self):
        return self._extra_metadata_value("min")

    @property
    def max(self):
        return self._extra_metadata_value("max")

    @property
    def enums(self):
        return self._extra_metadata_value("enums")

    @property
    def date_format(self):
        return self._extra_metadata_value("dateFormat", "date_format")