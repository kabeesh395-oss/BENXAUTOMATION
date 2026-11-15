from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

import yt_dlp
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import process

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
STATIC = Path(__file__).parent / "static"
for folder in (UPLOADS, OUTPUTS):
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AutoClip AI", version="0.1.0")
app.mount("/outputs", StaticFiles(directory=OUTPUTS), name="outputs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
jobs: dict[str, dict[str, Any]] = {}
lock = threading.Lock()


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "AutoClip AI", "mode": "local-first"}


def _run_job(job_id: str, source: Path, language: str | None, model: str, count: int):
    try:
        with lock:
            jobs[job_id]["status"] = "transcribing"
            jobs[job_id]["message"] = "Transcribing locally with Faster-Whisper"
        clips = process(source, OUTPUTS / job_id, language, model, count)
        with lock:
            jobs[job_id].update(status="completed", message="Clips ready", clips=clips)
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
                       count: int = Form(5)):
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}:
        raise HTTPException(400, "Unsupported video format.")
    job_id = uuid.uuid4().hex[:12]
    destination = UPLOADS / f"{job_id}{suffix}"
    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    jobs[job_id] = {"id": job_id, "status": "queued", "message": "Video uploaded",
                    "source": file.filename, "clips": []}
    background.add_task(_run_job, job_id, destination, language or None, model, max(1, min(count, 10)))
    return jobs[job_id]


@app.post("/api/jobs/url")
def create_url_job(background: BackgroundTasks, url: str = Form(...),
                   mode: str = Form("vod"), language: str = Form(""),
                   model: str = Form("small"), count: int = Form(5)):
    if not url.startswith(("https://", "http://")):
        raise HTTPException(400, "Enter a valid http(s) video URL.")
    if mode not in {"vod", "live"}:
        raise HTTPException(400, "Mode must be vod or live.")
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"id": job_id, "status": "downloading",
                    "message": "Connecting to source", "source": url, "clips": []}

    def download_then_process():
        try:
            with lock:
                jobs[job_id]["message"] = "Downloading / recording source"
            source = _download_url(job_id, url, mode)
            with lock:
                jobs[job_id]["message"] = "Source ready; starting AI analysis"
            _run_job(job_id, source, language or None, model, max(1, min(count, 10)))
        except Exception as exc:
            with lock:
                jobs[job_id].update(status="failed", message=str(exc))

    background.add_task(download_then_process)
    return jobs[job_id]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found. Jobs are stored in memory until the app restarts.")
        return dict(job)
