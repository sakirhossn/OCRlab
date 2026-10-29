"""Job orchestration, document ingestion, and compliance purge services."""

import json
import uuid
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.errors import AppException, NotFoundError
from app.core.storage import storage_vault
from app.models.document import Document
from app.models.job import Job, JobMode, JobStatus
from app.models.result import Result
from app.models.tenant import Tenant
from app.schemas.job import DocumentUploadResponse
from app.services.pdf_validator import document_validator
from app.services.quota_limiter import quota_service


class JobService:
    @staticmethod
    async def create_document_and_job(
        session: AsyncSession,
        tenant: Tenant,
        file_bytes: bytes,
        filename: str,
        mode: str = "auto",
        api_key_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> DocumentUploadResponse:
        """
        Ingests and validates document bytes, checks quotas, encrypts at rest,
        and creates an asynchronous job record.
        """
        # Idempotency check: if identical key already exists, return existing job
        if idempotency_key:
            stmt = select(Job, Document).join(Document, Job.document_id == Document.id).where(
                Job.tenant_id == tenant.id,
                Job.idempotency_key == idempotency_key,
            )
            existing = (await session.execute(stmt)).first()
            if existing:
                job, doc = existing
                return DocumentUploadResponse(
                    document_id=doc.id,
                    job_id=job.id,
                    status=job.status,
                    filename=doc.filename,
                    file_size_bytes=doc.file_size_bytes,
                    page_count=doc.page_count,
                    mode=job.mode,
                    created_at=job.created_at,
                )

        # 1. Validation & Safety Inspection
        info = document_validator.validate_and_inspect(file_bytes, filename)

        # 2. Quota Check (pre-flight check)
        await quota_service.check_and_reserve_quota(session, tenant, info.page_count)

        # 3. Encrypted Storage at Rest (AES-256-GCM)
        doc_id = str(uuid.uuid4())
        storage_path = storage_vault.encrypt_and_save(
            tenant_id=tenant.id,
            file_id=doc_id,
            data=info.file_bytes,
            subfolder="docs",
        )

        # 4. Create Document Record
        document = Document(
            id=doc_id,
            tenant_id=tenant.id,
            filename=filename,
            file_size_bytes=info.file_size_bytes,
            mime_type=info.mime_type,
            sha256_hash=info.sha256_hash,
            storage_path=str(storage_path),
            page_count=info.page_count,
            is_encrypted=False,
            is_purged=False,
        )
        session.add(document)

        # 5. Create Job Record
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            tenant_id=tenant.id,
            document_id=doc_id,
            api_key_id=api_key_id,
            idempotency_key=idempotency_key,
            status=JobStatus.QUEUED.value,
            mode=mode if mode in [m.value for m in JobMode] else JobMode.AUTO.value,
        )
        session.add(job)
        await session.flush()

        return DocumentUploadResponse(
            document_id=doc_id,
            job_id=job_id,
            status=job.status,
            filename=filename,
            file_size_bytes=info.file_size_bytes,
            page_count=info.page_count,
            mode=job.mode,
            created_at=job.created_at,
        )

    @staticmethod
    async def get_job_by_tenant(
        session: AsyncSession,
        tenant_id: str,
        job_id: str,
    ) -> Job:
        """Retrieves a job strictly scoped by tenant_id."""
        stmt = select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            raise NotFoundError("Job")
        return job

    @staticmethod
    async def list_jobs_by_tenant(
        session: AsyncSession,
        tenant_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Job], int]:
        """Returns paginated jobs and total count for a tenant."""
        count_stmt = select(func.count(Job.id)).where(Job.tenant_id == tenant_id)
        total = (await session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Job)
            .where(Job.tenant_id == tenant_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    @staticmethod
    async def get_result_content(
        session: AsyncSession,
        tenant_id: str,
        job_id: str,
        output_format: str = "json",
    ) -> Tuple[str, bytes]:
        """Retrieves and decrypts the job result in requested format (json, markdown, text)."""
        job = await JobService.get_job_by_tenant(session, tenant_id, job_id)
        if job.status != JobStatus.SUCCEEDED.value:
            raise AppException(
                code="JOB_NOT_COMPLETED",
                message=f"Job status is '{job.status}'. Results are only available for succeeded jobs.",
                status_code=400,
            )

        stmt = select(Result).where(Result.job_id == job_id, Result.tenant_id == tenant_id)
        res = (await session.execute(stmt)).scalar_one_or_none()
        if not res:
            raise NotFoundError("Result")

        if output_format == "markdown" and res.result_md_path:
            content = storage_vault.read_and_decrypt(res.result_md_path)
            return "text/markdown; charset=utf-8", content
        elif output_format == "text" and res.result_txt_path:
            content = storage_vault.read_and_decrypt(res.result_txt_path)
            return "text/plain; charset=utf-8", content
        else:
            content = storage_vault.read_and_decrypt(res.result_json_path)
            return "application/json; charset=utf-8", content

    @staticmethod
    async def delete_job_and_document(
        session: AsyncSession,
        tenant_id: str,
        job_id: str,
    ) -> None:
        """Permanently deletes job, results, and shreds document file from storage vault."""
        job = await JobService.get_job_by_tenant(session, tenant_id, job_id)

        # Purge document file
        doc = await session.get(Document, job.document_id)
        if doc and not doc.is_purged:
            storage_vault.delete_file(doc.storage_path)
            doc.is_purged = True

        # Purge result files if existing
        stmt = select(Result).where(Result.job_id == job_id)
        result_record = (await session.execute(stmt)).scalar_one_or_none()
        if result_record:
            if result_record.result_json_path:
                storage_vault.delete_file(result_record.result_json_path)
            if result_record.result_md_path:
                storage_vault.delete_file(result_record.result_md_path)
            if result_record.result_txt_path:
                storage_vault.delete_file(result_record.result_txt_path)
            await session.delete(result_record)

        await session.delete(job)
        await session.flush()


job_service = JobService()
