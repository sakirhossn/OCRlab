# System Architecture Reference: Unlimited OCR Cloud

## 1. High-Level Topology

```
                  +----------------------------------------------+
                  |                 Client Apps                  |
                  | Web UI / Python SDK / TypeScript SDK / cURL  |
                  +----------------------------------------------+
                                         |
                                         | HTTPS (TLS 1.3)
                                         v
+---------------------------------------------------------------------------------+
| Layer A: Oracle Cloud Infrastructure (Always Free ARM64 - 2 OCPU, 12GB RAM)     |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   | Caddy Edge Proxy (Auto HTTPS, Rate Limiting, Request ID, Gzip/Zstd)     |   |
|   +-------------------------------------------------------------------------+   |
|                                        |                                        |
|   +------------------------------------+------------------------------------+   |
|   | FastAPI Control Plane                                                   |   |
|   |  - Auth & Multi-Tenancy (Argon2id API Keys, Bearer JWT)                 |   |
|   |  - Document Ingestion & Validation (PyMuPDF header check, size limits)  |   |
|   |  - Job Manager & State Machine (PENDING, LEASED, PROCESSING, etc.)      |   |
|   |  - Quota & Rate Limit Engine (Redis Token Bucket / PostgreSQL checks)   |   |
|   |  - Encrypted Storage Manager (AES-256-GCM Document & Result Vault)     |   |
|   |  - Webhook Dispatcher (HMAC-SHA256, SSRF-safe outbound queue)           |   |
|   +-------------------------------------------------------------------------+   |
|         |                                      |                                |
|   +-----+-----+                          +-----+-----+                          |
|   | PostgreSQL | (Tenant Data, Jobs,     |   Redis   | (Job Lease Queue,        |
|   | 16 ARM64  |  Audit, Quotas)          | 7.2 ARM64 |  Cache, Token Bucket)    |
|   +-----------+                          +-----------+                          |
+---------------------------------------------------------------------------------+
                                         ^
                                         | Lease Pull & Result Push
                                         | (Outbound HTTPS only)
+----------------------------------------+----------------------------------------+
| Layer B: GPU Inference Worker (RunPod / Modal / Vast.ai / Local NVIDIA CUDA)    |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   | Worker Daemon (Python 3.11+, asyncio / uv)                              |   |
|   |  - Leased Job Polling with Heartbeat Renewal & Exponential Jitter       |   |
|   |  - Short-Lived HMAC Presigned URL Document Downloader                   |   |
|   |  - Pipeline Router: Route A (Digital Vector) vs Route B (AI Model)      |   |
|   |  - PDF Page Renderer (PyMuPDF bounded resolution, memory clamps)       |   |
|   |  - Unlimited-OCR-2 Inference Engine (PyTorch / SGLang / vLLM, SR-SWA)   |   |
|   |  - Deterministic Post-Processor (Markdown to Versioned Blocks JSON)     |   |
|   |  - Result Packager & Authenticated HTTPS Uploader                       |   |
|   +-------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------+
```

## 2. Job State Machine
A document processing job advances through strict state transitions:
1. `QUEUED`: Submitted by authenticated tenant, validated for size/format, assigned ID, quota deducted.
2. `LEASED`: Claimed by an authenticated GPU worker with lease expiration (default 300s).
3. `PROCESSING`: Worker acknowledges download, emits periodic heartbeats every 30s.
4. `SUCCEEDED`: Worker uploads structured JSON, Markdown, and text; lease is released; webhooks fired.
5. `FAILED`: Terminal error occurred. If retry count < max_retries (default 3), transitions back to `QUEUED` with backoff; otherwise marked `FAILED` and dead-letter logged.
6. `CANCELLED`: User or admin revoked job before processing finished.

## 3. Worker Lease Protocol
- **Lease Acquisition**: `POST /internal/v1/jobs/lease` (Worker presents worker-token, receives job_id, page_count, encrypted presigned download URL, and lease_id).
- **Heartbeat Renewal**: `POST /internal/v1/jobs/{id}/heartbeat` (Worker extends lease_timeout by 120s; if worker crashes, lease expires and job is automatically re-queued for another worker).
- **Completion**: `POST /internal/v1/jobs/{id}/complete` (Idempotent payload with structured JSON, raw markdown, plain text, engine stats).
- **Failure**: `POST /internal/v1/jobs/{id}/fail` (Error code, stack summary without sensitive customer data, fatal vs retryable flag).
