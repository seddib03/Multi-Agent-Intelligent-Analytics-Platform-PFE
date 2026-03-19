import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from app.models.project import ProjectStatus


# ─── Requests ─────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name:               str
    description:        Optional[str]  = None
    use_case:           Optional[str]  = None
    visual_preferences: Optional[dict] = None
    business_rules:     Optional[str]  = None


class ProjectUpdate(BaseModel):
    name:               Optional[str]           = None
    description:        Optional[str]           = None
    use_case:           Optional[str]           = None
    detected_sector:    Optional[str]           = None
    visual_preferences: Optional[dict]          = None
    business_rules:     Optional[str]           = None
    status:             Optional[ProjectStatus] = None


# ─── Responses ────────────────────────────────────────────────────────────────

class ProjectResponse(BaseModel):
    id:                 uuid.UUID
    name:               str
    description:        Optional[str]
    use_case:           Optional[str]
    detected_sector:    Optional[str]
    visual_preferences: Optional[str]
    status:             ProjectStatus
    business_rules:     Optional[str]
    owner_id:           uuid.UUID
    created_at:         datetime
    updated_at:         datetime
    model_config = {"from_attributes": True}


class ConversationPayload(BaseModel):
    updatedAt: Optional[str] = None
    messages: list[dict[str, Any]] = Field(default_factory=list)


class DashboardInsightPayload(BaseModel):
    generated: bool = False
    hasCharts: bool = False
    hasPredictions: bool = False
    generatedAt: Optional[str] = None
    title: Optional[str] = None
    kpis: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    predictions: list[dict[str, Any]] = Field(default_factory=list)