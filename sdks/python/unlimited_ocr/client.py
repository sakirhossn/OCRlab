"""Official client implementation for Unlimited OCR Cloud."""

import asyncio
import os
import time
from typing import Any, Dict, Optional, Union
import httpx
from unlimited_ocr.models import (
    DocumentUploadResponse,
    JobStatusResponse,
    StructuredResultContract,
    UsageStatsResponse,
)


class AsyncUnlimitedOCRClient:
    """Asynchronous client for Unlimited OCR Cloud API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.ocrlab.cloud/v1",
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.api_key = api_key or os.getenv("UNLIMITED_OCR_API_KEY", "")
        if not self.api_key:
            raise ValueError("API key must be provided or set via UNLIMITED_OCR_API_KEY environment variable.")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._internal_client = client

    def _get_headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "UnlimitedOCR-PythonSDK/1.0",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{path}"
        idemp = kwargs.pop("idempotency_key", None)
        headers = self._get_headers(idempotency_key=idemp)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        if self._internal_client:
            return await self._internal_client.request(method, url, headers=headers, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as ac:
                return await ac.request(method, url, headers=headers, **kwargs)

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str = "document.pdf",
        mode: str = "auto",
        idempotency_key: Optional[str] = None,
    ) -> DocumentUploadResponse:
        """Uploads a PDF or image file and initiates async OCR job."""
        files = {"file": (filename, file_bytes, "application/pdf")}
        data = {"mode": mode}
        resp = await self._request("POST", "/documents", files=files, data=data, idempotency_key=idempotency_key)
        if resp.status_code != 202:
            raise RuntimeError(f"Upload failed: HTTP {resp.status_code} - {resp.text}")
        return DocumentUploadResponse.model_validate(resp.json())

    async def get_job_status(self, job_id: str) -> JobStatusResponse:
        """Retrieves current job processing status and progress."""
        resp = await self._request("GET", f"/jobs/{job_id}")
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get job {job_id}: HTTP {resp.status_code}")
        return JobStatusResponse.model_validate(resp.json())

    async def wait_for_completion(
        self,
        job_id: str,
        poll_interval: float = 1.0,
        timeout: float = 60.0,
    ) -> JobStatusResponse:
        """Polls until job status transitions to succeeded or failed."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            status = await self.get_job_status(job_id)
            if status.status in ("succeeded", "failed", "cancelled"):
                return status
            await asyncio.sleep(poll_interval)
        raise TimeoutError(f"Job {job_id} did not finish within {timeout} seconds.")

    async def get_result_json(self, job_id: str) -> StructuredResultContract:
        """Retrieves structured result adhering to schema_version 1.0."""
        resp = await self._request("GET", f"/jobs/{job_id}/result", params={"format": "json"})
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to retrieve JSON result: HTTP {resp.status_code} - {resp.text}")
        return StructuredResultContract.model_validate(resp.json())

    async def get_result_markdown(self, job_id: str) -> str:
        """Retrieves extracted Markdown representation."""
        resp = await self._request("GET", f"/jobs/{job_id}/result", params={"format": "markdown"})
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to retrieve Markdown: HTTP {resp.status_code}")
        return resp.text

    async def get_result_text(self, job_id: str) -> str:
        """Retrieves extracted plain text."""
        resp = await self._request("GET", f"/jobs/{job_id}/result", params={"format": "text"})
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to retrieve text: HTTP {resp.status_code}")
        return resp.text

    async def get_usage(self) -> UsageStatsResponse:
        """Retrieves monthly page quota consumption and limits."""
        resp = await self._request("GET", "/usage")
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to retrieve usage stats: HTTP {resp.status_code}")
        return UsageStatsResponse.model_validate(resp.json())


class UnlimitedOCRClient:
    """Synchronous wrapper for Unlimited OCR Cloud API."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.ocrlab.cloud/v1", timeout: float = 30.0):
        self._async_client = AsyncUnlimitedOCRClient(api_key=api_key, base_url=base_url, timeout=timeout)

    def upload_document(self, file_bytes: bytes, filename: str = "document.pdf", mode: str = "auto", idempotency_key: Optional[str] = None) -> DocumentUploadResponse:
        return asyncio.run(self._async_client.upload_document(file_bytes, filename, mode, idempotency_key))

    def get_job_status(self, job_id: str) -> JobStatusResponse:
        return asyncio.run(self._async_client.get_job_status(job_id))

    def wait_for_completion(self, job_id: str, poll_interval: float = 1.0, timeout: float = 60.0) -> JobStatusResponse:
        return asyncio.run(self._async_client.wait_for_completion(job_id, poll_interval, timeout))

    def get_result_json(self, job_id: str) -> StructuredResultContract:
        return asyncio.run(self._async_client.get_result_json(job_id))

    def get_result_markdown(self, job_id: str) -> str:
        return asyncio.run(self._async_client.get_result_markdown(job_id))

    def get_result_text(self, job_id: str) -> str:
        return asyncio.run(self._async_client.get_result_text(job_id))

    def get_usage(self) -> UsageStatsResponse:
        return asyncio.run(self._async_client.get_usage())
