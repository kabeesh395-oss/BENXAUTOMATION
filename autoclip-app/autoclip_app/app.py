from __future__ import annotations

import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yt_dlp
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import process
from .youtube import connect_youtube, upload_public_video, youtube_status

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
STATIC = Path(__file__).parent / "static"
SCHEDULE_DB = DATA / "autoclip.sqlite3"
IST = timezone(timedelta(hours=5, minutes=30))
for folder in (UPLOADS, OUTPUTS):
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AutoClip AI", version="0.2.0")
app.mount("/outputs", StaticFiles(directory=OUTPUTS), name="outputs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
jobs: dict[str, dict[str, Any]] = {}
lock = threading.Lock()
_scheduler_started = False


@contextmanager
def _db():
    DATA.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(SCHEDULE_DB, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            run_at TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT 'small',
            clip_count INTEGER NOT NULL DEFAULT 5,
            status TEXT NOT NULL DEFAULT 'queued',
            job_id TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        )
    """)
        connection.commit()
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _now_ist() -> datetime:
    return datetime.now(IST)


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "AutoClip AI", "mode": "local-first"}


@app.get("/api/youtube/status")
def get_youtube_status():
    return youtube_status()


@app.post("/api/youtube/connect")
def youtube_connect():
    try:
        return connect_youtube()
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


def _run_job(job_id: str, source: Path, language: str | None, model: str,
             count: int, publish_public: bool = False):
    try:
        with lock:
            jobs[job_id]["status"] = "transcribing"
            jobs[job_id]["message"] = "Transcribing locally with Faster-Whisper"
        clips = process(source, OUTPUTS / job_id, language, model, count)
        if publish_public:
            if not youtube_status()["connected"]:
                raise RuntimeError("YouTube is not connected. Connect your channel before processing public uploads.")
            for index, clip in enumerate(clips, 1):
                with lock:
                    jobs[job_id]["status"] = "uploading"
                    jobs[job_id]["message"] = f"Uploading public Short {index}/{len(clips)} to YouTube"
                video_path = OUTPUTS / job_id / Path(clip["video_url"]).name
                uploaded = upload_public_video(
                    video_path,
                    clip.get("youtube_title", clip["title"]),
                    clip.get("youtube_description", clip["reason"]),
                    clip.get("youtube_tags", []),
                )
                clip.update(youtube_id=uploaded["video_id"], youtube_url=uploaded["url"],
                            upload_status="public")
        with lock:
            jobs[job_id].update(status="completed",
                message=("All clips processed and published publicly." if publish_public else "Clips ready"),
                clips=clips)
    except Exception as exc:
        with lock:
            jobs[job_id].update(status="failed", message=str(exc))


def _download_url(job_id: str, url: str, mode: str) -> Path:
    target = UPLOADS / job_id
    target.mkdir(parents=True, exist_ok=True)
    options = {"outtmpl": str(target / "%(title).80s-%(id)s.%(ext)s"),
               "format": "bv*+ba/b", "merge_output_format": "mp4",
               "noplaylist": True, "quiet": True, "no_warnings": True}
    if mode == "live":
        options["live_from_start"] = True
        options["wait_for_video"] = 10
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        filename = Path(downloader.prepare_filename(info))
    if not filename.exists():
        merged = filename.with_suffix(".mp4")
        if merged.exists():
            filename = merged
    if not filename.exists():
        matches = [p for p in target.glob("*")
                   if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
        if not matches:
            raise RuntimeError("Downloader finished but no video file was found.")
        filename = matches[0]
    return filename


@app.post("/api/jobs/upload")
async def upload_video(background: BackgroundTasks, file: UploadFile = File(...),
                       language: str = Form(""), model: str = Form("small"),
                       count: int = Form(5), publish_public: bool = Form(False)):
    if publish_public and not youtube_status()["connected"]:
        raise HTTPException(400, "Connect YouTube first before enabling public upload.")
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}:
        raise HTTPException(400, "Unsupported video format.")
    job_id = uuid.uuid4().hex[:12]
    destination = UPLOADS / f"{job_id}{suffix}"
    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    jobs[job_id] = {"id": job_id, "status": "queued", "message": "Video uploaded",
                    "source": file.filename, "clips": []}
    background.add_task(_run_job, job_id, destination, language or None, model,
                        max(1, min(count, 10)), publish_public)
    return jobs[job_id]


@app.post("/api/jobs/url")
def create_url_job(background: BackgroundTasks, url: str = Form(...),
                   mode: str = Form("vod"), language: str = Form(""),
                   model: str = Form("small"), count: int = Form(5),
                   publish_public: bool = Form(True)):
    if not url.startswith(("https://", "http://")):
        raise HTTPException(400, "Enter a valid http(s) video URL.")
    if mode not in {"vod", "live"}:
        raise HTTPException(400, "Mode must be vod or live.")
    if publish_public and not youtube_status()["connected"]:
        raise HTTPException(400, "Connect YouTube first. Public upload is enabled for this job.")
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"id": job_id, "status": "downloading",
                    "message": "Downloading source", "source": url, "clips": []}

    def download_then_process():
        try:
            with lock:
                jobs[job_id]["message"] = "Downloading / recording source"
            source = _download_url(job_id, url, mode)
            with lock:
                jobs[job_id]["message"] = "Source ready; starting AI analysis"
            _run_job(job_id, source, language or None, model,
                     max(1, min(count, 10)), publish_public)
        except Exception as exc:
            with lock:
                jobs[job_id].update(status="failed", message=str(exc))

    background.add_task(download_then_process)
    return jobs[job_id]


@app.post("/api/schedule")
def add_scheduled_source(url: str = Form(...), run_at: str = Form(...),
                         language: str = Form(""), model: str = Form("small"),
                         count: int = Form(5)):
    if not youtube_status()["connected"]:
        raise HTTPException(400, "Connect YouTube before scheduling automatic public uploads.")
    if not url.startswith(("https://", "http://")):
        raise HTTPException(400, "Enter a valid http(s) video URL.")
    try:
        scheduled = datetime.fromisoformat(run_at)
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=IST)
        scheduled = scheduled.astimezone(IST)
    except ValueError as exc:
        raise HTTPException(400, "Invalid schedule date/time.") from exc
    if scheduled <= _now_ist():
        raise HTTPException(400, "Choose a future date and time.")
    with _db() as conn:
        day = scheduled.date().isoformat()
        existing = conn.execute(
            "SELECT id FROM scheduled_sources WHERE substr(run_at,1,10)=? "
            "AND status IN ('queued','running','completed') LIMIT 1", (day,)
        ).fetchone()
        if existing:
            raise HTTPException(409, f"A source is already queued or processed for {day}.")
        cursor = conn.execute(
            "INSERT INTO scheduled_sources(url,run_at,language,model,clip_count,status,created_at) "
            "VALUES(?,?,?,?,?,'queued',?)",
            (url, scheduled.isoformat(), language, model, max(1, min(count, 5)), _now_ist().isoformat())
        )
        item_id = cursor.lastrowid
    return {"id": item_id, "status": "queued", "run_at": scheduled.isoformat(),
            "message": "One source queued. AutoClip will create and publish up to five public Shorts."}


@app.get("/api/schedule")
def list_scheduled_sources():
    with _db() as conn:
        rows = conn.execute(
            "SELECT id,url,run_at,status,job_id,error FROM scheduled_sources ORDER BY run_at DESC LIMIT 30"
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


def _scheduled_worker():
    while True:
        try:
            with _db() as conn:
                row = conn.execute(
                    "SELECT * FROM scheduled_sources WHERE status='queued' AND run_at<=? "
                    "ORDER BY run_at LIMIT 1", (_now_ist().isoformat(),)
                ).fetchone()
                if row:
                    conn.execute("UPDATE scheduled_sources SET status='running' WHERE id=? AND status='queued'",
                                 (row["id"],))
                    conn.commit()
            if row:
                job_id = uuid.uuid4().hex[:12]
                jobs[job_id] = {"id": job_id, "status": "downloading",
                    "message": "Scheduled source download started", "source": row["url"], "clips": []}
                with _db() as conn:
                    conn.execute("UPDATE scheduled_sources SET job_id=? WHERE id=?", (job_id, row["id"]))
                    conn.commit()
                try:
                    source = _download_url(job_id, row["url"], "vod")
                    _run_job(job_id, source, row["language"] or None, row["model"],
                             row["clip_count"], True)
                    state = jobs[job_id]
                    final_status = "completed" if state["status"] == "completed" else "failed"
                    with _db() as conn:
                        conn.execute("UPDATE scheduled_sources SET status=?,error=? WHERE id=?",
                            (final_status, "" if final_status == "completed" else state["message"], row["id"]))
                        conn.commit()
                except Exception as exc:
                    with _db() as conn:
                        conn.execute("UPDATE scheduled_sources SET status='failed',error=? WHERE id=?",
                                     (str(exc), row["id"]))
                        conn.commit()
        except Exception:
            pass
        time.sleep(15)


@app.on_event("startup")
def start_scheduler():
    global _scheduler_started
    with _db():
        pass
    if not _scheduler_started:
        threading.Thread(target=_scheduled_worker, name="autoclip-scheduler", daemon=True).start()
        _scheduler_started = True


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found. Jobs are stored in memory until the app restarts.")
        return dict(job)
