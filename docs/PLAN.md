# Unlimited OCR Cloud — Master Implementation Plan

## Executive Overview
**Unlimited OCR Cloud** (`ocrLab`) is a secure, enterprise-grade, multi-tenant PDF-to-structured-data API platform powered by Baidu Unlimited-OCR-2 and PyMuPDF. It bridges document ingestion with high-fidelity structured output (Markdown, versioned JSON, plain text) using a decoupled two-layer cloud architecture.

---

## 1. Architectural Guardrails & Invariants
1. **Decoupled 2-Tier Topology**:
   - **Layer A (Control Plane)**: Oracle Cloud Infrastructure Always Free Ampere A1 (2 OCPU ARM64, 12 GB RAM). Runs FastAPI, PostgreSQL 16, Redis 7, Caddy 2. **Strictly zero AI inference on this host**.
   - **Layer B (Inference Worker Plane)**: External GPU instances (RunPod, Modal, Vast.ai, or on-prem CUDA). Workers pull jobs over outbound HTTPS leases. No inbound worker ports.
2. **Dual-Route OCR Pipeline**:
   - **Route A (Vector Text)**: Digital PDFs with valid text layers are extracted via PyMuPDF. Fast, zero-GPU-cost, sub-second latency.
   - **Route B (AI OCR)**: Scanned or complex image pages are rendered safely (150–200 DPI) and processed via Baidu Unlimited-OCR-2.
   - **Hybrid Routing**: Document inspector checks vector-to-bitmap density per page.
3. **Structured Versioned Contract**: Output is strictly normalized to `schema_version: "1.0"` with typed layout blocks (`heading`, `paragraph`, `table`, `list`, `formula`, `caption`, `header`, `footer`, `unknown`).
4. **Security by Design**: Multi-tenant isolation at DB layer, Argon2id API key hashes, AES-256-GCM encryption at rest, SSRF prevention on webhooks and URLs, decompression bomb safeguards, and zero-log policy for document contents.

---

## 2. Integrated Skill Inventory
To maintain high development velocity and software quality without context bloat, the project adopts:
- **`ocr-api-platform`**: Domain-specific skill covering system topology, API contracts, PDF security, lease protocols, and deployment rules.
- **`get-shit-done` (GSD)**: Phase-driven execution loop (Discuss -> Plan -> Execute -> Verify -> Ship), preventing context rot.
- **`ralph`**: Autonomous PRD task loop backed by programmatic test backpressure (no task complete without passing tests).
- **`ponytail`**: Minimalist engineering mindset, YAGNI, standard library first, zero over-engineering.
- **`clean-code`**: Strict typing, Pydantic v2 schemas, SOLID design, high cohesion/low coupling.

---

## 3. Phased Execution Roadmap

### Phase 0 — Research and Planning (CURRENT)
- [x] Inspect upstream repository (`baidu/Unlimited-OCR`) and model card (`baidu/Unlimited-OCR-2`).
- [x] Verify hardware requirements (~3.3B parameters, 6.7–7.3 GB VRAM FP16/BF16, ~4 GB FP8; SGLang/vLLM/PyTorch).
- [x] Verify Oracle Always Free constraints (Ampere A1 ARM64, 2 OCPU, 12 GB RAM limit).
- [x] Inventory and create project skills (`ocr-api-platform`, `get-shit-done`, `ralph`, `ponytail`, `clean-code`) in `.agents/skills/` and `.claude/skills/`.
- [x] Create project invariants in `AGENTS.md`.
- [x] Author core documentation: `docs/PLAN.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/COST_MODEL.md`.
- [ ] **Checkpoint**: Present proposed architecture, verified requirements, skill inventory, and plan; request user approval before Phase 1.

---

