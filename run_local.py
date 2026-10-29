"""
Unified Local Runner for Unlimited OCR Cloud.

Runs both the FastAPI Control Plane and the Background Worker Daemon
in a single command and single process for convenient local development and testing.
"""

import asyncio
import logging
import sys
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.core.database import init_db
from app.main import app
from scripts.bootstrap import bootstrap
from worker.worker_daemon import ProductionOCRWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_local")


async def run_embedded_worker() -> None:
    """Embedded worker daemon loop running concurrently with the server."""
    # Wait 2 seconds for Uvicorn server to bind and start listening
    await asyncio.sleep(2.0)
    worker = ProductionOCRWorker(
        worker_id="local-embedded-worker",
        control_plane_url=f"http://127.0.0.1:{settings.port}",
        worker_token=settings.worker_auth_token,
    )
    logger.info(f"==> Background Worker active. Polling http://127.0.0.1:{settings.port} for jobs...")

    while not worker.should_stop:
        try:
            ran = await worker.process_one_job()
            if not ran:
                await asyncio.sleep(2.0)
            else:
                logger.info("==> Successfully completed OCR processing for leased job.")
        except Exception as e:
            # If server is still starting or shutting down, wait briefly
            await asyncio.sleep(3.0)


async def main() -> None:
    print("=" * 68)
    print("  STARTING UNLIMITED OCR CLOUD — LOCAL INSTANCE")
    print("=" * 68)

    # 1. Bootstrap database & demo key if needed
    await bootstrap()

    # 2. Configure Uvicorn server
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=settings.port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    print("\n" + "-" * 68)
    print(f"  Web Dashboard:  http://127.0.0.1:{settings.port}")
    print(f"  API Docs:       http://127.0.0.1:{settings.port}/docs")
    print(f"  API Key:        ocr_live_030e8d7bd1f44c5400d2c822b0e68bc550575e6643f63afe")
    print("-" * 68 + "\n")

    # 3. Run both FastAPI server and background worker concurrently
    try:
        await asyncio.gather(
            server.serve(),
            run_embedded_worker(),
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Stopping local server and worker...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
