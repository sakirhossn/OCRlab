"""Integration tests for the real dual-route OCR pipeline using ProductionOCRWorker."""

import pytest
from app.config import settings
from worker.worker_daemon import ProductionOCRWorker


@pytest.mark.asyncio
async def test_route_a_native_digital_pipeline(client, sample_tenant_and_key, make_pdf_bytes):
    _, _, raw_key = sample_tenant_and_key
    client_headers = {"Authorization": f"Bearer {raw_key}"}

    # 1. Upload digital PDF with mode="native_only"
    pdf_bytes = make_pdf_bytes(pages=1, text="Digital Native Vector Extraction Test")
    upload_res = await client.post(
        "/v1/documents",
        files={"file": ("digital_doc.pdf", pdf_bytes, "application/pdf")},
        data={"mode": "native_only"},
        headers=client_headers,
    )
    assert upload_res.status_code == 202
    job_id = upload_res.json()["job_id"]

    # 2. Instantiate and run Production OCR Worker
    worker = ProductionOCRWorker(
        worker_id="production-test-worker-01",
        control_plane_url="http://testserver",
        worker_token=settings.worker_auth_token,
        client=client,
    )
    processed = await worker.process_one_job()
    assert processed is True

    # 3. Verify Result Contract
    res = await client.get(f"/v1/jobs/{job_id}/result?format=json", headers=client_headers)
    assert res.status_code == 200
    contract = res.json()
    assert contract["schema_version"] == "1.0"
    assert contract["status"] == "succeeded"
    assert contract["page_count"] == 1
    assert contract["pages"][0]["route"] == "native_vector"
    assert len(contract["pages"][0]["blocks"]) > 0


@pytest.mark.asyncio
async def test_route_b_ai_ocr_pipeline(client, sample_tenant_and_key, make_pdf_bytes):
    _, _, raw_key = sample_tenant_and_key
    client_headers = {"Authorization": f"Bearer {raw_key}"}

    # 1. Upload PDF with mode="ocr_only" (forces Route B rasterization + Unlimited-OCR-2)
    pdf_bytes = make_pdf_bytes(pages=1, text="Scanned Document Simulation")
    upload_res = await client.post(
        "/v1/documents",
        files={"file": ("scanned_doc.pdf", pdf_bytes, "application/pdf")},
        data={"mode": "ocr_only"},
        headers=client_headers,
    )
    assert upload_res.status_code == 202
    job_id = upload_res.json()["job_id"]

    # 2. Instantiate and run Production OCR Worker
    worker = ProductionOCRWorker(
        worker_id="production-test-worker-02",
        control_plane_url="http://testserver",
        worker_token=settings.worker_auth_token,
        client=client,
    )
    processed = await worker.process_one_job()
    assert processed is True

    # 3. Verify Result Contract contains AI OCR blocks (headings, tables, formulas)
    res = await client.get(f"/v1/jobs/{job_id}/result?format=json", headers=client_headers)
    assert res.status_code == 200
    contract = res.json()
    assert contract["schema_version"] == "1.0"
    assert contract["status"] == "succeeded"
    assert contract["pages"][0]["route"] == "ai_ocr"

    blocks = contract["pages"][0]["blocks"]
    block_types = [b["type"] for b in blocks]
    assert "heading" in block_types
    assert "table" in block_types
    assert "formula" in block_types
    assert "paragraph" in block_types

    # 4. Verify Markdown and Text exports
    md_res = await client.get(f"/v1/jobs/{job_id}/result?format=markdown", headers=client_headers)
    assert md_res.status_code == 200
    assert "|" in md_res.text  # Table present

    txt_res = await client.get(f"/v1/jobs/{job_id}/result?format=text", headers=client_headers)
    assert txt_res.status_code == 200
    assert "Page 1" in txt_res.text
