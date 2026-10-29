# Unlimited OCR Cloud — Operational Runbook & Incident Response

This document provides Standard Operating Procedures (SOPs) for maintaining, troubleshooting, backing up, restoring, and securing the **Unlimited OCR Cloud** platform in production.

---

## 1. System Architecture Overview

- **Layer A (Control Plane)**: Oracle Always Free Ampere A1 (2 OCPU ARM64, 12 GB RAM) running Caddy, FastAPI, PostgreSQL 16, and Redis 7 via Docker Compose.
- **Layer B (Worker Plane)**: External GPU instances (RunPod, Modal, Vast.ai, or local CUDA) polling outbound over HTTPS.

---

## 2. Emergency Incident Response

### Severity 1: Control Plane Outage / High Latency
1. Check host resource usage via SSH:
   ```bash
   ssh ubuntu@<OCI_HOST_IP>
   uptime
   free -h
   docker stats --no-stream
   ```
2. Verify container health status:
   ```bash
   cd /opt/ocrLab/deploy/oracle
   docker compose -f docker-compose.oracle.yml ps
   ```
3. Inspect container logs:
   ```bash
   # FastAPI application logs
   docker compose -f docker-compose.oracle.yml logs --tail 200 control-plane

   # Caddy edge proxy logs
   docker compose -f docker-compose.oracle.yml logs --tail 100 caddy

   # Database logs
   docker compose -f docker-compose.oracle.yml logs --tail 100 db
   ```
4. Restart service stack if required:
   ```bash
   sudo systemctl restart ocr-cloud
   ```

---

## 3. Disaster Recovery & Backup Restoration

Backups are created daily at 03:00 UTC by [`deploy/oracle/backup.sh`](file:///c:/1002/Agent/ocrLab/deploy/oracle/backup.sh) and stored in `/opt/backups/ocrLab/daily/`.

### 3.1: Verifying Backup Checksums
Before restoring, confirm backup archive integrity:
```bash
cd /opt/backups/ocrLab/daily
sha256sum -c checksum_<TIMESTAMP>.sha256
```

### 3.2: Restoring the PostgreSQL Database
```bash
# 1. Stop the application control plane to avoid concurrent writes
docker compose -f /opt/ocrLab/deploy/oracle/docker-compose.oracle.yml stop control-plane

# 2. Decompress and restore database dump
gunzip -c /opt/backups/ocrLab/daily/db_<TIMESTAMP>.sql.gz | \
  docker compose -f /opt/ocrLab/deploy/oracle/docker-compose.oracle.yml exec -T db \
  psql -U ocr_admin -d ocr_cloud

# 3. Restart the control plane
docker compose -f /opt/ocrLab/deploy/oracle/docker-compose.oracle.yml start control-plane
```

### 3.3: Restoring the Encrypted Storage Vault
```bash
# Extract encrypted documents into the Docker volume mount
docker run --rm \
    -v ocr_vault_data:/target \
    -v /opt/backups/ocrLab/daily:/backup:ro \
    alpine:3.20 \
    tar -xzf /backup/vault_<TIMESTAMP>.tar.gz -C /target
```

---

## 4. Key Rotation Procedures

### 4.1: Rotating Worker Shared Secret (`WORKER_SECRET_KEY`)
1. Generate a new 64-character secret on the Oracle host:
   ```bash
   openssl rand -hex 32
   ```
2. Update `WORKER_SECRET_KEY` in `/opt/ocrLab/.env.production`.
3. Reload FastAPI without database downtime:
   ```bash
   docker compose -f /opt/ocrLab/deploy/oracle/docker-compose.oracle.yml restart control-plane
   ```
4. Update the environment variables in your active GPU workers (RunPod, Modal secrets, Vast.ai) with the new key.

### 4.2: Rotating Customer API Keys
API keys use Argon2id hashes with key prefixes (`sk_live_...`).
1. When a tenant requests key rotation, issue a new key through the REST API or Dashboard:
   ```bash
   POST /v1/api-keys
   {"name": "Rotated Production Key", "rate_limit_per_minute": 120}
   ```
2. Deploy the new key to client applications.
3. Revoke the old key via:
   ```bash
   DELETE /v1/api-keys/{old_key_id}
   ```

### 4.3: Rotating the Storage Vault Encryption Key (`STORAGE_VAULT_KEY`)
The vault uses AES-256-GCM. When rotating the master storage vault key:
1. Generate the new key: `openssl rand -hex 32`.
2. Execute the re-encryption migration script to read existing blobs with the old key and write them back encrypted with the new key.
3. Update `STORAGE_VAULT_KEY` in `.env.production` and restart the control plane.

---

## 5. Worker Queue & Stuck Job Management

### 5.1: Diagnosing Stale or Timed-Out Leases
If a GPU worker dies mid-inference, the lease state machine automatically marks the job for retry when its 300-second lease window expires.

To manually inspect or trigger timeout recovery:
```bash
# Inspect job queue count in Redis
docker compose -f /opt/ocrLab/deploy/oracle/docker-compose.oracle.yml exec redis redis-cli DBSIZE

# Inspect recent job errors in PostgreSQL
docker compose -f /opt/ocrLab/deploy/oracle/docker-compose.oracle.yml exec db psql -U ocr_admin -d ocr_cloud -c \
  "SELECT id, status, retry_count, error_code, updated_at FROM jobs WHERE status IN ('processing', 'failed') ORDER BY updated_at DESC LIMIT 10;"
```

### 5.2: Purging Dead-Letter Jobs
Jobs that fail more than 3 consecutive times (`retry_count >= 3`) transition to `dead_letter` status.
Review the failure cause in `error_code` before re-queueing or discarding.

---

## 6. Security Hardening Checklist

- [x] Host UFW firewall active: Ports 80, 443 permitted; internal ports (5432, 6379, 8000) strictly blocked.
- [x] OCI VCN Security List matches host UFW rules.
- [x] Caddy HTTP/3 and automated TLS renewal active with HSTS and CSP headers.
- [x] Outbound-only GPU worker architecture (no open inbound worker ports).
- [x] Short-lived HMAC document download tokens (300s TTL).
- [x] Strict SSRF validation blocking metadata IPs (`169.254.169.254`) and loopback/RFC1918 subnets.
- [x] Automatic daily backups with SHA-256 checksums and retention pruning.