### Phase 1 — Backend Foundation (COMPLETED)
**Focus**: Database models, migrations, authentication, tenant isolation, file ingestion, and quota system.
- [x] Database Architecture: SQLAlchemy 2.0 async models with DeclarativeBase (`Tenant`, `User`, `APIKey`, `Document`, `Job`, `Result`, `WebhookEndpoint`, `WebhookDelivery`, `UsageRecord`, `AuditLog`).
- [x] Authentication & Authorization: Argon2id salted key hashing, prefix indexing, constant-time verification, single-reveal key creation (`ocr_live_<hex>`).
- [x] File Ingestion & Validation: Strict magic byte detection (`%PDF-`, PNG, JPEG), PyMuPDF safe inspection, dimension and page clamps, decompression bomb defenses.
- [x] Encrypted Storage Vault: AES-256-GCM storage manager with 96-bit random nonces and compliance shredding.
- [x] Quotas & Rate Limiting: Sliding-window token bucket and monthly page quota tracking with atomic deduction.
- [x] Public REST API:
  - `POST /v1/documents` (HTTP 202 Accepted, Idempotency-Key handling).
  - `GET /v1/jobs/{id}`, `GET /v1/jobs/{id}/result`, `GET /v1/jobs`.
  - `DELETE /v1/jobs/{id}` (Permanent cryptographic deletion).
  - `GET /v1/usage`, `GET /v1/health`.
  - API key management (`POST /v1/api-keys`, `GET /v1/api-keys`, `DELETE /v1/api-keys/{id}`).
- [x] Automated Test Evidence: 16/16 tests passing across unit and integration suites (`tests/unit/test_crypto_storage.py`, `tests/unit/test_pdf_validator.py`, `tests/unit/test_quota_limiter.py`, `tests/integration/test_tenant_isolation.py`, `tests/integration/test_api_endpoints.py`).

---

### Phase 2 — End-to-End Mock Pipeline (COMPLETED)
**Focus**: Leased worker queue, worker communication protocol, deterministic mock inference, webhook engine.
- [x] Worker Lease State Machine:
  - Leased queue endpoints: `POST /internal/v1/jobs/lease`, `POST /internal/v1/jobs/{id}/heartbeat`, `POST /internal/v1/jobs/{id}/complete`, `POST /internal/v1/jobs/{id}/fail`, `POST /internal/v1/jobs/reclaim-leases`.
  - Heartbeat monitor and automatic lease expiration recovery (re-queuing abandoned jobs up to 3 retries, transition to dead-letter `FAILED` state on exceeded limits).
- [x] Secure Document Download Token:
  - Short-lived HMAC-signed download token (`generate_download_token` / `verify_download_token`) with 300s TTL.
  - Streaming document decryption endpoint `GET /internal/v1/jobs/{id}/download`.
- [x] Deterministic Mock Inference Worker:
  - Standalone daemon [`worker/mock_worker.py`](../worker/mock_worker.py) operating over HTTP/HTTPS with worker token authentication.
  - Simulates Route A (PyMuPDF digital extraction) and Route B (reconstructed headings, paragraphs, and tables).
  - Emits heartbeats, downloads encrypted payload, and submits versioned `schema_version: "1.0"` results.
- [x] SSRF-Protected Webhook Dispatcher:
  - Strict outbound URL validation resolving DNS synchronously and blocking RFC1918 private IPs, loopback, link-local, and cloud metadata (`169.254.169.254`).
  - HMAC-SHA256 signature generator (`X-UnlimitedOCR-Signature: t=...,v1=...`), timestamp, and event UUID.
  - Delivery logging in `webhook_deliveries` and tenant registration API (`/v1/webhooks`).
- [x] Automated Test Evidence: 25/25 tests passing (`tests/unit/test_webhook_dispatcher.py`, `tests/unit/test_lease_state_machine.py`, `tests/integration/test_end_to_end_mock.py`).

---

