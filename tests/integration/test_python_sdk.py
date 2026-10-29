"""Integration tests for the official Python SDK running against testserver."""

import pytest
from app.config import settings
from unlimited_ocr import AsyncUnlimitedOCRClient
from worker.mock_worker import MockOCRWorker


@pytest.mark.asyncio
async def test_python_sdk_lifecycle(client, sample_tenant_and_key, make_pdf_bytes):
    _, _, raw_key = sample_tenant_and_key

    # 1. Initialize Python SDK client passing the test transport client
    sdk_client = AsyncUnlimitedOCRClient(
        api_key=raw_key,
        base_url="http://testserver/v1",
        client=client,
    )

    # 2. Upload document via SDK
    pdf_bytes = make_pdf_bytes(pages=2, text="Python SDK Integration Test Document")
    upload_resp = await sdk_client.upload_document(
        file_bytes=pdf_bytes,
        filename="sdk_test.pdf",
        mode="auto",
    )
    assert upload_resp.job_id is not None
    assert upload_resp.status == "queued"
    assert upload_resp.page_count == 2
    job_id = upload_resp.job_id

    # 3. Process job via Mock Worker
    worker = MockOCRWorker(
        worker_id="sdk-mock-worker",
        base_url="http://testserver",
        worker_token=settings.worker_auth_token,
        client=client,
    )
    processed = await worker.process_one_job()
    assert processed is True

    # 4. Await completion via SDK
    finished_status = await sdk_client.wait_for_completion(job_id, poll_interval=0.05, timeout=10.0)
    assert finished_status.status == "succeeded"

    # 5. Fetch structured JSON Contract via SDK
    contract = await sdk_client.get_result_json(job_id)
    assert contract.schema_version == "1.0"
    assert contract.job_id == job_id
    assert contract.page_count == 2
    assert len(contract.pages) == 2

    # 6. Fetch Markdown & Text via SDK
    md = await sdk_client.get_result_markdown(job_id)
    assert "Page 1" in md

    txt = await sdk_client.get_result_text(job_id)
    assert "Page 1" in txt

    # 7. Check usage stats via SDK
    usage = await sdk_client.get_usage()
    assert usage.pages_used == 2
    assert usage.monthly_page_quota > 0
