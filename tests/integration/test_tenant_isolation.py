"""Integration tests for multi-tenant isolation and security boundaries."""

import pytest
from app.core.security import generate_api_key
from app.models.tenant import APIKey, Tenant


@pytest.mark.asyncio
async def test_tenant_data_isolation(client, db_session, make_pdf_bytes):
    # Setup Tenant Alpha
    tenant_a = Tenant(name="Tenant Alpha", slug="tenant-alpha", monthly_page_quota=100)
    db_session.add(tenant_a)
    await db_session.flush()

    raw_key_a, prefix_a, hash_a = generate_api_key()
    key_a = APIKey(tenant_id=tenant_a.id, name="Key A", key_prefix=prefix_a, hashed_key=hash_a)
    db_session.add(key_a)

    # Setup Tenant Beta
    tenant_b = Tenant(name="Tenant Beta", slug="tenant-beta", monthly_page_quota=100)
    db_session.add(tenant_b)
    await db_session.flush()

    raw_key_b, prefix_b, hash_b = generate_api_key()
    key_b = APIKey(tenant_id=tenant_b.id, name="Key B", key_prefix=prefix_b, hashed_key=hash_b)
    db_session.add(key_b)
    await db_session.commit()

    headers_a = {"Authorization": f"Bearer {raw_key_a}"}
    headers_b = {"Authorization": f"Bearer {raw_key_b}"}

    # 1. Tenant A uploads a document
    pdf_bytes = make_pdf_bytes(pages=2, text="Alpha Private Data")
    upload_res = await client.post(
        "/v1/documents",
        files={"file": ("alpha_report.pdf", pdf_bytes, "application/pdf")},
        data={"mode": "auto"},
        headers=headers_a,
    )
    assert upload_res.status_code == 202
    job_id_a = upload_res.json()["job_id"]

    # 2. Tenant A can view the job
    res_a = await client.get(f"/v1/jobs/{job_id_a}", headers=headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["id"] == job_id_a

    # 3. Tenant B MUST NOT be able to view Tenant A's job (must return 404 Not Found)
    res_b = await client.get(f"/v1/jobs/{job_id_a}", headers=headers_b)
    assert res_b.status_code == 404
    assert res_b.json()["error"]["code"] == "NOT_FOUND"

    # 4. Tenant B MUST NOT be able to delete Tenant A's job
    del_b = await client.delete(f"/v1/jobs/{job_id_a}", headers=headers_b)
    assert del_b.status_code == 404

    # 5. List jobs verification: Tenant B's job list contains 0 items
    list_b = await client.get("/v1/jobs", headers=headers_b)
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0
    assert len(list_b.json()["items"]) == 0

    # Tenant A's job list contains 1 item
    list_a = await client.get("/v1/jobs", headers=headers_a)
    assert list_a.status_code == 200
    assert list_a.json()["total"] == 1
    assert list_a.json()["items"][0]["id"] == job_id_a
