# PDF Ingestion Safety Reference: Unlimited OCR Cloud

## 1. Threats in PDF Ingestion
PDF is a complex format supporting compression streams, incremental updates, font programs, embedded Javascript, form actions, and external launch commands. Untrusted PDF uploads can trigger:
- Infinite loops / parser hangs (DoS)
- Decompression bombs (zip-bomb style memory exhaustion)
- Remote code execution via parser memory corruption (e.g. JBIG2 / font bugs)
- Server-Side Request Forgery via embedded URI actions
- Storage exhaustion via gigabyte-sized files

## 2. Ingestion Defense Pipeline
Every uploaded file passes through an ordered filter pipeline:

1. **Size & Magic Number Check (Fast Reject)**:
   - Max file size: 50MB (configurable per tenant).
   - Read first 1024 bytes: verify `%PDF-` signature. Reject immediately if absent.
2. **Page Count & Header Extraction (Safe Mode)**:
   - Open PDF with PyMuPDF in read-only buffer mode.
   - Extract page count. If page count > tenant max (default 200), return `413 Payload Too Large`.
3. **Encrypted / Password-Protected PDF Check**:
   - Check `doc.is_encrypted` or `doc.needs_pass`.
   - If encrypted without provided decryption key, return `422 Unprocessable Entity` with code `PDF_ENCRYPTED`.
4. **Decompression & Memory Limits**:
   - Set maximum memory threshold (512MB) for rendering subprocess.
   - Enforce page render timeout (10 seconds per page max).
5. **Sanitization during Rendering**:
   - PyMuPDF converts vector/font instructions directly into raster pixels (PNG/RGB bitmap).
   - Strips all active content (JavaScript, launch actions, URI actions).
   - Only pixel arrays are handed to Unlimited-OCR-2.
