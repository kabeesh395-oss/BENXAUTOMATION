from __future__ import annotations

"""Local, rolling live-stream clipper for public Twitch and YouTube Live streams.

Requires Streamlink, FFmpeg/ffprobe, Faster-Whisper and a running local Ollama.
Only public streams are supported; this module does not bypass access controls.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from .pipeline import choose_highlights, generate_metadata, render, transcribe

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUTS = DATA / "outputs"
SEGMENT_SECONDS = 5
WINDOW_SEGMENTS = 16  # approximately 80 seconds, including pre-roll
ANALYZE_EVERY_SECONDS = 15
PLATFORM_HOSTS = {
    "twitch": {"twitch.tv", "www.twitch.tv", "m.twitch.tv"},
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtube.com"},
}


def identify_platform(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Use an https Twitch or YouTube Live URL.")
    host = parsed.hostname.lower()
    for platform, hosts in PLATFORM_HOSTS.items():
        if host in hosts:
            return platform
    raise ValueError("Only Twitch and YouTube URLs are supported.")


def _run_capture(url: str, segment_dir: Path, stop: threading.Event) -> None:
    """Pipe Streamlink into FFmpeg and write short independently readable TS segments."""
    streamlink = shutil.which("streamlink")
    ffmpeg = shutil.which("ffmpeg")
    if not streamlink:
        raise RuntimeError("Streamlink is missing. Install it with: pip install streamlink")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is missing or not on PATH.")
    source = subprocess.Popen(
        [streamlink, "--stdout", url, "best"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    assert source.stdout is not None
    target = subprocess.Popen(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
         "-map", "0", "-c", "copy", "-f", "segment",
         "-segment_time", str(SEGMENT_SECONDS), "-reset_timestamps", "1",
         "-segment_format", "mpegts", str(segment_dir / "%08d.ts")],
        stdin=source.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    source.stdout.close()
    try:
        while not stop.wait(1):
            if source.poll() is not None and source.returncode not in (0, None):
                raise RuntimeError("Streamlink stopped. Confirm the stream is live and publicly accessible.")
            if target.poll() is not None:
                error = (target.stderr.read() if target.stderr else b"").decode("utf-8", "replace")
                raise RuntimeError("FFmpeg capture stopped: " + error[-1200:])
    finally:
        for process in (target, source):
            if process.poll() is None:
                process.terminate()
        for process in (target, source):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def _make_window(segments: list[Path], target: Path) -> float:
    concat_file = target.with_suffix(".txt")
    concat_file.write_text(
        "".join("file '" + p.resolve().as_posix().replace("'", "'\\''") + "'\n" for p in segments),
        encoding="utf-8",
    )
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", str(concat_file),
           "-c", "copy", "-movflags", "+faststart", str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode or not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("Could not assemble rolling live window: " + result.stderr[-1000:])
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(target)],
        capture_output=True, text=True, timeout=30,
    )
    if probe.returncode:
        raise RuntimeError("ffprobe could not read the rolling live window.")
    return float(probe.stdout.strip())


class LiveSession:
    def __init__(self, url: str, language: str | None, model: str, clip_count: int):
        self.id = uuid.uuid4().hex[:12]
        self.url = url
        self.platform = identify_platform(url)
        self.language = language
        self.model = model
        self.clip_count = max(1, min(clip_count, 10))
        self.status = "starting"
        self.message = "Starting live capture"
        self.clips: list[dict] = []
        self.error = ""
        self.started_at = time.time()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.directory = DATA / "live" / self.id
        self.segment_dir = self.directory / "segments"
        self.output_dir = OUTPUTS / self.id
        self.segment_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._last_clip_end = 0.0
        self._last_analyzed_segment = -1

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "id": self.id, "platform": self.platform, "source": self.url,
                "status": self.status, "message": self.message, "error": self.error,
                "clips": list(self.clips), "clip_count": len(self.clips),
                "elapsed_seconds": int(time.time() - self.started_at),
            }

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name=f"live-{self.id}", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        with self.lock:
            if self.status not in {"completed", "failed"}:
                self.status = "stopping"
                self.message = "Stopping capture and finalizing current analysis"

    def _run(self) -> None:
        capture_thread = threading.Thread(
            target=self._capture_guard, name=f"capture-{self.id}", daemon=True
        )
        capture_thread.start()
        try:
            with self.lock:
                self.status = "capturing"
                self.message = f"Capturing {self.platform} live stream; waiting for rolling buffer"
            while not self.stop_event.wait(ANALYZE_EVERY_SECONDS):
                segments = sorted(self.segment_dir.glob("*.ts"))
                if len(segments) < 8:
                    continue
                latest_index = int(segments[-1].stem)
                if latest_index == self._last_analyzed_segment:
                    continue
                self._last_analyzed_segment = latest_index
                selected = segments[-WINDOW_SEGMENTS:]
                window_start_seconds = int(selected[0].stem) * SEGMENT_SECONDS
                window = self.directory / "rolling-window.mp4"
                duration = _make_window(selected, window)
                with self.lock:
                    self.message = "Analyzing recent live audio with local Faster-Whisper and Ollama"
                rows = transcribe(window, self.model, self.language)
                try:
                    candidates = choose_highlights(rows, count=self.clip_count,
                                                   min_seconds=20, max_seconds=58)
                except RuntimeError as exc:
                    if "No valid highlights" in str(exc):
                        continue
                    raise
                for candidate in candidates:
                    # Require a newly observed moment and retain a short cooldown.
                    global_end = window_start_seconds + candidate.end
                    if candidate.end > duration + 0.5 or global_end < self._last_clip_end - 3:
                        continue
                    if any(abs(float(c.get("global_end", 0)) - global_end) < 12
                           for c in self.clips):
                        continue
                    index = len(self.clips) + 1
                    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", candidate.title).strip("-").lower()[:35] or f"clip-{index}"
                    target = self.output_dir / f"{index:02d}-{slug}.mp4"
                    with self.lock:
                        self.message = f"Rendering live highlight {index}"
                    render(window, rows, candidate, target)
                    metadata = generate_metadata(candidate)
                    clip = {
                        "id": index, "title": candidate.title, "reason": candidate.reason,
                        "score": candidate.score, "start": candidate.start, "end": candidate.end,
                        "duration": round(candidate.end - candidate.start, 2),
                        "global_end": global_end,
                        "youtube_title": metadata["title"],
                        "youtube_description": metadata["description"],
                        "youtube_tags": metadata["tags"],
                        "video_url": f"/outputs/{self.id}/{target.name}",
                        "subtitle_url": f"/outputs/{self.id}/{target.stem}.srt",
                        "status": "ready",
                    }
                    with self.lock:
                        self.clips.append(clip)
                        self._last_clip_end = candidate.end
                        self.message = f"Live clip {index} ready while stream is still running"
                    (self.output_dir / "clips.json").write_text(
                        json.dumps(self.clips, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                # Keep only a bounded rolling set; do not delete segments being analyzed.
                for old in segments[:-WINDOW_SEGMENTS]:
                    try:
                        old.unlink()
                    except OSError:
                        pass
            with self.lock:
                self.status = "completed"
                self.message = "Live capture stopped; generated clips are preserved"
        except Exception as exc:
            with self.lock:
                self.status = "failed"
                self.error = str(exc)
                self.message = "Live clipping stopped because capture or analysis failed"
        finally:
            self.stop_event.set()
            capture_thread.join(timeout=8)

    def _capture_guard(self) -> None:
        try:
            _run_capture(self.url, self.segment_dir, self.stop_event)
        except Exception as exc:
            with self.lock:
                if not self.stop_event.is_set():
                    self.error = str(exc)
                    self.status = "failed"
                    self.message = "Live capture failed"
            self.stop_event.set()
