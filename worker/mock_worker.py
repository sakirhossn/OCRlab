"""Deterministic Mock Inference Worker Daemon for local development and CI testing."""

import asyncio
import io
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
import pymupdf
from app.config import settings

logger = logging.getLogger(__name__)


class MockOCRWorker:
    """
    Mock inference worker daemon that connects outbound over HTTPS,
    leases jobs from the control plane, processes documents deterministically,
    and submits versioned structured results.
    """

    def __init__(
        self,
        worker_id: str = "mock-worker-01",
        base_url: str = "http://127.0.0.1:8000",
        worker_token: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.worker_id = worker_id
        self.base_url = base_url.rstrip("/")
        self.worker_token = worker_token or settings.worker_auth_token
        self.client = client
        self.should_stop = False

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.worker_token}",
            "User-Agent": f"UnlimitedOCR-MockWorker/{self.worker_id}",
        }

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        if self.client:
            return await self.client.request(method, url, headers=headers, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=30.0) as ac:
                return await ac.request(method, url, headers=headers, **kwargs)

    async def lease_job(self) -> Optional[Dict[str, Any]]:
        """Requests the next available job lease from the control plane."""
        resp = await self._request(
            "POST",
            "/internal/v1/jobs/lease",
            json={"worker_id": self.worker_id, "supported_engines": ["unlimited-ocr-2"]},
        )
        if resp.status_code == 200 and resp.text:
            return resp.json()
        return None

    async def send_heartbeat(self, job_id: str, progress_pct: int = 50) -> bool:
        """Sends a progress heartbeat to extend lease validity."""
        resp = await self._request(
            "POST",
            f"/internal/v1/jobs/{job_id}/heartbeat",
            json={"worker_id": self.worker_id, "progress_pct": progress_pct},
        )
        return resp.status_code == 200

    async def download_document(self, job_id: str, download_token: str) -> bytes:
        """Downloads document binary using short-lived signed lease token."""
        resp = await self._request(
            "GET",
            f"/internal/v1/jobs/{job_id}/download",
            params={"token": download_token},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to download document: HTTP {resp.status_code}")
        return resp.content

    def _deterministic_extract(
        self,
        file_bytes: bytes,
        document_id: str,
        job_id: str,
    ) -> Dict[str, Any]:
        """
        Processes document into versioned schema 1.0 JSON, Markdown, and text.
        Inspects native vector text with PyMuPDF, or simulates AI OCR layout.
        """
        pages_result: List[Dict[str, Any]] = []
        md_lines: List[str] = []
        txt_lines: List[str] = []

        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            total_pages = doc.page_count
        except Exception:
            # Fallback for single image or mock binary
            total_pages = 1
            doc = None

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            blocks: List[Dict[str, Any]] = []
            page_md: List[str] = [f"## Page {page_num}\n"]
            page_txt: List[str] = [f"--- Page {page_num} ---\n"]

            if doc:
                page = doc[page_idx]
                width = page.rect.width
                height = page.rect.height
                extracted_text = page.get_text("text").strip()
            else:
                width, height = 612.0, 792.0
                extracted_text = ""

            reading_order = 1

            if extracted_text:
                # Digital PDF Route A extraction
                paragraphs = [p.strip() for p in extracted_text.split("\n\n") if p.strip()]
                for p_idx, para in enumerate(paragraphs):
                    is_heading = len(para) < 60 and ("\n" not in para or p_idx == 0)
                    b_type = "heading" if is_heading else "paragraph"

                    block = {
                        "block_id": f"p{page_num}_b{reading_order}",
                        "type": b_type,
                        "text": para,
                        "reading_order": reading_order,
                    }
                    if is_heading:
                        block["level"] = 2
                        page_md.append(f"### {para}\n")
                    else:
                        page_md.append(f"{para}\n\n")

                    page_txt.append(f"{para}\n")
                    blocks.append(block)
                    reading_order += 1
            else:
                # Simulated Route B Unlimited-OCR-2 structured layout
                heading_block = {
                    "block_id": f"p{page_num}_b1",
                    "type": "heading",
                    "level": 1,
                    "text": f"Scanned Section Report - Page {page_num}",
                    "reading_order": 1,
                }
                blocks.append(heading_block)
                page_md.append(f"# Scanned Section Report - Page {page_num}\n\n")
                page_txt.append(f"Scanned Section Report - Page {page_num}\n\n")

                para_block = {
                    "block_id": f"p{page_num}_b2",
                    "type": "paragraph",
                    "text": "This structured text was accurately reconstructed from high-resolution document imaging.",
                    "reading_order": 2,
                }
                blocks.append(para_block)
                page_md.append(para_block["text"] + "\n\n")
                page_txt.append(para_block["text"] + "\n\n")

                table_block = {
                    "block_id": f"p{page_num}_b3",
                    "type": "table",
                    "reading_order": 3,
                    "headers": ["Item Description", "Qty", "Unit Price", "Total"],
                    "rows": [
                        ["Standard Processing Unit", "2", "$250.00", "$500.00"],
                        ["Extended OCR License", "1", "$1,200.00", "$1,200.00"],
                    ],
                }
                blocks.append(table_block)
                page_md.append("| Item Description | Qty | Unit Price | Total |\n|---|---|---|---|\n| Standard Processing Unit | 2 | $250.00 | $500.00 |\n| Extended OCR License | 1 | $1,200.00 | $1,200.00 |\n\n")
                page_txt.append("Item Description\tQty\tUnit Price\tTotal\nStandard Processing Unit\t2\t$250.00\t$500.00\n")

            pages_result.append({
                "page_number": page_num,
                "width_pts": width,
                "height_pts": height,
                "route": "native_vector" if extracted_text else "ai_ocr",
                "blocks": blocks,
            })
            md_lines.extend(page_md)
            txt_lines.extend(page_txt)

        if doc:
            doc.close()

        structured_json = {
            "schema_version": "1.0",
            "document_id": document_id,
            "job_id": job_id,
            "status": "succeeded",
            "page_count": total_pages,
            "engine": "unlimited-ocr-2-mock",
            "processing_time_seconds": 0.45,
            "pages": pages_result,
        }

        return {
            "json": structured_json,
            "markdown": "".join(md_lines),
            "text": "".join(txt_lines),
        }

    async def complete_job(self, job_id: str, results: Dict[str, Any]) -> bool:
        """Uploads completed structured OCR results."""
        resp = await self._request(
            "POST",
            f"/internal/v1/jobs/{job_id}/complete",
            json={
                "worker_id": self.worker_id,
                "engine": "unlimited-ocr-2-mock",
                "schema_version": "1.0",
                "processing_time_seconds": 0.45,
                "result_json": results["json"],
                "result_markdown": results["markdown"],
                "result_text": results["text"],
            },
        )
        return resp.status_code == 200

    async def fail_job(self, job_id: str, error_code: str, error_message: str, retryable: bool = True) -> bool:
        """Reports job failure."""
        resp = await self._request(
            "POST",
            f"/internal/v1/jobs/{job_id}/fail",
            json={
                "worker_id": self.worker_id,
                "error_code": error_code,
                "error_message": error_message,
                "retryable": retryable,
            },
        )
        return resp.status_code == 200

    async def process_one_job(self) -> bool:
        """
        Executes one complete mock processing cycle:
        1. Leases next job.
        2. Sends heartbeat.
        3. Downloads document.
        4. Processes document to versioned JSON/MD/text.
        5. Submits completed results.
        Returns True if a job was processed, False if queue was empty.
        """
        lease = await self.lease_job()
        if not lease:
            return False

        job_id = lease["job_id"]
        doc_id = lease["document_id"]
        download_token = lease["download_token"]

        # 1. Heartbeat
        await self.send_heartbeat(job_id, progress_pct=30)

        # 2. Download document
        file_bytes = await self.download_document(job_id, download_token)

        # 3. Simulate processing time
        await asyncio.sleep(0.05)
        await self.send_heartbeat(job_id, progress_pct=75)

        # 4. Deterministic extraction
        results = self._deterministic_extract(file_bytes, doc_id, job_id)

        # 5. Complete job
        success = await self.complete_job(job_id, results)
        return success
