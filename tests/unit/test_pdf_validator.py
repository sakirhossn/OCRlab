"""Unit tests for PDF and document image validator."""

import pytest
from app.core.errors import DocumentSecurityError
from app.services.pdf_validator import DocumentValidator


def test_validator_accepts_valid_pdf(make_pdf_bytes):
    validator = DocumentValidator(max_size_bytes=10 * 1024 * 1024, max_pages=50)
    pdf_bytes = make_pdf_bytes(pages=3, text="Quarterly Financial Audit Report")

    info = validator.validate_and_inspect(pdf_bytes, "audit.pdf")
    assert info.is_pdf is True
    assert info.mime_type == "application/pdf"
    assert info.page_count == 3
    assert info.is_encrypted is False
    assert info.is_digital_text is True


def test_validator_accepts_valid_png():
    validator = DocumentValidator()
    # Minimal 1x1 PNG image with magic bytes
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    info = validator.validate_and_inspect(png_bytes, "receipt.png")
    assert info.is_pdf is False
    assert info.mime_type == "image/png"
    assert info.page_count == 1


def test_validator_rejects_unsupported_file_format():
    validator = DocumentValidator()
    malicious_bytes = b"MZ\x90\x00\x03\x00\x00\x00ExecutableWindowsBinaryContent"

    with pytest.raises(DocumentSecurityError) as exc:
        validator.validate_and_inspect(malicious_bytes, "file.exe")
    assert exc.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_validator_rejects_exceeded_page_limit(make_pdf_bytes):
    validator = DocumentValidator(max_pages=5)
    pdf_bytes = make_pdf_bytes(pages=10)

    with pytest.raises(DocumentSecurityError) as exc:
        validator.validate_and_inspect(pdf_bytes, "long_manual.pdf")
    assert exc.value.code == "PAGE_LIMIT_EXCEEDED"


def test_validator_rejects_oversized_file(make_pdf_bytes):
    validator = DocumentValidator(max_size_bytes=100)  # Tiny 100 byte limit
    pdf_bytes = make_pdf_bytes(pages=1)

    with pytest.raises(DocumentSecurityError) as exc:
        validator.validate_and_inspect(pdf_bytes, "document.pdf")
    assert exc.value.code == "FILE_TOO_LARGE"


def test_validator_rejects_corrupted_pdf():
    validator = DocumentValidator()
    corrupt_bytes = b"%PDF-1.4\nCorrupted binary garbage that cannot be parsed."

    with pytest.raises(DocumentSecurityError) as exc:
        validator.validate_and_inspect(corrupt_bytes, "corrupt.pdf")
    assert exc.value.code == "MALFORMED_PDF"
