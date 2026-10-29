"""Pydantic models for the Unlimited OCR Cloud Python SDK."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentBlock(BaseModel):
    block_id: str
    type: str = Field(description="heading, paragraph, table, list, formula, caption, header, footer, unknown")
    reading_order: int
    text: Optional[str] = None
    level: Optional[int] = None
    headers: Optional[List[str]] = None
    rows: Optional[List[List[Any]]] = None
    items: Optional[List[str]] = None
    bbox: Optional[List[float]] = None


class DocumentPage(BaseModel):
    page_number: int
    width_pts: Optional[float] = None
    height_pts: Optional[float] = None
    route: Optional[str] = None
    blocks: List[DocumentBlock] = Field(default_factory=list)


class StructuredResultContract(BaseModel):
    schema_version: str = "1.0"
    document_id: str
    job_id: Optional[str] = None
    status: str
    page_count: int
    engine: str = "unlimited-ocr-2"
    processing_time_seconds: Optional[float] = None
    pages: List[DocumentPage] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    job_id: str = Field(alias="id")
    document_id: str
    status: str
    mode: str
    progress_pct: int
    retry_count: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class DocumentUploadResponse(BaseModel):
    document_id: str
    job_id: str
    status: str
    filename: str
    file_size_bytes: int
    page_count: int
    mode: str
    created_at: datetime


class UsageStatsResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    tier: str
    period_month: str
    monthly_page_quota: int
    pages_used: int
    pages_remaining: int
    quota_percentage_used: float
    rate_limit_rpm: int
