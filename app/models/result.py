"""Result storage model for structured OCR and layout extractions."""

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Result(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "results"

    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    engine: Mapped[str] = mapped_column(String(64), default="unlimited-ocr-2", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0", nullable=False)
    result_json_path: Mapped[str] = mapped_column(String(512), nullable=False)
    result_md_path: Mapped[str] = mapped_column(String(512), nullable=True)
    result_txt_path: Mapped[str] = mapped_column(String(512), nullable=True)
    processing_time_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="result")
