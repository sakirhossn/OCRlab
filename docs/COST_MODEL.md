# Cost Model & Unit Economics: Unlimited OCR Cloud

## 1. Executive Summary

Unlimited OCR Cloud is engineered to minimize infrastructure expenditure by leveraging free cloud control planes and on-demand GPU inference:
- **Control Plane**: $0.00 / month (Oracle Cloud Always Free Ampere A1).
- **GPU Inference**: Variable, on-demand ($0.20 to $0.44 / hour).
- **Blended Cost per Page**: ~$0.0003 to $0.0015 per page (approx. $0.30 - $1.50 per 1,000 pages).

---

## 2. Layer A: Oracle Cloud Always Free (Control Plane)

| Service | Specification | Free Tier Allowance | Our Utilization | Monthly Cost |
|---|---|---|---|---|
| **Compute** | Ampere A1 ARM64 | 4 OCPU, 24 GB RAM | 2 OCPU, 12 GB RAM | **$0.00** |
| **Boot Volume** | Block Storage | 200 GB Total | 100 GB | **$0.00** |
| **Outbound Data** | Network Egress | 10 TB / month | < 100 GB / month | **$0.00** |
| **Public IPv4** | Static IPv4 | 1 Free Ephemeral/Reserved | 1 IPv4 | **$0.00** |
| **TLS Certificate** | Let's Encrypt / Caddy | Unlimited | Automated | **$0.00** |
| **Total Layer A** | | | | **$0.00 / mo** |

---

## 3. Layer B: GPU Inference Economics (RunPod / Modal / Vast.ai)

Unlimited-OCR-2 (~3.3B parameters) requires ~7–9 GB VRAM in FP16/BF16, or ~4–5 GB in FP8. It runs efficiently on mid-tier consumer or datacenter GPUs.

### GPU Provider Comparison

| Provider | GPU Model | VRAM | Hourly Cost (Spot/Community) | Hourly Cost (On-Demand) | Pages / Second (Estimated) |
|---|---|---|---|---|---|
| **RunPod** | NVIDIA RTX 3090 | 24 GB | $0.22 / hr | $0.29 / hr | 1.8 – 2.5 pages/s |
| **RunPod** | NVIDIA RTX 4090 | 24 GB | $0.34 / hr | $0.44 / hr | 3.5 – 5.0 pages/s |
| **RunPod** | NVIDIA L4 | 24 GB | $0.30 / hr | $0.38 / hr | 2.5 – 3.2 pages/s |
| **Modal** | NVIDIA T4 | 16 GB | N/A (Serverless) | $0.000164 / sec ($0.59/hr) | 1.2 – 1.8 pages/s |
| **Vast.ai** | NVIDIA RTX 3080/3090 | 10-24 GB | $0.15 - $0.20 / hr | $0.25 / hr | 1.5 – 2.2 pages/s |

---

## 4. Per-Page Cost Analysis

### Scenario A: Route A (Digital Vector PDF via PyMuPDF)
- Native vector extraction runs entirely on CPU / worker with sub-second latency (~0.05 seconds/page).
- **Cost per page**: Negligible (~**$0.00001** / page).

### Scenario B: Route B (AI OCR via Unlimited-OCR-2 on RTX 4090)
- Hourly GPU rate: $0.44 / hour ($0.000122 / second).
- Average throughput: 4 pages / second.
- Time per page: 0.25 seconds.
- **Cost per page**: `0.25 s * $0.000122/s` = **$0.0000305** (approx. **$0.03 per 1,000 pages**).

### Scenario C: Conservative Real-World Blended Batch (including page rendering, I/O, and token generation)
- Real-world sustained speed: 1.5 pages / second on an RTX 3090 ($0.29 / hr).
- Pages per hour: `3,600 * 1.5` = 5,400 pages.
- Cost per 1,000 pages: `$0.29 / 5.4` = **$0.054** per 1,000 pages.
- Even factoring in idle worker buffer and network transfers, the cost remains **< $0.15 per 1,000 pages**, which is 10x to 50x lower than commercial proprietary OCR APIs ($1.50 to $10.00 per 1,000 pages).

---

## 5. Cost Optimization Strategies
1. **Hybrid Routing**:
   Digital PDFs skip the GPU model entirely, reducing GPU usage by up to 60-80% for standard corporate filings.
2. **Auto-Shutdown / Scale-to-Zero**:
   Workers monitor the control plane queue. If no jobs are queued for 5 minutes, serverless workers shut down automatically, avoiding idle burn.
3. **Sliding Window Tuning**:
   SR-SWA attention sliding window is configured to 512 tokens to prevent VRAM spikes during long-document generation.
