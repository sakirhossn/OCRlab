"""Rate limiting and monthly page quota management service."""

import time
from datetime import datetime, timezone
from typing import Dict, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.errors import QuotaExceededError, RateLimitExceededError
from app.models.tenant import Tenant
from app.models.usage import UsageRecord


class InMemoryTokenBucket:
    """Sliding-window token bucket rate limiter for local/single-node deployments."""

    def __init__(self):
        # key -> (tokens, last_updated_time)
        self.buckets: Dict[str, Tuple[float, float]] = {}

    def check_and_consume(self, key: str, rate_limit_rpm: int) -> bool:
        now = time.monotonic()
        capacity = float(rate_limit_rpm)
        fill_rate = capacity / 60.0  # tokens per second

        if key not in self.buckets:
            self.buckets[key] = (capacity - 1.0, now)
            return True

        tokens, last_time = self.buckets[key]
        elapsed = now - last_time
        tokens = min(capacity, tokens + elapsed * fill_rate)

        if tokens >= 1.0:
            self.buckets[key] = (tokens - 1.0, now)
            return True
        else:
            self.buckets[key] = (tokens, now)
            return False


token_bucket = InMemoryTokenBucket()


class QuotaService:
    """Checks and manages tenant monthly page quotas and rate limits."""

    @staticmethod
    def enforce_rate_limit(key_identifier: str, rate_limit_rpm: int) -> None:
        """Enforces rate limit or raises RateLimitExceededError."""
        allowed = token_bucket.check_and_consume(key_identifier, rate_limit_rpm)
        if not allowed:
            raise RateLimitExceededError(retry_after=10)

    @staticmethod
    async def get_monthly_usage(session: AsyncSession, tenant_id: str, period_month: str) -> int:
        """Calculates total pages processed by tenant in the given month."""
        stmt = select(func.coalesce(func.sum(UsageRecord.pages_processed), 0)).where(
            UsageRecord.tenant_id == tenant_id,
            UsageRecord.period_month == period_month,
        )
        result = await session.execute(stmt)
        return int(result.scalar_one())

    @classmethod
    async def check_and_reserve_quota(
        cls,
        session: AsyncSession,
        tenant: Tenant,
        requested_pages: int,
    ) -> None:
        """Checks if tenant has remaining quota for requested pages, otherwise raises QuotaExceededError."""
        now = datetime.now(timezone.utc)
        period_month = now.strftime("%Y-%m")

        used_pages = await cls.get_monthly_usage(session, tenant.id, period_month)
        if used_pages + requested_pages > tenant.monthly_page_quota:
            raise QuotaExceededError(
                f"Monthly quota exceeded. Used {used_pages}/{tenant.monthly_page_quota} pages; "
                f"requested {requested_pages} pages would exceed your tier limit."
            )

    @staticmethod
    async def record_usage(
        session: AsyncSession,
        tenant_id: str,
        job_id: str,
        pages_processed: int,
        mode_used: str,
    ) -> UsageRecord:
        """Records finalized page consumption."""
        now = datetime.now(timezone.utc)
        period_month = now.strftime("%Y-%m")

        record = UsageRecord(
            tenant_id=tenant_id,
            job_id=job_id,
            pages_processed=pages_processed,
            mode_used=mode_used,
            period_month=period_month,
        )
        session.add(record)
        await session.flush()
        return record


quota_service = QuotaService()
