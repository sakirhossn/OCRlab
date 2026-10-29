"""Job request and response schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    """Returned on HTTP 202 Accepted when a document is uploaded and queued."""
    document_id: str
    job_id: str
    status: str
    filename: str
    file_size_bytes: int
    page_count: int
    mode: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class JobSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    status: str
    mode: str
    progress_pct: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    items: List[JobSummaryResponse]
    total: int
    limit: int
    offset: int
