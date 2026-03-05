from pydantic import BaseModel, EmailStr
from typing import Optional


# ── Preferences ──────────────────────────────────────────────
class PreferencesResponse(BaseModel):
    dark_mode:        bool
    chart_style:      str
    density:          str
    accent_theme:     str
    primary_color:    str
    secondary_color:  str
    dashboard_layout: str
    visible_kpis:     list[str]

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    dark_mode:        Optional[bool]      = None
    chart_style:      Optional[str]       = None
    density:          Optional[str]       = None
    accent_theme:     Optional[str]       = None
    primary_color:    Optional[str]       = None
    secondary_color:  Optional[str]       = None
    dashboard_layout: Optional[str]       = None
    visible_kpis:     Optional[list[str]] = None


# ── User ─────────────────────────────────────────────────────
class UserResponse(BaseModel):
    id:           str
    email:        str
    first_name:   str
    last_name:    str
    company_name: str
    created_at:   str
    preferences:  Optional[PreferencesResponse] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    first_name: Optional[str]      = None
    last_name:  Optional[str]      = None
    email:      Optional[EmailStr] = None