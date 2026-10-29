#!/usr/bin/env bash
# ==============================================================================
# Unlimited OCR Cloud — Automated Backup & Disaster Recovery Script
# Target: PostgreSQL Database Dump + AES Encrypted Vault Archive
# Retention: Daily (7 days), Weekly (4 weeks)
# ==============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/backups/ocrLab}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ENV_FILE="${ENV_FILE:-/opt/ocrLab/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/ocrLab/deploy/oracle/docker-compose.oracle.yml}"

# Ensure backup destination exists with strict permissions
mkdir -p "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly"
chmod 700 "${BACKUP_DIR}"

echo "==> Starting Unlimited OCR Cloud Backup [${TIMESTAMP}]..."

if [ ! -f "${ENV_FILE}" ]; then
  echo "Error: Production env file ${ENV_FILE} not found." >&2
  exit 1
fi

# Load database credentials from production env
# shellcheck disable=SC1090
source "${ENV_FILE}"

DB_BACKUP_FILE="${BACKUP_DIR}/daily/db_${TIMESTAMP}.sql.gz"
VAULT_BACKUP_FILE="${BACKUP_DIR}/daily/vault_${TIMESTAMP}.tar.gz"

# 1. Database Backup (pg_dump inside Postgres container)
echo "==> Dumping PostgreSQL database: ${POSTGRES_DB}..."
docker compose -f "${COMPOSE_FILE}" exec -T db \
    pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
    | gzip -9 > "${DB_BACKUP_FILE}"
chmod 600 "${DB_BACKUP_FILE}"
echo "    Database backup saved: ${DB_BACKUP_FILE} ($(du -h "${DB_BACKUP_FILE}" | cut -f1))"

# 2. Storage Vault Backup (AES encrypted blobs)
echo "==> Archiving document storage vault..."
docker run --rm \
    -v ocr_vault_data:/source:ro \
    -v "${BACKUP_DIR}/daily":/backup \
    alpine:3.20 \
    tar -czf "/backup/vault_${TIMESTAMP}.tar.gz" -C /source .
chmod 600 "${VAULT_BACKUP_FILE}"
echo "    Vault backup saved: ${VAULT_BACKUP_FILE} ($(du -h "${VAULT_BACKUP_FILE}" | cut -f1))"

# 3. Generate SHA-256 Checksums
echo "==> Generating integrity checksums..."
cd "${BACKUP_DIR}/daily"
sha256sum "db_${TIMESTAMP}.sql.gz" "vault_${TIMESTAMP}.tar.gz" > "checksum_${TIMESTAMP}.sha256"
chmod 600 "checksum_${TIMESTAMP}.sha256"

# 4. Weekly Rotation (Every Sunday)
DOW=$(date +%u) # 1=Mon, 7=Sun
if [ "${DOW}" -eq 7 ]; then
    echo "==> Promoting today's backup to weekly retention..."
    cp -p "${DB_BACKUP_FILE}" "${BACKUP_DIR}/weekly/"
    cp -p "${VAULT_BACKUP_FILE}" "${BACKUP_DIR}/weekly/"
    cp -p "checksum_${TIMESTAMP}.sha256" "${BACKUP_DIR}/weekly/"
fi

# 5. Prune Expired Backups
echo "==> Pruning expired backups (7 daily, 28-day weekly)..."
find "${BACKUP_DIR}/daily" -type f -mtime +7 -delete
find "${BACKUP_DIR}/weekly" -type f -mtime +28 -delete

echo "==> Backup completed successfully at $(date)."
