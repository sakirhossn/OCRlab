"""Usage tracking and quota endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_tenant_and_key, get_db
from app.models.tenant import APIKey, Tenant
from app.schemas.usage import UsageStatsResponse
from app.services.quota_limiter import quota_service

router = APIRouter(prefix="/usage", tags=["Usage & Quotas"])


@router.get(
    "",
    response_model=UsageStatsResponse,
    summary="Get usage and quota status",
)
async def get_usage(
    auth_ctx: tuple[Tenant, APIKey] = Depends(get_current_tenant_and_key),
    session: AsyncSession = Depends(get_db),
) -> UsageStatsResponse:
    tenant, api_key = auth_ctx
    now = datetime.now(timezone.utc)
    period_month = now.strftime("%Y-%m")

    pages_used = await quota_service.get_monthly_usage(session, tenant.id, period_month)
    quota = tenant.monthly_page_quota
    remaining = max(0, quota - pages_used)
    pct = round((pages_used / quota) * 100, 2) if quota > 0 else 100.0

    return UsageStatsResponse(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tier=tenant.tier,
        period_month=period_month,
        monthly_page_quota=quota,
        pages_used=pages_used,
        pages_remaining=remaining,
        quota_percentage_used=pct,
        rate_limit_rpm=api_key.rate_limit_rpm,
    )
