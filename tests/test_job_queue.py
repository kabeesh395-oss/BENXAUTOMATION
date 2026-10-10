"""Tests for SQLite-backed JobQueue."""

from pathlib import Path

from benxautomation.queue.job_queue import JobQueue


class TestJobQueue:
    def test_enqueue_and_dequeue(self, tmp_path: Path):
        q = JobQueue(db_path=tmp_path / "test_jobs.db")
        job = q.enqueue("shorts", {"asset": "img.png", "duration": 5})

        assert job.id == 1
        assert job.status == "PENDING"
        assert job.job_type == "shorts"

        dequeued = q.dequeue()
        assert dequeued is not None
        assert dequeued.id == 1
        assert dequeued.status == "PROCESSING"

        # Subsequent dequeue on empty returns None
        assert q.dequeue() is None

    def test_complete_job(self, tmp_path: Path):
        q = JobQueue(db_path=tmp_path / "test_jobs.db")
        job = q.enqueue("longform", {"asset": "video.mp4"})
        dequeued = q.dequeue()
        assert dequeued is not None

        q.complete_job(dequeued.id, {"output": "/tmp/out.mp4"})
        updated = q.get_job(dequeued.id)
        assert updated is not None
        assert updated.status == "COMPLETED"
        assert updated.result == {"output": "/tmp/out.mp4"}

    def test_fail_job_with_retry(self, tmp_path: Path):
        q = JobQueue(db_path=tmp_path / "test_jobs.db")
        job = q.enqueue("shorts", {"asset": "bad.png"}, max_retries=1)
        dequeued = q.dequeue()
        assert dequeued is not None

        # First failure -> rescheduled to PENDING
        q.fail_job(dequeued.id, "FFmpeg error 1")
        retried = q.get_job(dequeued.id)
        assert retried is not None
        assert retried.status == "PENDING"
        assert retried.retry_count == 1

        # Second dequeue & second failure -> marks FAILED
        dequeued2 = q.dequeue()
        assert dequeued2 is not None
        q.fail_job(dequeued2.id, "FFmpeg error 2")
        failed = q.get_job(dequeued2.id)
        assert failed is not None
        assert failed.status == "FAILED"
        assert failed.retry_count == 2

    def test_restart_recovery(self, tmp_path: Path):
        db_path = tmp_path / "test_recovery.db"
        q1 = JobQueue(db_path=db_path)
        job = q1.enqueue("shorts", {"asset": "interrupted.png"})
        d = q1.dequeue()
        assert d is not None
        assert d.status == "PROCESSING"

        # Simulate crash: recreate queue instance
        q2 = JobQueue(db_path=db_path)
        recovered = q2.get_job(d.id)
        assert recovered is not None
        assert recovered.status == "PENDING"
