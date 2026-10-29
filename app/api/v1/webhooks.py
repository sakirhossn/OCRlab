"""Webhook configuration endpoints for tenants."""

from typing import List
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_tenant, get_db
from app.core.errors import NotFoundError
from app.models.tenant import Tenant
from app.models.webhook import WebhookEndpoint
from app.schemas.webhook import WebhookCreate, WebhookResponse
from app.services.webhook_service import webhook_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register webhook endpoint",
)
async def register_webhook(
    data: WebhookCreate,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    endpoint = await webhook_service.register_endpoint(
        session=session,
        tenant_id=tenant.id,
        url=data.url,
        secret=data.secret,
        events=data.events,
    )
    return WebhookResponse.model_validate(endpoint)


@router.get(
    "",
    response_model=List[WebhookResponse],
    summary="List active webhook endpoints",
)
async def list_webhooks(
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> List[WebhookResponse]:
    endpoints = await webhook_service.list_endpoints(session, tenant.id)
    return [WebhookResponse.model_validate(ep) for ep in endpoints]


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook endpoint",
)
async def delete_webhook(
    webhook_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> Response:
    endpoint = await session.get(WebhookEndpoint, webhook_id)
    if not endpoint or endpoint.tenant_id != tenant.id:
        raise NotFoundError("Webhook Endpoint")
    await session.delete(endpoint)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
