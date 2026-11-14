"""Local long-video to Shorts worker using Faster-Whisper, Ollama and FFmpeg.

All inference runs on the machine hosting this worker. YouTube upload is opt-in,
uses the repository's existing OAuth publisher, and is private-only by default.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from benxautomation.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class TranscriptLine:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Clip:
    start: float
    end: float
    title: str
    reason: str
    score: float
    transcript: str


def transcribe(video: Path, model_name: str = "small", language: str | None = None) -> list[TranscriptLine]:
    """Run Faster-Whisper locally; no remote transcription service is used."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install the worker extra: pip install -e '.[autoclip]'") from exc

    model = WhisperModel(model_name, device=os.getenv("WHISPER_DEVICE", "cpu"),
                         compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
    segments, _info = model.transcribe(str(video), language=language, vad_filter=True,
                                       word_timestamps=False, condition_on_previous_text=False)
    lines = [TranscriptLine(float(s.start), float(s.end), str(s.text).strip())
             for s in segments if str(s.text).strip() and float(s.end) > float(s.start)]
    if not lines:
        raise RuntimeError("Faster-Whisper returned no speech segments; refusing to invent a transcript.")
    return lines


def detect_highlights(lines: list[TranscriptLine], *, model: str = "qwen2.5:3b",
                      ollama_url: str = "http://127.0.0.1:11434", count: int = 5,
                      min_seconds: int = 20, max_seconds: int = 58) -> list[Clip]:
    """Ask a local Ollama model for timestamped highlights and validate its output."""
    if not lines:
        raise ValueError("Transcript is empty.")
    transcript = "\n".join(f"[{x.start:.2f}-{x.end:.2f}] {x.text}" for x in lines)
    prompt = f"""Select up to {count} compelling, context-complete YouTube Shorts from this transcript.
Return ONLY a JSON array. Each object must contain start_seconds, end_seconds, title,
reason and score (0-100). Clips must be {min_seconds}-{max_seconds} seconds, must not
overlap, must start/end near complete utterances, and must not invent statements.
Rank strongest first. Transcript timestamps are seconds:
{transcript[:100000]}"""
    response = requests.post(f"{ollama_url.rstrip('/')}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False,
              "format": "json", "options": {"temperature": 0.1}}, timeout=900)
    response.raise_for_status()
    raw = response.json().get("response", "")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama did not return valid JSON highlight candidates.") from exc
    if isinstance(data, dict):
        data = data.get("clips", data.get("highlights", []))
    if not isinstance(data, list):
        raise RuntimeError("Ollama response must be a JSON array of clips.")

    total = lines[-1].end
    clips: list[Clip] = []
    for item in data:
        try:
            start, end = float(item["start_seconds"]), float(item["end_seconds"])
            if start < 0 or end > total + 0.5 or end <= start:
                continue
            if not min_seconds <= end - start <= max_seconds:
                continue
            if any(not (end <= c.start or start >= c.end) for c in clips):
                continue
            text = " ".join(x.text for x in lines if x.end > start and x.start < end)
            if not text:
                continue
            clips.append(Clip(start, end, str(item.get("title", "Untitled highlight"))[:95],
                              str(item.get("reason", "Selected by local Ollama analysis"))[:500],
                              max(0.0, min(100.0, float(item.get("score", 0.0)))), text))
        except (KeyError, TypeError, ValueError):
            continue
    clips.sort(key=lambda c: c.score, reverse=True)
    if not clips:
        raise RuntimeError("Ollama produced no valid clips in the configured duration range.")
    return clips[:count]


def _srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_clip_srt(lines: list[TranscriptLine], start: float, end: float, target: Path) -> None:
    cues = []
    for line in lines:
        left, right = max(start, line.start), min(end, line.end)
        if right <= left:
            continue
        cues.append(f"{len(cues)+1}\n{_srt_time(left-start)} --> {_srt_time(right-start)}\n{line.text}\n")
    if not cues:
        raise RuntimeError("No subtitle cues overlap this clip.")
    target.write_text("\n".join(cues), encoding="utf-8")


