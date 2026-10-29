"""Unit tests for the route inspector (Route A vs Route B)."""

import pymupdf
from worker.route_inspector import RouteInspector


def test_route_inspector_selects_native_for_text_page(make_pdf_bytes):
    pdf_bytes = make_pdf_bytes(pages=1, text="Extensive digital vector text layer with paragraphs and numbers.")
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    route = RouteInspector.inspect_page(page, mode="auto")
    assert route == "native_vector"
    doc.close()


def test_route_inspector_selects_ocr_for_empty_page():
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)  # Blank page, no text
    route = RouteInspector.inspect_page(page, mode="auto")
    assert route == "ai_ocr"
    doc.close()


def test_route_inspector_respects_explicit_modes(make_pdf_bytes):
    pdf_bytes = make_pdf_bytes(pages=1, text="Vector text layer")
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]

    # Explicit OCR mode forces ai_ocr even with vector text
    assert RouteInspector.inspect_page(page, mode="ocr_only") == "ai_ocr"

    # Explicit native mode forces native_vector
    assert RouteInspector.inspect_page(page, mode="native_only") == "native_vector"
    doc.close()
