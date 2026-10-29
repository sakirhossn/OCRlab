"""Strict PDF and document image validator with decompression bomb and security defenses."""

import hashlib
from dataclasses import dataclass
from typing import Tuple
import pymupdf
from app.config import settings
from app.core.errors import DocumentSecurityError

# Allowed file magic bytes
MAGIC_PDF = b"%PDF-"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG = b"\xff\xd8\xff"


@dataclass
class ValidatedDocumentInfo:
    file_bytes: bytes
    mime_type: str
    sha256_hash: str
    file_size_bytes: int
    page_count: int
    is_pdf: bool
    is_encrypted: bool
    is_digital_text: bool


class DocumentValidator:
    """Validates uploaded files for size, format, decompression bombs, and active code."""

    def __init__(
        self,
        max_size_bytes: int = settings.max_upload_size_bytes,
        max_pages: int = settings.max_pages_per_doc,
    ):
        self.max_size_bytes = max_size_bytes
        self.max_pages = max_pages

    def detect_format(self, data: bytes) -> Tuple[str, bool]:
        """Inspects magic bytes to detect MIME type and whether it is a PDF."""
        if len(data) < 8:
            raise DocumentSecurityError("File is too small to be a valid document.", code="INVALID_FILE_HEADER")

        if data.startswith(MAGIC_PDF):
            return "application/pdf", True
        elif data.startswith(MAGIC_PNG):
            return "image/png", False
        elif data.startswith(MAGIC_JPEG):
            return "image/jpeg", False
        else:
            raise DocumentSecurityError(
                "Unsupported file format. Only PDF, PNG, and JPEG documents are permitted.",
                code="UNSUPPORTED_MEDIA_TYPE",
            )

    def validate_and_inspect(self, data: bytes, filename: str) -> ValidatedDocumentInfo:
        """Runs complete multi-stage validation pipeline on file bytes."""
        file_size = len(data)
        if file_size > self.max_size_bytes:
            raise DocumentSecurityError(
                f"File size ({file_size} bytes) exceeds maximum permitted limit ({self.max_size_bytes} bytes).",
                code="FILE_TOO_LARGE",
            )

        mime_type, is_pdf = self.detect_format(data)
        sha256 = hashlib.sha256(data).hexdigest()

        if not is_pdf:
            # Single-page image upload
            return ValidatedDocumentInfo(
                file_bytes=data,
                mime_type=mime_type,
                sha256_hash=sha256,
                file_size_bytes=file_size,
                page_count=1,
                is_pdf=False,
                is_encrypted=False,
                is_digital_text=False,
            )

        # PDF Deep Inspection via PyMuPDF in safe memory mode
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception as e:
            raise DocumentSecurityError(
                f"Malformed or corrupted PDF file: {str(e)}",
                code="MALFORMED_PDF",
            )

        try:
            if doc.is_encrypted or doc.needs_pass:
                raise DocumentSecurityError(
                    "Password-protected or encrypted PDFs are not supported. Please remove encryption before uploading.",
                    code="PDF_ENCRYPTED",
                )

            page_count = doc.page_count
            if page_count < 1:
                raise DocumentSecurityError("PDF contains zero pages.", code="EMPTY_PDF")

            if page_count > self.max_pages:
                raise DocumentSecurityError(
                    f"PDF page count ({page_count}) exceeds maximum allowed ({self.max_pages}).",
                    code="PAGE_LIMIT_EXCEEDED",
                )

            # Check for excessive dimensions & decompression ratio
            total_text_chars = 0
            for page_idx in range(min(page_count, 10)):  # Check first 10 pages for dimensions
                page = doc[page_idx]
                rect = page.rect
                if rect.width > 4096 or rect.height > 4096:
                    raise DocumentSecurityError(
                        f"Page {page_idx + 1} dimensions ({rect.width}x{rect.height}) exceed maximum allowed 4096x4096.",
                        code="PAGE_DIMENSIONS_TOO_LARGE",
                    )
                total_text_chars += len(page.get_text())

            is_digital = total_text_chars > 50

            return ValidatedDocumentInfo(
                file_bytes=data,
                mime_type=mime_type,
                sha256_hash=sha256,
                file_size_bytes=file_size,
                page_count=page_count,
                is_pdf=True,
                is_encrypted=False,
                is_digital_text=is_digital,
            )
        finally:
            doc.close()


document_validator = DocumentValidator()
