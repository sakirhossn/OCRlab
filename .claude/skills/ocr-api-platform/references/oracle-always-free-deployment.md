# Oracle Cloud Always Free Deployment Reference

## 1. Target Hardware & Specifications
- **Compute Instance**: Oracle Ampere A1 (ARM64 architecture, `VM.Standard.A1.Flex`)
- **OCPU Allocation**: 2 OCPUs (4 vCPUs)
- **Memory Allocation**: 12 GB RAM
- **Storage**: 100 GB Boot/Block Volume (Oracle Always Free provides up to 200 GB total)
- **OS**: Ubuntu 24.04 LTS ARM64 or Ubuntu 22.04 LTS ARM64

## 2. Resource Budgeting on Oracle ARM64

| Service | CPU Limit | RAM Limit | Purpose |
|---|---|---|---|
| **Caddy 2** | 0.2 OCPU | 128 MB | Reverse proxy, TLS 1.3 termination, rate limiting |
| **FastAPI App** | 1.0 OCPU | 1024 MB | 4 Uvicorn workers on ARM64, API validation, state machine |
| **PostgreSQL 16** | 0.5 OCPU | 2048 MB | Persistent relational storage, tenant indexes, RLS |
| **Redis 7** | 0.2 OCPU | 512 MB | Quotas, rate limit buckets, active leases, pub/sub |
| **Buffer / OS** | 0.1 OCPU | ~8 GB Free | OS cache, file I/O buffers, temporary staging |

> [!CRITICAL]
> **DO NOT** run the 3.3B Unlimited-OCR-2 model on the Oracle ARM64 control plane. CPU inference on 3.3B parameters without AVX-512/AMX or CUDA causes 100% CPU lockup and server crashes. The Oracle instance is exclusively a control plane.

## 3. Container Images & ARM64 Compatibility
Every Docker image must provide native `linux/arm64` manifests:
- `caddy:2.8-alpine` (multi-arch `linux/arm64`)
- `python:3.11-slim-bookworm` (multi-arch `linux/arm64`)
- `postgres:16-alpine` (multi-arch `linux/arm64`)
- `redis:7.2-alpine` (multi-arch `linux/arm64`)

## 4. OCI Ingress & Firewall Rules
1. **OCI VCN Ingress Rules**:
   - Port 80 (HTTP) -> Redirect to HTTPS
   - Port 443 (HTTPS) -> Caddy proxy
   - Port 22 (SSH) -> Restrict to admin IP if possible
2. **Local UFW Rules (Ubuntu)**:
   ```bash
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
