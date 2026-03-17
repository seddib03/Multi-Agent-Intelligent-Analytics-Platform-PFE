import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# ─── Sub-models ───────────────────────────────────────────────────────────────
class ColumnProfile(BaseModel):
    original_name:  str
    detected_type:  str
    null_percent:   float
    unique_count:   int
    sample_values:  list[Any]
    stats:          Optional[dict] = None
    extra_metadata: Optional[dict[str, Any]] = None


# ─── Requests ─────────────────────────────────────────────────────────────────
class ColumnMetadataUpdate(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    original_name: str = Field(validation_alias=AliasChoices("original_name", "originalName"))
    business_name: Optional[str] = Field(default=None, validation_alias=AliasChoices("business_name", "businessName"))
    business_type: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("business_type", "semantic_type", "semanticType"),
    )
    description: Optional[str] = None
    pattern: Optional[str] = None
    nullable: Optional[bool | str] = None
    min: Optional[Any] = Field(default=None, validation_alias=AliasChoices("min", "minimum"))
    max: Optional[Any] = Field(default=None, validation_alias=AliasChoices("max", "maximum"))
    enums: Optional[list[Any] | str] = None
    date_format: Optional[str] = Field(default=None, validation_alias=AliasChoices("date_format", "dateFormat"))

    def to_extra_metadata_patch(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {}

        if self.pattern is not None:
            metadata["pattern"] = self.pattern
        if self.nullable is not None:
            metadata["nullable"] = self.nullable
        if self.min is not None:
            metadata["min"] = self.min
        if self.max is not None:
            metadata["max"] = self.max
        if self.enums is not None:
            metadata["enums"] = self.enums
        if self.date_format is not None:
            metadata["dateFormat"] = self.date_format

        for key, value in (self.model_extra or {}).items():
            if value is not None:
                metadata[key] = value

        return metadata


class MetadataUpdateRequest(BaseModel):
    columns: list[ColumnMetadataUpdate]


class ApplyCorrectionsRequest(BaseModel):
    corrections: list[str]


# ─── Responses ────────────────────────────────────────────────────────────────
class UploadResponse(BaseModel):
    file_id:           uuid.UUID
    original_filename: str
    row_count:         int
    column_count:      int
    file_size_bytes:   int
    detected_sector:   Optional[str]
    quality_score:     float
    preview:           list[dict[str, Any]]
    columns:           list[ColumnProfile]
    file_path:         Optional[str] = None


class DictionaryUploadResponse(BaseModel):
    original_filename: str
    stored_path:       str
    file_size_bytes:   int


class DatasetPreviewResponse(BaseModel):
    rows:       list[dict[str, Any]]
    total_rows: int
    columns:    list[str]


class DatasetColumnResponse(BaseModel):
    id:             uuid.UUID
    original_name:  str
    business_name:  Optional[str]
    description:    Optional[str]
    detected_type:  str
    business_type:  Optional[str]
    semantic_type:  Optional[str]
    null_percent:   Optional[float]
    unique_count:   Optional[int]
    sample_values:  Optional[list]
    stats:          Optional[dict]
    extra_metadata: Optional[dict]
    pattern:        Optional[Any]
    nullable:       Optional[Any]
    min:            Optional[Any]
    max:            Optional[Any]
    enums:          Optional[Any]
    date_format:    Optional[Any]
    column_order:   int
    model_config = {"from_attributes": True}


class DatasetProfileResponse(BaseModel):
    dataset_id: uuid.UUID
    columns:    list[DatasetColumnResponse]


class DatasetResponse(BaseModel):
    id:                uuid.UUID
    project_id:        uuid.UUID
    original_filename: str
    file_format:       str
    file_size_bytes:   int
    row_count:         Optional[int]
    column_count:      Optional[int]
    quality_score:     Optional[float]
    quality_report:    Optional[dict] = None
    created_at:        datetime
    updated_at:        datetime
    model_config = {"from_attributes": True}


class QualityIssue(BaseModel):
    type:     str
    severity: str
    message:  str
    fix:      str


class ColumnQuality(BaseModel):
    column:  str
    issues:  list[QualityIssue]
    score:   float


class QualityReportResponse(BaseModel):
    dataset_id:              uuid.UUID
    global_score:            float
    total_columns:           int
    columns_ok:              int
    columns_issues:          int
    critical_count:          int
    warning_count:           int
    issues:                  list[ColumnQuality]
    corrections_available:   list[str]


class ApplyCorrectionsResponse(BaseModel):
    dataset_id: uuid.UUID
    applied:    list[str]
    skipped:    list[str]
    message:    str
    note:       str