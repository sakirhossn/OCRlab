# Integration Patterns Reference: Unlimited OCR Cloud

## 1. Overview of Integration Ecosystem
Unlimited OCR Cloud is engineered to serve as the unified OCR engine for diverse business applications without requiring existing architectures to be rewritten.

## 2. Standard Integration Flow
```
+-------------+         +---------------------+         +--------------------+
| Client App  |         | Unlimited OCR Cloud |         | GPU Worker (Baidu) |
+-------------+         +---------------------+         +--------------------+
       |                           |                              |
       | 1. POST /v1/documents     |                              |
       |-------------------------->|                              |
       | 2. 202 (job_id, status)   |                              |
       |<--------------------------|                              |
       |                           | 3. Leases Job                |
       |                           |<-----------------------------|
       |                           | 4. Processes PDF & OCR       |
       |                           |----------------------------->|
       |                           | 5. Completes with JSON       |
       |                           |<-----------------------------|
       | 6. Webhook (HMAC signed)  |                              |
       |<--------------------------|                              |
       | 7. GET /v1/jobs/{id}/res  |                              |
       |-------------------------->|                              |
       | 8. 200 Structured Data    |                              |
       |<--------------------------|                              |
       | 9. Save to Client DB      |                              |
       |    (ERP/CRM/RAG)          |                              |
+-------------+         +---------------------+         +--------------------+
```

## 3. Official Client Toolkits
- **Python SDK (`unlimited_ocr`)**:
  - Typed Pydantic models for Document, Page, Block, Table, and Formula.
  - Automatic polling or webhook verification helpers.
  - LLM prompt-injection sanitization utilities.
- **TypeScript / Node.js SDK (`@unlimited-ocr/sdk`)**:
  - Full TypeScript declarations, browser and Node.js support.
  - Streaming file upload with retry handling.
- **cURL & Postman Collection**:
  - Ready-to-import Postman collection with environment variable substitution.
- **Workflow Connectors**:
  - **n8n Workflow**: Webhook trigger + HTTP node to retrieve parsed markdown.
  - **ERP & Accounting Connector**: Maps extracted tables directly into invoice line items (SKU, quantity, unit price, tax).
  - **RAG / Vector Database Ingestion**: Chunking by extracted block boundaries (heading-aware chunks).
- **Model Context Protocol (MCP) Server**:
  - Exposes tools `ocr_parse_document`, `ocr_check_status`, `ocr_get_result` to AI agents (Claude, Cursor, Gemini).
