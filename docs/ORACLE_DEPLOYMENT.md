# Oracle Cloud Infrastructure (OCI) Always Free Deployment Guide

**Target Host**: Oracle Ampere A1 Compute Instance (`VM.Standard.A1.Flex`)  
**Architecture**: 2 OCPU ARM64 (Neoverse-N1), 12 GB RAM  
**Operating System**: Ubuntu 24.04 LTS aarch64  
**Primary Invariant**: **Control Plane Only**. Never run Unlimited-OCR-2 or heavy GPU inference models on this host.

---

## 1. Resource Budget & Sizing

The Oracle Always Free tier provides up to 4 OCPUs and 24 GB RAM. We strictly budget **2 OCPUs and 12 GB RAM** for the Control Plane to ensure deterministic stability and leave head-room for OS buffering:

| Service | Container Image | Memory Limit | CPU Limit | Purpose |
|---|---|---|---|---|
| **Caddy** | `caddy:2.8.4-alpine` | 256 MB | 0.50 OCPU | Edge proxy, TLS auto-renewal (HTTP/2 & HTTP/3), security headers |
| **Control Plane** | `ocr-control-plane:arm64` | 2048 MB | 1.50 OCPU | FastAPI app, REST API, auth, document ingestion, lease dispatch |
| **PostgreSQL 16** | `postgres:16-alpine` | 2560 MB | 1.00 OCPU | Multi-tenant relational store, audit logs, job states, quotas |
| **Redis 7** | `redis:7.2-alpine` | 512 MB | 0.50 OCPU | Rate limiting token buckets, worker lease cache |
| **OS & File Cache** | Ubuntu Linux Kernel | ~6500 MB | - | Page cache for encrypted document vault read/writes |
| **Total Allocations**| - | **5376 MB** | - | **Well within 12 GB physical RAM** |

---

## 2. Oracle Cloud Console Provisioning

### Step 2.1: Virtual Cloud Network (VCN) & Ingress Rules
1. In the OCI Console, navigate to **Networking** > **Virtual Cloud Networks**.
2. Select your VCN and click **Security Lists** > **Default Security List**.
3. Under **Ingress Rules**, ensure the following stateful rules exist:

| Direction | Source CIDR | IP Protocol | Destination Port | Purpose |
|---|---|---|---|---|
| Ingress | `0.0.0.0/0` | TCP | `22` | Administrative SSH access |
| Ingress | `0.0.0.0/0` | TCP | `80` | Caddy ACME HTTP-01 challenge |
| Ingress | `0.0.0.0/0` | TCP | `443` | Public HTTPS Web Dashboard & API |
| Ingress | `0.0.0.0/0` | UDP | `443` | HTTP/3 QUIC |

> [!IMPORTANT]
> **Never open ports 5432 (Postgres), 6379 (Redis), or 8000 (FastAPI)** in the OCI Security List. All internal communication is restricted to Docker bridge networks.

### Step 2.2: Compute Instance Creation
1. Go to **Compute** > **Instances** > **Create Instance**.
2. Name: `ocr-control-plane`.
3. Image: **Ubuntu 24.04** (Canonical Ubuntu Server 24.04 Minimal aarch64).
4. Shape: **Ampere VM.Standard.A1.Flex**:
   - OCPUs: **2**
   - Memory (GB): **12**
5. Networking: Assign a public IPv4 address.
6. SSH Keys: Upload your public SSH key.
7. Boot Volume: 50 GB to 100 GB (Always Free allows up to 200 GB total storage across tenancy).

---

## 3. Host System Setup & Hardening

Connect to your instance via SSH:
```bash
ssh ubuntu@<YOUR_OCI_PUBLIC_IP>
```

### Step 3.1: System Updates & Docker Installation
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git ufw fail2ban ca-certificates

# Install Official Docker Engine (includes Docker Compose v2)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
```

### Step 3.2: Configure Firewall & Fix OCI Iptables
Oracle Linux and Ubuntu cloud images come with custom iptables rules that can block incoming HTTP/S traffic even when OCI security lists are opened.

Run the provided setup script:
```bash
cd /opt
sudo git clone https://github.com/your-org/ocrLab.git
cd /opt/ocrLab
sudo chmod +x deploy/oracle/setup-firewall.sh deploy/oracle/backup.sh
sudo ./deploy/oracle/setup-firewall.sh
```

---

## 4. Application Configuration

### Step 4.1: Production Environment File
Copy the production template:
```bash
cp .env.production.example .env.production
```

Generate secure 256-bit secrets using `openssl`:
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate STORAGE_VAULT_KEY (AES-256-GCM, exact 64 hex characters)
openssl rand -hex 32

# Generate WORKER_SECRET_KEY (shared secret for GPU worker lease auth)
openssl rand -hex 32

# Generate POSTGRES_PASSWORD
openssl rand -base64 24
```

Edit `.env.production`:
```bash
nano .env.production
```
Configure your domain name (`APP_DOMAIN=ocr.yourdomain.com`) and paste the generated secrets. Ensure your DNS `A` or `AAAA` record points `ocr.yourdomain.com` to the OCI public IP.

---

## 5. Deployment & Systemd Service

### Step 5.1: Build and Launch Containers
```bash
cd /opt/ocrLab/deploy/oracle
docker compose -f docker-compose.oracle.yml up -d --build
```

Verify that all 4 containers are running and healthy:
```bash
docker compose -f docker-compose.oracle.yml ps
```

Expected output:
```text
NAME                IMAGE                     COMMAND                  SERVICE         STATUS                    PORTS
ocr_caddy           caddy:2.8.4-alpine        "caddy run --config …"   caddy           Up (healthy)              0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
ocr_control_plane   ocr-control-plane:arm64   "uvicorn app.main:ap…"   control-plane   Up (healthy)              8000/tcp
ocr_postgres        postgres:16-alpine        "docker-entrypoint.s…"   db              Up (healthy)              5432/tcp
ocr_redis           redis:7.2-alpine          "docker-entrypoint.s…"   redis           Up (healthy)              6379/tcp
```

### Step 5.2: Install Systemd Service for Auto-Start
Ensure the control plane automatically restarts across VM reboots:
```bash
sudo cp deploy/oracle/ocr-cloud.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ocr-cloud
```

### Step 5.3: Automated Backups
Schedule daily backups at 03:00 UTC via cron:
```bash
sudo crontab -e
```
Add the following line:
```cron
0 3 * * * /opt/ocrLab/deploy/oracle/backup.sh >> /var/log/ocr_backup.log 2>&1
```

---

## 6. Verification and Health Checks

1. Verify public HTTPS and Let's Encrypt TLS:
   ```bash
   curl -I https://ocr.yourdomain.com/v1/health
   ```
   Should return `HTTP/2 200` with HSTS headers.

2. Inspect real-time container memory usage:
   ```bash
   docker stats --no-stream
   ```
   Ensure total RAM consumed across all 4 containers stays well below the 12 GB physical capacity.
