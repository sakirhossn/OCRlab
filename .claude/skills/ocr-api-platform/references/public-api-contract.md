# Public REST API Contract: Unlimited OCR Cloud (`/v1`)

## 1. Authentication & Base Headers
All requests require an API key passed in the `Authorization` or `X-API-Key` header:
```http
Authorization: Bearer ocr_live_xxxxxxxxxxxxxxxxxxxxxxxx
# OR
X-API-Key: ocr_live_xxxxxxxxxxxxxxxxxxxxxxxx
```
Optional client headers:
- `Idempotency-Key`: UUID string to prevent duplicate document submissions on network retries.
- `X-Request-ID`: Trace identifier returned in all responses.

## 2. Endpoints Summary

| Method | Endpoint | Description | Status Code |
|---|---|---|---|
| `POST` | `/v1/documents` | Upload PDF or image file; initiate async processing job | `202 Accepted` |
| `GET` | `/v1/jobs/{id}` | Retrieve job state, progress percentage, page count, and metadata | `200 OK` |
| `GET` | `/v1/jobs/{id}/result` | Retrieve structured result in format (`json`, `markdown`, `text`) | `200 OK` |
| `GET` | `/v1/jobs` | Paginated listing of jobs belonging to the authenticated tenant | `200 OK` |
| `DELETE` | `/v1/jobs/{id}` | Permanently purge document and extracted results (GDPR/compliance) | `204 No Content` |
| `GET` | `/v1/usage` | Inspect current monthly page quotas, consumed pages, and tier limits | `200 OK` |
| `GET` | `/v1/health` | Safe public system health check (uptime, queue depth, engine status) | `200 OK` |

## 3. Document Submission (`POST /v1/documents`)
### Request: `multipart/form-data`
- `file`: PDF or image binary (Max 50MB, max 200 pages by default).
- `mode`: `auto` (default), `native_only`, `ocr_only`, or `hybrid`.
- `webhook_url`: Optional HTTPS destination for job completion alerts.
- `callback_metadata`: Optional client-provided key-value JSON string returned in webhook payload.
- `output_formats`: Array/comma-separated (`json`, `markdown`, `text`).

### Response (`202 Accepted`):
```json
{
  "document_id": "doc_9f1a28b4c7",
  "job_id": "job_01h8x9p3q7",
  "status": "queued",
  "filename": "quarterly_financials.pdf",
  "file_size_bytes": 1048576,
  "page_count_estimated": 8,
  "mode": "auto",
  "created_at": "2026-10-28T13:50:00Z"
}
```

## 4. Structured Output Contract (`GET /v1/jobs/{id}/result?format=json`)
```json
{
  "schema_version": "1.0",
  "document_id": "doc_9f1a28b4c7",
  "job_id": "job_01h8x9p3q7",
  "status": "succeeded",
  "page_count": 2,
  "engine": "unlimited-ocr-2",
  "mode_applied": "hybrid",
  "processing_time_seconds": 3.42,
  "pages": [
    {
      "page_number": 1,
      "width_pts": 612.0,
      "height_pts": 792.0,
      "route": "ai_ocr",
      "blocks": [
        {
          "block_id": "p1_b1",
          "type": "heading",
          "level": 1,
          "text": "Executive Summary",
          "reading_order": 1,
          "bbox": [54.0, 72.0, 558.0, 96.0]
        },
        {
          "block_id": "p1_b2",
          "type": "paragraph",
          "text": "This report details our performance across key business divisions.",
          "reading_order": 2,
          "bbox": [54.0, 110.0, 558.0, 150.0]
        },
        {
          "block_id": "p1_b3",
          "type": "table",
          "reading_order": 3,
          "headers": ["Metric", "FY25", "FY26 Target"],
          "rows": [
            ["ARR Growth", "42%", "60%"],
            ["Gross Margin", "78%", "82%"]
          ],
          "bbox": [54.0, 160.0, 558.0, 280.0]
        }
      ]
    }
  ]
}
```

## 5. Standard Error Format
RFC 7807 compliant error format:
```json
{
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Monthly page limit exceeded. Used 1000/1000 pages.",
    "request_id": "req_63bf9102",
    "timestamp": "2026-10-28T13:50:00Z"
  }
}
```
