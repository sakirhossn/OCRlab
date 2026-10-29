"""Route decision inspector: determines Route A (Native Vector) vs Route B (AI OCR)."""

from typing import Dict, List, Literal
import pymupdf

RouteType = Literal["native_vector", "ai_ocr"]


class RouteInspector:
    """Evaluates page text density and layout characteristics to select the processing route."""

    @staticmethod
    def inspect_page(page: pymupdf.Page, mode: str = "auto") -> RouteType:
        """Determines the optimal extraction route for a single page."""
        if mode == "native_only":
            return "native_vector"
        if mode == "ocr_only":
            return "ai_ocr"

        # Auto / Hybrid mode heuristic
        text = page.get_text("text").strip()
        char_count = len(text)

        # Calculate image area coverage
        page_area = max(1.0, page.rect.width * page.rect.height)
        images = page.get_images()
        image_area_sum = 0.0

        for img_info in images:
            xref = img_info[0]
            for img_rect in page.get_image_rects(xref):
                image_area_sum += img_rect.width * img_rect.height

        image_coverage = min(1.0, image_area_sum / page_area)

        # Decision rule:
        # If vector text exists (> 40 chars) and page is not dominated by a scan (> 60% image):
        if char_count > 40 and image_coverage < 0.60:
            return "native_vector"
        else:
            return "ai_ocr"

    @classmethod
    def inspect_document(cls, doc: pymupdf.Document, mode: str = "auto") -> List[RouteType]:
        """Returns route decision for each page in the document."""
        return [cls.inspect_page(page, mode) for page in doc]


route_inspector = RouteInspector()
