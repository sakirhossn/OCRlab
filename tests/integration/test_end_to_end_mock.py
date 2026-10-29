"""Complete End-to-End integration test simulating the entire lifecycle with the mock worker."""

import pytest
from app.config import settings
from worker.mock_worker import MockOCRWorker


@pytest.mark.asyncio
async def test_complete_end_to_end_pipeline(client, sample_tenant_and_key, make_pdf_bytes):
    _, _, raw_key = sample_tenant_and_key
    client_headers = {"Authorization": f"Bearer {raw_key}"}

    # 1. Upload a 2-page digital PDF via REST API
    pdf_bytes = make_pdf_bytes(pages=2, text="Annual Corporate Performance Review")
    upload_res = await client.post(
        "/v1/documents",
        files={"file": ("performance_review.pdf", pdf_bytes, "application/pdf")},
        data={"mode": "auto"},
        headers=client_headers,
    )
    assert upload_res.status_code == 202
    upload_data = upload_res.json()
    job_id = upload_data["job_id"]
    assert upload_data["status"] == "queued"
    assert upload_data["page_count"] == 2

    # 2. Verify job is currently queued
    status_res = await client.get(f"/v1/jobs/{job_id}", headers=client_headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "queued"

    # 3. Instantiate Mock Worker using the test client
    mock_worker = MockOCRWorker(
        worker_id="modal-test-worker-01",
        base_url="http://testserver",
        worker_token=settings.worker_auth_token,
        client=client,
    )

    # 4. Mock worker leases and processes the job
    processed = await mock_worker.process_one_job()
    assert processed is True

    # 5. Verify job is now SUCCEEDED
    status_res_after = await client.get(f"/v1/jobs/{job_id}", headers=client_headers)
    assert status_res_after.status_code == 200
    job_info = status_res_after.json()
    assert job_info["status"] == "succeeded"
    assert job_info["progress_pct"] == 100

    # 6. Retrieve structured JSON result
    json_res = await client.get(f"/v1/jobs/{job_id}/result?format=json", headers=client_headers)
    assert json_res.status_code == 200
    assert "application/json" in json_res.headers["content-type"]
    result_data = json_res.json()
    assert result_data["schema_version"] == "1.0"
    assert result_data["job_id"] == job_id
    assert result_data["status"] == "succeeded"
    assert result_data["page_count"] == 2
    assert len(result_data["pages"]) == 2
    assert len(result_data["pages"][0]["blocks"]) > 0

    # 7. Retrieve Markdown result
    md_res = await client.get(f"/v1/jobs/{job_id}/result?format=markdown", headers=client_headers)
    assert md_res.status_code == 200
    assert "text/markdown" in md_res.headers["content-type"]
    assert "Page 1" in md_res.text

    # 8. Retrieve Plain Text result
    txt_res = await client.get(f"/v1/jobs/{job_id}/result?format=text", headers=client_headers)
    assert txt_res.status_code == 200
    assert "text/plain" in txt_res.headers["content-type"]
    assert "Page 1" in txt_res.text

    # 9. Verify monthly usage accounting
    usage_res = await client.get("/v1/usage", headers=client_headers)
    assert usage_res.status_code == 200
    usage_data = usage_res.json()
    assert usage_data["pages_used"] == 2
    assert usage_data["pages_remaining"] == usage_data["monthly_page_quota"] - 2
