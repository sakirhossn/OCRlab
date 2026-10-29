#!/usr/bin/env bash
# ==============================================================================
# Unlimited OCR Cloud — RunPod GPU Worker Launch Script
# Recommended GPU: NVIDIA RTX 4090 (24GB VRAM) or A10G (24GB VRAM)
# ==============================================================================

set -euo pipefail

echo "========================================================"
echo " Starting Unlimited OCR Cloud GPU Worker on RunPod..."
echo "========================================================"

# Check GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo "==> NVIDIA GPU Detected:"
    nvidia-smi --query-gpu=gpu_name,memory.total,driver_version --format=csv,noheader
else
    echo "WARNING: nvidia-smi not found! GPU inference will fail." >&2
fi

# Ensure model directory exists on persistent volume
MODEL_DIR="${TRANSFORMERS_CACHE:-/workspace/models}"
mkdir -p "${MODEL_DIR}"

# Check for required environment variables
if [ -z "${CONTROL_PLANE_URL:-}" ]; then
    echo "ERROR: CONTROL_PLANE_URL environment variable is required (e.g. https://ocr.example.com)." >&2
    exit 1
fi

if [ -z "${WORKER_SECRET_KEY:-}" ]; then
    echo "ERROR: WORKER_SECRET_KEY environment variable is required." >&2
    exit 1
fi

export MODEL_NAME_OR_PATH="${MODEL_NAME_OR_PATH:-baidu/Unlimited-OCR-2}"
export GPU_PLATFORM="runpod"
export IDLE_SHUTDOWN_TIMEOUT="${IDLE_SHUTDOWN_TIMEOUT:-900}" # 15 minutes

echo "==> Configuration:"
echo "    Control Plane: ${CONTROL_PLANE_URL}"
echo "    Model:         ${MODEL_NAME_OR_PATH}"
echo "    Model Cache:   ${MODEL_DIR}"
echo "    Idle Timeout:  ${IDLE_SHUTDOWN_TIMEOUT}s"

# Pre-download model weights if not present (to avoid download latency during job processing)
echo "==> Verifying model weights in ${MODEL_DIR}..."
python -c "
import os
from huggingface_hub import snapshot_download
model_id = os.environ.get('MODEL_NAME_OR_PATH', 'baidu/Unlimited-OCR-2')
cache_dir = os.environ.get('TRANSFORMERS_CACHE', '/workspace/models')
print(f'Checking/Downloading {model_id}...')
snapshot_download(repo_id=model_id, local_dir=os.path.join(cache_dir, 'unlimited_ocr_2'), ignore_patterns=['*.bin', '*.pt'])
print('Model weights verified.')
" || echo "Note: Model pre-download skipped or deferred to first inference."

echo "==> Starting Worker Daemon (outbound HTTPS polling)..."
exec python -m worker.worker_daemon
