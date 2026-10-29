"""Unit tests for the safe PDF page rasterizer."""

import io
from PIL import Image
import pymupdf
import pytest
from app.core.errors import DocumentSecurityError
from worker.rasterizer import SafePageRasterizer


def test_rasterizer_renders_png_bytes(make_pdf_bytes):
    pdf_bytes = make_pdf_bytes(pages=1, text="High-Resolution Document Rendering Test")
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    rasterizer = SafePageRasterizer(dpi=150)
    png_bytes, width, height = rasterizer.render_page(page)

    assert isinstance(png_bytes, bytes)
    assert png_bytes.startswith(b"\x89PNG")
    assert width > 0 and height > 0

    # Verify PNG is openable by PIL
    img = Image.open(io.BytesIO(png_bytes))
    assert img.format == "PNG"
    assert img.size == (width, height)
    doc.close()


def test_rasterizer_rejects_excessive_dpi():
    with pytest.raises(DocumentSecurityError) as exc:
        SafePageRasterizer(dpi=600)  # Max allowed is 300
    assert exc.value.code == "EXCESSIVE_DPI_REQUESTED"
