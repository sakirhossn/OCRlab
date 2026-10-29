# GPU Inference Requirements Reference: Baidu Unlimited-OCR-2

## 1. Model Overview & Architecture
- **Model Name**: `baidu/Unlimited-OCR-2`
- **Backbone**: Vision-Language Model with `UnlimitedOCRForCausalLM` decoder (~3.3B parameters).
- **Core Mechanism**: Reference Sliding Window Attention (R-SWA / SR-SWA).
  - Fixed-size working references (e.g. 512 tokens).
  - Constant KV cache footprint during long-sequence decoding.
  - Capable of ingesting stacks of 20 to 100+ pages without context memory explosion.
- **License**: MIT License (permissive commercial use).

## 2. Hardware & VRAM Profiling

| Precision / Quantization | Model Weight Footprint | Peak VRAM (Inference) | Recommended Hardware |
|---|---|---|---|
| **BF16 / FP16 (Full Precision)** | ~6.6 GB | ~8.0 - 9.5 GB | RTX 3090, RTX 4090, A10G, L4, T4 (16GB) |
| **FP8 Dynamic** | ~3.8 GB | ~5.0 - 6.0 GB | RTX 4090, Ada Lovelace, Hopper |
| **INT4 / AWQ** | ~2.2 GB | ~3.5 - 4.5 GB | RTX 3060 (12GB), T4 (16GB), RTX 4070 |

## 3. Serving Engines: Transformers vs SGLang vs vLLM

### Option A: SGLang (Recommended for High Throughput)
```bash
python -m sglang.launch_server \
  --model baidu/Unlimited-OCR-2 \
  --served-model-name Unlimited-OCR-2 \
  --attention-backend fa3 \
  --page-size 1 \
  --mem-fraction-static 0.8 \
  --context-length 32768 \
  --enable-custom-logit-processor \
  --disable-overlap-schedule \
  --skip-server-warmup \
  --host 127.0.0.1 \
  --port 10000
```

### Option B: Native PyTorch / Transformers Worker Daemon
For RunPod / Modal serverless workers:
```python
import torch
from transformers import AutoModel, AutoTokenizer

model_id = "baidu/Unlimited-OCR-2"
tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
model = AutoModel.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    trust_remote_code=True,
    device_map="cuda:0"
).eval()
```

## 4. Deterministic Post-Processing
Unlimited-OCR-2 natively generates layout Markdown (with `#` headers, LaTeX math `$`, and tables `|...|`).
The worker post-processor deterministically converts this stream into the versioned JSON contract:
1. Parse Markdown headings -> `type: "heading"`, `level: 1..6`.
2. Parse Markdown tables -> `type: "table"`, `headers: [...]`, `rows: [[...]]`.
3. Parse LaTeX math blocks -> `type: "formula"`, `text: "$$..."`.
4. Parse bullet lists -> `type: "list"`, `items: [...]`.
5. Parse standard text -> `type: "paragraph"`.
6. Assign sequential `reading_order` per page.
