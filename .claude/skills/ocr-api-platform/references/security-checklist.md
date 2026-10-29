# Security Checklist Reference: Unlimited OCR Cloud

## 1. Untrusted Input Handling (PDFs & Images)
- [ ] **Strict Magic Byte & MIME Validation**: Never rely on file extension. Check file signatures (`%PDF-`, `\x89PNG`, `\xFF\xD8\xFF`).
- [ ] **Decompression Bomb Protection**: Limit uncompressed object size in PyMuPDF/Poppler. Enforce max memory budget (e.g., 512MB per render job).
- [ ] **Page Count Limits**: Reject PDFs exceeding tenant quota or hard limit (e.g., 200 pages) before rendering.
- [ ] **Pixel Limit Safeguards**: Limit rendered image resolution to max 300 DPI (standard 150–200 DPI recommended for OCR) and total dimensions to ≤ 4096 x 4096 per page.
- [ ] **Parser Sandboxing**: Run document parsing in isolated subprocesses or memory-constrained worker containers.
- [ ] **JavaScript & Action Stripping**: PyMuPDF strips embedded actions, JS, and external launch commands during rendering.

## 2. Infrastructure & Network Security
- [ ] **Decoupled Worker Architecture**: GPU worker initiates all connections outward via HTTPS. Inbound worker ports are closed.
- [ ] **SSRF Defense on Webhooks & URLs**:
  - Whitelist HTTP/HTTPS schemes only.
  - Resolve DNS synchronously before connection.
  - Reject private IPv4 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
  - Reject loopback (127.0.0.0/8) and link-local (169.254.0.0/16).
  - Explicitly reject Cloud Metadata Services (`169.254.169.254`, `fd00:ec2::254`).
  - Disable automatic redirects, or re-validate resolved IP on every redirect hop.
- [ ] **TLS Enforcement**: Caddy enforces TLS 1.3/1.2 with HSTS. Plain HTTP redirects to HTTPS.

## 3. Authentication & Tenant Isolation
- [ ] **Cryptographic Secret Storage**: Store API keys as salted hashes using Argon2id or PBKDF2-SHA256 with high work factors. Secret keys shown exactly once at creation.
- [ ] **Tenant Scoping in Every Query**: All database queries MUST enforce `tenant_id = :current_tenant_id`. No cross-tenant leaks.
- [ ] **Short-Lived Worker Tokens**: Lease tokens expire in 300s and authorize access only to the assigned document.
- [ ] **Role-Based Access Control**: Strict segregation between `tenant_user`, `tenant_admin`, and `platform_superadmin`.

## 4. Encryption & Privacy
- [ ] **Encryption at Rest**: Files stored using AES-256-GCM. Storage keys injected via environment secrets, never committed to VCS.
- [ ] **Zero-Log Confidentiality**: Never log PDF content, extracted OCR text, raw API keys, or webhook HMAC secrets.
- [ ] **Prompt Injection Defense for Downstream LLMs**: Clearly tag OCR text as untrusted raw document data. Provide delimiters (`<document_content>...</document_content>`) and sanitization helpers in SDKs.
- [ ] **Retention Enforcement**: Automatically purge expired documents and results according to tenant retention policy (e.g., 24h, 7d, 30d, or immediate deletion post-fetch).
