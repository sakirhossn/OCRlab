#!/usr/bin/env bash
# ==============================================================================
# Unlimited OCR Cloud — Oracle Cloud Infrastructure (OCI) Host Firewall Setup
# Target: Ubuntu 24.04 ARM64 (Ampere A1)
# ==============================================================================

set -euo pipefail

echo "==> Configuring Host Firewall for Unlimited OCR Cloud (OCI Always Free)..."

# Ensure root privileges
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (use sudo)." >&2
  exit 1
fi

# Step 1: Fix Oracle Linux / Ubuntu default iptables rules
# OCI Ubuntu images typically have pre-configured restrictive iptables rules
# that drop traffic even if UFW or OCI Security Lists allow it.
echo "==> Adjusting iptables rules for OCI Ubuntu..."
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT || true
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT || true
iptables -I INPUT 6 -m state --state NEW -p udp --dport 443 -j ACCEPT || true
netfilter-persistent save 2>/dev/null || true

# Step 2: Configure UFW (Uncomplicated Firewall)
echo "==> Configuring UFW..."
apt-get update -qq
apt-get install -y -qq ufw

# Set default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (rate limited)
ufw limit 22/tcp comment 'SSH rate-limited'

# Allow HTTP and HTTPS for Caddy edge proxy
ufw allow 80/tcp comment 'HTTP (Caddy Let\'s Encrypt ACME)'
ufw allow 443/tcp comment 'HTTPS (Caddy)'
ufw allow 443/udp comment 'HTTP/3 QUIC (Caddy)'

# Explicitly ensure internal services are NOT exposed to the public internet
# Port 5432 (Postgres), Port 6379 (Redis), Port 8000 (FastAPI Internal)
ufw deny 5432 comment 'Deny Postgres direct external access'
ufw deny 6379 comment 'Deny Redis direct external access'
ufw deny 8000 comment 'Deny Control Plane direct external access'

# Enable UFW
echo "y" | ufw enable

echo "==> Firewall status:"
ufw status verbose

echo "======================================================================="
echo "OCI Ingress Security List Reminder:"
echo "Ensure your OCI Virtual Cloud Network (VCN) Security List has matching"
echo "Stateful Ingress Rules for:"
echo "  - Port 22  (TCP)  - Management SSH"
echo "  - Port 80  (TCP)  - HTTP ACME Challenge"
echo "  - Port 443 (TCP)  - HTTPS Web & API"
echo "  - Port 443 (UDP)  - HTTP/3 QUIC"
echo "======================================================================="
