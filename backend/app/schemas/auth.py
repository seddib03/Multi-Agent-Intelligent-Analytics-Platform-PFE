from pydantic import BaseModel, EmailStr
from typing import Optional

class RegisterRequest(BaseModel):
    email:        EmailStr
    password:     str
    first_name:   str
    last_name:    str
    company_name: str

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str

class UserDTO(BaseModel):
    id:           str
    email:        str
    first_name:   str
    last_name:    str
    company_name: str
    created_at:   str

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    user:          UserDTO

class RefreshRequest(BaseModel):
    refresh_token: str

class PreferencesUpdate(BaseModel):
    dark_mode:        Optional[bool]   = None
    chart_style:      Optional[str]    = None
    density:          Optional[str]    = None
    accent_theme:     Optional[str]    = None
    primary_color:    Optional[str]    = None
    secondary_color:  Optional[str]    = None
    dashboard_layout: Optional[str]    = None
    visible_kpis:     Optional[list[str]] = None

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name:  Optional[str] = None
    email:      Optional[EmailStr] = None

class UserProfileResponse(BaseModel):
    id:           str
    email:        str
    first_name:   str
    last_name:    str
    company_name: str
    created_at:   str
    preferences:  dict

    class Config:
        from_attributes = True