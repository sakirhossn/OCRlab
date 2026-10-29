"""Worker lease management and state machine orchestration."""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.errors import AppException, NotFoundError, UnauthorizedError
from app.core.security import generate_download_token
from app.core.storage import storage_vault
from app.models.document import Document
from app.models.job import Job, JobStatus
from app.models.result import Result
from app.schemas.worker import JobLeaseResponse, WorkerCompleteRequest, WorkerFailRequest
from app.services.quota_limiter import quota_service
from app.services.webhook_service import webhook_service


class LeaseService:
    @staticmethod
    async def claim_next_job(
        session: AsyncSession,
        worker_id: str,
    ) -> Optional[JobLeaseResponse]:
        """
        Atomically leases the oldest available queued job to a worker.
        Returns JobLeaseResponse or None if queue is empty.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(Job, Document)
            .join(Document, Job.document_id == Document.id)
            .where(Job.status == JobStatus.QUEUED.value)
            .order_by(Job.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = (await session.execute(stmt)).first()
        if not result:
            return None

        job, doc = result

        # Assign lease
        lease_expires = now + timedelta(seconds=settings.lease_timeout_seconds)
        job.status = JobStatus.LEASED.value
        job.lease_worker_id = worker_id
        job.leased_at = now
        job.lease_expires_at = lease_expires
        job.updated_at = now

        # Generate short-lived HMAC download token
        download_token = generate_download_token(
            document_id=doc.id,
            tenant_id=job.tenant_id,
            ttl_seconds=settings.lease_timeout_seconds,
        )

        await session.flush()

        return JobLeaseResponse(
            job_id=job.id,
            document_id=doc.id,
            filename=doc.filename,
            file_size_bytes=doc.file_size_bytes,
            page_count=doc.page_count,
            mode=job.mode,
            download_token=download_token,
            lease_expires_at=lease_expires,
        )

    @staticmethod
    async def renew_heartbeat(
        session: AsyncSession,
        job_id: str,
        worker_id: str,
        progress_pct: int,
    ) -> Job:
        """Extends worker lease timeout and updates progress."""
        now = datetime.now(timezone.utc)
        stmt = select(Job).where(Job.id == job_id)
        job = (await session.execute(stmt)).scalar_one_or_none()
        if not job:
            raise NotFoundError("Job")

        if job.lease_worker_id != worker_id:
            raise UnauthorizedError("Heartbeat rejected: worker ID does not match lease holder.")

        if job.status not in (JobStatus.LEASED.value, JobStatus.PROCESSING.value):
            raise AppException(
                code="INVALID_JOB_STATE",
                message=f"Cannot heartbeat job in state '{job.status}'",
                status_code=409,
            )

        job.status = JobStatus.PROCESSING.value
        job.progress_pct = max(job.progress_pct, progress_pct)
        job.lease_expires_at = now + timedelta(seconds=settings.lease_heartbeat_extension_seconds)
        job.updated_at = now

        await session.flush()
        return job

    @staticmethod
    async def complete_job(
        session: AsyncSession,
        job_id: str,
        worker_id: str,
        payload: WorkerCompleteRequest,
    ) -> Job:
        """Finalizes job, saves encrypted results, records usage, and dispatches webhook."""
        now = datetime.now(timezone.utc)
        stmt = select(Job, Document).join(Document, Job.document_id == Document.id).where(Job.id == job_id)
        res = (await session.execute(stmt)).first()
        if not res:
            raise NotFoundError("Job")

        job, doc = res
        if job.lease_worker_id != worker_id:
            raise UnauthorizedError("Completion rejected: worker ID does not match lease holder.")

        # 1. Save structured result JSON to AES-256-GCM vault
        json_bytes = json.dumps(payload.result_json, indent=2).encode("utf-8")
        json_path = storage_vault.encrypt_and_save(
            tenant_id=job.tenant_id,
            file_id=f"{job.id}_result",
            data=json_bytes,
            subfolder="results",
            extension=".json.enc",
        )

        md_path_str = None
        if payload.result_markdown:
            md_path = storage_vault.encrypt_and_save(
                tenant_id=job.tenant_id,
                file_id=f"{job.id}_result",
                data=payload.result_markdown.encode("utf-8"),
                subfolder="results",
                extension=".md.enc",
            )
            md_path_str = str(md_path)

        txt_path_str = None
        if payload.result_text:
            txt_path = storage_vault.encrypt_and_save(
                tenant_id=job.tenant_id,
                file_id=f"{job.id}_result",
                data=payload.result_text.encode("utf-8"),
                subfolder="results",
                extension=".txt.enc",
            )
            txt_path_str = str(txt_path)

        # 2. Create Result DB Record
        result_record = Result(
            job_id=job.id,
            tenant_id=job.tenant_id,
            engine=payload.engine,
            schema_version=payload.schema_version,
            result_json_path=str(json_path),
            result_md_path=md_path_str,
            result_txt_path=txt_path_str,
            processing_time_seconds=payload.processing_time_seconds,
            page_count=doc.page_count,
        )
        session.add(result_record)

        # 3. Transition Job to SUCCEEDED
        job.status = JobStatus.SUCCEEDED.value
        job.progress_pct = 100
        job.completed_at = now
        job.updated_at = now

        # 4. Record finalized page usage
        await quota_service.record_usage(
            session=session,
            tenant_id=job.tenant_id,
            job_id=job.id,
            pages_processed=doc.page_count,
            mode_used=job.mode,
        )

        # 5. Dispatch Webhook Event
        event_payload = {
            "event": "job.completed",
            "job_id": job.id,
            "document_id": doc.id,
            "status": "succeeded",
            "page_count": doc.page_count,
            "processing_time_seconds": payload.processing_time_seconds,
            "completed_at": now.isoformat(),
        }
        await webhook_service.dispatch_job_event(
            session=session,
            tenant_id=job.tenant_id,
            job_id=job.id,
            event_type="job.completed",
            event_payload=event_payload,
        )

        await session.flush()
        return job

    @staticmethod
    async def fail_job(
        session: AsyncSession,
        job_id: str,
        worker_id: str,
        payload: WorkerFailRequest,
    ) -> Job:
        """Handles job failure: re-queues if retryable, or marks failed and dead-letters."""
        now = datetime.now(timezone.utc)
        stmt = select(Job).where(Job.id == job_id)
        job = (await session.execute(stmt)).scalar_one_or_none()
        if not job:
            raise NotFoundError("Job")

        if job.lease_worker_id != worker_id:
            raise UnauthorizedError("Failure report rejected: worker ID does not match lease holder.")

        if payload.retryable and job.retry_count < job.max_retries:
            # Re-queue for another attempt
            job.status = JobStatus.QUEUED.value
            job.retry_count += 1
            job.lease_worker_id = None
            job.leased_at = None
            job.lease_expires_at = None
            job.updated_at = now
        else:
            # Permanent terminal failure
            job.status = JobStatus.FAILED.value
            job.error_code = payload.error_code
            job.error_message = payload.error_message
            job.completed_at = now
            job.updated_at = now

            # Dispatch job.failed webhook
            event_payload = {
                "event": "job.failed",
                "job_id": job.id,
                "document_id": job.document_id,
                "status": "failed",
                "error_code": payload.error_code,
                "error_message": payload.error_message,
                "failed_at": now.isoformat(),
            }
            await webhook_service.dispatch_job_event(
                session=session,
                tenant_id=job.tenant_id,
                job_id=job.id,
                event_type="job.failed",
                event_payload=event_payload,
            )

        await session.flush()
        return job

    @staticmethod
    async def reclaim_expired_leases(session: AsyncSession) -> int:
        """Scans for abandoned worker leases and reclaims or marks them failed."""
        now = datetime.now(timezone.utc)
        stmt = select(Job).where(
            Job.status.in_([JobStatus.LEASED.value, JobStatus.PROCESSING.value]),
            Job.lease_expires_at < now,
        )
        expired_jobs = (await session.execute(stmt)).scalars().all()
        reclaimed_count = 0

        for job in expired_jobs:
            if job.retry_count < job.max_retries:
                job.status = JobStatus.QUEUED.value
                job.retry_count += 1
                job.lease_worker_id = None
                job.leased_at = None
                job.lease_expires_at = None
            else:
                job.status = JobStatus.FAILED.value
                job.error_code = "WORKER_LEASE_TIMEOUT"
                job.error_message = "Worker lease expired without heartbeat and maximum retries were exceeded."
                job.completed_at = now

            job.updated_at = now
            reclaimed_count += 1

        if reclaimed_count > 0:
            await session.flush()
        return reclaimed_count


lease_service = LeaseService()
