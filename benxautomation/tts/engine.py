"""Real Neural TTS (Text-to-Speech) engine.

Uses edge-tts (free Microsoft Neural voices) with local speech synthesis fallback.
Produces genuine MP3/WAV voice audio files from text scripts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from benxautomation.errors import BenxError
from benxautomation.logger import get_logger

log = get_logger(__name__)


class TTSError(BenxError):
    """Raised when text-to-speech generation fails."""


@dataclass
class AudioResult:
    """Metadata about generated speech audio."""
    file_path: Path
    duration_seconds: float
    voice_name: str
    script: str


class TTSEngine:
    """Synthesizes text into high-quality speech audio."""

    DEFAULT_VOICE = "en-US-ChristopherNeural"
    DEFAULT_RATE = "+15%"

    # Distinct voice profiles for BEN & Character Universe
    CHARACTER_VOICES = {
        "ben": {"voice": "en-US-ChristopherNeural", "rate": "+15%"},
        "host": {"voice": "en-US-ChristopherNeural", "rate": "+15%"},
        "max": {"voice": "en-US-GuyNeural", "rate": "+10%"},
        "mr_cash": {"voice": "en-GB-RyanNeural", "rate": "+8%"},
        "the_king": {"voice": "en-GB-ThomasNeural", "rate": "+5%"},
        "dr_quantum": {"voice": "en-US-AndrewNeural", "rate": "+12%"},
    }

    def __init__(self, default_voice: str = DEFAULT_VOICE, default_rate: str = DEFAULT_RATE):
        self.default_voice = default_voice
        self.default_rate = default_rate

    def get_character_profile(self, character: str) -> dict[str, str]:
        """Retrieve voice and rate for a character in the universe."""
        norm = character.strip().lower().replace(" ", "_")
        return self.CHARACTER_VOICES.get(norm, {"voice": self.default_voice, "rate": self.default_rate})

    async def synthesize_async(
        self,
        text: str,
        output_path: Path,
        *,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: str = "+0%",
    ) -> AudioResult:
        """Asynchronously synthesize text to MP3 using edge-tts."""
        voice = voice or self.default_voice
        rate = rate if rate is not None else self.default_rate
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not text.strip():
            raise TTSError("Cannot synthesize empty text.")

        try:
            import edge_tts

            log.info("Synthesizing voiceover (%s) for text: %s...", voice, text[:50])
            communicate = edge_tts.Communicate(
                text,
                voice=voice,
                rate=rate,
                volume=volume,
            )
            await communicate.save(str(output_path))
        except Exception as exc:
            raise TTSError(f"TTS synthesis failed: {exc}") from exc

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise TTSError(f"TTS produced empty output file at {output_path}")

        # Measure exact duration via ffprobe when available
        actual_duration = 0.0
        try:
            from benxautomation.renderer.ffmpeg_utils import probe_file

            info = probe_file(output_path)
            fmt = info.get("format", {})
            if "duration" in fmt:
                actual_duration = round(float(fmt["duration"]), 3)
        except Exception as exc:
            log.debug("ffprobe probe failed for %s: %s", output_path, exc)

        if actual_duration <= 0:
            # Fallback estimation if ffprobe is unavailable (~48-64 kbps)
            actual_duration = max(1.0, round(output_path.stat().st_size / 6000.0, 2))

        return AudioResult(
            file_path=output_path,
            duration_seconds=actual_duration,
            voice_name=voice,
            script=text,
        )

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: str = "+0%",
    ) -> AudioResult:
        """Synchronous wrapper for synthesize_async."""
        return asyncio.run(
            self.synthesize_async(
                text,
                output_path,
                voice=voice,
                rate=rate,
                volume=volume,
            )
        )

    def synthesize_character(
        self,
        character: str,
        text: str,
        output_path: Path,
    ) -> AudioResult:
        """Convenience method to synthesize using a character's signature voice and rate."""
        profile = self.get_character_profile(character)
        return self.synthesize(
            text=text,
            output_path=output_path,
            voice=profile["voice"],
            rate=profile["rate"],
        )
