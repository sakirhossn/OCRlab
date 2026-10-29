"""Usage and quota status response schema."""

from pydantic import BaseModel


class UsageStatsResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    tier: str
    period_month: str  # "YYYY-MM"
    monthly_page_quota: int
    pages_used: int
    pages_remaining: int
    quota_percentage_used: float
    rate_limit_rpm: int
