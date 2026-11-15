from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import requests


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Candidate:
    start: float
    end: float
    title: str
    reason: str
    score: float
    transcript: str


def transcribe(source: Path, model_name: str = "small", language: str | None = None) -> list[Segment]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Faster-Whisper missing. Run: pip install -r requirements.txt") from exc
    model = WhisperModel(model_name, device=os.getenv("WHISPER_DEVICE", "cpu"),
                         compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
    parts, _ = model.transcribe(str(source), language=language, vad_filter=True,
                                condition_on_previous_text=False)
    rows = [Segment(float(x.start), float(x.end), str(x.text).strip())
            for x in parts if str(x.text).strip() and float(x.end) > float(x.start)]
    if not rows:
        raise RuntimeError("No speech was detected. Try another language or source file.")
    return rows


def choose_highlights(rows: list[Segment], count: int = 5, min_seconds: int = 20,
                      max_seconds: int = 58) -> list[Candidate]:
    if not rows:
        raise ValueError("Transcript is empty.")
    transcript = "\n".join(f"[{x.start:.2f}-{x.end:.2f}] {x.text}" for x in rows)
    prompt = f"""You are an editor selecting strong, context-complete short video clips.
Return ONLY a JSON array of up to {count} objects with start_seconds, end_seconds,
title, reason, score (0-100). Each clip must be {min_seconds}-{max_seconds} seconds,
non-overlapping, grounded in the transcript, and start/end at complete thoughts.
Rank best first. Timestamps are seconds.
TRANSCRIPT:
{transcript[:90000]}"""
    endpoint = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    try:
        response = requests.post(f"{endpoint}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json",
                  "options": {"temperature": 0.1}}, timeout=900)
        response.raise_for_status()
        raw = response.json().get("response", "")
        payload = json.loads(raw)
    except requests.RequestException as exc:
        raise RuntimeError("Local Ollama is unavailable. Start Ollama and run: ollama pull qwen2.5:3b") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Ollama returned invalid highlight JSON.") from exc
    if isinstance(payload, dict):
        payload = payload.get("clips", payload.get("highlights", []))
    if not isinstance(payload, list):
        raise RuntimeError("Ollama response must contain a JSON array.")
    duration = rows[-1].end
    clips: list[Candidate] = []
    for item in payload:
        try:
            start, end = float(item["start_seconds"]), float(item["end_seconds"])
            if start < 0 or end > duration + 0.5 or not min_seconds <= end-start <= max_seconds:
                continue
            if any(not (end <= c.start or start >= c.end) for c in clips):
                continue
            spoken = " ".join(x.text for x in rows if x.end > start and x.start < end)
            if not spoken:
                continue
            score = max(0.0, min(100.0, float(item.get("score", 0))))
            clips.append(Candidate(start, end, str(item.get("title", "Highlight"))[:90],
                str(item.get("reason", "Selected by local model"))[:300], score, spoken))
        except (KeyError, TypeError, ValueError):
            continue
    clips.sort(key=lambda x: x.score, reverse=True)
    if not clips:
        raise RuntimeError("No valid highlights found. Try a longer video or a different Whisper language.")
    return clips[:count]


def _srt_stamp(value: float) -> str:
    ms = max(0, round(value * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def render(source: Path, rows: list[Segment], clip: Candidate, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    srt = target.with_suffix(".srt")
    cues = []
    for row in rows:
        left, right = max(clip.start, row.start), min(clip.end, row.end)
        if right > left:
            cues.append(f"{len(cues)+1}\n{_srt_stamp(left-clip.start)} --> {_srt_stamp(right-clip.start)}\n{row.text}\n")
    if not cues:
        raise RuntimeError("No subtitle cues overlap this highlight.")
    srt.write_text("\n".join(cues), encoding="utf-8")
    sub = str(srt.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    vf = (f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          f"subtitles='{sub}':force_style='FontName=Arial,FontSize=22,"
          "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,"
          "Outline=3,Shadow=1,Alignment=2,MarginV=170',setsar=1,fps=30,format=yuv420p")
    cmd = ["ffmpeg", "-hide_banner", "-y", "-ss", f"{clip.start:.3f}", "-i", str(source),
           "-t", f"{clip.end-clip.start:.3f}", "-vf", vf, "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode or not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg render failed: {result.stderr[-2500:]}")
    return target



def generate_metadata(clip: Candidate) -> dict:
    """Create YouTube SEO metadata locally; use a safe deterministic fallback."""
    fallback_tags = list(dict.fromkeys(
        word.lower() for word in re.findall(r"[A-Za-z0-9]{4,}", clip.title + " " + clip.transcript)
    ))[:12]
    fallback = {
        "title": clip.title[:95] or "Best Moment",
        "description": f"{clip.reason}\n\n{clip.transcript[:1200]}\n\n#Shorts",
        "tags": fallback_tags or ["shorts", "highlights"],
    }
    endpoint = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    prompt = f"""Create YouTube Shorts metadata for this clip. Return ONLY one JSON object:
{{"title":"under 100 characters","description":"engaging factual description with #Shorts","tags":["up to 15 relevant tags"]}}
Do not invent facts, names, claims or links. Keep the title accurate and concise.
Clip title: {clip.title}
Why it matters: {clip.reason}
Transcript: {clip.transcript[:3500]}"""
    try:
        response = requests.post(
            f"{endpoint}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json",
                  "options": {"temperature": 0.2}},
            timeout=180,
        )
        response.raise_for_status()
        data = json.loads(response.json().get("response", "{}"))
        title = str(data.get("title", fallback["title"])).strip()[:100]
        description = str(data.get("description", fallback["description"])).strip()[:5000]
        raw_tags = data.get("tags", fallback["tags"])
        tags = [str(tag).strip()[:30] for tag in raw_tags if str(tag).strip()] if isinstance(raw_tags, list) else fallback["tags"]
        return {"title": title or fallback["title"], "description": description or fallback["description"],
                "tags": tags[:15]}
    except Exception:
        return fallback


def process(source: Path, output: Path, language: str | None = None,
            whisper_model: str = "small", count: int = 5) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    rows = transcribe(source, whisper_model, language)
    (output / "transcript.json").write_text(
        json.dumps([asdict(x) for x in rows], ensure_ascii=False, indent=2), encoding="utf-8")
    clips = choose_highlights(rows, count=max(1, min(count, 10)))
    result = []
    for index, clip in enumerate(clips, 1):
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", clip.title).strip("-").lower()[:40] or f"clip-{index}"
        target = output / f"{index:02d}-{slug}.mp4"
        render(source, rows, clip, target)
        metadata = generate_metadata(clip)
        result.append({"id": index, "title": clip.title, "reason": clip.reason,
            "score": clip.score, "start": clip.start, "end": clip.end,
            "duration": round(clip.end-clip.start, 2),
            "youtube_title": metadata["title"],
            "youtube_description": metadata["description"],
            "youtube_tags": metadata["tags"],
            "video_url": f"/outputs/{output.name}/{target.name}",
            "subtitle_url": f"/outputs/{output.name}/{target.stem}.srt"})
    (output / "clips.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
