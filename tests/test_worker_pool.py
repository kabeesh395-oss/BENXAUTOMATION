"""Tests for QueueWorkerPool."""

from pathlib import Path
import pytest

from benxautomation.queue.job_queue import Job, JobQueue
from benxautomation.queue.monitor import ResourceMonitor
from benxautomation.queue.worker import QueueWorkerPool


class TestQueueWorkerPool:
    def test_process_one_job_success(self, tmp_path: Path):
        queue = JobQueue(db_path=tmp_path / "worker_test.db")
        queue.enqueue("shorts", {"asset": "test.png"})

        def dummy_handler(job: Job) -> dict:
            return {"status": "ok", "processed_type": job.job_type}

        pool = QueueWorkerPool(queue, dummy_handler, max_workers=1)
        processed = pool.process_one_job()

        assert processed is True
        job = queue.get_job(1)
        assert job is not None
        assert job.status == "COMPLETED"
        assert job.result == {"status": "ok", "processed_type": "shorts"}

    def test_process_one_job_with_handler_error(self, tmp_path: Path):
        queue = JobQueue(db_path=tmp_path / "worker_err.db")
        queue.enqueue("longform", {"asset": "bad.png"}, max_retries=0)

        def failing_handler(job: Job) -> dict:
            raise RuntimeError("Rendering crashed")

        pool = QueueWorkerPool(queue, failing_handler, max_workers=1)
        pool.process_one_job()

        job = queue.get_job(1)
        assert job is not None
        assert job.status == "FAILED"
        assert "Rendering crashed" in (job.error_message or "")

    def test_emergency_stop_halts_processing(self, tmp_path: Path):
        queue = JobQueue(db_path=tmp_path / "worker_stop.db")
        queue.enqueue("shorts", {"asset": "test.png"})

        monitor = ResourceMonitor(watch_dir=tmp_path)
        monitor.trigger_emergency_stop()

        pool = QueueWorkerPool(queue, lambda j: {}, monitor=monitor)
        processed = pool.process_one_job()

        assert processed is False
        # Job must remain PENDING
        job = queue.get_job(1)
        assert job is not None
        assert job.status == "PENDING"
