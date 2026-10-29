# Webhook Security Reference: Unlimited OCR Cloud

## 1. Webhook Threat Model
Outbound webhooks notify client systems when OCR jobs complete (`job.completed`) or fail (`job.failed`). Key threats include:
- Server-Side Request Forgery (SSRF) to internal infrastructure or cloud metadata services.
- Man-in-the-Middle (MitM) eavesdropping or tampering.
- Replay attacks against client webhook receivers.
- Denial of Service against slow or unresponsive consumer endpoints.

## 2. SSRF Prevention Rules
Before any HTTP request is dispatched:
1. **Scheme Validation**: Only `https://` destinations are allowed in production. `http://` allowed only on explicitly tagged dev environments.
2. **DNS Pre-Resolution**:
   - Hostname is resolved to IP addresses via standard DNS.
   - Every resolved IP is checked against forbidden ranges:
     - `127.0.0.0/8` (Loopback)
     - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (RFC1918 Private)
     - `169.254.0.0/16` (Link-local / Cloud metadata `169.254.169.254`)
     - `0.0.0.0/8`, `224.0.0.0/4`, `240.0.0.0/4`
     - `::1`, `fc00::/7`, `fe80::/10` (IPv6 loopback/private)
   - If ANY resolved IP falls in a forbidden range, the webhook dispatch is rejected immediately.
3. **Redirect Disabling**: HTTP redirects (`301`, `302`) are followed only after re-resolving and re-checking the destination IP.

## 3. HMAC-SHA256 Signatures
Every webhook request includes standard verification headers:
- `X-UnlimitedOCR-Signature`: `t=1730112345,v1=9f8a...`
- `X-UnlimitedOCR-Timestamp`: Unix epoch integer.
- `X-UnlimitedOCR-Event-ID`: Unique UUID for idempotency deduplication.

### Signature Calculation:
```python
import hmac, hashlib

payload_to_sign = f"t={timestamp}.{raw_json_body}".encode('utf-8')
signature = hmac.new(webhook_secret.encode('utf-8'), payload_to_sign, hashlib.sha256).hexdigest()
```

## 4. Delivery & Retry Policy
- Exponential backoff with jitter: Retries at 30s, 2m, 10m, 1h, 6h.
- Max 5 retry attempts before marking webhook as failed.
- Timeout: 10-second connect timeout, 15-second read timeout.