### Phase 3 — Real OCR & Post-Processing (COMPLETED)
**Focus**: Baidu Unlimited-OCR-2 integration, SGLang/Transformers worker daemon, PyMuPDF rendering, deterministic post-processor.
- [x] Route A Implementation (Native Vector):
  - PyMuPDF text & layout extraction for digital PDFs (`worker/native_extractor.py`).
  - Font size hierarchy, heading classification (level 1-3), list item detection.
  - PyMuPDF table detection (`page.find_tables()`), cell grid extraction, bounding boxes.
- [x] Route B Implementation (AI OCR):
  - Safe page rasterizer (`worker/rasterizer.py`): renders to RGB bitmap (150 DPI default, max 300 DPI, max 4096px clamps).
  - Unlimited-OCR-2 inference runner (`worker/unlimited_ocr_engine.py`) supporting SGLang server and PyTorch with SR-SWA 512-token sliding window.
  - Automated route inspector (`worker/route_inspector.py`) selecting Route A vs Route B on page-level text density.
- [x] Deterministic Post-Processor (`worker/post_processor.py`):
  - Parsers for headings, tables (GFM Markdown / LaTeX), LaTeX display and inline formulas (`$$...$$`), bullet lists, captions, and paragraphs.
  - Assembles verified `StructuredResultContract` adhering strictly to `schema_version: "1.0"`.
  - Renders clean Markdown and plain text exports.
- [x] Production GPU Worker Daemon (`worker/worker_daemon.py`):
  - Standalone production worker leasing jobs via outbound HTTPS, emitting progress heartbeats, executing dual-route pipeline, and completing jobs idempotently.
- [x] Automated Test Evidence: 35/35 tests passing (`tests/unit/test_rasterizer.py`, `tests/unit/test_route_inspector.py`, `tests/unit/test_native_extractor.py`, `tests/unit/test_post_processor.py`, `tests/integration/test_real_ocr_pipeline.py`).

---

### Phase 4 — Frontend Web Dashboard (COMPLETED)
**Focus**: Modern enterprise SaaS UI, responsive layout, PDF split-screen viewer, API management, admin console.
- [x] Visual Design & UI System (Uizze UI Standards):
  - High-clarity typography, white/slate/blue color palette, dark and light mode toggle with local storage persistence.
  - Installed Uizze UI design skills (`uizze-ui`, `anti-ui-slop`, `ui-design`) under `.agents/skills/` and `.claude/skills/`.
  - Responsive desktop, tablet, and mobile layouts.
- [x] Core Dashboard Views (10 Sections):
  1. Dashboard: Real-time metric counters (Total Docs, Pages, Workers, System Health), recent conversions table with fast inspect.
  2. Convert Documents: Drag-and-drop dropzone, mode selector (`auto`, `native_only`, `ocr_only`), real-time upload progress, split-screen viewer.
  3. Split-Screen Viewer: Source rendered preview on left, multi-tab structured inspector on right (Markdown, JSON Contract, Tables, Plain Text) with copy-to-clipboard and export actions.
  4. Batch Processing: Multi-file selection queue with per-file status indicators.
  5. Conversion History: Paginated job history with status badges and deep inspection.
  6. API Keys: Key creation with single-reveal secret modal, rate limits, monthly quota, and revocation.
  7. API Documentation: Embedded cURL examples and direct links to Swagger `/docs` and ReDoc `/redoc`.
  8. Webhooks: Endpoint registration with SSRF protection, HMAC signature guidance, and delivery logs.
  9. Usage & Quotas: Progress gauges, monthly page quota tracking, tier limits.
  10. Admin Console: OCI ARM64 resource monitor and stale lease recovery triggers.
- [x] Automated Test Evidence: 38/38 tests passing (`tests/integration/test_frontend.py`).

---

### Phase 5 — External Integrations & SDKs (COMPLETED)
**Focus**: Developer toolkits, client SDKs, workflow automation, and AI agent integration.
- [x] Official SDKs:
  - Python SDK (`unlimited_ocr`): Typed Pydantic models, webhook verification, prompt-injection defense utilities.
  - TypeScript SDK (`@unlimited-ocr/sdk`): Strict TypeScript typings, native Fetch client, zero-crypto-dependency Web Crypto HMAC verifier.
