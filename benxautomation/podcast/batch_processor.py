"""Batch processing and queue management for Podcast-to-Shorts.

Processes multiple podcast or livestream replay sources in a resilient,
fault-tolerant pipeline with restart recovery and duplicate prevention.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from benxautomation.logger import get_logger
from benxautomation.podcast.errors import PodcastError
from benxautomation.podcast.models import (
    ClipMetadata,
    HighlightCandidate,
    PodcastInput,
    PodcastPipelineConfig,
    PodcastTranscript,
    RightsDeclaration,
    SubtitleStyle,
)
from benxautomation.podcast.pipeline import PodcastToShortsPipeline

log = get_logger(__name__)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", slug)[:40] or "source"


@dataclass
class BatchJob:
    """A batch processing job tracking source, state, and outputs."""
    id: int
    source: str
    status: str  # "PENDING", "PROCESSING", "COMPLETED", "FAILED"
    clips_target: int
    language: str
    rights_declaration: dict[str, Any]
    output_dir: str
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    rendered_clips: list[str] = None

    def __post_init__(self):
        if self.rendered_clips is None:
            self.rendered_clips = []


class PodcastBatchProcessor:
    """Manages batch queues, resumable execution, and isolated outputs."""

    def __init__(
        self,
        db_path: Path | str = "output/podcast_batch_jobs.db",
        pipeline: Optional[PodcastToShortsPipeline] = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.pipeline = pipeline or PodcastToShortsPipeline()
        self._lock = threading.Lock()
        self._init_db()
        self.recover_interrupted_jobs()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    clips_target INTEGER NOT NULL DEFAULT 3,
                    language TEXT NOT NULL DEFAULT 'en',
                    rights_declaration TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    rendered_clips TEXT NOT NULL DEFAULT '[]',
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def recover_interrupted_jobs(self) -> int:
        """Reset stuck PROCESSING jobs back to PENDING after a system restart."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE batch_jobs SET status = 'PENDING', updated_at = ? WHERE status = 'PROCESSING'",
                (datetime.now(timezone.utc).isoformat(),)
            )
            count = cursor.rowcount
            conn.commit()
            if count > 0:
                log.info("Recovered %d interrupted podcast batch jobs back to PENDING", count)
            return count

    def add_job(
        self,
        source: str,
        rights_declaration: RightsDeclaration,
        *,
        clips_target: int = 3,
        language: str = "en",
    ) -> int:
        """Add a source to the batch processing queue."""
        now = datetime.now(timezone.utc).isoformat()
        source_slug = _slugify(Path(source).stem if "http" not in source else source.split("=")[-1])
        output_dir = str(self.pipeline.output_dir / source_slug)

        with self._lock, self._get_connection() as conn:
            # Check existing
            row = conn.execute("SELECT id, status FROM batch_jobs WHERE source = ?", (source,)).fetchone()
            if row:
                if row["status"] in ("PENDING", "PROCESSING"):
                    log.info("Source '%s' already in queue (job #%d, status: %s)", source, row["id"], row["status"])
                    return row["id"]
                elif row["status"] == "COMPLETED":
                    log.info("Source '%s' already completed in job #%d", source, row["id"])
                    return row["id"]
                else:  # FAILED -> reset to PENDING for retry
                    conn.execute(
                        "UPDATE batch_jobs SET status = 'PENDING', error_message = NULL, updated_at = ? WHERE id = ?",
                        (now, row["id"])
                    )
                    conn.commit()
                    return row["id"]

            cursor = conn.execute(
                """
                INSERT INTO batch_jobs (
                    source, status, clips_target, language, rights_declaration,
                    output_dir, rendered_clips, created_at, updated_at
                ) VALUES (?, 'PENDING', ?, ?, ?, ?, '[]', ?, ?)
                """,
                (
                    source,
                    clips_target,
                    language,
                    json.dumps(rights_declaration.to_dict()),
                    output_dir,
                    now,
                    now,
                )
            )
            conn.commit()
            return cursor.lastrowid

    def list_jobs(self, status: Optional[str] = None) -> list[BatchJob]:
        """List jobs filtered by status."""
        query = "SELECT * FROM batch_jobs"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY id ASC"

        with self._lock, self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            jobs = []
            for r in rows:
                jobs.append(
                    BatchJob(
                        id=r["id"],
                        source=r["source"],
                        status=r["status"],
                        clips_target=r["clips_target"],
                        language=r["language"],
                        rights_declaration=json.loads(r["rights_declaration"]),
                        output_dir=r["output_dir"],
                        rendered_clips=json.loads(r["rendered_clips"]),
                        error_message=r["error_message"],
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                    )
                )
            return jobs

    def process_next_job(
        self,
        *,
        upload_private: bool = False,
        reframing_mode: str = "blur_pad",
    ) -> Optional[dict[str, Any]]:
        """Fetch and execute the next pending job."""
        job_id = None
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM batch_jobs WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            job_id = row["id"]
            conn.execute(
                "UPDATE batch_jobs SET status = 'PROCESSING', updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), job_id)
            )
            conn.commit()

        # Execute outside lock
        job = self.get_job(job_id)
        if not job:
            return None

        log.info("Batch processing job #%d: source='%s'", job.id, job.source)
        try:
            rights_decl = RightsDeclaration(**job.rights_declaration)
            self.pipeline.rights_reviewer.assert_publishing_allowed(rights_decl)

            # 1. Ingest
            inp = self.pipeline.ingest(job.source)

            # 2. Transcribe
            transcript = self.pipeline.transcribe(inp, language=job.language)

            # 3. Detect highlights
            candidates = self.pipeline.detect_highlights(transcript, max_candidates=job.clips_target)

            # 4. Render clips
            rendered_paths: list[str] = []
            source_dir = Path(job.output_dir)
            source_dir.mkdir(parents=True, exist_ok=True)

            for cand in candidates:
                cand.approved = True
                clip_dir = source_dir / cand.clip_id
                clip_mp4 = clip_dir / f"{cand.clip_id}.mp4"

                # Check if already rendered to avoid duplicate work
                if clip_mp4.is_file() and clip_mp4.stat().st_size > 0:
                    log.info("Clip '%s' already exists for job #%d — skipping duplicate render", cand.clip_id, job.id)
                    rendered_paths.append(str(clip_mp4))
                    continue

                meta = self.pipeline.render_clip(
                    podcast_input=inp,
                    transcript=transcript,
                    candidate=cand,
                    rights_declaration=rights_decl,
                    reframing_mode=reframing_mode,
                    clip_output_dir=source_dir,
                )
                rendered_paths.append(meta.video_path)

                if upload_private:
                    self.pipeline.upload_to_youtube(meta, privacy_status="private", user_approved=True)

            # Mark COMPLETED
            now = datetime.now(timezone.utc).isoformat()
            with self._lock, self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE batch_jobs SET
                        status = 'COMPLETED',
                        rendered_clips = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (json.dumps(rendered_paths), now, job.id)
                )
                conn.commit()

            return {
                "job_id": job.id,
                "status": "COMPLETED",
                "source": job.source,
                "rendered_clips": rendered_paths,
            }

        except Exception as exc:
            log.error("Batch job #%d failed: %s", job.id, exc)
            now = datetime.now(timezone.utc).isoformat()
            with self._lock, self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE batch_jobs SET
                        status = 'FAILED',
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (str(exc), now, job.id)
                )
                conn.commit()
            return {
                "job_id": job.id,
                "status": "FAILED",
                "error": str(exc),
            }

    def process_all_pending(
        self,
        *,
        upload_private: bool = False,
        reframing_mode: str = "blur_pad",
    ) -> list[dict[str, Any]]:
        """Run through all pending jobs in the queue sequentially."""
        results = []
        while True:
            res = self.process_next_job(upload_private=upload_private, reframing_mode=reframing_mode)
            if res is None:
                break
            results.append(res)
        return results

    def get_job(self, job_id: int) -> Optional[BatchJob]:
        with self._lock, self._get_connection() as conn:
            r = conn.execute("SELECT * FROM batch_jobs WHERE id = ?", (job_id,)).fetchone()
            if not r:
                return None
            return BatchJob(
                id=r["id"],
                source=r["source"],
                status=r["status"],
                clips_target=r["clips_target"],
                language=r["language"],
                rights_declaration=json.loads(r["rights_declaration"]),
                output_dir=r["output_dir"],
                rendered_clips=json.loads(r["rendered_clips"]),
                error_message=r["error_message"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def get_summary(self) -> dict[str, int]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute("SELECT status, count(*) as cnt FROM batch_jobs GROUP BY status").fetchall()
            summary = {"PENDING": 0, "PROCESSING": 0, "COMPLETED": 0, "FAILED": 0}
            for r in rows:
                summary[r["status"]] = r["cnt"]
            return summary
