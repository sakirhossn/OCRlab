"""Production GPU Worker Daemon for Unlimited OCR Cloud."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import httpx
import pymupdf
from app.config import settings
from app.schemas.result import DocumentBlock, DocumentPage, StructuredResultContract
from worker.native_extractor import native_pdf_extractor
from worker.post_processor import post_processor
from worker.rasterizer import page_rasterizer
from worker.route_inspector import route_inspector
from worker.unlimited_ocr_engine import unlimited_ocr_engine

logger = logging.getLogger(__name__)


class ProductionOCRWorker:
    """
    Production worker daemon connecting strictly outward over HTTPS.
    Executes Route A (PyMuPDF native extraction) or Route B (Unlimited-OCR-2 inference)
    per page, normalizes output to versioned schema 1.0 JSON, and submits to control plane.
    """

    def __init__(
        self,
        worker_id: str = "gpu-worker-01",
        control_plane_url: str = "http://127.0.0.1:8000",
        worker_token: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.worker_id = worker_id
        self.control_plane_url = control_plane_url.rstrip("/")
        self.worker_token = worker_token or settings.worker_auth_token
        self.client = client
        self.should_stop = False

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.worker_token}",
            "User-Agent": f"UnlimitedOCR-Worker/{self.worker_id}",
        }

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.control_plane_url}{path}"
        headers = self._get_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        if self.client:
            return await self.client.request(method, url, headers=headers, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=30.0) as ac:
                return await ac.request(method, url, headers=headers, **kwargs)

    async def lease_job(self) -> Optional[Dict[str, Any]]:
        """Claims next job lease from the control plane."""
        resp = await self._request(
            "POST",
            "/internal/v1/jobs/lease",
            json={"worker_id": self.worker_id, "supported_engines": ["unlimited-ocr-2"]},
        )
        if resp.status_code == 200 and resp.text:
            return resp.json()
        return None

    async def send_heartbeat(self, job_id: str, progress_pct: int) -> bool:
        """Sends progress heartbeat to prevent lease timeout."""
        resp = await self._request(
            "POST",
            f"/internal/v1/jobs/{job_id}/heartbeat",
            json={"worker_id": self.worker_id, "progress_pct": progress_pct},
        )
        return resp.status_code == 200

    async def download_document(self, job_id: str, download_token: str) -> bytes:
        """Downloads document binary using short-lived signed token."""
        resp = await self._request(
            "GET",
            f"/internal/v1/jobs/{job_id}/download",
            params={"token": download_token},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Download failed with HTTP {resp.status_code}")
        return resp.content

    async def process_document(
        self,
        file_bytes: bytes,
        document_id: str,
        job_id: str,
        mode: str = "auto",
    ) -> StructuredResultContract:
        """
        Executes dual-route OCR pipeline:
        - Inspects each page.
        - Route A: extracts native vector text & tables.
        - Route B: safe rasterizer -> Unlimited-OCR-2 inference.
        - Assembles stable contract schema 1.0 JSON.
        """
        start_time = time.monotonic()
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        total_pages = doc.page_count
        pages: List[DocumentPage] = []

        try:
            for page_idx in range(total_pages):
                page_num = page_idx + 1
                page = doc[page_idx]

                # Progress heartbeat every page
                progress = int(((page_idx + 1) / total_pages) * 85)
                try:
                    await self.send_heartbeat(job_id, progress)
                except Exception:
                    pass

                # Determine route for this page
                route = route_inspector.inspect_page(page, mode=mode)

                if route == "native_vector":
                    # Route A: Native extraction
                    raw_blocks = native_pdf_extractor.extract_page_blocks(page, page_num)
                    doc_blocks = [
                        DocumentBlock(
                            block_id=b["block_id"],
                            type=b["type"],
                            reading_order=b["reading_order"],
                            text=b.get("text"),
                            level=b.get("level"),
                            headers=b.get("headers"),
                            rows=b.get("rows"),
                            items=b.get("items"),
                            bbox=b.get("bbox"),
                        )
                        for b in raw_blocks
                    ]
                else:
                    # Route B: Baidu Unlimited-OCR-2 inference
                    png_bytes, _, _ = page_rasterizer.render_page(page)
                    raw_markdown = await unlimited_ocr_engine.ocr_page_image(png_bytes, page_number=page_num)
                    doc_blocks = post_processor.parse_page_markdown(raw_markdown, page_number=page_num)

                pages.append(DocumentPage(
                    page_number=page_num,
                    width_pts=round(page.rect.width, 2),
                    height_pts=round(page.rect.height, 2),
                    route=route,
                    blocks=doc_blocks,
                ))

            elapsed = time.monotonic() - start_time
            contract = post_processor.assemble_contract(
                document_id=document_id,
                job_id=job_id,
                pages=pages,
                engine="unlimited-ocr-2",
                processing_time_seconds=elapsed,
            )
            return contract
        finally:
            doc.close()

    async def complete_job(
        self,
        job_id: str,
        contract: StructuredResultContract,
    ) -> bool:
        """Uploads completed contract, Markdown, and text to control plane."""
        markdown_text = post_processor.render_markdown(contract)
        plain_text = post_processor.render_plain_text(contract)

        resp = await self._request(
            "POST",
            f"/internal/v1/jobs/{job_id}/complete",
            json={
                "worker_id": self.worker_id,
                "engine": contract.engine,
                "schema_version": contract.schema_version,
                "processing_time_seconds": contract.processing_time_seconds,
                "result_json": contract.model_dump(),
                "result_markdown": markdown_text,
                "result_text": plain_text,
            },
        )
        return resp.status_code == 200

    async def fail_job(self, job_id: str, error_code: str, error_message: str, retryable: bool = True) -> bool:
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
        """Processes one leased job completely. Returns True if job was processed."""
        lease = await self.lease_job()
        if not lease:
            return False

        job_id = lease["job_id"]
        doc_id = lease["document_id"]
        download_token = lease["download_token"]
        mode = lease.get("mode", "auto")

        try:
            # 1. Download
            file_bytes = await self.download_document(job_id, download_token)

            # 2. Process
            contract = await self.process_document(file_bytes, doc_id, job_id, mode=mode)

            # 3. Complete
            success = await self.complete_job(job_id, contract)
            return success
        except Exception as e:
            logger.exception(f"Worker failure processing job {job_id}")
            await self.fail_job(job_id, error_code="WORKER_PROCESSING_ERROR", error_message=str(e), retryable=False)
            return False


async def run_worker_loop() -> None:
    import os
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    worker = ProductionOCRWorker(
        worker_id=os.getenv("WORKER_ID", "local-worker-01"),
        control_plane_url=os.getenv("CONTROL_PLANE_URL", "http://127.0.0.1:8000"),
        worker_token=os.getenv("WORKER_SECRET_KEY", settings.worker_auth_token),
    )
    logger.info(f"Starting worker daemon {worker.worker_id} polling {worker.control_plane_url}...")
    while not worker.should_stop:
        try:
            ran = await worker.process_one_job()
            if not ran:
                await asyncio.sleep(2.0)
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(5.0)


if __name__ == "__main__":
    asyncio.run(run_worker_loop())
