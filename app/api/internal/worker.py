"""Internal GPU worker protocol endpoints (outbound HTTPS worker connection)."""

from typing import Optional
from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.database import get_db
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.security import verify_download_token
from app.core.storage import storage_vault
from app.models.document import Document
from app.schemas.worker import (
    JobLeaseRequest,
    JobLeaseResponse,
    WorkerCompleteRequest,
    WorkerFailRequest,
    WorkerHeartbeatRequest,
)
from app.services.lease_service import lease_service

router = APIRouter(prefix="/internal/v1/jobs", tags=["Internal Worker API"])


async def require_worker_auth(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_worker_token: Optional[str] = Header(None, alias="X-Worker-Token"),
) -> None:
    """Verifies that request originates from an authorized GPU worker daemon."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_worker_token:
        token = x_worker_token.strip()

    if not token or token != settings.worker_auth_token:
        raise UnauthorizedError("Unauthorized worker authentication token.")


@router.post(
    "/lease",
    response_model=Optional[JobLeaseResponse],
    summary="Lease next available queued job to worker",
)
async def lease_job(
    payload: JobLeaseRequest,
    _: None = Depends(require_worker_auth),
    session: AsyncSession = Depends(get_db),
) -> Optional[JobLeaseResponse]:
    return await lease_service.claim_next_job(session, payload.worker_id)


@router.post(
    "/{job_id}/heartbeat",
    summary="Renew lease timeout with progress update",
)
async def renew_heartbeat(
    job_id: str,
    payload: WorkerHeartbeatRequest,
    _: None = Depends(require_worker_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    job = await lease_service.renew_heartbeat(
        session, job_id, payload.worker_id, payload.progress_pct
    )
    return {"status": "heartbeat_acknowledged", "lease_expires_at": job.lease_expires_at}


@router.get(
    "/{job_id}/download",
    summary="Download encrypted document using short-lived signed token",
)
async def download_document(
    job_id: str,
    token: str = Query(..., description="Short-lived HMAC signed download token"),
    _: None = Depends(require_worker_auth),
    session: AsyncSession = Depends(get_db),
) -> Response:
    try:
        doc_id, tenant_id = verify_download_token(token)
    except Exception as e:
        raise UnauthorizedError(f"Invalid download token: {str(e)}")

    doc = await session.get(Document, doc_id)
    if not doc or doc.tenant_id != tenant_id:
        raise NotFoundError("Document")

    # Decrypt from vault and return
    file_bytes = storage_vault.read_and_decrypt(doc.storage_path)
    return Response(content=file_bytes, media_type=doc.mime_type)


@router.post(
    "/{job_id}/complete",
    summary="Complete job with structured JSON, Markdown, and text",
)
async def complete_job(
    job_id: str,
    payload: WorkerCompleteRequest,
    _: None = Depends(require_worker_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    job = await lease_service.complete_job(session, job_id, payload.worker_id, payload)
    return {"status": job.status, "completed_at": job.completed_at}


@router.post(
    "/{job_id}/fail",
    summary="Report job processing failure",
)
async def fail_job(
    job_id: str,
    payload: WorkerFailRequest,
    _: None = Depends(require_worker_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    job = await lease_service.fail_job(session, job_id, payload.worker_id, payload)
    return {"status": job.status, "retry_count": job.retry_count}


@router.post(
    "/reclaim-leases",
    summary="Admin / internal trigger to reclaim expired abandoned leases",
)
async def reclaim_leases(
    _: None = Depends(require_worker_auth),
    session: AsyncSession = Depends(get_db),
) -> dict:
    reclaimed = await lease_service.reclaim_expired_leases(session)
    return {"reclaimed_count": reclaimed}


@router.post(
    "/{job_id}/process-local",
    summary="Process job locally using native extraction engine",
)
async def process_job_local(
    job_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import select
    from app.models.job import Job
    from app.models.document import Document
    from app.core.storage import storage_vault
    from worker.worker_daemon import ProductionOCRWorker
    from app.schemas.worker import WorkerCompleteRequest
    from worker.post_processor import post_processor

    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("Job not found.")

    doc_stmt = select(Document).where(Document.id == job.document_id)
    doc_res = await session.execute(doc_stmt)
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document not found.")

    file_bytes = storage_vault.read_and_decrypt(doc.storage_path)

    worker = ProductionOCRWorker(worker_id="local-daemon", control_plane_url=f"http://127.0.0.1:{settings.port}")
    contract = await worker.process_document(file_bytes, doc.id, job.id, mode=job.mode)

    # Set worker lease ID and processing state
    job.status = "processing"
    job.lease_worker_id = "local-daemon"
    await session.flush()

    complete_req = WorkerCompleteRequest(
        worker_id="local-daemon",
        engine=contract.engine,
        schema_version=contract.schema_version,
        processing_time_seconds=contract.processing_time_seconds,
        result_json=contract.model_dump(),
        result_markdown=post_processor.render_markdown(contract),
        result_text=post_processor.render_plain_text(contract),
    )

    await lease_service.complete_job(session, job.id, "local-daemon", complete_req)
    await session.commit()
    return {"status": "succeeded", "job_id": job.id, "pages_processed": len(contract.pages)}
