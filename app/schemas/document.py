"""Document response schema."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    filename: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    page_count: int
    is_encrypted: bool
    is_purged: bool
    created_at: datetime
