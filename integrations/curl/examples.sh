#!/usr/bin/env bash
# ==============================================================================
# Unlimited OCR Cloud — cURL Reference Commands
# ==============================================================================

BASE_URL="https://api.ocrlab.cloud/v1"
API_KEY="ocr_live_xxxxxxxxxxxxxxxxxxxxxxxx"

# 1. Health Check (Public)
curl -s -X GET "${BASE_URL}/health" | jq .

# 2. Upload PDF Document (Mode: Auto / Hybrid)
curl -s -X POST "${BASE_URL}/documents" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Idempotency-Key: $(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo idemp-01)" \
  -F "file=@sample_invoice.pdf" \
  -F "mode=auto" | jq .

# 3. Check Job Status
JOB_ID="your_job_id_here"
curl -s -X GET "${BASE_URL}/jobs/${JOB_ID}" \
  -H "Authorization: Bearer ${API_KEY}" | jq .

# 4. Fetch Structured JSON Result (Schema Version 1.0)
curl -s -X GET "${BASE_URL}/jobs/${JOB_ID}/result?format=json" \
  -H "Authorization: Bearer ${API_KEY}" | jq .

# 5. Fetch Markdown Layout Representation
curl -s -X GET "${BASE_URL}/jobs/${JOB_ID}/result?format=markdown" \
  -H "Authorization: Bearer ${API_KEY}"

# 6. Fetch Plain Text
curl -s -X GET "${BASE_URL}/jobs/${JOB_ID}/result?format=text" \
  -H "Authorization: Bearer ${API_KEY}"

# 7. Check Current Quota & Usage
curl -s -X GET "${BASE_URL}/usage" \
  -H "Authorization: Bearer ${API_KEY}" | jq .

# 8. Register Webhook
curl -s -X POST "${BASE_URL}/webhooks" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://erp.example.com/api/webhooks/ocr", "secret": "whsec_super_secret_signing_key_32b"}' | jq .

# 9. Cryptographically Delete Job & Shred Document
curl -s -i -X DELETE "${BASE_URL}/jobs/${JOB_ID}" \
  -H "Authorization: Bearer ${API_KEY}"
