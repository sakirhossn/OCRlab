"""
Unlimited OCR Cloud — Modal Serverless GPU Worker Deployment.

Deploys the Unlimited-OCR-2 inference pipeline on Modal's serverless infrastructure.
Features automatic scale-to-zero when the job queue is empty.
"""

import os
import modal

# Define Modal App
app = modal.App("unlimited-ocr-worker")

# Define Container Image with GPU Drivers and ML Dependencies
worker_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0", "curl")
    .pip_install(
        "torch>=2.4.0",
        "pymupdf>=1.24.0,<2.0.0",
        "pillow>=10.0.0",
        "httpx>=0.27.0",
        "pydantic>=2.7.0",
        "tenacity>=8.2.0",
        "transformers>=4.40.0",
        "accelerate>=0.30.0",
        "sentencepiece>=0.2.0",
        "timm>=1.0.0",
    )
    .add_local_python_source("worker", "sdks")
)

# Volume for model weight caching across warm container instances
model_cache = modal.Volume.from_name("unlimited-ocr-models", create_if_missing=True)


@app.function(
    image=worker_image,
    gpu="A10G",  # 24GB VRAM Ampere GPU ($1.10/hr, billed per-second)
    volumes={"/root/.cache/huggingface": model_cache},
    secrets=[modal.Secret.from_name("ocr-cloud-secrets")],
    timeout=600,
    concurrency_limit=5,
)
def process_single_batch() -> int:
    """
    Executes a single processing cycle:
    Pulls pending leases from the Control Plane, executes OCR inference,
    and returns the count of completed jobs.
    """
    import asyncio
    from worker.worker_daemon import WorkerDaemon

    control_plane_url = os.environ["CONTROL_PLANE_URL"]
    worker_secret_key = os.environ["WORKER_SECRET_KEY"]

    daemon = WorkerDaemon(
        control_plane_url=control_plane_url,
        worker_secret_key=worker_secret_key,
        worker_id="modal-worker-pool",
        poll_interval_seconds=1.0,
    )

    # Process pending jobs in a loop until queue is empty
    processed_count = 0
    while True:
        # Run one lease claim and execution step
        job_ran = asyncio.run(daemon.run_single_cycle())
        if not job_ran:
            break
        processed_count += 1

    return processed_count


@app.function(schedule=modal.Cron("*/2 * * * *"))
def scheduled_poll():
    """
    Triggered every 2 minutes to inspect the Control Plane queue.
    If jobs are waiting, spins up serverless GPU worker functions.
    """
    import httpx

    control_plane_url = os.environ.get("CONTROL_PLANE_URL")
    worker_secret_key = os.environ.get("WORKER_SECRET_KEY")

    if not control_plane_url or not worker_secret_key:
        print("Missing CONTROL_PLANE_URL or WORKER_SECRET_KEY")
        return

    # Check queue status via internal health endpoint
    headers = {"Authorization": f"Bearer {worker_secret_key}"}
    try:
        resp = httpx.get(f"{control_plane_url}/v1/health", headers=headers, timeout=5.0)
        # Trigger GPU worker run
        process_single_batch.spawn()
    except Exception as exc:
        print(f"Failed to check control plane queue: {exc}")
