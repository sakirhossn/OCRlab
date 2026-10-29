"""Job lifecycle and result retrieval endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_tenant, get_db
from app.models.tenant import Tenant
from app.schemas.job import JobListResponse, JobStatusResponse, JobSummaryResponse
from app.services.job_service import job_service

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
)
async def get_job_status(
    job_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    job = await job_service.get_job_by_tenant(session, tenant.id, job_id)
    return JobStatusResponse.model_validate(job)


@router.get(
    "/{job_id}/result",
    summary="Retrieve OCR result in JSON, Markdown, or plain text",
)
async def get_job_result(
    job_id: str,
    format: str = Query("json", pattern="^(json|markdown|text)$"),
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> Response:
    media_type, content_bytes = await job_service.get_result_content(
        session, tenant.id, job_id, output_format=format
    )
    return Response(content=content_bytes, media_type=media_type)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List authorized jobs",
)
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> JobListResponse:
    items, total = await job_service.list_jobs_by_tenant(
        session, tenant.id, limit=limit, offset=offset
    )
    return JobListResponse(
        items=[JobSummaryResponse.model_validate(j) for j in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete job and purge document",
)
async def delete_job(
    job_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_db),
) -> Response:
    await job_service.delete_job_and_document(session, tenant.id, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
