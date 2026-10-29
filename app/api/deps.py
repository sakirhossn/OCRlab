"""FastAPI dependencies for authentication, tenant context, and database sessions."""

from typing import Optional, Tuple
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.errors import UnauthorizedError
from app.models.tenant import APIKey, Tenant
from app.services.quota_limiter import quota_service
from app.services.tenant_service import tenant_service


async def get_raw_api_key(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> str:
    """Extracts raw API key from Authorization Bearer or X-API-Key header."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if x_api_key:
        return x_api_key.strip()
    raise UnauthorizedError("Missing API key. Provide via 'Authorization: Bearer <key>' or 'X-API-Key: <key>' header.")


async def get_current_tenant_and_key(
    raw_key: str = Depends(get_raw_api_key),
    session: AsyncSession = Depends(get_db),
) -> Tuple[Tenant, APIKey]:
    """Authenticates the caller and enforces per-key rate limits."""
    tenant, api_key = await tenant_service.authenticate_key(session, raw_key)

    # Enforce rate limiting
    quota_service.enforce_rate_limit(f"apikey:{api_key.id}", api_key.rate_limit_rpm)

    return tenant, api_key


async def get_current_tenant(
    auth_ctx: Tuple[Tenant, APIKey] = Depends(get_current_tenant_and_key),
) -> Tenant:
    """Convenience dependency returning the authenticated Tenant."""
    return auth_ctx[0]
