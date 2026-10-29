"""Deterministic post-processor: maps OCR Markdown into versioned Blocks JSON (schema 1.0)."""

import re
from typing import Any, Dict, List, Optional, Tuple
from app.schemas.result import DocumentBlock, DocumentPage, StructuredResultContract


def parse_markdown_table(lines: List[str]) -> Optional[Dict[str, Any]]:
    """Parses a block of Markdown table lines into headers and rows."""
    if len(lines) < 2:
        return None

    # Check for separator line (e.g. |---|---|)
    has_separator = False
    sep_idx = -1
    for idx, l in enumerate(lines):
        if re.match(r"^\|?\s*[-:]+[-| :]*\|?$", l.strip()):
            has_separator = True
            sep_idx = idx
            break

    if not has_separator or sep_idx == 0:
        return None

    # Extract headers
    header_line = lines[0].strip().strip("|")
    headers = [c.strip() for c in header_line.split("|")]

    # Extract rows (lines after separator)
    rows = []
    for line in lines[sep_idx + 1:]:
        clean = line.strip().strip("|")
        if not clean:
            continue
        cells = [c.strip() for c in clean.split("|")]
        # Pad row to match headers count if necessary
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(cells[:len(headers)])

    return {"headers": headers, "rows": rows}


class DeterministicPostProcessor:
    """Converts upstream OCR markdown text into versioned schema 1.0 DocumentPage blocks."""

    @classmethod
    def parse_page_markdown(cls, markdown_text: str, page_number: int) -> List[DocumentBlock]:
        blocks: List[DocumentBlock] = []
        reading_order = 1

        # Normalize line endings and split into raw paragraphs
        paragraphs = re.split(r"\n\s*\n", markdown_text.strip())

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            lines = para.split("\n")
            first_line = lines[0].strip()

            # 1. Heading check (#, ##, ###)
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", first_line)
            if heading_match and len(lines) == 1:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                blocks.append(DocumentBlock(
                    block_id=f"p{page_number}_b{reading_order}",
                    type="heading",
                    level=level,
                    text=text,
                    reading_order=reading_order,
                ))
                reading_order += 1
                continue

            # 2. Formula check ($$ ... $$)
            if para.startswith("$$") and para.endswith("$$"):
                formula_text = para.strip("$\n ")
                blocks.append(DocumentBlock(
                    block_id=f"p{page_number}_b{reading_order}",
                    type="formula",
                    text=f"$${formula_text}$$",
                    reading_order=reading_order,
                ))
                reading_order += 1
                continue

            # 3. Table check (| col1 | col2 |)
            if lines[0].startswith("|") or ("|" in lines[0] and len(lines) >= 2):
                tbl_data = parse_markdown_table(lines)
                if tbl_data:
                    blocks.append(DocumentBlock(
                        block_id=f"p{page_number}_b{reading_order}",
                        type="table",
                        headers=tbl_data["headers"],
                        rows=tbl_data["rows"],
                        reading_order=reading_order,
                    ))
                    reading_order += 1
                    continue

            # 4. List check (- item, * item, 1. item)
            is_list = all(
                re.match(r"^\s*([*\-+]|\d+\.)\s+", l) for l in lines
            )
            if is_list and len(lines) > 0:
                items = [re.sub(r"^\s*([*\-+]|\d+\.)\s+", "", l).strip() for l in lines]
                blocks.append(DocumentBlock(
                    block_id=f"p{page_number}_b{reading_order}",
                    type="list",
                    items=items,
                    text=para,
                    reading_order=reading_order,
                ))
                reading_order += 1
                continue

            # 5. Caption check (Figure 1: or Table 1:)
            if re.match(r"^(Figure|Table|Fig\.)\s+\d+[:.]", first_line, re.IGNORECASE):
                blocks.append(DocumentBlock(
                    block_id=f"p{page_number}_b{reading_order}",
                    type="caption",
                    text=para,
                    reading_order=reading_order,
                ))
                reading_order += 1
                continue

            # 6. Default: Paragraph
            blocks.append(DocumentBlock(
                block_id=f"p{page_number}_b{reading_order}",
                type="paragraph",
                text=para,
                reading_order=reading_order,
            ))
            reading_order += 1

        return blocks

    @classmethod
    def assemble_contract(
        cls,
        document_id: str,
        job_id: str,
        pages: List[DocumentPage],
        engine: str = "unlimited-ocr-2",
        processing_time_seconds: float = 0.0,
    ) -> StructuredResultContract:
        """Assembles verified contract JSON."""
        return StructuredResultContract(
            schema_version="1.0",
            document_id=document_id,
            job_id=job_id,
            status="succeeded",
            page_count=len(pages),
            engine=engine,
            processing_time_seconds=round(processing_time_seconds, 2),
            pages=pages,
        )

    @classmethod
    def render_markdown(cls, contract: StructuredResultContract) -> str:
        """Renders assembled blocks into clean Markdown."""
        lines: List[str] = []
        for page in contract.pages:
            lines.append(f"## Page {page.page_number}\n")
            for b in page.blocks:
                if b.type == "heading":
                    hashes = "#" * (b.level or 2)
                    lines.append(f"{hashes} {b.text}\n")
                elif b.type == "table":
                    if b.headers:
                        lines.append("| " + " | ".join(b.headers) + " |")
                        lines.append("| " + " | ".join(["---"] * len(b.headers)) + " |")
                        if b.rows:
                            for row in b.rows:
                                lines.append("| " + " | ".join(str(c) for c in row) + " |")
                        lines.append("")
                elif b.type == "list":
                    if b.items:
                        for it in b.items:
                            lines.append(f"- {it}")
                        lines.append("")
                elif b.type == "formula":
                    lines.append(f"\n{b.text}\n")
                else:
                    lines.append(f"{b.text}\n")
            lines.append("")
        return "\n".join(lines).strip()

    @classmethod
    def render_plain_text(cls, contract: StructuredResultContract) -> str:
        """Renders assembled blocks into clean plain text."""
        lines: List[str] = []
        for page in contract.pages:
            lines.append(f"--- Page {page.page_number} ---")
            for b in page.blocks:
                if b.type == "table" and b.headers:
                    lines.append("\t".join(b.headers))
                    if b.rows:
                        for r in b.rows:
                            lines.append("\t".join(str(c) for c in r))
                elif b.type == "list" and b.items:
                    for it in b.items:
                        lines.append(f"• {it}")
                elif b.text:
                    lines.append(b.text)
            lines.append("")
        return "\n".join(lines).strip()


post_processor = DeterministicPostProcessor()
