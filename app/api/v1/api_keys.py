"""API key management endpoints."""

from typing import List
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_tenant, get_db
from app.models.tenant import Tenant
from app.schemas.api_key import APIKeyCreate, APIKeyCreatedSecretResponse, APIKeyResponse
from app.services.tenant_service import tenant_service

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post(
    "",
    response_model=APIKeyCreatedSecretResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Generates a new API key. Note: The secret_key is displayed only once.",
)
async def create_api_key(
    data: APIKeyCreate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> APIKeyCreatedSecretResponse:
    key_record, raw_secret = await tenant_service.create_api_key(session, tenant.id, data)
    key_dict = APIKeyResponse.model_validate(key_record).model_dump()
    key_dict["secret_key"] = raw_secret
    return APIKeyCreatedSecretResponse(**key_dict)


@router.get(
    "",
    response_model=List[APIKeyResponse],
    summary="List API keys",
)
async def list_api_keys(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> List[APIKeyResponse]:
    keys = await tenant_service.list_keys(session, tenant.id)
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API key",
)
async def revoke_api_key(
    key_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await tenant_service.revoke_key(session, tenant.id, key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
