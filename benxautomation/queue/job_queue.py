"""Persistent SQLite-backed job queue for continuous video automation.

Features:
- Thread-safe transactions
- Restart recovery (stuck PROCESSING jobs are recovered to PENDING)
- Automatic retry tracking with configurable maximum retries
- Support for both Shorts and Long-form formats
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from benxautomation.errors import BenxError
from benxautomation.logger import get_logger

log = get_logger(__name__)


class QueueError(BenxError):
    """Raised on queue operation errors."""


class DuplicateJobError(QueueError):
    """Raised when an identical job is already pending or processing in the queue."""


@dataclass
class Job:
    """A unit of work in the queue."""
    id: int
    job_type: str  # "shorts", "longform", "both"
    payload: dict[str, Any]
    status: str    # "PENDING", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED"
    retry_count: int
    max_retries: int
    created_at: str
    updated_at: str
    deduplication_key: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[dict[str, Any]] = None


class JobQueue:
    """SQLite-backed persistent queue with restart recovery and retries."""

    def __init__(self, db_path: Path | str = "jobs.db"):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()
        self.recover_interrupted_jobs()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    deduplication_key TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT,
                    result TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dedup ON jobs(deduplication_key, status)")

            # Ensure deduplication_key exists in existing schemas
            cursor = conn.execute("PRAGMA table_info(jobs)")
            cols = [col["name"] for col in cursor.fetchall()]
            if "deduplication_key" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN deduplication_key TEXT")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_dedup ON jobs(deduplication_key, status)")

            conn.commit()

    def recover_interrupted_jobs(self) -> int:
        """Reset any jobs left in PROCESSING back to PENDING on startup."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = 'PENDING', updated_at = ?
                WHERE status = 'PROCESSING'
                """,
                (now,),
            )
            count = cursor.rowcount
            conn.commit()
            if count > 0:
                log.warning("Recovered %d interrupted jobs from PROCESSING to PENDING.", count)
            return count

    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any],
        *,
        max_retries: int = 3,
        deduplication_key: Optional[str] = None,
        prevent_duplicates: bool = True,
    ) -> Job:
        """Add a new job to the queue, preventing duplicates if key is given."""
        now = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload, default=str)

        with self._lock, self._get_connection() as conn:
            if deduplication_key and prevent_duplicates:
                cursor = conn.execute(
                    """
                    SELECT id FROM jobs
                    WHERE deduplication_key = ? AND status IN ('PENDING', 'PROCESSING')
                    LIMIT 1
                    """,
                    (deduplication_key,),
                )
                existing = cursor.fetchone()
                if existing:
                    log.warning(
                        "Duplicate job rejected: key '%s' matches active job %d",
                        deduplication_key,
                        existing["id"],
                    )
                    raise DuplicateJobError(
                        f"Job with deduplication key '{deduplication_key}' is already active (id={existing['id']})"
                    )

            cursor = conn.execute(
                """
                INSERT INTO jobs (job_type, payload, status, retry_count, max_retries, deduplication_key, created_at, updated_at)
                VALUES (?, ?, 'PENDING', 0, ?, ?, ?, ?)
                """,
                (job_type, payload_json, max_retries, deduplication_key, now, now),
            )
            conn.commit()
            job_id = cursor.lastrowid

        return self.get_job(job_id)  # type: ignore[return-value]

    def dequeue(self) -> Optional[Job]:
        """Atomically fetch the next PENDING job and mark it PROCESSING."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            # Select oldest pending job
            cursor = conn.execute(
                """
                SELECT id FROM jobs
                WHERE status = 'PENDING'
                ORDER BY id ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None

            job_id = row["id"]
            conn.execute(
                """
                UPDATE jobs
                SET status = 'PROCESSING', updated_at = ?
                WHERE id = ? AND status = 'PENDING'
                """,
                (now, job_id),
            )
            conn.commit()

        return self.get_job(job_id)

    def complete_job(self, job_id: int, result: dict[str, Any]) -> None:
        """Mark a job as COMPLETED with its result."""
        now = datetime.now(timezone.utc).isoformat()
        result_json = json.dumps(result, default=str)
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'COMPLETED', result = ?, updated_at = ?
                WHERE id = ?
                """,
                (result_json, now, job_id),
            )
            conn.commit()
        log.info("Job %d completed successfully.", job_id)

    def fail_job(self, job_id: int, error_message: str) -> None:
        """Handle job failure, triggering retry if attempts remain."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT retry_count, max_retries FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return

            retries = row["retry_count"] + 1
            max_retries = row["max_retries"]

            if retries <= max_retries:
                # Reschedule retry
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'PENDING', retry_count = ?, error_message = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (retries, error_message, now, job_id),
                )
                log.warning("Job %d failed (attempt %d/%d). Rescheduled for retry.", job_id, retries, max_retries)
            else:
                # Exceeded retries -> mark FAILED
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'FAILED', retry_count = ?, error_message = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (retries, error_message, now, job_id),
                )
                log.error("Job %d failed permanently after %d retries: %s", job_id, max_retries, error_message)

            conn.commit()

    def get_job(self, job_id: int) -> Optional[Job]:
        """Fetch job by ID."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_job(row)

    def count_by_status(self) -> dict[str, int]:
        """Return counts of jobs in each status."""
        counts = {"PENDING": 0, "PROCESSING": 0, "COMPLETED": 0, "FAILED": 0, "CANCELLED": 0}
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT status, count(*) as cnt FROM jobs GROUP BY status")
            for row in cursor.fetchall():
                counts[row["status"]] = row["cnt"]
        return counts

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            job_type=row["job_type"],
            payload=json.loads(row["payload"]),
            status=row["status"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deduplication_key=row["deduplication_key"] if "deduplication_key" in row.keys() else None,
            error_message=row["error_message"],
            result=json.loads(row["result"]) if row["result"] else None,
        )
