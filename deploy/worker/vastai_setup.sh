#!/usr/bin/env bash
# ==============================================================================
# Unlimited OCR Cloud — Vast.ai GPU Worker Provisioning Script
# Target Instance: NVIDIA RTX 3090 / 4090 (24GB VRAM)
# ==============================================================================

set -euo pipefail

echo "========================================================"
echo " Initializing Unlimited OCR Cloud GPU Worker on Vast.ai"
echo "========================================================"

# Step 1: Check environment variables
if [ -z "${CONTROL_PLANE_URL:-}" ] || [ -z "${WORKER_SECRET_KEY:-}" ]; then
    echo "ERROR: Please set CONTROL_PLANE_URL and WORKER_SECRET_KEY before running." >&2
    echo "Usage: CONTROL_PLANE_URL=https://ocr.example.com WORKER_SECRET_KEY=secret ./vastai_setup.sh" >&2
    exit 1
fi

# Step 2: System packages
apt-get update -qq && apt-get install -y -qq python3-pip python3-venv git curl libgl1 libglib2.0-0

# Step 3: Python Virtual Environment
VENV_PATH="/root/ocr_venv"
if [ ! -d "${VENV_PATH}" ]; then
    echo "==> Creating virtual environment..."
    python3 -m venv "${VENV_PATH}"
fi

# Activate venv
# shellcheck disable=SC1091
source "${VENV_PATH}/bin/activate"

# Step 4: Install dependencies
echo "==> Installing PyTorch and OCR dependencies..."
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install "pymupdf>=1.24.0,<2.0.0" pillow httpx pydantic tenacity transformers accelerate sentencepiece timm

# Step 5: Start Worker Daemon
export GPU_PLATFORM="vastai"
echo "==> Starting Worker Daemon..."
exec python3 -m worker.worker_daemon
