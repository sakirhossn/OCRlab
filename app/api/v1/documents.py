"""Document submission and job creation API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_tenant_and_key, get_db
from app.core.errors import DocumentSecurityError
from app.models.tenant import APIKey, Tenant
from app.schemas.job import DocumentUploadResponse
from app.services.job_service import job_service

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload document and create OCR job",
    description="Accepts PDF, PNG, or JPEG file for asynchronous structured OCR processing.",
)
async def upload_document(
    file: UploadFile = File(...),
    mode: str = Form(default="auto"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    auth_ctx: tuple[Tenant, APIKey] = Depends(get_current_tenant_and_key),
    session: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    tenant, api_key = auth_ctx

    if not file.filename:
        raise DocumentSecurityError("Filename must not be empty.", code="INVALID_FILENAME")

    # Read binary bytes
    content = await file.read()

    response = await job_service.create_document_and_job(
        session=session,
        tenant=tenant,
        file_bytes=content,
        filename=file.filename,
        mode=mode,
        api_key_id=api_key.id,
        idempotency_key=idempotency_key,
    )
    return response
