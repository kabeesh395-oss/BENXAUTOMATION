"""Comprehensive end-to-end acceptance tests for the persistent job queue.

Verifies:
- Enqueue / Dequeue lifecycle
- Duplicate-job prevention
- Automatic retry on handler failures
- Final failure marking after max_retries
- Simulated stuck job recovery upon restart
- Bounded concurrency across worker pool
- Continuous discovery of dynamically enqueued jobs
- Emergency stop safeguard (manual & signal file)
- Low-disk protection safeguard
"""

import threading
import time
from pathlib import Path
import pytest

from benxautomation.queue.job_queue import DuplicateJobError, Job, JobQueue
from benxautomation.queue.monitor import ResourceMonitor
from benxautomation.queue.worker import QueueWorkerPool


@pytest.fixture
def isolated_queue(tmp_path: Path) -> JobQueue:
    db_file = tmp_path / "acceptance_jobs.db"
    return JobQueue(db_file)


class TestQueueAcceptanceLifecycle:
    """Verify queue behavior end to end."""

    def test_duplicate_job_prevention(self, isolated_queue: JobQueue) -> None:
        """Enqueueing identical deduplication_key must raise DuplicateJobError."""
        j1 = isolated_queue.enqueue(
            "shorts",
            {"title": "Deep Sea 1"},
            deduplication_key="video-deep-sea-42",
        )
        assert j1.id > 0
        assert j1.deduplication_key == "video-deep-sea-42"

        with pytest.raises(DuplicateJobError) as exc_info:
            isolated_queue.enqueue(
                "shorts",
                {"title": "Deep Sea 1 duplicate"},
                deduplication_key="video-deep-sea-42",
            )
        assert "video-deep-sea-42" in str(exc_info.value)

    def test_success_job_lifecycle(self, isolated_queue: JobQueue) -> None:
        """Enqueue, process, and complete job with recorded result."""
        job = isolated_queue.enqueue("shorts", {"asset": "sample.png"})

        def success_handler(j: Job) -> dict:
            return {"output_file": "final.mp4", "render_time_s": 3.2}

        pool = QueueWorkerPool(isolated_queue, success_handler)
        did_process = pool.process_one_job()
        assert did_process is True

        completed_job = isolated_queue.get_job(job.id)
        assert completed_job is not None
        assert completed_job.status == "COMPLETED"
        assert completed_job.result == {"output_file": "final.mp4", "render_time_s": 3.2}

    def test_retry_and_permanent_failure(self, isolated_queue: JobQueue) -> None:
        """Failing job retries up to max_retries before becoming FAILED."""
        job = isolated_queue.enqueue(
            "longform",
            {"fail": True},
            max_retries=2,
        )

        def failing_handler(j: Job) -> dict:
            raise RuntimeError("Renderer crashed")

        pool = QueueWorkerPool(isolated_queue, failing_handler)

        # Attempt 1 -> Rescheduled to PENDING with retry_count=1
        assert pool.process_one_job() is True
        j1 = isolated_queue.get_job(job.id)
        assert j1.status == "PENDING"
        assert j1.retry_count == 1
        assert "Renderer crashed" in j1.error_message

        # Attempt 2 -> Rescheduled to PENDING with retry_count=2
        assert pool.process_one_job() is True
        j2 = isolated_queue.get_job(job.id)
        assert j2.status == "PENDING"
        assert j2.retry_count == 2

        # Attempt 3 -> Exceeds max_retries (2) -> status FAILED
        assert pool.process_one_job() is True
        j3 = isolated_queue.get_job(job.id)
        assert j3.status == "FAILED"
        assert j3.retry_count == 3
        assert "Renderer crashed" in j3.error_message

        # Next dequeue should find no pending jobs
        assert pool.process_one_job() is False

    def test_simulated_stuck_job_restart_recovery(self, tmp_path: Path) -> None:
        """Simulated crash leaves job in PROCESSING; restart resets it to PENDING."""
        db_path = tmp_path / "crash_recovery.db"
        q1 = JobQueue(db_path)
        job = q1.enqueue("shorts", {"task": "render"})

        # Dequeue marks it PROCESSING
        dequeued = q1.dequeue()
        assert dequeued is not None
        assert dequeued.id == job.id
        assert dequeued.status == "PROCESSING"

        # Simulate system crash without completion.
        # Now instantiate a new JobQueue on the same database
        q2 = JobQueue(db_path)
        recovered_job = q2.get_job(job.id)
        assert recovered_job.status == "PENDING"

    def test_continuous_discovery_and_bounded_concurrency(self, isolated_queue: JobQueue) -> None:
        """Worker pool processes jobs concurrently up to max_workers and discovers new jobs."""
        active_concurrency = 0
        max_observed_concurrency = 0
        lock = threading.Lock()

        def slow_handler(j: Job) -> dict:
            nonlocal active_concurrency, max_observed_concurrency
            with lock:
                active_concurrency += 1
                if active_concurrency > max_observed_concurrency:
                    max_observed_concurrency = active_concurrency
            time.sleep(0.08)
            with lock:
                active_concurrency -= 1
            return {"done": True}

        pool = QueueWorkerPool(
            isolated_queue,
            slow_handler,
            max_workers=2,
            poll_interval=0.02,
        )

        for i in range(4):
            isolated_queue.enqueue("shorts", {"index": i})

        # Run loop in background thread
        thread = threading.Thread(target=pool.run_worker_loop, kwargs={"max_cycles": 15})
        thread.start()

        # Dynamically enqueue another job while worker loop is running
        time.sleep(0.05)
        isolated_queue.enqueue("longform", {"dynamic": True})

        thread.join(timeout=5.0)

        # Concurrency must be bounded to max_workers (2)
        assert max_observed_concurrency <= 2
        assert max_observed_concurrency >= 1

        stats = isolated_queue.count_by_status()
        assert stats["COMPLETED"] == 5
        assert stats["PENDING"] == 0

    def test_emergency_stop_halts_processing(self, isolated_queue: JobQueue, tmp_path: Path) -> None:
        """Emergency stop prevents jobs from being dequeued."""
        stop_file = tmp_path / "emergency.stop"
        monitor = ResourceMonitor(emergency_signal_file=stop_file)

        isolated_queue.enqueue("shorts", {"item": 1})
        pool = QueueWorkerPool(isolated_queue, lambda j: {}, monitor=monitor)

        # Trigger stop via signal file
        stop_file.touch()
        assert pool.process_one_job() is False
        assert isolated_queue.get_job(1).status == "PENDING"

        # Clear stop file
        stop_file.unlink()
        assert pool.process_one_job() is True
        assert isolated_queue.get_job(1).status == "COMPLETED"

    def test_low_disk_protection_halts_processing(self, isolated_queue: JobQueue) -> None:
        """Low disk space halts processing immediately."""
        monitor = ResourceMonitor(min_free_bytes=10**15)  # 1 Petabyte minimum
        isolated_queue.enqueue("shorts", {"item": 1})
        pool = QueueWorkerPool(isolated_queue, lambda j: {}, monitor=monitor)

        assert pool.process_one_job() is False
        assert isolated_queue.get_job(1).status == "PENDING"
