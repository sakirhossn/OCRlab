# Unlimited OCR Cloud (ocrLab) — Agent Operational Guide

This document defines core conventions, architecture invariants, security mandates, and development workflows for all AI coding agents working on this codebase.

## 1. Project Invariants
- **Layer A (Control Plane)**: Oracle Cloud Infrastructure Always Free Ampere A1 (2 OCPU ARM64, 12 GB RAM). **Never run heavy GPU/LLM models on this host**.
- **Layer B (Worker Plane)**: External GPU instances (RunPod, Modal, Vast.ai, or local NVIDIA CUDA). Workers connect strictly **outbound over HTTPS**. No inbound worker ports.
- **OCR Engine**: Baidu `Unlimited-OCR-2` (3.3B parameters, Reference Sliding Window Attention R-SWA / SR-SWA).
- **Dual Pipeline**:
  - Route A: Digital PDFs with clean vector text layers extracted natively via PyMuPDF.
  - Route B: Scanned/image pages rendered safely to 150-200 DPI images and processed with Unlimited-OCR-2.
- **Contract Schema**: Versioned JSON schema (`1.0`) with typed blocks (`heading`, `paragraph`, `table`, `list`, `formula`, `caption`, `header`, `footer`, `unknown`).

## 2. Security Mandates
1. **Never Log Sensitive Data**: No PDF contents, extracted OCR text, raw API keys, or webhook HMAC secrets in logs.
2. **SSRF Defense**: For all outgoing webhook requests and URL ingestion, resolve DNS before connecting. Reject loopback, RFC1918, link-local, and cloud metadata (`169.254.169.254`).
3. **Tenant Scoping**: All database queries MUST enforce `tenant_id = :tenant_id`.
4. **Untrusted Input**: Treat all PDF uploads as hostile decompression bombs until checked via safe PyMuPDF headers.

## 3. Engineering Practices (Adopted Skills)
- **GSD (Get Shit Done)**: Phase-driven progress with explicit checkpoints and tests.
- **Ralph**: Autonomous task loop verified by test suites.
- **Ponytail**: Minimalist code, YAGNI, standard library first, zero over-engineering.
- **Clean Code**: Explicit typing, Pydantic v2 validation, single responsibility.

## 4. Environment & Dependencies
- Python: 3.11+ managed via `uv`.
- Control Plane Services: FastAPI, PostgreSQL 16, Redis 7, Caddy 2.
- Worker: PyTorch, PyMuPDF, Transformers / SGLang.
- Tests: `pytest`, `pytest-asyncio`, `httpx`.
