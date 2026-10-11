"""Subtitle export and styling module for Podcast-to-Shorts.

Generates synchronized per-clip SRT, WebVTT, and stylized ASS subtitle files,
with full UTF-8 support for English, Tamil, and Tamil-English (Tanglish).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from benxautomation.logger import get_logger
from benxautomation.podcast.errors import SubtitlesError
from benxautomation.podcast.models import (
    HighlightCandidate,
    PodcastTranscript,
    SubtitleStyle,
    TranscriptSegment,
)

log = get_logger(__name__)


def _seconds_to_srt_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seconds_to_vtt_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _seconds_to_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))  # Centiseconds (2 digits)
    if cs >= 100:
        s += 1
        cs = 0
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


class PodcastSubtitleManager:
    """Exports and formats subtitles per clip."""

    def get_clip_segments(
        self,
        candidate: HighlightCandidate,
        transcript: PodcastTranscript,
    ) -> list[TranscriptSegment]:
        """Slice and time-shift transcript segments for the candidate clip."""
        c_start = candidate.start_seconds
        c_end = candidate.end_seconds
        dur = candidate.duration

        clip_segs: list[TranscriptSegment] = []
        idx = 1

        for seg in transcript.segments:
            # Overlap condition
            if seg.end_seconds > c_start and seg.start_seconds < c_end:
                rel_start = max(0.0, seg.start_seconds - c_start)
                rel_end = min(dur, seg.end_seconds - c_start)
                if rel_end > rel_start:
                    clip_segs.append(
                        TranscriptSegment(
                            index=idx,
                            start_seconds=round(rel_start, 3),
                            end_seconds=round(rel_end, 3),
                            text=seg.text,
                            speaker=seg.speaker,
                        )
                    )
                    idx += 1

        # Fallback if no individual segments matched
        if not clip_segs and candidate.transcript_text:
            clip_segs.append(
                TranscriptSegment(
                    index=1,
                    start_seconds=0.0,
                    end_seconds=round(dur, 3),
                    text=candidate.transcript_text,
                    speaker="Speaker",
                )
            )

        return clip_segs

    def export_srt(
        self,
        candidate: HighlightCandidate,
        transcript: PodcastTranscript,
        output_path: Path,
    ) -> Path:
        """Export standardized SubRip (.srt) subtitle file."""
        segments = self.get_clip_segments(candidate, transcript)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        blocks = []
        for s in segments:
            start_str = _seconds_to_srt_time(s.start_seconds)
            end_str = _seconds_to_srt_time(s.end_seconds)
            blocks.append(f"{s.index}\n{start_str} --> {end_str}\n{s.text}\n")

        content = "\n".join(blocks)
        output_path.write_text(content, encoding="utf-8")
        log.info("Exported SRT to: %s (%d cues)", output_path.name, len(segments))
        return output_path

    def export_vtt(
        self,
        candidate: HighlightCandidate,
        transcript: PodcastTranscript,
        output_path: Path,
    ) -> Path:
        """Export standardized WebVTT (.vtt) subtitle file."""
        segments = self.get_clip_segments(candidate, transcript)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        blocks = ["WEBVTT\n"]
        for s in segments:
            start_str = _seconds_to_vtt_time(s.start_seconds)
            end_str = _seconds_to_vtt_time(s.end_seconds)
            blocks.append(f"{start_str} --> {end_str}\n{s.text}\n")

        content = "\n".join(blocks)
        output_path.write_text(content, encoding="utf-8")
        log.info("Exported VTT to: %s (%d cues)", output_path.name, len(segments))
        return output_path

    def export_ass(
        self,
        candidate: HighlightCandidate,
        transcript: PodcastTranscript,
        output_path: Path,
        style: SubtitleStyle,
    ) -> Path:
        """Export styled Advanced SubStation Alpha (.ass) subtitle file for FFmpeg burning."""
        segments = self.get_clip_segments(candidate, transcript)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font_name},{style.font_size},{style.primary_color},&H000000FF,{style.outline_color},{style.back_color},-1,0,0,0,100,100,0,0,{style.border_style},{style.outline_width},{style.shadow_width},{style.alignment},40,40,{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for s in segments:
            start_str = _seconds_to_ass_time(s.start_seconds)
            end_str = _seconds_to_ass_time(s.end_seconds)
            clean_text = s.text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
            events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{clean_text}")

        full_ass = header + "\n".join(events) + "\n"
        output_path.write_text(full_ass, encoding="utf-8")
        log.info("Exported ASS subtitles to: %s", output_path.name)
        return output_path
