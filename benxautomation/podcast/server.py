"""FastAPI Web Dashboard Server for Podcast-to-Shorts Automation.

Provides the 8-step production pipeline:
Paste Link -> Analyze -> Select Highlights -> Edit Captions ->
Rights Review -> Render -> Preview -> Approve -> Upload.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from benxautomation.podcast.models import (
    HighlightCandidate,
    PodcastInput,
    PodcastPipelineConfig,
    PodcastTranscript,
    RightsDeclaration,
    SubtitleStyle,
)
from benxautomation.podcast.pipeline import PodcastToShortsPipeline
from benxautomation.renderer.ffmpeg_utils import ffmpeg_is_available, ffprobe_is_available

# Logger & in-memory log buffer for genuine live logging
pipeline_logs: list[dict[str, str]] = []


class InMemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        pipeline_logs.append({
            "level": record.levelname,
            "message": msg,
            "time": record.asctime if hasattr(record, "asctime") else "",
        })
        if len(pipeline_logs) > 300:
            pipeline_logs.pop(0)


logger = logging.getLogger("benxautomation")
handler = InMemoryLogHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(handler)

app = FastAPI(title="BENX Podcast-to-Shorts Studio", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = PodcastToShortsPipeline()

# In-memory session state for dashboard
session_state: dict[str, Any] = {
    "current_input": None,
    "current_transcript": None,
    "candidates": [],
    "selected_candidate": None,
    "rendered_metadata": {},
}

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# Request schemas
class IngestRequest(BaseModel):
    source: str  # URL or file path


class AnalyzeRequest(BaseModel):
    language: str = "en"
    max_candidates: int = 4
    min_duration: float = 15.0
    max_duration: float = 60.0


class RenderRequest(BaseModel):
    clip_id: str
    start_seconds: float
    end_seconds: float
    hook: str
    summary: str
    reframing_mode: str = "blur_pad"
    subtitle_style: dict[str, Any] = {}
    rights_declaration: dict[str, Any]


class UploadRequest(BaseModel):
    clip_id: str
    privacy_status: str = "private"
    user_approved: bool = True


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>BENX Podcast Studio - Dashboard Initializing...</h1>")


@app.get("/api/status")
def get_system_status() -> dict[str, Any]:
    ffmpeg_ok = ffmpeg_is_available()
    ffprobe_ok = ffprobe_is_available()

    oauth_status = "NOT_CONFIGURED"
    channel_name = None
    try:
        if pipeline.publisher and pipeline.publisher.oauth_manager:
            channel = pipeline.publisher.oauth_manager.verify_channel()
            oauth_status = "CONNECTED"
            channel_name = f"{channel.title} (@{channel.custom_url})"
    except Exception as e:
        oauth_status = f"ERROR: {str(e)[:50]}"

    return {
        "ffmpeg_available": ffmpeg_ok,
        "ffprobe_available": ffprobe_ok,
        "youtube_oauth_status": oauth_status,
        "youtube_channel": channel_name,
        "output_dir": str(pipeline.output_dir.resolve()),
        "has_active_input": session_state["current_input"] is not None,
        "active_title": session_state["current_input"].title if session_state["current_input"] else None,
    }


@app.get("/api/logs")
def get_logs() -> list[dict[str, str]]:
    return pipeline_logs


@app.post("/api/ingest")
def api_ingest(req: IngestRequest) -> dict[str, Any]:
    try:
        inp = pipeline.ingest(req.source)
        session_state["current_input"] = inp
        session_state["current_transcript"] = None
        session_state["candidates"] = []
        return {"status": "SUCCESS", "input": inp.to_dict()}
    except Exception as e:
        logger.error("Ingest error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze")
def api_analyze(req: AnalyzeRequest) -> dict[str, Any]:
    inp: Optional[PodcastInput] = session_state.get("current_input")
    if not inp:
        raise HTTPException(status_code=400, detail="No active input ingested. Ingest a URL or file first.")

    try:
        pipeline.config.min_clip_duration = req.min_duration
        pipeline.config.max_clip_duration = req.max_duration
        pipeline.highlight_detector.min_clip_duration = req.min_duration
        pipeline.highlight_detector.max_clip_duration = req.max_duration

        transcript = pipeline.transcribe(inp, language=req.language)
        session_state["current_transcript"] = transcript

        candidates = pipeline.detect_highlights(transcript, max_candidates=req.max_candidates)
        session_state["candidates"] = candidates

        return {
            "status": "SUCCESS",
            "total_segments": len(transcript.segments),
            "transcript_duration": transcript.total_duration,
            "candidates": [c.to_dict() for c in candidates],
        }
    except Exception as e:
        logger.error("Analysis error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/rights/verify")
def api_verify_rights(declaration: RightsDeclaration) -> dict[str, Any]:
    valid, errors = pipeline.verify_rights(declaration)
    return {
        "valid": valid,
        "errors": errors,
        "disclaimer": pipeline.rights_reviewer.get_disclaimer(),
    }


@app.post("/api/render")
def api_render(req: RenderRequest) -> dict[str, Any]:
    inp: Optional[PodcastInput] = session_state.get("current_input")
    transcript: Optional[PodcastTranscript] = session_state.get("current_transcript")
    if not inp or not transcript:
        raise HTTPException(status_code=400, detail="Must ingest and analyze podcast before rendering.")

    rights_decl = RightsDeclaration(**req.rights_declaration)
    valid, errors = pipeline.verify_rights(rights_decl)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Rights verification failed: {'; '.join(errors)}")

    cand = HighlightCandidate(
        clip_id=req.clip_id,
        start_seconds=req.start_seconds,
        end_seconds=req.end_seconds,
        duration=round(req.end_seconds - req.start_seconds, 2),
        hook=req.hook,
        reason="User-configured highlight",
        score=95.0,
        summary=req.summary,
        transcript_text="",
        approved=True,
    )

    style = SubtitleStyle(**req.subtitle_style) if req.subtitle_style else SubtitleStyle()

    try:
        meta = pipeline.render_clip(
            podcast_input=inp,
            transcript=transcript,
            candidate=cand,
            rights_declaration=rights_decl,
            style=style,
            reframing_mode=req.reframing_mode,
        )
        session_state["rendered_metadata"][req.clip_id] = meta
        return {"status": "SUCCESS", "metadata": meta.to_dict()}
    except Exception as e:
        logger.error("Render error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/clips/{clip_id}/preview")
def api_preview_clip(clip_id: str) -> FileResponse:
    meta = session_state["rendered_metadata"].get(clip_id)
    if not meta:
        # Check output directory
        target = pipeline.output_dir / clip_id / f"{clip_id}.mp4"
        if target.is_file():
            return FileResponse(target, media_type="video/mp4")
        raise HTTPException(status_code=404, detail=f"Rendered clip '{clip_id}' not found.")
    return FileResponse(Path(meta.video_path), media_type="video/mp4")


@app.get("/api/clips/{clip_id}/thumbnail")
def api_preview_thumbnail(clip_id: str) -> FileResponse:
    meta = session_state["rendered_metadata"].get(clip_id)
    if meta and Path(meta.thumbnail_path).is_file():
        return FileResponse(Path(meta.thumbnail_path), media_type="image/jpeg")
    target = pipeline.output_dir / clip_id / f"{clip_id}_thumbnail.jpg"
    if target.is_file():
        return FileResponse(target, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Thumbnail not found.")


@app.post("/api/upload")
def api_upload(req: UploadRequest) -> dict[str, Any]:
    meta = session_state["rendered_metadata"].get(req.clip_id)
    if not meta:
        # Try loading metadata.json
        meta_file = pipeline.output_dir / req.clip_id / f"{req.clip_id}_metadata.json"
        if meta_file.is_file():
            import json
            from benxautomation.podcast.models import ClipMetadata
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            meta = ClipMetadata(**data)
        else:
            raise HTTPException(status_code=404, detail=f"No rendered clip found for '{req.clip_id}'.")

    try:
        res = pipeline.upload_to_youtube(
            metadata=meta,
            privacy_status=req.privacy_status,
            user_approved=req.user_approved,
        )
        return {"status": "SUCCESS", "upload_result": res}
    except Exception as e:
        logger.error("Upload error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
