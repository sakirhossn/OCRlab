# Integration Guide: Unlimited OCR Cloud

This guide provides end-to-end instructions and code examples for integrating **Unlimited OCR Cloud** into your existing software infrastructure.

---

## 1. Quickstart with Python SDK

### Installation
```bash
pip install ./sdks/python
# OR
pip install unlimited-ocr
```

### Complete Upload & Extraction Workflow
```python
from unlimited_ocr import UnlimitedOCRClient, wrap_untrusted_ocr_text

# Initialize client
client = UnlimitedOCRClient(
    api_key="ocr_live_xxxxxxxxxxxxxxxxxxxxxxxx",
    base_url="https://api.ocrlab.cloud/v1"
)

# 1. Upload PDF document
with open("financial_report.pdf", "rb") as f:
    upload = client.upload_document(
        file_bytes=f.read(),
        filename="financial_report.pdf",
        mode="auto"  # auto, native_only, ocr_only, or hybrid
    )

print(f"Job queued: {upload.job_id} (Estimated pages: {upload.page_count})")

# 2. Poll until finished (or listen via Webhooks)
status = client.wait_for_completion(upload.job_id, timeout=60.0)

# 3. Retrieve structured JSON contract (Schema Version 1.0)
contract = client.get_result_json(upload.job_id)
print(f"Extraction engine: {contract.engine}")
for page in contract.pages:
    print(f"\n--- Page {page.page_number} ({page.route}) ---")
    for block in page.blocks:
        if block.type == "table":
            print(f"[Table] Headers: {block.headers}")
            print(f"        Rows: {len(block.rows)}")
        elif block.type == "heading":
            print(f"[H{block.level}] {block.text}")
        else:
            print(f"[{block.type}] {block.text[:60]}...")

# 4. Retrieve Markdown and protect against LLM prompt injection
markdown = client.get_result_markdown(upload.job_id)
safe_llm_prompt = wrap_untrusted_ocr_text(markdown)
```

---

## 2. Quickstart with TypeScript / Node.js SDK

### Installation
```bash
npm install ./sdks/typescript
# OR
npm install @unlimited-ocr/sdk
```

### Async Upload & Result Retrieval
```typescript
import { UnlimitedOCRClient } from '@unlimited-ocr/sdk';
import * as fs from 'fs';

const client = new UnlimitedOCRClient({
  apiKey: process.env.UNLIMITED_OCR_API_KEY,
  baseUrl: 'https://api.ocrlab.cloud/v1',
});

async function run() {
  const fileBuffer = fs.readFileSync('balance_sheet.pdf');

  // 1. Upload
  const upload = await client.uploadDocument(fileBuffer, 'balance_sheet.pdf', 'auto');
  console.log(`Job Created: ${upload.job_id}`);

  // 2. Await Completion
  const finished = await client.waitForCompletion(upload.job_id);

  // 3. Retrieve JSON Contract
  const contract = await client.getResultJSON(upload.job_id);
  console.log(`Document ID: ${contract.document_id}, Total Pages: ${contract.page_count}`);
}

run().catch(console.error);
```

---

## 3. Webhook Verification (HMAC-SHA256)

Unlimited OCR Cloud sends signed notifications when jobs transition to `job.completed` or `job.failed`.

### Python Receiver Example (FastAPI)
```python
from fastapi import FastAPI, Request, HTTPException
from unlimited_ocr import verify_webhook_signature

app = FastAPI()
WEBHOOK_SECRET = "whsec_your_registered_secret_here"

@app.post("/api/webhooks/ocr")
async def handle_ocr_webhook(request: Request):
    raw_body = await request.body()
    headers = dict(request.headers)

    # Replay-protected HMAC verification
    is_valid = verify_webhook_signature(
        secret=WEBHOOK_SECRET,
        headers=headers,
        raw_payload=raw_body,
        tolerance_seconds=300
    )
    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid signature or expired timestamp.")

    data = await request.json()
    job_id = data["job_id"]
    print(f"Received verified event {data['event']} for job {job_id}")
    return {"status": "received"}
```

---

## 4. Model Context Protocol (MCP) Integration for AI Agents

To equip Claude Desktop, Cursor, or Gemini with Unlimited OCR tools:

### Configuration (`claude_desktop_config.json` / `mcp_config.json`):
```json
{
  "mcpServers": {
    "unlimited-ocr": {
      "command": "python",
      "args": ["/path/to/ocrLab/integrations/mcp/mcp_server.py"],
      "env": {
        "UNLIMITED_OCR_API_KEY": "ocr_live_xxxxxxxxxxxxxxxxxxxxxxxx",
        "UNLIMITED_OCR_BASE_URL": "https://api.ocrlab.cloud/v1"
      }
    }
  }
}
```

### Available Tools:
- `ocr_parse_document(file_path, mode)`: Uploads and returns safe structured Markdown and JSON.
- `ocr_check_job_status(job_id)`: Inspects active job states.
- `ocr_get_result(job_id, format)`: Retrieves JSON, Markdown, or text.
- `ocr_get_usage()`: Returns remaining monthly page quotas.

---

## 5. Enterprise Connectors Included in Repository

- **n8n Workflow**: [`integrations/n8n/invoice_intake_workflow.json`](../integrations/n8n/invoice_intake_workflow.json)
- **ERP Line-Item Mapper**: [`integrations/erp/erp_invoice_connector.py`](../integrations/erp/erp_invoice_connector.py)
- **RAG Vector Database Chunker**: [`integrations/rag/rag_ingestion_chunker.py`](../integrations/rag/rag_ingestion_chunker.py)
- **Postman Collection**: [`integrations/postman/ocrLab.postman_collection.json`](../integrations/postman/ocrLab.postman_collection.json)
- **cURL Scripts**: [`integrations/curl/examples.sh`](../integrations/curl/examples.sh)
