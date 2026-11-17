"""Optional local signals for ranking AutoClip moments.

Audio loudness is measured with FFmpeg's volumedetect filter. Chat events can be
provided as JSONL sidecar records with a numeric `time` field in source seconds.
No external chat API, account token, or paid service is contacted here.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any


def measure_loudness(source: Path, start: float, end: float) -> dict[str, float] | None:
    """Return mean/max dBFS for a time range, or None when measurement fails."""
    duration = end - start
    if start < 0 or duration <= 0:
        raise ValueError("A valid non-negative time range is required.")
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start:.3f}",
            "-t", f"{duration:.3f}", "-i", str(source), "-vn",
            "-af", "volumedetect", "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=90,
    )
    output = result.stderr or ""
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", output)
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", output)
    if result.returncode or not mean_match or not max_match:
        return None
    return {"mean_db": float(mean_match.group(1)), "peak_db": float(max_match.group(1))}


def load_chat_events(path: Path) -> list[dict[str, Any]]:
    """Load timestamped chat events from JSONL; ignore malformed or untimed rows."""
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
            timestamp = float(item["time"])
            if timestamp >= 0:
                events.append({**item, "time": timestamp})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            continue
    return events


def chat_activity_score(events: list[dict[str, Any]], start: float, end: float) -> float | None:
    """Score relative chat burst (0-100) against event density in supplied data."""
    if end <= start:
        raise ValueError("End time must be greater than start time.")
    in_window = sum(start <= float(event.get("time", -1)) <= end for event in events)
    if not events:
        return None
    total_span = max(float(event.get("time", 0)) for event in events) - min(
        float(event.get("time", 0)) for event in events
    )
    baseline = len(events) / max(total_span, 1.0) * (end - start)
    if in_window == 0:
        return 0.0
    return round(min(100.0, 100.0 * in_window / max(1.0, baseline * 3.0)), 2)


def combine_moment_score(
    transcript_score: float,
    loudness: dict[str, float] | None = None,
    chat_score: float | None = None,
) -> float:
    """Blend only available signals; absent inputs do not lower the score."""
    values = [(0.70, max(0.0, min(100.0, transcript_score)))]
    if loudness is not None:
        # Map typical speech (-40 dBFS) to quiet and energetic (-10 dBFS) to high.
        audio_score = max(0.0, min(100.0, (loudness["mean_db"] + 40.0) / 30.0 * 100.0))
        values.append((0.20, audio_score))
    if chat_score is not None:
        values.append((0.10, max(0.0, min(100.0, chat_score))))
    weight = sum(w for w, _ in values)
    return round(sum(w * score for w, score in values) / weight, 2)
