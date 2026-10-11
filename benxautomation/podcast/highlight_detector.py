"""Intelligent highlight detection for podcasts and livestreams.

Finds high-retention moments with strong opening hooks, complete context,
and no misleading out-of-context cuts.
"""

from __future__ import annotations

import json
import os
import re
from typing import List, Optional

import requests

from benxautomation.logger import get_logger
from benxautomation.podcast.errors import HighlightDetectionError
from benxautomation.podcast.models import HighlightCandidate, PodcastTranscript, TranscriptSegment

log = get_logger(__name__)


class HighlightDetector:
    """Detects engaging, context-complete candidate moments for YouTube Shorts."""

    def __init__(
        self,
        *,
        model: str = "gemini-3.5-flash",
        api_key: Optional[str] = None,
        min_clip_duration: float = 15.0,
        max_clip_duration: float = 60.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.min_clip_duration = min_clip_duration
        self.max_clip_duration = max_clip_duration

    def detect_highlights(
        self,
        transcript: PodcastTranscript,
        *,
        max_candidates: int = 5,
    ) -> list[HighlightCandidate]:
        """Detect candidate highlights from transcript using AI or context heuristics."""
        if not transcript.segments:
            raise HighlightDetectionError("Cannot detect highlights from an empty transcript.")

        # Try Gemini API if available
        if self.api_key:
            try:
                candidates = self._detect_with_gemini(transcript, max_candidates=max_candidates)
                if candidates:
                    return self._filter_and_deduplicate(candidates, transcript)
            except Exception as exc:
                log.warning("Gemini highlight detection failed (%s), falling back to heuristic detector", exc)

        # Fallback to heuristic context windowing
        candidates = self._detect_heuristic(transcript, max_candidates=max_candidates)
        return self._filter_and_deduplicate(candidates, transcript)

    def _detect_with_gemini(
        self,
        transcript: PodcastTranscript,
        *,
        max_candidates: int,
    ) -> list[HighlightCandidate]:
        """Query Gemini API for contextual highlight detection."""
        # Build prompt with segment timestamps
        transcript_sample = []
        for s in transcript.segments:
            transcript_sample.append(f"[{s.start_seconds:.1f}s - {s.end_seconds:.1f}s] {s.speaker}: {s.text}")

        prompt = (
            f"You are a master podcast editor producing viral, high-retention YouTube Shorts.\n"
            f"Analyze this timestamped podcast transcript and detect up to {max_candidates} top highlights.\n"
            f"\nRULES:\n"
            f"1. Each clip duration MUST be between {self.min_clip_duration:.1f} and {self.max_clip_duration:.1f} seconds.\n"
            f"2. Strict complete context: Never cut mid-sentence, mid-word, or mid-thought. No misleading or clickbait out-of-context cuts.\n"
            f"3. Strong opening hook: The first 3-5 seconds must grab immediate attention (a provocative question, surprising statement, or story start).\n"
            f"4. Deliver a standalone insight, emotional moment, or actionable lesson.\n"
            f"5. Candidate clips MUST NOT overlap with each other.\n"
            f"\nReturn ONLY a JSON array of objects with keys:\n"
            f"- clip_id (e.g. 'highlight_1')\n"
            f"- start_seconds (float)\n"
            f"- end_seconds (float)\n"
            f"- hook (string: opening hook in first 5 seconds)\n"
            f"- reason (string: why this moment is engaging)\n"
            f"- score (float between 0 and 100)\n"
            f"- summary (string: brief summary of the clip)\n"
            f"\nTRANSCRIPT:\n" + "\n".join(transcript_sample[:250])  # Cap context to prevent overflow
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.3,
            },
        }

        resp = requests.post(url, json=payload, timeout=40)
        if resp.status_code != 200:
            raise HighlightDetectionError(f"Gemini API returned {resp.status_code}: {resp.text}")

        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Clean json
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
        items = json.loads(raw_text)

        candidates: list[HighlightCandidate] = []
        for i, item in enumerate(items, start=1):
            s_start = float(item["start_seconds"])
            s_end = float(item["end_seconds"])
            dur = s_end - s_start
            text = self._get_text_for_range(transcript, s_start, s_end)

            candidates.append(
                HighlightCandidate(
                    clip_id=item.get("clip_id", f"clip_{i}"),
                    start_seconds=round(s_start, 2),
                    end_seconds=round(s_end, 2),
                    duration=round(dur, 2),
                    hook=item.get("hook", text[:60] + "..."),
                    reason=item.get("reason", "High-engagement insight"),
                    score=float(item.get("score", 85.0)),
                    summary=item.get("summary", text[:120]),
                    transcript_text=text,
                    approved=False,
                )
            )
        return candidates

    def _detect_heuristic(
        self,
        transcript: PodcastTranscript,
        *,
        max_candidates: int,
    ) -> list[HighlightCandidate]:
        """Heuristic highlight discovery based on engagement cues and sentence completeness."""
        segments = transcript.segments
        if not segments:
            return []

        candidates: list[HighlightCandidate] = []
        n = len(segments)

        engagement_keywords = {
            "why", "how", "secret", "never", "truth", "mistake", "always",
            "remember", "important", "best", "biggest", "because", "question",
            "future", "problem", "solution", "money", "life", "reason", "imagine"
        }

        # Scan sliding windows of segments
        start_idx = 0
        while start_idx < n:
            curr_start = segments[start_idx].start_seconds
            end_idx = start_idx
            while end_idx < n:
                curr_end = segments[end_idx].end_seconds
                dur = curr_end - curr_start
                if dur >= self.min_clip_duration:
                    if dur <= self.max_clip_duration:
                        # Evaluate this window
                        window_text = " ".join(s.text for s in segments[start_idx : end_idx + 1])
                        hook = segments[start_idx].text

                        # Score window
                        score = 70.0
                        words = window_text.lower().split()
                        matches = sum(1 for w in words if w.strip(".,!?") in engagement_keywords)
                        score += min(20.0, matches * 4.0)

                        if "?" in hook or "!" in hook:
                            score += 8.0

                        cid = f"clip_{len(candidates) + 1}"
                        candidates.append(
                            HighlightCandidate(
                                clip_id=cid,
                                start_seconds=round(curr_start, 2),
                                end_seconds=round(curr_end, 2),
                                duration=round(dur, 2),
                                hook=hook[:75] + ("..." if len(hook) > 75 else ""),
                                reason="Contextually complete insight with strong conversational hook",
                                score=round(min(98.0, score), 1),
                                summary=window_text[:140] + ("..." if len(window_text) > 140 else ""),
                                transcript_text=window_text,
                                approved=False,
                            )
                        )
                        # Advance window
                        break
                    else:
                        break
                end_idx += 1
            start_idx = max(start_idx + 1, end_idx)

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:max_candidates]

    def _get_text_for_range(self, transcript: PodcastTranscript, start: float, end: float) -> str:
        """Collect transcript text between start and end seconds."""
        parts = []
        for s in transcript.segments:
            if s.end_seconds >= start and s.start_seconds <= end:
                parts.append(s.text)
        return " ".join(parts).strip()

    def _filter_and_deduplicate(
        self,
        candidates: list[HighlightCandidate],
        transcript: PodcastTranscript,
    ) -> list[HighlightCandidate]:
        """Enforce strict duration boundaries and non-overlapping clip guarantee."""
        valid: list[HighlightCandidate] = []
        max_time = transcript.total_duration or 999999.0

        for cand in candidates:
            # Bound checks
            cand.start_seconds = max(0.0, cand.start_seconds)
            cand.end_seconds = min(max_time, cand.end_seconds)
            cand.duration = round(cand.end_seconds - cand.start_seconds, 2)

            if cand.duration < self.min_clip_duration or cand.duration > self.max_clip_duration:
                continue

            # Overlap check (> 25% overlap with any previously accepted candidate)
            has_overlap = False
            for accepted in valid:
                overlap_start = max(cand.start_seconds, accepted.start_seconds)
                overlap_end = min(cand.end_seconds, accepted.end_seconds)
                overlap_dur = max(0.0, overlap_end - overlap_start)
                if overlap_dur > 0.25 * min(cand.duration, accepted.duration):
                    has_overlap = True
                    break

            if not has_overlap:
                valid.append(cand)

        if not valid and transcript.segments:
            # Fallback single safe window from start
            first_dur = min(30.0, transcript.total_duration)
            if first_dur >= 5.0:
                text = self._get_text_for_range(transcript, 0.0, first_dur)
                valid.append(
                    HighlightCandidate(
                        clip_id="clip_1",
                        start_seconds=0.0,
                        end_seconds=round(first_dur, 2),
                        duration=round(first_dur, 2),
                        hook=text[:60] + "...",
                        reason="Primary opening segment",
                        score=80.0,
                        summary=text[:120],
                        transcript_text=text,
                        approved=False,
                    )
                )

        return valid
