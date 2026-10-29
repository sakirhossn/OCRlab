"""Unit tests for worker lease lifecycle, heartbeats, and timeout recovery."""

from datetime import datetime, timedelta, timezone
import pytest
from app.core.errors import UnauthorizedError
from app.models.document import Document
from app.models.job import Job, JobStatus
from app.models.tenant import Tenant
from app.services.lease_service import LeaseService


@pytest.mark.asyncio
async def test_worker_lease_claim_and_empty_queue(db_session):
    tenant = Tenant(name="Test Org", slug="test-org")
    db_session.add(tenant)
    await db_session.flush()

    doc = Document(
        tenant_id=tenant.id,
        filename="report.pdf",
        file_size_bytes=1000,
        mime_type="application/pdf",
        sha256_hash="hash123",
        storage_path="/tmp/test.enc",
        page_count=2,
    )
    db_session.add(doc)
    await db_session.flush()

    job = Job(
        tenant_id=tenant.id,
        document_id=doc.id,
        status=JobStatus.QUEUED.value,
        mode="auto",
    )
    db_session.add(job)
    await db_session.commit()

    # 1. Worker claims lease
    worker_id = "runpod-worker-01"
    lease = await LeaseService.claim_next_job(db_session, worker_id)
    assert lease is not None
    assert lease.job_id == job.id
    assert lease.filename == "report.pdf"
    assert lease.page_count == 2
    assert lease.download_token is not None

    # 2. Check DB state updated
    await db_session.refresh(job)
    assert job.status == JobStatus.LEASED.value
    assert job.lease_worker_id == worker_id
    assert job.lease_expires_at is not None

    # 3. Second claim attempt on empty queue returns None
    lease_2 = await LeaseService.claim_next_job(db_session, "other-worker")
    assert lease_2 is None


@pytest.mark.asyncio
async def test_heartbeat_renewal_and_mismatch_rejection(db_session):
    tenant = Tenant(name="Test Org 2", slug="test-org-2")
    db_session.add(tenant)
    await db_session.flush()

    job = Job(
        tenant_id=tenant.id,
        document_id="doc_xyz",
        status=JobStatus.LEASED.value,
        lease_worker_id="legit-worker",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=100),
    )
    db_session.add(job)
    await db_session.commit()

    # Legit worker heartbeats
    updated_job = await LeaseService.renew_heartbeat(db_session, job.id, "legit-worker", 40)
    assert updated_job.status == JobStatus.PROCESSING.value
    assert updated_job.progress_pct == 40

    # Rogue worker heartbeats -> rejected
    with pytest.raises(UnauthorizedError):
        await LeaseService.renew_heartbeat(db_session, job.id, "rogue-worker", 50)


@pytest.mark.asyncio
async def test_lease_timeout_recovery_and_dead_letter(db_session):
    tenant = Tenant(name="Recovery Org", slug="recovery-org")
    db_session.add(tenant)
    await db_session.flush()

    past_time = datetime.now(timezone.utc) - timedelta(seconds=600)

    # Job 1: retry_count = 0 -> should be re-queued
    job_retryable = Job(
        tenant_id=tenant.id,
        document_id="doc_1",
        status=JobStatus.PROCESSING.value,
        lease_worker_id="crashed-worker",
        lease_expires_at=past_time,
        retry_count=0,
        max_retries=3,
    )
    # Job 2: retry_count = 3 -> should fail with dead letter
    job_dead_letter = Job(
        tenant_id=tenant.id,
        document_id="doc_2",
        status=JobStatus.PROCESSING.value,
        lease_worker_id="crashed-worker-2",
        lease_expires_at=past_time,
        retry_count=3,
        max_retries=3,
    )
    db_session.add_all([job_retryable, job_dead_letter])
    await db_session.commit()

    # Reclaim expired leases
    reclaimed = await LeaseService.reclaim_expired_leases(db_session)
    assert reclaimed == 2

    await db_session.refresh(job_retryable)
    await db_session.refresh(job_dead_letter)

    # Job 1 transitioned to QUEUED
    assert job_retryable.status == JobStatus.QUEUED.value
    assert job_retryable.retry_count == 1
    assert job_retryable.lease_worker_id is None

    # Job 2 transitioned to FAILED
    assert job_dead_letter.status == JobStatus.FAILED.value
    assert job_dead_letter.error_code == "WORKER_LEASE_TIMEOUT"
