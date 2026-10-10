"""Bounded background worker for AI investigations.

The queue is backed by persistent job state (the investigations table), not by
in-process memory, so a job survives process restarts and can be re-driven.
``InvestigationService.run_job`` is idempotent, which makes this worker safe to
replace later with Cloud Tasks / Cloud Run: a Cloud Task handler only needs to
call the same idempotent entry point.
"""

from __future__ import annotations

import argparse
import logging
import threading

logger = logging.getLogger(__name__)


class InvestigationWorker:
    """Single-loop worker: claims queued jobs from persistent storage."""

    def __init__(self, service, poll_interval: float = 1.0) -> None:
        self._service = service
        self._poll_interval = poll_interval
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="investigation-worker", daemon=True
        )
        self._thread.start()
        logger.info("Investigation worker started")

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        logger.info("Investigation worker stopped")

    def wake(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                jobs = self._service.repository.queued_jobs(limit=1)
            except Exception:  # database hiccup; keep the worker alive
                logger.exception("Worker failed to read queued jobs")
                jobs = []
            for job in jobs:
                if self._stop.is_set():
                    break
                self._service.run_job(job["investigation_id"])
            self._wake.wait(timeout=self._poll_interval)
            self._wake.clear()


def main() -> None:
    """Run an investigation worker standalone, outside the FastAPI process.

    Useful for Cloud Tasks / Cloud Run style deployments where the API and the
    worker are separate processes sharing the same persistent job store.
    """
    parser = argparse.ArgumentParser(
        prog="python -m services.api.services.investigation_worker",
        description="Process queued AI investigations from a shared job store.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds between queue polls (default: 1.0).",
    )
    args = parser.parse_args()

    from services.api.services.investigation_service import InvestigationService

    service = InvestigationService()
    service.initialize()
    worker = InvestigationWorker(service, poll_interval=args.poll_interval)
    worker.start()
    logger.info("Standalone investigation worker started")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        worker.stop()
        logger.info("Standalone investigation worker stopped")


if __name__ == "__main__":
    main()
