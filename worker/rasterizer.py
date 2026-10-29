"""Safe PDF page rasterizer with memory clamps and resolution limits."""

import io
from typing import Optional, Tuple
import pymupdf
from PIL import Image
from app.core.errors import DocumentSecurityError

DEFAULT_DPI = 150
MAX_DPI = 300
MAX_DIMENSION = 4096


class SafePageRasterizer:
    """Renders PDF pages to safe RGB bitmap images with strict bounds."""

    def __init__(self, dpi: int = DEFAULT_DPI):
        if dpi > MAX_DPI:
            raise DocumentSecurityError(
                f"Requested DPI ({dpi}) exceeds maximum permitted resolution ({MAX_DPI} DPI).",
                code="EXCESSIVE_DPI_REQUESTED",
            )
        self.dpi = dpi
        # PyMuPDF standard base resolution is 72 DPI
        self.zoom = dpi / 72.0

    def render_page(self, page: pymupdf.Page) -> Tuple[bytes, int, int]:
        """
        Renders a single PyMuPDF page to PNG image bytes.
        Returns: (png_bytes, width_px, height_px)
        """
        rect = page.rect
        if rect.width > MAX_DIMENSION or rect.height > MAX_DIMENSION:
            raise DocumentSecurityError(
                f"Page dimensions ({rect.width}x{rect.height}) exceed maximum allowed {MAX_DIMENSION}x{MAX_DIMENSION} points.",
                code="PAGE_DIMENSIONS_TOO_LARGE",
            )

        # Scale matrix for target DPI
        matrix = pymupdf.Matrix(self.zoom, self.zoom)

        try:
            # Render to pixmap with alpha=False (RGB)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            width, height = pix.width, pix.height

            if width > MAX_DIMENSION or height > MAX_DIMENSION:
                # Clamp to MAX_DIMENSION if scaling pushed it over
                scale_down = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
                matrix = pymupdf.Matrix(self.zoom * scale_down, self.zoom * scale_down)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                width, height = pix.width, pix.height

            png_bytes = pix.tobytes(output="png")
            return png_bytes, width, height
        except Exception as e:
            raise DocumentSecurityError(
                f"Page rendering failed: {str(e)}",
                code="PAGE_RENDER_FAILED",
            )


page_rasterizer = SafePageRasterizer()
