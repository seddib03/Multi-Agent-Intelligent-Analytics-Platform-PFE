import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ─── Requests ─────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name:               str
    description:        Optional[str]  = None
    use_case:           Optional[str]  = None
    visual_preferences: Optional[dict] = None


class ProjectUpdate(BaseModel):
    name:               Optional[str]  = None
    description:        Optional[str]  = None
    use_case:           Optional[str]  = None
    visual_preferences: Optional[dict] = None


# ─── Responses ────────────────────────────────────────────

class ProjectResponse(BaseModel):
    id:                 uuid.UUID
    name:               str
    description:        Optional[str]
    use_case:           Optional[str]
    detected_sector:    Optional[str]
    visual_preferences: Optional[str]   # stocké en JSON string
    owner_id:           uuid.UUID
    company_id:         str
    created_at:         datetime
    updated_at:         datetime

    model_config = {"from_attributes": True}