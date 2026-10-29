"""Unit tests for quota manager and rate limiter."""

import pytest
from app.core.errors import QuotaExceededError, RateLimitExceededError
from app.models.tenant import Tenant
from app.services.quota_limiter import InMemoryTokenBucket, QuotaService


def test_token_bucket_burst_and_recovery():
    bucket = InMemoryTokenBucket()
    key = "tenant_test_rate"
    rpm = 5

    # Should consume 5 tokens successfully
    for _ in range(5):
        assert bucket.check_and_consume(key, rpm) is True

    # 6th immediate request must be rejected
    assert bucket.check_and_consume(key, rpm) is False


@pytest.mark.asyncio
async def test_quota_service_enforces_monthly_limit(db_session):
    tenant = Tenant(
        name="Small Org",
        slug="small-org",
        tier="free",
        monthly_page_quota=10,
    )
    db_session.add(tenant)
    await db_session.commit()

    # Request 8 pages (allowed, 8 <= 10)
    await QuotaService.check_and_reserve_quota(db_session, tenant, 8)
    await QuotaService.record_usage(db_session, tenant.id, "job_1", 8, "auto")

    # Request 2 pages (allowed, 8 + 2 == 10)
    await QuotaService.check_and_reserve_quota(db_session, tenant, 2)
    await QuotaService.record_usage(db_session, tenant.id, "job_2", 2, "auto")

    # Request 1 page (rejected, 10 + 1 > 10)
    with pytest.raises(QuotaExceededError) as exc:
        await QuotaService.check_and_reserve_quota(db_session, tenant, 1)
    assert exc.value.code == "QUOTA_EXCEEDED"
