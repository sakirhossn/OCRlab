"""Schemas for internal GPU worker lease protocol."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobLeaseRequest(BaseModel):
    worker_id: str = Field(description="Unique worker identifier (e.g. runpod-inst-9481)")
    supported_engines: List[str] = Field(default_factory=lambda: ["unlimited-ocr-2"])


class JobLeaseResponse(BaseModel):
    job_id: str
    document_id: str
    filename: str
    file_size_bytes: int
    page_count: int
    mode: str
    download_token: str
    lease_expires_at: datetime


class WorkerHeartbeatRequest(BaseModel):
    worker_id: str
    progress_pct: int = Field(default=50, ge=0, le=100)


class WorkerCompleteRequest(BaseModel):
    worker_id: str
    engine: str = "unlimited-ocr-2"
    schema_version: str = "1.0"
    processing_time_seconds: float = 0.0
    result_json: Dict[str, Any]
    result_markdown: Optional[str] = None
    result_text: Optional[str] = None


class WorkerFailRequest(BaseModel):
    worker_id: str
    error_code: str
    error_message: str
    retryable: bool = True
