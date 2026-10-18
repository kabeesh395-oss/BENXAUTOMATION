"""Agent 4: Sonic Studio & Audio Engineer.

Synthesizes high-velocity, catchy narration using Christopher Neural (+15% speed),
mixes character dialogues, manages SFX cues, and exports broadcast WAV/MP3.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from benxautomation.agents.script_director import ProductionScript
from benxautomation.logger import get_logger
from benxautomation.tts.engine import TTSEngine

log = get_logger(__name__)


@dataclass
class AudioMixResult:
    """Output of AudioEngineerAgent processing."""
    mp3_path: Path
    wav_path: Path
    total_duration: float
    scene_timestamps: List[Tuple[float, float, str]] = field(default_factory=list)


class AudioEngineerAgent:
    """Agent 4: Manages neural voice synthesis, character voice mapping, and sonic timing."""

    def __init__(self, tts_engine: TTSEngine | None = None):
        self.tts = tts_engine or TTSEngine()

    def produce_audio(self, script: ProductionScript, output_dir: Path) -> AudioMixResult:
        """Synthesize all scene dialogues and assemble final master narration track."""
        output_dir.mkdir(parents=True, exist_ok=True)
        final_mp3 = output_dir / f"{script.topic_id}_narration.mp3"
        final_wav = output_dir / f"{script.topic_id}_narration.wav"

        # Synthesize full script with Christopher @ +15%
        full_text = script.full_voiceover_text
        log.info("Synthesizing fast-paced catchy voiceover for %s (%d chars)...", script.topic_id, len(full_text))

        # Use host character's voice profile
        audio_res = self.tts.synthesize_character(
            character="ben",
            text=full_text,
            output_path=final_mp3,
        )

        total_duration = audio_res.duration_seconds
        log.info("Master voiceover generated: %s (Duration: %.2fs)", final_mp3.name, total_duration)

        # Convert MP3 to 16-bit 44.1kHz mono WAV for high-precision Lip-Sync RMS analysis
        self._convert_to_wav(final_mp3, final_wav)

        # Calculate proportional timestamps for each scene based on character word count
        timestamps = self._calculate_scene_timestamps(script, total_duration)

        return AudioMixResult(
            mp3_path=final_mp3,
            wav_path=final_wav,
            total_duration=total_duration,
            scene_timestamps=timestamps,
        )

    def _convert_to_wav(self, mp3_path: Path, wav_path: Path) -> None:
        """Convert MP3 to uncompressed 16-bit mono WAV using FFmpeg."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(mp3_path),
            "-ac",
            "1",
            "-ar",
            "44100",
            str(wav_path),
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            log.warning("FFmpeg WAV conversion failed: %s", exc)

    def _calculate_scene_timestamps(
        self, script: ProductionScript, total_duration: float
    ) -> List[Tuple[float, float, str]]:
        """Map each scene's start and end times proportionately across speech duration."""
        total_words = sum(len(s.dialogue.split()) for s in script.scenes)
        if total_words == 0:
            return []

        timestamps = []
        cur_time = 0.0
        for s in script.scenes:
            w_count = len(s.dialogue.split())
            frac = w_count / total_words
            duration = frac * total_duration
            start_t = cur_time
            end_t = min(total_duration, cur_time + duration)
            timestamps.append((start_t, end_t, s.dialogue))
            cur_time = end_t

        return timestamps
