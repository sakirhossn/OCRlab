"""Webhook request and response schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WebhookCreate(BaseModel):
    url: str = Field(description="HTTPS webhook destination URL")
    secret: str = Field(min_length=8, description="Secret key used for HMAC-SHA256 signature verification")
    events: Optional[List[str]] = Field(default_factory=lambda: ["job.completed", "job.failed"])


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime
