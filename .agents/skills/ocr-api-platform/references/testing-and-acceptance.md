# Testing and Acceptance Reference: Unlimited OCR Cloud

## 1. Testing Strategy & Principles
- **No False Claims**: Do not mark any feature or requirement as working unless it has passed automated or verified manual tests.
- **Clear Distinction**: Clearly differentiate in test summaries between:
  - **Passed Tests**: Executed and verified in current local/CI environment.
  - **Mocked Tests**: Executed using deterministic mock inference engine.
  - **Pending Live Tests**: Real GPU / Oracle Cloud deployments awaiting infrastructure credentials.

## 2. Test Suites
1. **Unit Tests (`tests/unit/`)**:
   - PDF validation: magic bytes, page limits, password detection, corrupt streams.
   - Post-processor: Markdown table parsing, heading hierarchy, block ordering, formula extraction.
   - Security: SSRF DNS resolver, HMAC signer/verifier, Argon2id key hashing, prompt injection delimiters.
2. **Integration Tests (`tests/integration/`)**:
   - Control plane API: document upload, status check, result retrieval, job deletion.
   - Multi-tenant isolation: Tenant A cannot access Tenant B jobs; rate limits enforce HTTP 429; quotas enforce HTTP 403/422.
   - Worker lease lifecycle: lease claim, heartbeat renewal, lease expiry recovery, complete, fail.
   - Webhook delivery: mock receiver validation, signature verification, retry backoff.
3. **Document Benchmark Corpus (`tests/corpus/`)**:
   - Labeled test suite:
     - 1. Simple scanned one-page document.
     - 2. Two-column academic PDF.
     - 3. Multi-row financial balance sheet table.
     - 4. Hindi & English mixed document.
     - 5. High-resolution rotated scan.
     - 6. 50-page long technical manual.
   - Evaluation metrics: Character Error Rate (CER), Table Cell Accuracy, Reading Order Score, Processing Latency.

## 3. Final Acceptance Checklist
1. PDF upload works via web UI and REST API.
2. Async worker leases and processes document.
3. Downloadable JSON, Markdown, and text match versioned schema.
4. Tenant isolation verified (zero cross-tenant leak).
5. Signed HMAC webhooks verified by test receiver.
6. OCI ARM64 Docker Compose builds and passes smoke test.
7. Real GPU worker deployment verified on NVIDIA hardware.
8. Documentation matches implemented endpoints and schemas.
