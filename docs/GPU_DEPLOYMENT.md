# GPU Inference Worker Deployment Guide (Layer B)

**Project**: Unlimited OCR Cloud (`ocrLab`)  
**Engine**: Baidu `Unlimited-OCR-2` (~3.3B parameters)  
**Inference Modes**: Native CUDA (PyTorch / Transformers / SGLang)  
**Core Invariant**: Workers connect **outbound only** over HTTPS. No open inbound ports.

---

## 1. Hardware Requirements & VRAM Budgeting

Unlimited-OCR-2 uses Reference Sliding Window Attention (R-SWA / SR-SWA) with a 512-token window size. The model requires NVIDIA CUDA architecture:

| Precision / Quantization | Model Weight Size | Peak Inference VRAM | Recommended Minimum GPU |
|---|---|---|---|
| **FP16 / BF16 (Default)** | ~6.6 GB | **7.5 – 9.5 GB** | **NVIDIA RTX 4090 (24GB)**, **A10G (24GB)**, **RTX 3090 (24GB)** |
| **FP8 / AWQ (Quantized)** | ~3.4 GB | **5.0 – 6.0 GB** | **NVIDIA RTX 4070 (12GB)**, **RTX 3060 (12GB)**, **T4 (16GB)** |

### Performance Expectations
- **Route A (Digital PDF Native)**: ~0.05s – 0.15s per page (PyMuPDF vector extraction, no GPU needed).
- **Route B (AI OCR Engine)**: ~1.2s – 2.8s per page on an RTX 4090 / A10G (rasterization + Unlimited-OCR-2 + post-processing).

---

## 2. Security & Network Model

```
+------------------------------------+                  +-----------------------------+
|    Layer B: GPU Worker Host        |                  |  Layer A: Oracle OCI Host   |
| (RunPod / Modal / Vast.ai / CUDA)  |                  |    (Always Free ARM64)      |
|                                    |                  |                             |
|  [worker_daemon.py]                |                  |                             |
|         |                          |                  |                             |
|         +--- Outbound HTTPS POST --+----------------->| /v1/internal/leases/claim   |
|         |<-- Returns Job Lease ----+------------------| (Auth: WORKER_SECRET_KEY)   |
|         |                          |                  |                             |
|         +--- Download PDF Stream --+----------------->| /v1/internal/documents/dl   |
|         |<-- AES Decrypted PDF ----+------------------| (Signed HMAC Token, 300s)   |
|         |                          |                  |                             |
|   (Rasterize & OCR Inference)      |                  |                             |
|         |                          |                  |                             |
|         +--- Upload Schema 1.0 ----+----------------->| /v1/internal/leases/complete|
|                                    |                  +-----------------------------+
+------------------------------------+
```

- **Zero Inbound Ports**: The worker needs no public IP, no port forwarding, and no open listener.
- **Worker Authentication**: All requests require `Authorization: Bearer <WORKER_SECRET_KEY>`.
- **Short-Lived Leases**: Documents are downloaded via temporary HMAC signatures (300-second TTL).

---

## 3. Deployment Options

### Option A: RunPod Cloud GPU (On-Demand / Spot)

RunPod offers RTX 4090 and A10G instances at ~\$0.30–\$0.70/hour.

1. **Create Template**:
   - Container Image: `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime`
   - Volume Mount: `/workspace/models` (Persistent Volume recommended so weights are cached)
   - Expose Ports: *Leave completely empty* (outbound only)
2. **Environment Variables**:
   ```ini
   CONTROL_PLANE_URL=https://ocr.yourdomain.com
   WORKER_SECRET_KEY=your_64_char_worker_secret_key
   GPU_PLATFORM=runpod
   RUNPOD_API_KEY=your_runpod_api_key
   RUNPOD_POD_ID=$RUNPOD_POD_ID
   IDLE_SHUTDOWN_TIMEOUT=900
   ```
3. **Container Start Command**:
   ```bash
   bash -c "curl -sSL https://raw.githubusercontent.com/your-org/ocrLab/main/deploy/worker/runpod_start.sh | bash"
   ```
4. **Auto-Shutdown**: When no jobs are claimed for 15 minutes (`900` seconds), the worker calls the RunPod API to terminate the pod automatically.

---

### Option B: Modal Serverless GPU (Scale-to-Zero)

Modal enables zero-idle-cost GPU execution by spinning up an A10G container only when jobs are waiting in the queue, and scaling down to 0 replicas when the queue is drained.

1. Install Modal CLI:
   ```bash
   pip install modal
   modal setup
   ```
2. Store secrets in Modal:
   ```bash
   modal secret create ocr-cloud-secrets \
     CONTROL_PLANE_URL="https://ocr.yourdomain.com" \
     WORKER_SECRET_KEY="your_64_char_worker_secret_key"
   ```
3. Deploy the Modal App:
   ```bash
   modal deploy deploy/worker/modal_worker.py
   ```
4. The scheduled cron triggers every 2 minutes, processes any queued jobs, and powers down when done.

---

### Option C: Vast.ai Budget GPU (RTX 3090 / 4090)

Vast.ai provides low-cost GPU instances (~\$0.20–\$0.40/hour).

1. Rent an instance with **Ubuntu 22.04**, **CUDA 12+**, and at least 16GB VRAM.
2. Connect via SSH:
   ```bash
   ssh -p <PORT> root@<VAST_IP>
   ```
3. Clone and run the setup script:
   ```bash
   git clone https://github.com/your-org/ocrLab.git
   cd ocrLab
   CONTROL_PLANE_URL="https://ocr.yourdomain.com" \
   WORKER_SECRET_KEY="your_64_char_worker_secret_key" \
   ./deploy/worker/vastai_setup.sh
   ```

---

### Option D: Local NVIDIA GPU Workstation / On-Premise

To run workers on a local NVIDIA workstation:

1. Clone repository and setup environment:
   ```bash
   git clone https://github.com/your-org/ocrLab.git
   cd ocrLab
   uv sync --extra test
   ```
2. Set environment variables:
   ```bash
   export CONTROL_PLANE_URL="https://ocr.yourdomain.com"
   export WORKER_SECRET_KEY="your_64_char_worker_secret_key"
   export WORKER_ID="local-cuda-workstation-01"
   export MOCK_OCR="false"
   ```
3. Run the daemon:
   ```bash
   python -m worker.worker_daemon
   ```

---

## 4. Operational Monitoring & Verification

### Verifying GPU Ingestion
Monitor real-time daemon logs:
```text
2026-10-28 12:00:01 [INFO] [Worker:runpod-gpu-01] Polling for available jobs...
2026-10-28 12:00:03 [INFO] Claimed lease for Job: 550e8400-e29b-41d4-a716-446655440000 (Lease ID: lease_89a7f)
2026-10-28 12:00:04 [INFO] Downloaded PDF (1,420,112 bytes). Validating structure...
2026-10-28 12:00:04 [INFO] Page 1: Native vector inspection detected 850 chars. Selecting Route A.
2026-10-28 12:00:05 [INFO] Page 2: Scanned bitmap detected. Rendering at 150 DPI and executing Unlimited-OCR-2 (Route B)...
2026-10-28 12:00:07 [INFO] Inference completed in 1.82s. Post-processing into Schema 1.0 JSON.
2026-10-28 12:00:08 [INFO] Uploaded result payload. Job marked SUCCEEDED.
```

### Checking VRAM Usage
```bash
watch -n 1 nvidia-smi
```
Confirm GPU memory stabilizes around 7.5–9.5 GB during Route B inference with zero memory leaks across multiple job iterations.
