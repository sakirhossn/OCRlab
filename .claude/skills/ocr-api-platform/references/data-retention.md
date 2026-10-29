# Data Retention Reference: Unlimited OCR Cloud

## 1. Regulatory Context & Principles
To comply with global data protection laws (GDPR, ISO 27001, Indian Digital Personal Data Protection Act 2023), the platform enforces data minimization and automated lifecycle management.

## 2. Retention Modes
Tenants can configure their retention policy in the dashboard:
- **Ephemeral (Zero-Storage)**: Document binary is deleted immediately after worker completes OCR. Extracted result is cached for 1 hour for client pickup, then permanently deleted.
- **24 Hours**: Default setting for high-security environments.
- **7 Days / 30 Days**: Standard business workflow window.
- **Manual Deletion Only**: Documents retained until explicitly deleted via `DELETE /v1/jobs/{id}` or UI.

## 3. Cryptographic Storage & Purge Workflow
1. **At Rest**: Document files and JSON results are stored encrypted with AES-256-GCM.
2. **Permanent Deletion (`DELETE /v1/jobs/{id}`)**:
   - The encrypted file on disk is overwritten or removed.
   - The encryption metadata key is destroyed.
   - Database record is marked `PURGED` and content columns are set to `NULL`.
3. **Automated Janitor Cron**:
   - Background task runs every hour:
     `SELECT id, tenant_id FROM jobs WHERE expires_at < NOW() AND status != 'PURGED'`
   - Executes hard purge of all associated storage files.
