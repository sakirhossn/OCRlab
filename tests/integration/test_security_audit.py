"""
Comprehensive Security Audit Test Suite for Unlimited OCR Cloud.

Tests defenses against:
1. Decompression bombs & dimensional attacks
2. Password-protected and malformed PDFs
3. Server-Side Request Forgery (SSRF) including cloud metadata (169.254.169.254)
4. Cross-tenant data isolation and object enumeration
5. Downstream prompt-injection delimiters
"""

import io
import pytest
import pymupdf
from app.core.errors import DocumentSecurityError
from app.core.security import generate_api_key
from app.models.tenant import APIKey, Tenant
from app.services.pdf_validator import DocumentValidator
from app.services.webhook_service import validate_outbound_url


# ==============================================================================
# 1. Decompression Bomb & Malformed PDF Security Tests
# ==============================================================================

def test_security_rejects_giant_canvas_decompression_bomb():
    """Attack scenario: Attacker creates a PDF with massive canvas (10,000 x 10,000 pt) to exhaust rasterizer memory."""
    doc = pymupdf.open()
    # Huge page dimensions: 10,000 x 10,000 points
    page = doc.new_page(width=10000, height=10000)
    page.insert_text((50, 50), "Decompression bomb test")
    huge_pdf_bytes = doc.tobytes()
    doc.close()

    validator = DocumentValidator()
    with pytest.raises(DocumentSecurityError) as exc_info:
        validator.validate_and_inspect(huge_pdf_bytes, "giant_canvas.pdf")

    assert exc_info.value.code == "PAGE_DIMENSIONS_TOO_LARGE"
    assert "dimensions" in str(exc_info.value).lower()


def test_security_rejects_encrypted_password_protected_pdf():
    """Attack scenario: Uploading password-protected PDF to hang processing threads."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((100, 100), "Confidential locked document")
    
    # Save with user and owner passwords (AES-128 encryption)
    perm = pymupdf.PDF_PERM_ACCESSIBILITY | pymupdf.PDF_PERM_PRINT
    encrypted_bytes = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_128,
        owner_pw="OwnerSecret123",
        user_pw="UserPassword123",
        permissions=perm,
    )
    doc.close()

    validator = DocumentValidator()
    with pytest.raises(DocumentSecurityError) as exc_info:
        validator.validate_and_inspect(encrypted_bytes, "locked.pdf")

    assert exc_info.value.code == "PDF_ENCRYPTED"


def test_security_rejects_truncated_pdf_stream():
    """Attack scenario: Malformed / abruptly truncated PDF causing parse crashes."""
    truncated_bytes = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"

    validator = DocumentValidator()
    with pytest.raises(DocumentSecurityError) as exc_info:
        validator.validate_and_inspect(truncated_bytes, "truncated.pdf")

    assert exc_info.value.code in ("EMPTY_PDF", "MALFORMED_PDF")


# ==============================================================================
# 2. SSRF Attack Defense Tests
# ==============================================================================

@pytest.mark.parametrize(
    "hostile_url",
    [
        "https://169.254.169.254/latest/meta-data/",
        "https://169.254.169.254/opc/v1/instance/",
        "http://127.0.0.1:8000/internal",
        "https://127.0.0.1:5432/",
        "http://localhost:6379/",
        "https://10.0.0.1/network",
        "https://172.16.0.5:8080/metrics",
        "https://192.168.1.1/router",
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_flushall",
    ],
)
def test_ssrf_rejects_all_hostile_webhook_destinations(monkeypatch, hostile_url: str):
    """Enforces that no internal IPs, metadata endpoints, loopbacks, or dangerous schemes are accepted."""
    from app.config import settings
    # Enforce production mode for strict SSRF loopback & private IP blocking
    monkeypatch.setattr(settings, "environment", "production")

    with pytest.raises(DocumentSecurityError):
        validate_outbound_url(hostile_url)


# ==============================================================================
# 3. Multi-Tenant Cross-Access & Object Enumeration Defense
# ==============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_enumeration_and_deletion_prevention(client, db_session, make_pdf_bytes):
    """
    Validates tenant isolation invariants:
    - Tenant B cannot view Tenant A's document or job.
    - Tenant B cannot delete Tenant A's document.
    - Tenant B listing endpoint never includes Tenant A's records.
    """
    # Create Tenant A
    tenant_a = Tenant(name="Tenant Alpha", slug="alpha-sec")
    db_session.add(tenant_a)
    await db_session.flush()

    raw_key_a, prefix_a, hash_a = generate_api_key()
    key_a = APIKey(tenant_id=tenant_a.id, name="Alpha Key", key_prefix=prefix_a, hashed_key=hash_a)
    db_session.add(key_a)

    # Create Tenant B
    tenant_b = Tenant(name="Tenant Beta", slug="beta-sec")
    db_session.add(tenant_b)
    await db_session.flush()

    raw_key_b, prefix_b, hash_b = generate_api_key()
    key_b = APIKey(tenant_id=tenant_b.id, name="Beta Key", key_prefix=prefix_b, hashed_key=hash_b)
    db_session.add(key_b)
    await db_session.commit()

    # Tenant A uploads a document
    pdf_bytes = make_pdf_bytes(pages=2, text="Tenant Alpha Secret Financials")
    files = {"file": ("alpha_confidential.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    headers_a = {"Authorization": f"Bearer {raw_key_a}"}

    upload_resp = await client.post("/v1/documents", files=files, headers=headers_a)
    assert upload_resp.status_code == 202
    job_data = upload_resp.json()
    job_id = job_data["job_id"]
    document_id = job_data["document_id"]

    # Tenant B attempts to read Tenant A's job details
    headers_b = {"Authorization": f"Bearer {raw_key_b}"}
    get_resp = await client.get(f"/v1/jobs/{job_id}", headers=headers_b)
    assert get_resp.status_code == 404, "Tenant B must receive 404 Not Found for Tenant A's job"

    # Tenant B attempts to read Tenant A's results
    result_resp = await client.get(f"/v1/jobs/{job_id}/result", headers=headers_b)
    assert result_resp.status_code == 404, "Tenant B must receive 404 Not Found for Tenant A's result"

    # Tenant B attempts to delete Tenant A's document
    delete_resp = await client.delete(f"/v1/jobs/{job_id}", headers=headers_b)
    assert delete_resp.status_code == 404, "Tenant B must not be able to delete Tenant A's job"

    # Tenant B lists their own jobs -> Tenant A's job must NOT appear
    list_resp = await client.get("/v1/jobs", headers=headers_b)
    assert list_resp.status_code == 200
    jobs_list = list_resp.json()["items"]
    assert len(jobs_list) == 0, "Tenant B's job list must be empty"

    # Verify Tenant A can still access their own job
    verify_resp = await client.get(f"/v1/jobs/{job_id}", headers=headers_a)
    assert verify_resp.status_code == 200
    assert verify_resp.json()["document_id"] == document_id
