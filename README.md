# Unlimited OCR Cloud (ocrLab)

> **Secure, High-Throughput PDF-to-Structured-Data SaaS Platform** powered by Baidu Unlimited-OCR-2 and PyMuPDF.

---

## Overview

**Unlimited OCR Cloud** converts PDF documents and scanned images into rich, machine-readable structured content (Markdown, versioned JSON, and plain text) with table, formula, and layout preservation.

The platform employs a decoupled two-tier architecture:
- **Control Plane (Layer A)**: Oracle Cloud Infrastructure Always Free Ampere A1 (2 OCPU ARM64, 12 GB RAM) running FastAPI, PostgreSQL 16, Redis 7, and Caddy with automatic TLS. **No AI models run on this host.**
- **Worker Plane (Layer B)**: Independent GPU inference workers (RunPod, Modal, Vast.ai, or local NVIDIA CUDA) running Baidu Unlimited-OCR-2 with Sparse Reference Sliding Window Attention (SR-SWA). Workers connect strictly outbound via HTTPS.

---

## Key Features

- **Dual-Route OCR Pipeline**:
  - **Route A (Native Vector)**: PyMuPDF for digitally generated PDFs (sub-second, zero GPU cost).
  - **Route B (AI OCR)**: Baidu Unlimited-OCR-2 for scans, handwriting, tables, and complex multi-column layouts.
  - **Hybrid Mode**: Automatic per-page routing based on vector text density.
- **Enterprise Multi-Tenancy**:
  - Strict tenant scoping in database queries.
  - Argon2id salted API keys with scopes and quotas.
  - AES-256-GCM encryption at rest.
- **Lease-Based Queue**:
  - Outbound-only worker communication.
  - Heartbeat leasing with automatic crash recovery and dead-letter queues.
- **Signed Webhooks**:
  - HMAC-SHA256 signatures with timestamp replay protection.
  - Strict SSRF defense with synchronous DNS pre-resolution blocking private, loopback, and cloud metadata addresses (`169.254.169.254`).
- **Developer Toolkits**:
  - Python SDK with LLM prompt-injection defense delimiters.
  - TypeScript SDK, Postman collection, OpenAPI 3.1 specification.
  - n8n workflow, ERP table mapping, RAG ingestion, and Model Context Protocol (MCP) server.

---

## Architecture

```
[Clients: Web UI / Python SDK / TypeScript SDK / cURL / MCP]
                           |
                           v (HTTPS / TLS 1.3)
+-------------------------------------------------------------+
| Layer A: Oracle Cloud Always Free (ARM64 Ubuntu 24.04)       |
|   - Caddy Edge Proxy (Let's Encrypt TLS)                    |
|   - FastAPI Control Plane (Auth, Ingestion, Quotas, States) |
|   - PostgreSQL 16 (Tenant isolation, Jobs, Audit logs)      |
|   - Redis 7 (Lease state, Token bucket rate limiting)       |
+-------------------------------------------------------------+
                           ^
                           | Outbound HTTPS Leases
+-------------------------------------------------------------+
| Layer B: GPU Inference Worker (RunPod / Modal / CUDA)       |
|   - Worker Daemon (Lease polling & heartbeat renewal)       |
|   - PyMuPDF Vector Extraction (Route A)                     |
|   - Baidu Unlimited-OCR-2 (Route B, SR-SWA, ~3.3B VLM)       |
|   - Deterministic Post-Processor -> Versioned 1.0 JSON      |
+-------------------------------------------------------------+
```

---

## Documentation Index

- [Master Implementation Plan](docs/PLAN.md)
- [System Architecture](docs/ARCHITECTURE.md)
- [Security Specification & Threat Model](docs/SECURITY.md)
- [Public REST API Specification](docs/API.md)
- [External Integrations & SDKs Guide](docs/INTEGRATION.md)
- [Oracle Cloud Always Free Deployment](docs/ORACLE_DEPLOYMENT.md)
- [GPU Inference Worker Deployment](docs/GPU_DEPLOYMENT.md)
- [Operational Runbook & Disaster Recovery](docs/RUNBOOK.md)
- [Testing & Quality Verification](docs/TESTING.md)
- [Cost Model & Economics](docs/COST_MODEL.md)
- [Agent Operating Conventions](AGENTS.md)
- [Skills Ecosystem](.agents/skills/ocr-api-platform/SKILL.md)

---

## Quickstart & Verification

### Running Test Suite (56 Tests)
```bash
# Run complete test suite (unit, integration, security audit)
uv run pytest -v
```

### Local Development Server
```bash
# Start FastAPI Control Plane locally
uv run uvicorn app.main:app --reload --port 8000
```
Open [http://localhost:8000](http://localhost:8000) or [http://localhost:8000/dashboard](http://localhost:8000/dashboard) to view the Web UI Dashboard.

### Production Deployment
- **Layer A (Oracle Cloud Always Free ARM64)**: See [Oracle Deployment Guide](docs/ORACLE_DEPLOYMENT.md)
- **Layer B (GPU Inference Worker)**: See [GPU Deployment Guide](docs/GPU_DEPLOYMENT.md)

---

## Project Status

**Current Status**: **Production-Ready & Fully Verified (Phases 0–7 Complete)**
- Automated Test Suite: **56 / 56 tests passing** (100% pass rate)
- Backend API & Multi-Tenant Engine: Complete & hardened
- Dual-Route OCR Engine & Post-Processor: Complete & verified
- Enterprise Frontend Web Dashboard: Complete with 10 modules
- Client SDKs & Integrations: Python, TypeScript, MCP, n8n, ERP, RAG
- Cloud Infrastructure: Oracle ARM64 Compose stack, Caddy auto-TLS, GPU worker templates
