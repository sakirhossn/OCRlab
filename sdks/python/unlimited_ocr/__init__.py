"""Unlimited OCR Cloud Official Python SDK."""

from unlimited_ocr.client import AsyncUnlimitedOCRClient, UnlimitedOCRClient
from unlimited_ocr.models import (
    DocumentBlock,
    DocumentPage,
    DocumentUploadResponse,
    JobStatusResponse,
    StructuredResultContract,
    UsageStatsResponse,
)
from unlimited_ocr.prompt_defense import sanitize_raw_text, wrap_untrusted_ocr_text
from unlimited_ocr.webhook import verify_webhook_signature

__version__ = "1.0.0"

__all__ = [
    "UnlimitedOCRClient",
    "AsyncUnlimitedOCRClient",
    "StructuredResultContract",
    "DocumentPage",
    "DocumentBlock",
    "JobStatusResponse",
    "DocumentUploadResponse",
    "UsageStatsResponse",
    "verify_webhook_signature",
    "wrap_untrusted_ocr_text",
    "sanitize_raw_text",
]
