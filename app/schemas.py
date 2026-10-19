"""
Pydantic schemas for request validation and response serialization.
Boundary schemas enforce strict validation, rejecting malformed inputs with 4xx.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


# ---------------------------------------------------------
# Tenant & Auth Schemas
# ---------------------------------------------------------
class TenantRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    company_name: Optional[str] = Field(None, max_length=255)


class TenantLogin(BaseModel):
    email: EmailStr
    password: str


class TenantResponse(BaseModel):
    id: str
    email: str
    company_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ---------------------------------------------------------
# Widget Schemas
# ---------------------------------------------------------
class FormFieldSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=100)
    type: str = Field("text", pattern="^(text|email|tel|number|textarea|select)$")
    required: bool = False
    placeholder: Optional[str] = Field(None, max_length=100)
    options: Optional[List[str]] = None  # for select dropdowns


class WidgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    widget_type: str = Field("signup", pattern="^(signup|contact|cta|popover)$")
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    button_text: str = Field("Submit", min_length=1, max_length=50)
    fields: List[FormFieldSchema] = Field(default_factory=list)
    display_options: Dict[str, Any] = Field(default_factory=dict)


class WidgetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    widget_type: Optional[str] = Field(None, pattern="^(signup|contact|cta|popover)$")
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    button_text: Optional[str] = Field(None, min_length=1, max_length=50)
    fields: Optional[List[FormFieldSchema]] = None
    display_options: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class WidgetResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    widget_type: str
    title: str
    description: Optional[str] = None
    button_text: str
    fields: List[FormFieldSchema]
    display_options: Dict[str, Any]
    is_active: bool
    snippet: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicWidgetConfigResponse(BaseModel):
    id: str
    widget_type: str
    title: str
    description: Optional[str] = None
    button_text: str
    fields: List[FormFieldSchema]
    display_options: Dict[str, Any]
    submit_url: str


# ---------------------------------------------------------
# Submission Schemas
# ---------------------------------------------------------
class PublicSubmissionRequest(BaseModel):
    widget_id: str = Field(..., min_length=1, max_length=64)
    data: Dict[str, Any] = Field(..., description="User form field values")
    website_hp: Optional[str] = Field(
        default="",
        max_length=500,
        description="Honeypot field for anti-bot spam defense; MUST be empty"
    )

    @field_validator("data")
    @classmethod
    def validate_data_not_empty(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("Submission data cannot be empty")
        return v


class PublicSubmissionResponse(BaseModel):
    success: bool
    submission_id: str
    status: str
    message: str


class SubmissionDetailResponse(BaseModel):
    id: str
    widget_id: str
    payload: Dict[str, Any]
    geo_country: Optional[str] = None
    geo_city: Optional[str] = None
    geo_provider: Optional[str] = None
    status: str
    created_at: datetime


# ---------------------------------------------------------
# Dashboard & Analytics Schemas
# ---------------------------------------------------------
class WidgetStatItem(BaseModel):
    widget_id: str
    widget_name: str
    submission_count: int


class GeoStatItem(BaseModel):
    country: str
    count: int


class DashboardStatsResponse(BaseModel):
    total_submissions: int
    last_24h_count: int
    last_7d_count: int
    per_widget: List[WidgetStatItem]
    geo_breakdown: List[GeoStatItem]
