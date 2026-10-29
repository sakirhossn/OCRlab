# Tenant Isolation Reference: Unlimited OCR Cloud

## 1. Multi-Tenancy Architecture
The platform is designed to serve multiple corporate tenants, departments, and external API users on a shared infrastructure with strict logical boundaries.

### Data Model Hierarchy
- **Organization / Tenant**: The billing and administrative root. Owns users, API keys, documents, quotas, and retention policies.
- **User**: Individual team member with roles (`admin`, `member`, `viewer`).
- **API Key**: Scoped token linked to a tenant, with rate limits, allowed endpoints, and expiration.
- **Document & Job**: Scoped strictly by `tenant_id`.

## 2. Database-Level Enforcement
- All tenant-owned tables (`documents`, `jobs`, `results`, `api_keys`, `webhooks`, `usage_records`) include `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`.
- Repository access layer strictly enforces `tenant_id` filter on all queries:
  ```python
  query = select(Job).where(Job.id == job_id, Job.tenant_id == current_tenant.id)
  ```
- No query ever looks up an object by `id` alone without validating ownership.
- Cross-tenant access attempts immediately trigger a security audit event and return `404 Not Found` (never `403 Forbidden` to prevent object enumeration).

## 3. Storage Isolation
- Encrypted document storage utilizes tenant-prefixed storage paths:
  `/storage/vault/{tenant_id}/{document_id}.enc`
- Download tokens generated for workers are short-lived (HMAC signed, TTL 300 seconds) and restricted to a single specific `document_id`.
