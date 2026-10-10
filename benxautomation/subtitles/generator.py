"""Subtitle generation and synchronization module.

Creates standard SRT and ASS subtitle files aligned with speech audio timing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class SubtitleSegment:
    """A timed subtitle segment."""
    index: int
    start_seconds: float
    end_seconds: float
    text: str

    def to_srt_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def to_srt_block(self) -> str:
        start_str = self.to_srt_time(self.start_seconds)
        end_str = self.to_srt_time(self.end_seconds)
        return f"{self.index}\n{start_str} --> {end_str}\n{self.text}\n"


class SubtitleGenerator:
    """Generates SRT and ASS subtitle files."""

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        """Split text into sentences while keeping sensible chunks."""
        # Split on sentence terminals or commas if too long
        raw = re.split(r'(?<=[.!?。！？])\s+', text.strip())
        sentences: list[str] = []
        for s in raw:
            s = s.strip()
            if s:
                sentences.append(s)
        return sentences if sentences else [text.strip()]

    def generate_srt_from_text(
        self,
        text: str,
        total_duration_seconds: float,
        output_path: Path,
    ) -> Path:
        """Create an SRT subtitle file distributing duration across sentences."""
        sentences = self.split_sentences(text)
        total_chars = sum(len(s) for s in sentences) or 1
        output_path.parent.mkdir(parents=True, exist_ok=True)

        segments: list[SubtitleSegment] = []
        current_time = 0.0

        for idx, sentence in enumerate(sentences, start=1):
            fraction = len(sentence) / total_chars
            duration = max(0.8, fraction * total_duration_seconds)
            end_time = min(total_duration_seconds, current_time + duration)
            if idx == len(sentences):
                end_time = total_duration_seconds

            segments.append(
                SubtitleSegment(
                    index=idx,
                    start_seconds=current_time,
                    end_seconds=end_time,
                    text=sentence,
                )
            )
            current_time = end_time

        srt_content = "\n".join(seg.to_srt_block() for seg in segments)
        output_path.write_text(srt_content, encoding="utf-8")
        return output_path
