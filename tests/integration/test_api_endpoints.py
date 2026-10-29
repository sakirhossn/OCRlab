"""Integration tests for all public REST API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_check_public(client):
    res = await client.get("/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "degraded")
    assert "version" in data
    assert data["service"] == "Unlimited OCR Cloud"


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client):
    res = await client.get("/v1/jobs")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_api_key_management_flow(client, sample_tenant_and_key):
    _, _, raw_key = sample_tenant_and_key
    headers = {"Authorization": f"Bearer {raw_key}"}

    # 1. Create a new API key
    create_res = await client.post(
        "/v1/api-keys",
        json={"name": "Frontend Agent Key", "rate_limit_rpm": 100, "monthly_quota": 500},
        headers=headers,
    )
    assert create_res.status_code == 201
    key_data = create_res.json()
    assert "secret_key" in key_data
    assert key_data["secret_key"].startswith("ocr_live_")
    new_key_id = key_data["id"]
    new_secret = key_data["secret_key"]

    # 2. List API keys (must NOT expose raw secret_key)
    list_res = await client.get("/v1/api-keys", headers=headers)
    assert list_res.status_code == 200
    keys = list_res.json()
    assert len(keys) >= 2
    for k in keys:
        assert "secret_key" not in k

    # 3. New key can authenticate
    new_auth_headers = {"Authorization": f"Bearer {new_secret}"}
    usage_res = await client.get("/v1/usage", headers=new_auth_headers)
    assert usage_res.status_code == 200

    # 4. Revoke key
    revoke_res = await client.delete(f"/v1/api-keys/{new_key_id}", headers=headers)
    assert revoke_res.status_code == 204

    # 5. Revoked key can no longer authenticate
    revoked_res = await client.get("/v1/usage", headers=new_auth_headers)
    assert revoked_res.status_code == 401


@pytest.mark.asyncio
async def test_document_upload_and_idempotency(client, sample_tenant_and_key, make_pdf_bytes):
    _, _, raw_key = sample_tenant_and_key
    headers = {"Authorization": f"Bearer {raw_key}", "Idempotency-Key": "idemp_test_uuid_12345"}

    pdf_bytes = make_pdf_bytes(pages=2, text="Audited Balance Sheet")

    # 1. First upload -> 202 Accepted
    res1 = await client.post(
        "/v1/documents",
        files={"file": ("balance_sheet.pdf", pdf_bytes, "application/pdf")},
        data={"mode": "auto"},
        headers=headers,
    )
    assert res1.status_code == 202
    data1 = res1.json()
    job_id_1 = data1["job_id"]
    assert data1["status"] == "queued"
    assert data1["page_count"] == 2

    # 2. Duplicate upload with same Idempotency-Key -> Returns same job_id without duplicate processing
    res2 = await client.post(
        "/v1/documents",
        files={"file": ("balance_sheet.pdf", pdf_bytes, "application/pdf")},
        data={"mode": "auto"},
        headers=headers,
    )
    assert res2.status_code == 202
    data2 = res2.json()
    assert data2["job_id"] == job_id_1

    # 3. Check job status
    status_res = await client.get(f"/v1/jobs/{job_id_1}", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["id"] == job_id_1

    # 4. Delete job
    del_res = await client.delete(f"/v1/jobs/{job_id_1}", headers=headers)
    assert del_res.status_code == 204

    # 5. Job is gone
    gone_res = await client.get(f"/v1/jobs/{job_id_1}", headers=headers)
    assert gone_res.status_code == 404
