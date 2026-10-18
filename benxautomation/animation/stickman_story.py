"""End-to-End Story-to-Animation Pipeline for Funny Stickman (BEN & MAX) Productions.

Workflow:
1. Comedy Script Generation / Catalog Selection (BEN & MAX slapstick storytelling)
2. Narration Audio Synthesis (Edge-TTS neural voices with fallback)
3. Subtitle Generation (SRT & mobile safe-zone ASS)
4. Procedural Stickman Animation & FFmpeg rawvideo encoding (24fps 1080x1920 or 1920x1080)
5. Mathematical Motion & Media Validation (Pixel delta, freeze prevention, stream checks)
6. Thumbnail extraction and structured metadata export
7. Strict Private-Upload Safeguards
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benxautomation.animation.motion_validator import MotionValidationResult, MotionValidator
from benxautomation.animation.stickman_engine import ComedyScene, StickmanAnimationEngine
from benxautomation.config import AppConfig, PublishingConfig
from benxautomation.logger import get_logger
from benxautomation.renderer.ffmpeg_utils import find_ffmpeg, find_ffprobe, probe_file
from benxautomation.subtitles.generator import SubtitleGenerator
from benxautomation.tts.engine import TTSEngine

log = get_logger(__name__)


@dataclass
class StickmanStoryScript:
    """Full script specification for a Funny Stickman animation."""
    story_id: str
    title: str
    topic: str
    scenes: List[ComedyScene]
    format: str = "shorts"  # "shorts" (1080x1920) or "longform" (1920x1080)
    voice: str = "en-US-ChristopherNeural"
    tags: List[str] = field(default_factory=list)
    description: str = ""
    license_statement: str = "Original characters (BEN & MAX), procedural stickman animation, and script by BENXAUTOMATION."

    @property
    def total_duration(self) -> float:
        return sum(s.duration_seconds for s in self.scenes)

    def validate(self) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not self.title.strip():
            errors.append("Story title cannot be empty.")
        if not self.scenes:
            errors.append("Story must contain at least one comedy scene.")
        for i, sc in enumerate(self.scenes):
            if sc.duration_seconds <= 0.0:
                errors.append(f"Scene {i} ({sc.scene_id}): duration must be positive.")
        return len(errors) == 0, errors


@dataclass
class StickmanStoryResult:
    """Production artifacts bundle and quality status."""
    story_id: str
    title: str
    format: str
    video_path: Path
    audio_path: Path
    srt_path: Path
    vtt_path: Path
    ass_path: Path
    thumbnail_path: Path
    metadata_path: Path
    duration_seconds: float
    fps: int
    motion_verified: bool
    motion_score: float
    quality_passed: bool
    quality_issues: List[str] = field(default_factory=list)
    youtube_status: str = "NOT_UPLOADED"
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "story_id": self.story_id,
            "title": self.title,
            "format": self.format,
            "video_path": str(self.video_path),
            "audio_path": str(self.audio_path),
            "srt_path": str(self.srt_path),
            "vtt_path": str(self.vtt_path),
            "ass_path": str(self.ass_path),
            "thumbnail_path": str(self.thumbnail_path),
            "metadata_path": str(self.metadata_path),
            "duration_seconds": round(self.duration_seconds, 2),
            "fps": self.fps,
            "motion_verified": self.motion_verified,
            "motion_score": round(self.motion_score, 4),
            "quality_passed": self.quality_passed,
            "quality_issues": self.quality_issues,
            "youtube_status": self.youtube_status,
            "youtube_video_id": self.youtube_video_id,
            "youtube_url": self.youtube_url,
        }


class FunnyStickmanScriptCatalog:
    """Curated collection of physical comedy stories starring BEN and MAX."""

    @staticmethod
    def get_quantum_banana_glitch() -> StickmanStoryScript:
        """Original 30-second slapstick story: The Quantum Banana Glitch."""
        scenes = [
            ComedyScene(
                scene_id="scene_01_hook",
                duration_seconds=7.0,
                title="The Quantum Anti-Gravity Hack",
                narration="Behold! My brand new Quantum Anti-Gravity Gizmo! No more walking, no more traffic, just pure levitation genius!",
                ben_action="idle",
                max_action="watch",
                sfx_cue=None,
                punchline_sub="Behold! My Quantum Anti-Gravity Gizmo!",
                backdrop_theme="studio_dark",
            ),
            ComedyScene(
                scene_id="scene_02_escalation",
                duration_seconds=8.0,
                title="Full Speed Ahead",
                narration="Activating turbo propulsion in three, two, one! Look at this speed, Max! Nothing can possibly stop me now!",
                ben_action="run",
                max_action="panic",
                sfx_cue="whoosh",
                punchline_sub="Nothing can possibly stop me now!",
                backdrop_theme="studio_dark",
            ),
            ComedyScene(
                scene_id="scene_03_slapstick_climax",
                duration_seconds=7.5,
                title="The Banana Slip",
                narration="Wait, is that a banana on the floor?! Whooaaa! My gravity calculations did not account for slippery fruit peelings!",
                ben_action="slip",
                max_action="shock",
                sfx_cue="boing",
                punchline_sub="WHOOOAA! Slippery fruit physics!",
                backdrop_theme="studio_dark",
            ),
            ComedyScene(
                scene_id="scene_04_punchline_outro",
                duration_seconds=7.5,
                title="Reality Check",
                narration="Gravity still works, genius. Next time, invent a shoe that knows how to step over trash. Subscribe for more smart ideas!",
                ben_action="shrug",
                max_action="facepalm",
                sfx_cue="splat",
                punchline_sub="Gravity still works, genius. Subscribe!",
                backdrop_theme="studio_dark",
            ),
        ]
        return StickmanStoryScript(
            story_id="ben_max_quantum_banana",
            title="When Your Anti-Gravity Gizmo Meets a Banana Peel | BEN & MAX",
            topic="Physical comedy, stickman cartoon animation, AI gadgets",
            scenes=scenes,
            format="shorts",
            voice="en-US-ChristopherNeural",
            tags=["funny", "stickman", "cartoon", "animation", "comedy", "shorts", "benx", "humor"],
            description="BEN invents a quantum anti-gravity gizmo, but forgets that banana peel friction still rules the universe! An original funny stickman animation by BENXAUTOMATION.",
        )


class StickmanStoryPipeline:
    """End-to-End generator producing fully verified Stickman animation packages."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or AppConfig()
        self.tts = TTSEngine()
        self.sub_gen = SubtitleGenerator()
        self.validator = MotionValidator(
            ffmpeg_path=self.config.rendering.ffmpeg_path,
            ffprobe_path=self.config.rendering.ffprobe_path,
        )

    def run_pipeline(
        self,
        script: StickmanStoryScript,
        output_dir: Path = Path("output/stickman_sample"),
        burn_subtitles: bool = True,
    ) -> StickmanStoryResult:
        """Execute end-to-end stickman video generation."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        story_id = script.story_id

        log.info("Starting Funny Stickman Story Pipeline: '%s' (%.1fs)", script.title, script.total_duration)

        # 1. Synthesize Audio
        audio_path = out_dir / f"{story_id}_narration.mp3"
        full_text = " ".join(s.narration for s in script.scenes)
        self._synthesize_voice(full_text, audio_path, script.voice)

        # Probe audio duration
        a_info = probe_file(audio_path, ffprobe_path=self.config.rendering.ffprobe_path)
        actual_audio_dur = float(a_info.get("format", {}).get("duration", script.total_duration)) if a_info else script.total_duration

        # 2. Generate Subtitles (SRT, VTT, ASS)
        srt_path = out_dir / f"{story_id}.srt"
        vtt_path = out_dir / f"{story_id}.vtt"
        ass_path = out_dir / f"{story_id}.ass"
        self._build_subtitles(script, actual_audio_dur, srt_path, vtt_path, ass_path)

        # 3. Setup Render Dimensions
        is_shorts = (script.format == "shorts")
        width = 1080 if is_shorts else 1920
        height = 1920 if is_shorts else 1080
        fps = 24

        raw_video_path = out_dir / f"{story_id}_raw.mp4"
        engine = StickmanAnimationEngine(
            width=width,
            height=height,
            fps=fps,
            ffmpeg_path=self.config.rendering.ffmpeg_path,
        )

        # 4. Render Visual Frames + Audio Track
        engine.render_to_mp4(script.scenes, raw_video_path, audio_path=audio_path)

        # 5. Burn-in Subtitles if requested
        final_video_path = out_dir / f"{story_id}.mp4"
        if burn_subtitles and ass_path.is_file():
            self._burn_ass_subtitles(raw_video_path, ass_path, final_video_path)
            if raw_video_path.is_file() and final_video_path != raw_video_path:
                raw_video_path.unlink()
        else:
            if raw_video_path != final_video_path:
                shutil.move(str(raw_video_path), str(final_video_path))

        # 6. Extract Thumbnail
        thumb_path = out_dir / f"{story_id}_thumb.jpg"
        self._extract_thumbnail(final_video_path, thumb_path, offset_sec=min(8.0, script.total_duration * 0.5))

        # 7. Quality & Mathematical Motion Verification
        v_info = probe_file(final_video_path, ffprobe_path=self.config.rendering.ffprobe_path)
        dur = float(v_info.get("format", {}).get("duration", script.total_duration)) if v_info else script.total_duration

        motion_res = self.validator.validate_animation(
            final_video_path,
            expected_width=width,
            expected_height=height,
            min_duration=10.0,
            max_duration=60.0,
            min_motion_score=0.5,
        )

        quality_passed = motion_res.is_valid
        issues = motion_res.reasons

        # 8. Export Metadata JSON
        meta_path = out_dir / f"{story_id}_metadata.json"
        result = StickmanStoryResult(
            story_id=story_id,
            title=script.title,
            format=script.format,
            video_path=final_video_path,
            audio_path=audio_path,
            srt_path=srt_path,
            vtt_path=vtt_path,
            ass_path=ass_path,
            thumbnail_path=thumb_path,
            metadata_path=meta_path,
            duration_seconds=dur,
            fps=fps,
            motion_verified=motion_res.motion_score >= 0.005,
            motion_score=motion_res.motion_score,
            quality_passed=quality_passed,
            quality_issues=issues,
        )

        meta_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        log.info("Stickman pipeline complete: %s (Motion Score: %.4f)", final_video_path, motion_res.motion_score)
        return result

    def _synthesize_voice(self, text: str, audio_path: Path, voice: str) -> None:
        """Synthesize voice using TTSEngine."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(self.tts.synthesize, text, audio_path, voice=voice).result()
        else:
            self.tts.synthesize(text, audio_path, voice=voice)

    def _build_subtitles(
        self,
        script: StickmanStoryScript,
        total_duration: float,
        srt_out: Path,
        vtt_out: Path,
        ass_out: Path,
    ) -> None:
        """Create synchronized SRT, VTT, and styled ASS subtitles."""
        srt_blocks: List[str] = []
        vtt_blocks: List[str] = ["WEBVTT\n"]
        ass_events: List[str] = []

        cur_t = 0.0
        idx = 1
        is_shorts = (script.format == "shorts")
        margin_v = 330 if is_shorts else 75
        font_size = 54 if is_shorts else 42

        for sc in script.scenes:
            st = cur_t
            et = cur_t + sc.duration_seconds
            text = sc.punchline_sub if sc.punchline_sub else sc.narration

            # Format times
            sh, sm, ss, sms = int(st // 3600), int((st % 3600) // 60), int(st % 60), int((st - int(st)) * 1000)
            eh, em, es, ems = int(et // 3600), int((et % 3600) // 60), int(et % 60), int((et - int(et)) * 1000)

            srt_blocks.append(f"{idx}\n{sh:02d}:{sm:02d}:{ss:02d},{sms:03d} --> {eh:02d}:{em:02d}:{es:02d},{ems:03d}\n{text}\n")
            vtt_blocks.append(f"{sh:02d}:{sm:02d}:{ss:02d}.{sms:03d} --> {eh:02d}:{em:02d}:{es:02d}.{ems:03d}\n{text}\n")

            ass_st = f"{sh}:{sm:02d}:{ss:02d}.{int(sms / 10):02d}"
            ass_et = f"{eh}:{em:02d}:{es:02d}.{int(ems / 10):02d}"
            ass_events.append(f"Dialogue: 0,{ass_st},{ass_et},Default,,0,0,0,,{text}")

            cur_t = et
            idx += 1

        srt_out.write_text("\n".join(srt_blocks), encoding="utf-8")
        vtt_out.write_text("\n".join(vtt_blocks), encoding="utf-8")

        res_x = 1080 if is_shorts else 1920
        res_y = 1920 if is_shorts else 1080

        ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {res_x}
PlayResY: {res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,1.5,2,30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        ass_out.write_text(ass_header + "\n".join(ass_events) + "\n", encoding="utf-8")

    def _burn_ass_subtitles(self, in_video: Path, ass_file: Path, out_video: Path) -> None:
        """Burn styled ASS subtitles into video using FFmpeg libass."""
        ass_escaped = str(ass_file.resolve()).replace("\\", "/").replace(":", "\\:")
        cmd = [
            self.config.rendering.ffmpeg_path,
            "-y",
            "-i", str(in_video),
            "-vf", f"subtitles='{ass_escaped}'",
            "-c:a", "copy",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            str(out_video),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            log.warning("Subtitle burn-in failed, falling back to direct copy: %s", res.stderr[-500:])
            shutil.copy2(str(in_video), str(out_video))

    def _extract_thumbnail(self, video_path: Path, thumb_out: Path, offset_sec: float = 8.0) -> None:
        """Extract crisp JPEG thumbnail using FFmpeg."""
        cmd = [
            self.config.rendering.ffmpeg_path,
            "-y",
            "-ss", f"{offset_sec:.2f}",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_out),
        ]
        subprocess.run(cmd, capture_output=True, text=True)
