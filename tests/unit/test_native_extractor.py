"""Unit tests for Route A native PyMuPDF text and table extractor."""

import pymupdf
from worker.native_extractor import NativePDFExtractor


def test_native_extractor_extracts_headings_and_paragraphs():
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Insert a prominent title heading
    page.insert_text((50, 80), "Financial Audit FY25", fontsize=18)
    # Insert regular paragraph text
    page.insert_text(
        (50, 150),
        "This document details the corporate balance sheet, liquidity ratios, and capital expenditures for FY25.",
        fontsize=11,
    )
    # Insert list items
    page.insert_text((50, 220), "- Revenue growth of 24% YoY\n- Operating margin improved to 18%\n- Zero debt maintained", fontsize=10)

    blocks = NativePDFExtractor.extract_page_blocks(page, page_num=1)
    doc.close()

    assert len(blocks) >= 2
    types = [b["type"] for b in blocks]
    assert "heading" in types
    assert "paragraph" in types or "list" in types

    # Check reading order
    for idx, b in enumerate(blocks, start=1):
        assert b["reading_order"] == idx
        assert "bbox" in b
        assert len(b["bbox"]) == 4
