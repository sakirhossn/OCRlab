"""Tenant and organization schemas."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=100)
    tier: str = Field(default="free")
    monthly_page_quota: int = Field(default=1000, ge=10)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    tier: str
    monthly_page_quota: int
    is_active: bool
    created_at: datetime