- [x] Integration Guides & Assets:
  - cURL commands and Postman collection (`integrations/postman/ocrLab.postman_collection.json`).
  - n8n workflow JSON example for automated invoice intake (`integrations/n8n/invoice_intake_workflow.json`).
  - Generic ERP / Accounting connector for table extraction to invoice line items (`integrations/erp/erp_invoice_connector.py`).
  - RAG / Vector Database ingestion script with hierarchical chunking (`integrations/rag/rag_ingestion_chunker.py`).
  - Model Context Protocol (MCP) server for Claude, Cursor, and Gemini agents (`integrations/mcp/mcp_server.py`).
- [x] Deliverables & Verification:
  - Automated tests running SDK clients against the live API; Postman collection validation. All 42 unit and integration tests passing.

---

### Phase 6 — Cloud Deployment Configurations (COMPLETED)
**Focus**: Production deployment assets for Oracle Cloud Always Free (ARM64) and GPU Worker environments.
- [x] Layer A (Oracle Always Free ARM64):
  - `deploy/oracle/docker-compose.oracle.yml` with multi-arch ARM64 images (`caddy`, `postgres:16-alpine`, `redis:7.2-alpine`, `fastapi-control-plane:arm64`).
  - Automated TLS, HTTP/2 & HTTP/3, and security headers via `deploy/oracle/Caddyfile`.
  - Memory clamps strictly adhering to 2 OCPU / 12 GB RAM (total limit: 5.4 GB).
  - Systemd service file (`deploy/oracle/ocr-cloud.service`), UFW firewall script (`deploy/oracle/setup-firewall.sh`), automated backup script (`deploy/oracle/backup.sh`).
- [x] Layer B (GPU Inference Worker):
  - `deploy/worker/Dockerfile.worker` (NVIDIA CUDA base, PyTorch, PyMuPDF, Transformers).
  - RunPod startup template (`deploy/worker/runpod_start.sh`), Modal serverless App (`deploy/worker/modal_worker.py`), Vast.ai setup script (`deploy/worker/vastai_setup.sh`).
  - Worker auto-shutdown controller (`deploy/worker/auto_shutdown.py`) to eliminate idle GPU charges.
- [x] Deliverables & Verification:
  - Comprehensive operations guides: `docs/ORACLE_DEPLOYMENT.md` and `docs/GPU_DEPLOYMENT.md`.

---

### Phase 7 — Security & Quality Verification (COMPLETED)
**Focus**: Hardening, automated security suites, accuracy benchmarks, and disaster recovery.
- [x] Security Audit:
  - Decompression bomb attack suite (giant canvas 10,000x10,000pt dimensions rejected with `PAGE_DIMENSIONS_TOO_LARGE`).
  - Malformed & password-protected PDF tests (AES-128 locked PDFs rejected with `PDF_ENCRYPTED`).
  - SSRF test suite (strictly blocks `169.254.169.254`, loopback `127.0.0.1`, `[::1]`, RFC 1918 subnets, dangerous schemes).
  - Cross-tenant data leak tests (object enumeration returns 404, cross-tenant deletions blocked, job listings completely scoped).
  - Prompt injection mitigation tests (escapes sensitive LLM control tokens into `[ESCAPED_TOKEN:...]`).
- [x] Quality Benchmark Corpus & Operations:
  - Document archetype evaluation (financial reports, scanned invoices, complex academic papers) documented in `docs/TESTING.md`.
  - Operational runbook and incident response standard operating procedures in `docs/RUNBOOK.md`.
  - Backup and restore procedures verified for PostgreSQL and AES encrypted storage vault.
- [x] Deliverables & Verification:
  - Complete 56-test regression suite passing in 12.5 seconds with zero failures (`tests/integration/test_security_audit.py`).
  - Final project completion and system verification reports.
