"""Route A: Native PDF text and table extraction using PyMuPDF."""

from typing import Any, Dict, List, Optional, Tuple
import pymupdf


def rects_overlap(r1: Tuple[float, float, float, float], r2: Tuple[float, float, float, float]) -> bool:
    """Checks if two rectangles [x0, y0, x1, y1] significantly intersect."""
    x0_1, y0_1, x1_1, y1_1 = r1
    x0_2, y0_2, x1_2, y1_2 = r2

    intersect_x0 = max(x0_1, x0_2)
    intersect_y0 = max(y0_1, y0_2)
    intersect_x1 = min(x1_1, x1_2)
    intersect_y1 = min(y1_1, y1_2)

    if intersect_x1 > intersect_x0 and intersect_y1 > intersect_y0:
        intersect_area = (intersect_x1 - intersect_x0) * (intersect_y1 - intersect_y0)
        area1 = max(1.0, (x1_1 - x0_1) * (y1_1 - y0_1))
        return (intersect_area / area1) > 0.5
    return False


class NativePDFExtractor:
    """Extracts structured text, headings, lists, and tables natively via PyMuPDF."""

    @staticmethod
    def extract_page_blocks(page: pymupdf.Page, page_num: int) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        table_bboxes: List[Tuple[float, float, float, float]] = []

        # 1. Native Table Extraction via PyMuPDF TableFinder
        try:
            tabs = page.find_tables()
            for t_idx, tab in enumerate(tabs):
                bbox = tab.bbox  # (x0, y0, x1, y1)
                table_bboxes.append(bbox)
                extracted_data = tab.extract()

                if extracted_data and len(extracted_data) > 0:
                    headers = [str(col).strip() if col is not None else "" for col in extracted_data[0]]
                    rows = []
                    for row in extracted_data[1:]:
                        rows.append([str(c).strip() if c is not None else "" for c in row])

                    blocks.append({
                        "block_id": f"p{page_num}_tbl{t_idx+1}",
                        "type": "table",
                        "y_pos": bbox[1],
                        "x_pos": bbox[0],
                        "headers": headers,
                        "rows": rows,
                        "bbox": [round(c, 2) for c in bbox],
                    })
        except Exception:
            # If table finder is unsupported or fails, fall back gracefully to text blocks
            pass

        # 2. Text Block Extraction (with heading and list detection)
        text_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
        b_idx = 1
        for tb in text_blocks:
            x0, y0, x1, y1, text, block_no, b_type = tb
            if b_type != 0:  # 0 is text; 1 is image
                continue

            cleaned_text = text.strip()
            if not cleaned_text:
                continue

            # Skip text that belongs inside a detected table
            block_rect = (x0, y0, x1, y1)
            if any(rects_overlap(block_rect, t_box) for t_box in table_bboxes):
                continue

            # Classify block type
            lines = [l.strip() for l in cleaned_text.split("\n") if l.strip()]
            first_line = lines[0] if lines else ""

            # Check for list
            if len(lines) > 1 and all(l.startswith(("-", "•", "*")) or (l[:2].isdigit() and l[2:4] in (". ", ") ")) for l in lines):
                items = [l.lstrip("-•* 0123456789.)").strip() for l in lines]
                blocks.append({
                    "block_id": f"p{page_num}_b{b_idx}",
                    "type": "list",
                    "y_pos": y0,
                    "x_pos": x0,
                    "items": items,
                    "text": cleaned_text,
                    "bbox": [round(c, 2) for c in block_rect],
                })
            # Check for heading: short text, single or few lines, often prominent
            elif len(cleaned_text) < 80 and len(lines) <= 2:
                level = 1 if len(cleaned_text) < 40 and y0 < 150 else 2
                blocks.append({
                    "block_id": f"p{page_num}_b{b_idx}",
                    "type": "heading",
                    "level": level,
                    "y_pos": y0,
                    "x_pos": x0,
                    "text": cleaned_text,
                    "bbox": [round(c, 2) for c in block_rect],
                })
            else:
                blocks.append({
                    "block_id": f"p{page_num}_b{b_idx}",
                    "type": "paragraph",
                    "y_pos": y0,
                    "x_pos": x0,
                    "text": cleaned_text,
                    "bbox": [round(c, 2) for c in block_rect],
                })
            b_idx += 1

        # 3. Sort by reading order (top-to-bottom y, then left-to-right x)
        blocks.sort(key=lambda b: (b["y_pos"], b["x_pos"]))

        # Assign final reading_order integers
        for order, b in enumerate(blocks, start=1):
            b["reading_order"] = order
            # Remove internal sort keys
            b.pop("y_pos", None)
            b.pop("x_pos", None)

        return blocks


native_pdf_extractor = NativePDFExtractor()
