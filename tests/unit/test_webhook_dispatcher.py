"""Unit tests for SSRF defense, webhook signature generation, and delivery."""

import pytest
from app.core.errors import DocumentSecurityError
from app.services.webhook_service import validate_outbound_url


def test_ssrf_rejects_cloud_metadata_service():
    # Explicit AWS / OCI / GCP metadata IP
    with pytest.raises(DocumentSecurityError) as exc:
        validate_outbound_url("https://169.254.169.254/metadata/v1")
    assert "metadata" in exc.value.message.lower() or "link_local" in exc.value.code.lower() or "metadata" in exc.value.code.lower()


def test_ssrf_rejects_private_rfc1918_addresses():
    private_urls = [
        "https://10.0.0.1/webhook",
        "https://172.16.0.5:8443/webhook",
        "https://192.168.1.100/callback",
    ]
    for url in private_urls:
        with pytest.raises(DocumentSecurityError) as exc:
            validate_outbound_url(url)
        assert "private" in exc.value.message.lower() or "prohibited" in exc.value.code.lower()


def test_ssrf_rejects_insecure_scheme_in_production(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "environment", "production")

    with pytest.raises(DocumentSecurityError) as exc:
        validate_outbound_url("http://example.com/webhook")
    assert exc.value.code in ("INSECURE_WEBHOOK_SCHEME", "UNSUPPORTED_SCHEME")


def test_ssrf_rejects_unsupported_protocols():
    unsupported = [
        "ftp://example.com/file",
        "file:///etc/passwd",
        "gopher://example.com",
    ]
    for url in unsupported:
        with pytest.raises(DocumentSecurityError) as exc:
            validate_outbound_url(url)
        assert exc.value.code == "UNSUPPORTED_SCHEME"


def test_ssrf_allows_legitimate_https_url():
    # Known public domain
    url = "https://httpbin.org/post"
    validated = validate_outbound_url(url)
    assert validated == url
