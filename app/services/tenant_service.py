"""Tenant management and API key authentication services."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.security import generate_api_key, verify_api_key
from app.models.tenant import APIKey, Tenant
from app.schemas.api_key import APIKeyCreate
from app.schemas.tenant import TenantCreate


class TenantService:
    @staticmethod
    async def create_tenant(session: AsyncSession, data: TenantCreate) -> Tenant:
        tenant = Tenant(
            name=data.name,
            slug=data.slug,
            tier=data.tier,
            monthly_page_quota=data.monthly_page_quota,
        )
        session.add(tenant)
        await session.flush()
        return tenant

    @staticmethod
    async def get_tenant(session: AsyncSession, tenant_id: str) -> Tenant:
        stmt = select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise NotFoundError("Tenant")
        return tenant

    @staticmethod
    async def create_api_key(
        session: AsyncSession,
        tenant_id: str,
        data: APIKeyCreate,
    ) -> Tuple[APIKey, str]:
        """Generates a new API key. Returns the APIKey database record and the raw secret."""
        raw_key, prefix, hashed_key = generate_api_key()

        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

        api_key = APIKey(
            tenant_id=tenant_id,
            name=data.name,
            key_prefix=prefix,
            hashed_key=hashed_key,
            scopes=data.scopes,
            rate_limit_rpm=data.rate_limit_rpm,
            monthly_quota=data.monthly_quota,
            expires_at=expires_at,
        )
        session.add(api_key)
        await session.flush()
        return api_key, raw_key

    @staticmethod
    async def authenticate_key(session: AsyncSession, raw_key: str) -> Tuple[Tenant, APIKey]:
        """Authenticates a raw API key using constant-time Argon2id comparison."""
        if not raw_key or len(raw_key) < 16:
            raise UnauthorizedError("Malformed API key")

        prefix = raw_key[:16]
        stmt = select(APIKey).where(
            APIKey.key_prefix == prefix,
            APIKey.is_revoked == False,
        )
        result = await session.execute(stmt)
        keys = result.scalars().all()

        matched_key: Optional[APIKey] = None
        for k in keys:
            if verify_api_key(raw_key, k.hashed_key):
                matched_key = k
                break

        if not matched_key:
            raise UnauthorizedError("Invalid API key")

        # Check expiration
        now = datetime.now(timezone.utc)
        if matched_key.expires_at and matched_key.expires_at < now:
            raise UnauthorizedError("API key has expired")

        # Update last used
        matched_key.last_used_at = now
        matched_key.usage_count += 1
        await session.flush()

        # Load tenant
        tenant = await session.get(Tenant, matched_key.tenant_id)
        if not tenant or not tenant.is_active:
            raise UnauthorizedError("Associated tenant is deactivated")

        return tenant, matched_key

    @staticmethod
    async def list_keys(session: AsyncSession, tenant_id: str) -> List[APIKey]:
        stmt = select(APIKey).where(APIKey.tenant_id == tenant_id, APIKey.is_revoked == False)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def revoke_key(session: AsyncSession, tenant_id: str, key_id: str) -> None:
        stmt = select(APIKey).where(APIKey.id == key_id, APIKey.tenant_id == tenant_id)
        result = await session.execute(stmt)
        key = result.scalar_one_or_none()
        if not key:
            raise NotFoundError("API Key")
        key.is_revoked = True
        await session.flush()


tenant_service = TenantService()
