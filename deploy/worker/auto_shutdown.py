"""
Unlimited OCR Cloud — Worker Auto-Shutdown Controller.

Monitors GPU worker activity and automatically stops the instance or pod
when the job queue remains empty for an extended threshold, avoiding
unnecessary GPU cloud rental expenses.
"""

import os
import sys
import time
import logging
import subprocess

logger = logging.getLogger("worker.auto_shutdown")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class IdleShutdownMonitor:
    def __init__(self, idle_timeout_seconds: int = 900):
        self.idle_timeout_seconds = idle_timeout_seconds
        self.last_active_timestamp = time.time()
        self.platform = os.getenv("GPU_PLATFORM", "generic").lower()
        self.pod_id = os.getenv("RUNPOD_POD_ID")
        self.api_key = os.getenv("RUNPOD_API_KEY")

    def record_activity(self) -> None:
        """Called whenever a job is claimed or processed."""
        self.last_active_timestamp = time.time()

    def check_idle_timeout(self) -> bool:
        """Returns True if worker has been idle beyond the configured threshold."""
        idle_duration = time.time() - self.last_active_timestamp
        if idle_duration >= self.idle_timeout_seconds:
            logger.warning(
                "Worker has been idle for %d seconds (threshold: %d s). Triggering auto-shutdown.",
                int(idle_duration),
                self.idle_timeout_seconds,
            )
            return True
        return False

    def trigger_shutdown(self) -> None:
        """Executes platform-appropriate termination."""
        logger.info("Executing auto-shutdown on platform: %s", self.platform)

        if self.platform == "runpod" and self.pod_id and self.api_key:
            # Trigger RunPod Pod Termination via REST API
            import httpx
            url = f"https://api.runpod.io/graphql?api_key={self.api_key}"
            mutation = {
                "query": f'mutation {{ podStop(input: {{ podId: "{self.pod_id}" }}) {{ id desiredStatus }} }}'
            }
            try:
                resp = httpx.post(url, json=mutation, timeout=10.0)
                logger.info("RunPod shutdown response: %s", resp.text)
            except Exception as exc:
                logger.error("Failed to stop RunPod instance via API: %s", exc)

        elif self.platform == "vastai":
            try:
                subprocess.run(["vastai", "stop", "instance"], check=False)
            except Exception as exc:
                logger.error("Failed to execute vastai stop: %s", exc)

        else:
            # Generic Linux VM / bare-metal server
            try:
                subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
            except Exception as exc:
                logger.error("Failed to execute system shutdown: %s", exc)

        # Terminate daemon process
        sys.exit(0)
