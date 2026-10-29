---
name: ocr-api-platform
description: >-
  Architectural, security, and deployment standards for building the Unlimited OCR Cloud platform:
  multi-tenant FastAPI control plane on Oracle Always Free ARM64, decoupled GPU inference workers
  running Baidu Unlimited-OCR-2, PDF processing pipeline, and enterprise integrations.
---

# OCR API Platform Skill: Unlimited OCR Cloud

## Overview
This skill guides the design, implementation, verification, and deployment of **Unlimited OCR Cloud** (ocrLab), a production-grade, secure, multi-tenant PDF-to-structured-data SaaS platform powered by Baidu Unlimited-OCR-2 and PyMuPDF.

## Architecture Highlights
- **Decoupled 2-Tier Architecture**:
  - **Layer A (Control Plane)**: Oracle Cloud Infrastructure (OCI) Always Free Ampere A1 (2 OCPU ARM64, 12 GB RAM). Runs FastAPI, PostgreSQL, Redis, Caddy (automated Let's Encrypt TLS), job state machine, tenant isolation, quota management, and signed webhooks. **Never runs heavy AI models**.
  - **Layer B (Worker Plane)**: External GPU instances (RunPod, Modal, Vast.ai, or self-hosted CUDA). Connects strictly **outbound over HTTPS** using short-lived signed leases. No inbound public ports required. Executes Baidu Unlimited-OCR-2 with R-SWA / SR-SWA attention.
- **Dual-Route OCR Pipeline**:
  - **Route A (Native Vector)**: PyMuPDF extraction for digital PDFs with high-quality native text layers. Avoids GPU waste.
  - **Route B (AI OCR)**: Unlimited-OCR-2 for scanned, degraded, or image-heavy pages with table/math/reading order reconstruction.
  - **Deterministic Post-Processor**: Normalizes output to stable `schema_version: "1.0"` JSON, GitHub-flavored Markdown, and plain text.

## Progressive Reference Documentation
Consult the detailed reference files for specific platform requirements:
- [System Architecture](references/system-architecture.md): Topology, state machine, lease protocol, and data flows.
- [Public API Contract](references/public-api-contract.md): Versioned `/v1` endpoints, headers, error formats, and idempotency.
- [Security Checklist](references/security-checklist.md): Defense-in-depth, parser sandboxing, and prompt-injection defenses.
- [Oracle Always Free Deployment](references/oracle-always-free-deployment.md): OCI Ampere A1 ARM64 Docker Compose and resource limits.
- [GPU Inference Requirements](references/gpu-inference-requirements.md): VRAM budgets, SGLang / vLLM configs, and SR-SWA parameters.
- [PDF Ingestion Safety](references/pdf-ingestion-safety.md): Decompression bomb prevention, page clamps, and PyMuPDF sanitization.
- [Tenant Isolation](references/tenant-isolation.md): Multi-tenancy, Row Level Security, scoped API keys, and data boundaries.
- [Data Retention](references/data-retention.md): Automated file purging, encryption at rest, and zero-knowledge storage options.
- [Webhook Security](references/webhook-security.md): HMAC-SHA256 signatures, SSRF prevention, and backoff delivery.
- [Integration Patterns](references/integration-patterns.md): Python/TS SDKs, n8n, ERP connectors, and MCP server bridges.
- [Testing & Acceptance](references/testing-and-acceptance.md): CI/CD mock testing, real GPU verification, and benchmark evaluation.

## Operational Rules for Agents
1. **Never fabricate model outputs or test results**: Always test against actual schemas and record whether real GPU vs mock inference was used.
2. **Never expose worker ports**: Worker must pull leases via HTTP POST/GET to the control plane.
3. **Never run Unlimited-OCR-2 on Oracle ARM64 CPU**: Keep the control plane lightweight, responsive, and within the 2 OCPU / 12 GB RAM free tier limit.
4. **Validate SSRF rigorously**: For webhooks and any URL submission, resolve DNS and reject private, loopback, link-local, and cloud metadata addresses (`169.254.169.254`).
