"""API key request and response schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class APIKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    scopes: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_rpm: int = Field(default=60, ge=1, le=1000)
    monthly_quota: int = Field(default=1000, ge=10)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    key_prefix: str
    scopes: List[str]
    rate_limit_rpm: int
    monthly_quota: int
    usage_count: int
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_revoked: bool
    created_at: datetime


class APIKeyCreatedSecretResponse(APIKeyResponse):
    """Returned ONLY ONCE upon key creation. Contains the raw secret key."""
    secret_key: str = Field(
        description="The plaintext secret API key. Store this securely; it will never be displayed again."
    )
