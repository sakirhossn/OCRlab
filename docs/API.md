# Unlimited OCR Cloud — Public REST API Specification (`/v1`)

## 1. Base URL & Authentication

- **Production Edge**: `https://api.ocrlab.cloud/v1` (terminates via Caddy TLS 1.3)
- **Local Dev**: `http://localhost:8000/v1`

### Authentication Headers
Pass the raw API key in either header:
```http
Authorization: Bearer ocr_live_xxxxxxxxxxxxxxxxxxxxxxxx
# OR
X-API-Key: ocr_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

### Traceability & Idempotency Headers
- `X-Request-ID`: Client-provided or server-generated UUID returned in every response.
- `Idempotency-Key`: UUID string on `POST /v1/documents` to safely retry uploads without duplicate job creation or quota charges.

---

## 2. Endpoints

### 2.1 Health Check
`GET /v1/health`
- **Auth**: None (Public)
- **Response**: `200 OK`
```json
{
  "status": "healthy",
  "service": "Unlimited OCR Cloud",
  "version": "1.0.0",
  "environment": "development",
  "database": "connected"
}
```

---

### 2.2 Upload Document & Create Job
`POST /v1/documents`
- **Auth**: Required (`read:documents`, `write:documents`)
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `file`: PDF, PNG, or JPEG binary file (max 50 MB, max 200 pages).
  - `mode`: `auto` (default), `native_only`, `ocr_only`, or `hybrid`.
- **Response**: `202 Accepted`
```json
{
  "document_id": "8f3b25e1-5bc3-4819-86ec-36c1e550c6bb",
  "job_id": "4b9e11ad-323d-4952-b437-db7b3f94ec62",
  "status": "queued",
  "filename": "financial_report.pdf",
  "file_size_bytes": 1048576,
  "page_count": 8,
  "mode": "auto",
  "created_at": "2026-10-28T15:20:00Z"
}
```

---

### 2.3 Check Job Status
`GET /v1/jobs/{id}`
- **Auth**: Required
- **Response**: `200 OK`
```json
{
  "id": "4b9e11ad-323d-4952-b437-db7b3f94ec62",
  "document_id": "8f3b25e1-5bc3-4819-86ec-36c1e550c6bb",
  "status": "queued",
  "mode": "auto",
  "progress_pct": 0,
  "retry_count": 0,
  "error_code": null,
  "error_message": null,
  "created_at": "2026-10-28T15:20:00Z",
  "updated_at": "2026-10-28T15:20:00Z",
  "completed_at": null
}
```

---

### 2.4 Retrieve Structured Result
`GET /v1/jobs/{id}/result?format=json`
- **Auth**: Required
- **Query Parameters**:
  - `format`: `json` (default), `markdown`, or `text`.
- **Response**: `200 OK`
```json
{
  "schema_version": "1.0",
  "document_id": "8f3b25e1-5bc3-4819-86ec-36c1e550c6bb",
  "job_id": "4b9e11ad-323d-4952-b437-db7b3f94ec62",
  "status": "succeeded",
  "page_count": 1,
  "engine": "unlimited-ocr-2",
  "pages": [
    {
      "page_number": 1,
      "blocks": [
        {
          "block_id": "b1",
          "type": "heading",
          "level": 1,
          "text": "Executive Summary",
          "reading_order": 1
        },
        {
          "block_id": "b2",
          "type": "paragraph",
          "text": "This document outlines our Q3 financial figures.",
          "reading_order": 2
        },
        {
          "block_id": "b3",
          "type": "table",
          "reading_order": 3,
          "headers": ["Department", "Budget", "Spend"],
          "rows": [["Engineering", "$1.2M", "$1.1M"], ["Sales", "$800k", "$750k"]]
        }
      ]
    }
  ]
}
```

---

### 2.5 List Tenant Jobs
`GET /v1/jobs?limit=20&offset=0`
- **Auth**: Required
- **Response**: `200 OK`
```json
{
  "items": [
    {
      "id": "4b9e11ad-323d-4952-b437-db7b3f94ec62",
      "document_id": "8f3b25e1-5bc3-4819-86ec-36c1e550c6bb",
      "status": "succeeded",
      "mode": "auto",
      "progress_pct": 100,
      "created_at": "2026-10-28T15:20:00Z",
      "completed_at": "2026-10-28T15:20:04Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### 2.6 Delete Document & Job
`DELETE /v1/jobs/{id}`
- **Auth**: Required
- **Response**: `204 No Content`
- **Action**: Immediately overwrites and cryptographically shreds document and result files from the AES-256-GCM vault.

---

### 2.7 Usage & Quotas
`GET /v1/usage`
- **Auth**: Required
- **Response**: `200 OK`
```json
{
  "tenant_id": "tenant_123",
  "tenant_name": "Acme Corp",
  "tier": "pro",
  "period_month": "2026-10",
  "monthly_page_quota": 1000,
  "pages_used": 150,
  "pages_remaining": 850,
  "quota_percentage_used": 15.0,
  "rate_limit_rpm": 60
}
```

---

### 2.8 API Key Management
- `POST /v1/api-keys`: Create a new key. Secret key is displayed strictly once.
- `GET /v1/api-keys`: List active keys.
- `DELETE /v1/api-keys/{id}`: Revoke an existing key.
