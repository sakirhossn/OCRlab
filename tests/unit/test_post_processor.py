"""Unit tests for deterministic post-processor and contract assembler."""

from worker.post_processor import DeterministicPostProcessor, parse_markdown_table


def test_markdown_table_parser():
    table_lines = [
        "| Department | Headcount | Budget |",
        "|---|---|---|",
        "| Engineering | 45 | $4.5M |",
        "| Marketing | 12 | $1.2M |",
    ]
    data = parse_markdown_table(table_lines)
    assert data is not None
    assert data["headers"] == ["Department", "Headcount", "Budget"]
    assert len(data["rows"]) == 2
    assert data["rows"][0] == ["Engineering", "45", "$4.5M"]
    assert data["rows"][1] == ["Marketing", "12", "$1.2M"]


def test_post_processor_parses_complex_markdown():
    raw_markdown = """# Enterprise Feasibility Report

This document outlines key technical and operational requirements.

| Metric | Target | Status |
|---|---|---|
| Latency | < 500ms | Met |
| Accuracy | > 98% | Met |

$$
E = mc^2
$$

- Complete Phase 1
- Complete Phase 2
- Complete Phase 3

Figure 1: Performance scaling curves across document lengths.
"""
    blocks = DeterministicPostProcessor.parse_page_markdown(raw_markdown, page_number=1)
    assert len(blocks) >= 6

    block_types = [b.type for b in blocks]
    assert "heading" in block_types
    assert "paragraph" in block_types
    assert "table" in block_types
    assert "formula" in block_types
    assert "list" in block_types
    assert "caption" in block_types

    # Verify heading details
    h_block = next(b for b in blocks if b.type == "heading")
    assert h_block.level == 1
    assert h_block.text == "Enterprise Feasibility Report"

    # Verify table details
    tbl_block = next(b for b in blocks if b.type == "table")
    assert tbl_block.headers == ["Metric", "Target", "Status"]
    assert len(tbl_block.rows) == 2

    # Verify formula
    f_block = next(b for b in blocks if b.type == "formula")
    assert "$$E = mc^2$$" in f_block.text

    # Verify reading order
    for idx, b in enumerate(blocks, start=1):
        assert b.reading_order == idx