def render_clip(video: Path, clip: Clip, lines: list[TranscriptLine], output: Path,
                *, width: int = 1080, height: int = 1920) -> Path:
    """Create a 9:16 H.264 MP4 with subtitles permanently burned into the image."""
    output.parent.mkdir(parents=True, exist_ok=True)
    srt = output.with_suffix(".srt")
    write_clip_srt(lines, clip.start, clip.end, srt)
    # FFmpeg filter escaping for Windows drive colon, backslashes and apostrophes.
    sub_path = str(srt.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
          f"subtitles='{sub_path}':force_style='FontName=Arial,FontSize=22,"
          "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,"
          "Outline=3,Shadow=1,Alignment=2,MarginV=180',setsar=1,fps=30,format=yuv420p")
    cmd = ["ffmpeg", "-hide_banner", "-y", "-ss", f"{clip.start:.3f}", "-i", str(video),
           "-t", f"{clip.end-clip.start:.3f}", "-vf", vf, "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg render failed: {result.stderr[-4000:]}")
    return output


def upload_private(video: Path, title: str, description: str, tags: list[str]) -> dict[str, Any]:
    """Use BENXAUTOMATION's existing OAuth, resumable uploader and duplicate ledger."""
    from benxautomation.config import PublishingConfig
    from benxautomation.publisher.youtube import YouTubePublisher
    cfg = PublishingConfig(enabled=True, enforce_private=True)
    publisher = YouTubePublisher(cfg)
    return publisher.upload(video, title=title, description=description, tags=tags,
                            privacy_status="private", allow_duplicate=False)


def run(video: Path, output_dir: Path, *, language: str | None, whisper_model: str,
        ollama_model: str, max_clips: int, upload: bool, rights_confirmed: bool) -> list[dict[str, Any]]:
    if not video.is_file():
        raise FileNotFoundError(video)
    if upload and not rights_confirmed:
        raise PermissionError("Upload blocked: pass --rights-confirmed only when you own or have permission to use the source.")
    output_dir.mkdir(parents=True, exist_ok=True)
    log.info("Transcribing locally with Faster-Whisper model=%s", whisper_model)
    lines = transcribe(video, whisper_model, language)
    transcript_path = output_dir / f"{video.stem}_transcript.json"
    transcript_path.write_text(json.dumps([x.__dict__ for x in lines], ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Selecting highlights with local Ollama model=%s", ollama_model)
    clips = detect_highlights(lines, model=ollama_model, count=max_clips)
    results = []
    for index, clip in enumerate(clips, start=1):
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", clip.title).strip("-").lower()[:48] or f"clip-{index}"
        target = output_dir / f"{index:02d}-{slug}.mp4"
        render_clip(video, clip, lines, target)
        item: dict[str, Any] = {"video": str(target), "srt": str(target.with_suffix(".srt")),
            "start_seconds": clip.start, "end_seconds": clip.end, "title": clip.title,
            "score": clip.score, "reason": clip.reason, "analysis_source": "local Ollama",
            "transcription_source": "local Faster-Whisper"}
        if upload:
            item["youtube"] = upload_private(target, clip.title[:95],
                f"{clip.reason}\n\nSource: {video.name}\n#Shorts", ["Shorts", "Podcast"])
        results.append(item)
    (output_dir / "autoclip_manifest.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-hosted AutoClip AI long-video to Shorts worker")
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/autoclip"))
    parser.add_argument("--language", default=None, help="Whisper language code, e.g. en or ta; omit for auto-detect")
    parser.add_argument("--whisper-model", default="small", choices=["tiny", "base", "small", "medium", "large-v3"])
    parser.add_argument("--ollama-model", default="qwen2.5:3b")
    parser.add_argument("--max-clips", type=int, default=5)
    parser.add_argument("--upload", action="store_true", help="Upload finished clips as PRIVATE to configured YouTube channel")
    parser.add_argument("--rights-confirmed", action="store_true", help="Confirm you own or are authorized to repurpose the source")
    args = parser.parse_args()
    results = run(args.video, args.output, language=args.language, whisper_model=args.whisper_model,
                  ollama_model=args.ollama_model, max_clips=max(1, min(args.max_clips, 10)),
                  upload=args.upload, rights_confirmed=args.rights_confirmed)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
