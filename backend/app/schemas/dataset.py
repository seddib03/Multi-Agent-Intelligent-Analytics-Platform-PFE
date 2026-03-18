import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


# ─── Sub-models ───────────────────────────────────────────────────────────────
class ColumnProfile(BaseModel):
    original_name:  str
    detected_type:  str
    null_percent:   float
    unique_count:   int
    sample_values:  list[Any]
    stats:          Optional[dict] = None


# ─── Requests ─────────────────────────────────────────────────────────────────
class ColumnMetadataUpdate(BaseModel):
    original_name: str
    business_name: Optional[str] = None
    business_type: Optional[str] = None


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


class DatasetPreviewResponse(BaseModel):
    rows:       list[dict[str, Any]]
    total_rows: int
    columns:    list[str]


class DatasetColumnResponse(BaseModel):
    id:             uuid.UUID
    original_name:  str
    business_name:  Optional[str]
    detected_type:  str
    business_type:  Optional[str]
    null_percent:   Optional[float]
    unique_count:   Optional[int]
    sample_values:  Optional[list]
    stats:          Optional[dict]
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