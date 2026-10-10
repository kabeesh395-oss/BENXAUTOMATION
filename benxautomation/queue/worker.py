"""Continuous queue worker pool with bounded concurrency and resource safeguards."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from benxautomation.errors import BenxError
from benxautomation.logger import get_logger
from benxautomation.queue.job_queue import Job, JobQueue
from benxautomation.queue.monitor import ResourceMonitor

log = get_logger(__name__)


class QueueWorkerPool:
    """Manages bounded parallel workers processing the persistent job queue."""

    def __init__(
        self,
        queue: JobQueue,
        handler: Callable[[Job], dict[str, Any]],
        *,
        max_workers: int = 2,
        monitor: Optional[ResourceMonitor] = None,
        poll_interval: float = 1.0,
    ):
        self.queue = queue
        self.handler = handler
        self.max_workers = max(1, max_workers)
        self.monitor = monitor or ResourceMonitor()
        self.poll_interval = poll_interval
        self._running = False

    def process_one_job(self) -> bool:
        """Fetch and process a single job from the queue. Returns True if job was processed."""
        # 1. Check safeguards before dequeuing
        if self.monitor.check_emergency_stop():
            log.warning("Emergency stop active. Worker will not dequeue jobs.")
            return False

        if not self.monitor.check_storage_safety():
            log.warning("Storage safeguard threshold breached. Pausing job processing.")
            return False

        job = self.queue.dequeue()
        if not job:
            return False

        log.info("Worker started processing Job %d (type=%s)", job.id, job.job_type)
        try:
            # Re-check safeguards immediately before execution
            self.monitor.enforce_safeguards()
            result = self.handler(job)
            self.queue.complete_job(job.id, result)
            return True
        except Exception as exc:
            log.exception("Error processing Job %d: %s", job.id, exc)
            self.queue.fail_job(job.id, str(exc))
            return True

    def run_worker_loop(self, *, max_cycles: Optional[int] = None) -> None:
        """Continuous execution loop with bounded concurrency."""
        self._running = True
        log.info("Starting QueueWorkerPool with %d bounded workers...", self.max_workers)

        cycles = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while self._running:
                if max_cycles is not None and cycles >= max_cycles:
                    break
                cycles += 1

                # Check safeguards
                if self.monitor.check_emergency_stop():
                    log.warning("Emergency stop triggered. Worker loop exiting.")
                    break

                # Dispatch jobs up to max_workers
                futures = []
                for _ in range(self.max_workers):
                    job = self.queue.dequeue()
                    if not job:
                        break
                    futures.append(executor.submit(self._execute_single_job, job))

                if futures:
                    for f in as_completed(futures):
                        try:
                            f.result()
                        except Exception as e:
                            log.error("Worker task execution error: %s", e)
                else:
                    # Queue is empty, pause briefly
                    time.sleep(self.poll_interval)

        self._running = False
        log.info("QueueWorkerPool stopped.")

    def stop(self) -> None:
        """Stop worker execution loop."""
        self._running = False

    def _execute_single_job(self, job: Job) -> None:
        try:
            self.monitor.enforce_safeguards()
            result = self.handler(job)
            self.queue.complete_job(job.id, result)
        except Exception as exc:
            log.exception("Job %d failed during execution: %s", job.id, exc)
            self.queue.fail_job(job.id, str(exc))
