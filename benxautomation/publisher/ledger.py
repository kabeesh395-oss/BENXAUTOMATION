"""Persistent upload ledger for preventing duplicate YouTube uploads and tracking resumable sessions."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from benxautomation.logger import get_logger

log = get_logger(__name__)

DEFAULT_LEDGER_DIR = Path.home() / ".benxautomation"
DEFAULT_LEDGER_FILE = DEFAULT_LEDGER_DIR / "upload_ledger.sqlite"


@dataclass
class UploadRecord:
    """A record in the upload ledger."""
    id: int
    content_hash: str
    file_path: str
    file_size: int
    title: str
    privacy_status: str
    status: str  # "IN_PROGRESS", "COMPLETED", "FAILED"
    video_id: Optional[str] = None
    channel_id: Optional[str] = None
    session_uri: Optional[str] = None
    bytes_uploaded: int = 0
    error_message: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class UploadLedger:
    """Thread-safe, SQLite-backed persistent ledger for YouTube video uploads."""

    def __init__(self, db_path: Path | str = DEFAULT_LEDGER_FILE):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS upload_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    video_id TEXT,
                    channel_id TEXT,
                    privacy_status TEXT NOT NULL,
                    session_uri TEXT,
                    bytes_uploaded INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_hash ON upload_ledger(content_hash, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_video_id ON upload_ledger(video_id)")
            conn.commit()

    @staticmethod
    def compute_file_hash(file_path: Path | str) -> str:
        """Compute SHA-256 digest of a video file in chunks."""
        path = Path(file_path)
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    def get_completed_upload(self, content_hash: str) -> Optional[UploadRecord]:
        """Find an already completed upload matching this file's content hash."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM upload_ledger
                WHERE content_hash = ? AND status = 'COMPLETED' AND video_id IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (content_hash,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
            return None

    def get_active_session(self, content_hash: str) -> Optional[UploadRecord]:
        """Find an active IN_PROGRESS resumable upload session matching this file."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM upload_ledger
                WHERE content_hash = ? AND status = 'IN_PROGRESS' AND session_uri IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (content_hash,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
            return None

    def get_record_by_video_id(self, video_id: str) -> Optional[UploadRecord]:
        """Find upload record by YouTube video ID."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM upload_ledger WHERE video_id = ? ORDER BY id DESC LIMIT 1",
                (video_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
            return None

    def record_start(
        self,
        content_hash: str,
        file_path: Path | str,
        file_size: int,
        title: str,
        privacy_status: str,
        session_uri: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> UploadRecord:
        """Record the initiation of a resumable upload session."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO upload_ledger (
                    content_hash, file_path, file_size, title, privacy_status,
                    session_uri, bytes_uploaded, status, channel_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 'IN_PROGRESS', ?, ?, ?)
                """,
                (
                    content_hash,
                    str(file_path),
                    file_size,
                    title,
                    privacy_status,
                    session_uri,
                    channel_id,
                    now,
                    now,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid

        return self.get_record_by_id(record_id)  # type: ignore[return-value]

    def update_progress(
        self,
        record_id: int,
        bytes_uploaded: int,
        session_uri: Optional[str] = None,
    ) -> None:
        """Update bytes uploaded progress for a resumable upload."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            if session_uri:
                conn.execute(
                    """
                    UPDATE upload_ledger
                    SET bytes_uploaded = ?, session_uri = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (bytes_uploaded, session_uri, now, record_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE upload_ledger
                    SET bytes_uploaded = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (bytes_uploaded, now, record_id),
                )
            conn.commit()

    def record_complete(
        self,
        record_id: int,
        video_id: str,
        privacy_status: str = "private",
    ) -> UploadRecord:
        """Mark an upload as COMPLETED with the verified YouTube video ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE upload_ledger
                SET status = 'COMPLETED', video_id = ?, privacy_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (video_id, privacy_status, now, record_id),
            )
            conn.commit()
        log.info("Ledger recorded COMPLETED upload ID=%d -> video_id=%s", record_id, video_id)
        return self.get_record_by_id(record_id)  # type: ignore[return-value]

    def record_failure(self, record_id: int, error_message: str) -> None:
        """Mark an upload attempt as FAILED."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE upload_ledger
                SET status = 'FAILED', error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (error_message, now, record_id),
            )
            conn.commit()
        log.warning("Ledger recorded FAILED upload ID=%d: %s", record_id, error_message)

    def record_completed_upload(
        self,
        content_hash: str,
        video_id: str,
        title: str,
        privacy_status: str = "private",
        file_path: str = "",
        file_size: int = 0,
        channel_id: Optional[str] = None,
    ) -> UploadRecord:
        """Directly register a known existing completed upload (e.g. verified acceptance test)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO upload_ledger (
                    content_hash, file_path, file_size, title, video_id,
                    privacy_status, bytes_uploaded, status, channel_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?, ?)
                """,
                (
                    content_hash,
                    str(file_path),
                    file_size,
                    title,
                    video_id,
                    privacy_status,
                    file_size,
                    channel_id,
                    now,
                    now,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
        return self.get_record_by_id(record_id)  # type: ignore[return-value]

    def get_record_by_id(self, record_id: int) -> Optional[UploadRecord]:
        """Fetch record by internal ID."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM upload_ledger WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
            return None

    def list_records(self, limit: int = 50) -> list[UploadRecord]:
        """List most recent upload records."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM upload_ledger ORDER BY id DESC LIMIT ?", (limit,))
            return [self._row_to_record(r) for r in cursor.fetchall()]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> UploadRecord:
        return UploadRecord(
            id=row["id"],
            content_hash=row["content_hash"],
            file_path=row["file_path"],
            file_size=row["file_size"],
            title=row["title"],
            privacy_status=row["privacy_status"],
            status=row["status"],
            video_id=row["video_id"],
            channel_id=row["channel_id"],
            session_uri=row["session_uri"],
            bytes_uploaded=row["bytes_uploaded"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
