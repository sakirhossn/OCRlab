"""Versioned structured output schemas (Schema Version 1.0)."""

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class DocumentBlock(BaseModel):
    block_id: str
    type: str = Field(
        description="Block type: heading, paragraph, table, list, formula, caption, header, footer, unknown"
    )
    reading_order: int
    text: Optional[str] = None
    level: Optional[int] = Field(default=None, description="Heading level (1-6) when type == 'heading'")
    headers: Optional[List[str]] = Field(default=None, description="Table column headers when type == 'table'")
    rows: Optional[List[List[Any]]] = Field(default=None, description="Table row cells when type == 'table'")
    items: Optional[List[str]] = Field(default=None, description="List items when type == 'list'")
    bbox: Optional[List[float]] = Field(
        default=None,
        description="Optional bounding box [x0, y0, x1, y1] if reliably determined by the engine",
    )


class DocumentPage(BaseModel):
    page_number: int
    width_pts: Optional[float] = None
    height_pts: Optional[float] = None
    route: Optional[str] = Field(default=None, description="native_vector or ai_ocr")
    blocks: List[DocumentBlock] = Field(default_factory=list)


class StructuredResultContract(BaseModel):
    """The stable, versioned contract for structured OCR responses."""
    schema_version: str = "1.0"
    document_id: str
    job_id: Optional[str] = None
    status: str
    page_count: int
    engine: str = "unlimited-ocr-2"
    processing_time_seconds: Optional[float] = None
    pages: List[DocumentPage] = Field(default_factory=list)
