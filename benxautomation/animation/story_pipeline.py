"""End-to-End Story-to-Animation Pipeline for BENX Mascot Productions.

Story input / Script generation
→ Scene breakdown & validation
→ Dialogue & Character action mapping
→ Voice synthesis & Timing synchronization
→ Subtitle generation (SRT & VTT)
→ 2D Mascot frame animation & FFmpeg rendering
→ Mathematical Motion & Media validation
→ Output bundling (MP4, Thumbnail, SRT, VTT, Metadata)
→ Optional YouTube Private Upload Gate
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

from benxautomation.animation.mascot_engine import (
    MascotAnimationEngine,
    MascotRenderConfig,
    MascotScene,
)
from benxautomation.animation.motion_validator import MotionValidationResult, MotionValidator
from benxautomation.config import AppConfig, PublishingConfig
from benxautomation.logger import get_logger
from benxautomation.renderer.ffmpeg_utils import probe_file
from benxautomation.subtitles.generator import SubtitleGenerator
from benxautomation.tts.engine import TTSEngine

log = get_logger(__name__)


@dataclass
class StoryScript:
    story_id: str
    title: str
    topic: str
    scenes: list[MascotScene]
    format: str = "shorts"  # "shorts" (9:16) or "longform" (16:9)
    voice: str = "en-US-ChristopherNeural"
    tags: list[str] = field(default_factory=list)
    description: str = ""
    license_statement: str = "Original character, procedural 2D animation, and script by BENXAUTOMATION."

    def validate(self) -> Tuple[bool, list[str]]:
        errors: list[str] = []
        if not self.title.strip():
            errors.append("Story title cannot be empty.")
        if not self.scenes:
            errors.append("Story must contain at least one scene.")
        for sc in self.scenes:
            valid, sc_errs = sc.validate()
            if not valid:
                errors.extend(sc_errs)
        return len(errors) == 0, errors


@dataclass
class MascotStoryResult:
    story_id: str
    title: str
    format: str
    video_path: Path
    audio_path: Path
    srt_path: Path
    vtt_path: Path
    thumbnail_path: Path
    metadata_path: Path
    duration_seconds: float
    fps: int
    motion_verified: bool
    motion_score: float
    quality_passed: bool
    quality_issues: list[str] = field(default_factory=list)
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
            "thumbnail_path": str(self.thumbnail_path),
            "metadata_path": str(self.metadata_path),
            "duration_seconds": self.duration_seconds,
            "fps": self.fps,
            "motion_verified": self.motion_verified,
            "motion_score": self.motion_score,
            "quality_passed": self.quality_passed,
            "quality_issues": self.quality_issues,
            "youtube_status": self.youtube_status,
            "youtube_video_id": self.youtube_video_id,
            "youtube_url": self.youtube_url,
        }


class LocalStoryScriptCatalog:
    """Provides high-quality offline deterministic story templates when AI models are unavailable."""

    @staticmethod
    def get_preset_story(story_id: str = "ai_quantum_leap", fmt: str = "shorts") -> StoryScript:
        presets = {
            "ai_quantum_leap": StoryScript(
                story_id="ai_quantum_leap",
                title="The Quantum Computing Breakthrough Explained",
                topic="Technology & AI",
                format=fmt,
                tags=["quantum", "ai", "technology", "benx", "future"],
                description="BENX explains how quantum supercomputers will rewrite encryption and AI intelligence.",
                scenes=[
                    MascotScene(
                        scene_id="scene_1_hook",
                        duration_seconds=3.0,
                        dialogue="What happens when computers think in quantum states instead of ones and zeros?",
                        pose="gesture",
                        expression="surprised",
                        view="front",
                        camera_motion="DOLLY_IN_CLOSEUP",
                        theme="cyber_grid",
                        action_text="QUANTUM LEAP",
                    ),
                    MascotScene(
                        scene_id="scene_2_problem",
                        duration_seconds=3.5,
                        dialogue="Traditional chips check one path at a time. Quantum qubits explore every possibility simultaneously.",
                        pose="thinking_chin",
                        expression="serious",
                        view="three_quarter_left",
                        camera_motion="PAN_LEFT_TO_RIGHT",
                        theme="cyber_grid",
                        action_text="PARALLEL QUBITS",
                    ),
                    MascotScene(
                        scene_id="scene_3_solution",
                        duration_seconds=3.5,
                        dialogue="Simulating new medicine that took forty years could now finish in under forty minutes.",
                        pose="pointing_up",
                        expression="excited",
                        view="front",
                        camera_motion="STATIC_MEDIUM",
                        theme="cyber_grid",
                        action_text="INSTANT DISCOVERY",
                    ),
                    MascotScene(
                        scene_id="scene_4_conclusion",
                        duration_seconds=3.0,
                        dialogue="The quantum revolution is already here. Follow BENX for daily high-tech breakdowns!",
                        pose="cheer",
                        expression="happy",
                        view="front",
                        camera_motion="STATIC_MEDIUM",
                        theme="cyber_grid",
                        action_text="STAY CURIOUS",
                    ),
                ],
            ),
            "cyber_security_shield": StoryScript(
                story_id="cyber_security_shield",
                title="Zero Trust Security in 30 Seconds",
                topic="Cybersecurity",
                format=fmt,
                tags=["cybersecurity", "zerotrust", "privacy", "benx"],
                description="BENX breaks down why zero trust architecture is mandatory for modern data protection.",
                scenes=[
                    MascotScene(
                        scene_id="scene_1_hook",
                        duration_seconds=3.0,
                        dialogue="Never trust, always verify. That simple principle protects billions of data records daily.",
                        pose="pointing_right",
                        expression="serious",
                        view="front",
                        camera_motion="DOLLY_IN_CLOSEUP",
                        theme="cyber_grid",
                        action_text="NEVER TRUST",
                    ),
                    MascotScene(
                        scene_id="scene_2_detail",
                        duration_seconds=3.5,
                        dialogue="Old firewalls only guarded the perimeter. Modern zero trust authenticates every single packet.",
                        pose="shrug",
                        expression="confused",
                        view="three_quarter_right",
                        camera_motion="STATIC_MEDIUM",
                        theme="cyber_grid",
                        action_text="MICRO-SEGMENTATION",
                    ),
                    MascotScene(
                        scene_id="scene_3_outro",
                        duration_seconds=3.0,
                        dialogue="Stay protected, encrypt everything, and keep your digital fortress secure with BENX!",
                        pose="gesture",
                        expression="happy",
                        view="front",
                        camera_motion="STATIC_MEDIUM",
                        theme="cyber_grid",
                        action_text="STAY SECURE",
                    ),
                ],
            ),
        }
        return presets.get(story_id, presets["ai_quantum_leap"])

    @staticmethod
    def parse_raw_story_text(title: str, text: str, fmt: str = "shorts") -> StoryScript:
        """Break down raw user story text into structured mascot animation scenes."""
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()] if text.strip() else ["Welcome to BENX automation."]

        poses = ["gesture", "thinking_chin", "pointing_up", "shrug", "cheer"]
        exprs = ["surprised", "serious", "excited", "confused", "happy"]
        views = ["front", "three_quarter_left", "front", "three_quarter_right", "front"]
        cams = ["DOLLY_IN_CLOSEUP", "PAN_LEFT_TO_RIGHT", "STATIC_MEDIUM", "STATIC_MEDIUM", "STATIC_MEDIUM"]

        scenes: list[MascotScene] = []
        for idx, para in enumerate(paragraphs):
            word_count = len(para.split())
            dur = max(2.5, min(8.0, word_count * 0.4))
            scenes.append(
                MascotScene(
                    scene_id=f"scene_{idx + 1}",
                    duration_seconds=round(dur, 2),
                    dialogue=para,
                    pose=poses[idx % len(poses)],
                    expression=exprs[idx % len(exprs)],
                    view=views[idx % len(views)],
                    camera_motion=cams[idx % len(cams)],
                    theme="cyber_grid",
                    action_text=f"PART {idx + 1}",
                )
            )

        safe_id = "".join(c if c.isalnum() else "_" for c in title.lower())[:30].strip("_") or "story"
        return StoryScript(
            story_id=safe_id,
            title=title,
            topic="Custom Story",
            scenes=scenes,
            format=fmt,
            description=f"Original story by BENX: {title}",
        )


class StoryAnimationPipeline:
    """Full production pipeline executing story parsing to validated video bundle."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        output_dir: Path = Path("output/mascot_animated"),
        assets_dir: Path = Path("assets/mascot"),
    ) -> None:
        self.config = config or AppConfig()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir = Path(assets_dir)

        self.tts_engine = TTSEngine()
        self.subtitle_generator = SubtitleGenerator()
        self.validator = MotionValidator(
            ffmpeg_path=self.config.rendering.ffmpeg_path,
            ffprobe_path=self.config.rendering.ffprobe_path,
        )

    def produce_story_animation(
        self,
        script: StoryScript,
        *,
        fps: int = 24,
        upload_private: bool = False,
    ) -> MascotStoryResult:
        """Execute end-to-end production of a mascot story animation."""
        # 1. Validate scene data
        valid, errors = script.validate()
        if not valid:
            raise ValueError(f"Script validation failed for '{script.title}': {'; '.join(errors)}")

        job_dir = self.output_dir / f"{script.story_id}_{script.format}"
        job_dir.mkdir(parents=True, exist_ok=True)

        audio_path = job_dir / f"{script.story_id}_narration.mp3"
        srt_path = job_dir / f"{script.story_id}_subtitles.srt"
        vtt_path = job_dir / f"{script.story_id}_subtitles.vtt"
        video_path = job_dir / f"{script.story_id}.mp4"
        thumb_path = job_dir / f"{script.story_id}_thumbnail.jpg"
        meta_path = job_dir / f"{script.story_id}_metadata.json"

        # 2. Synthesize audio narration
        full_narration = " ".join(sc.dialogue for sc in script.scenes)
        tts_res = self.tts_engine.synthesize(
            full_narration,
            audio_path,
            voice=script.voice,
        )
        audio_dur = tts_res.duration_seconds

        # 3. Align scene durations with speech timing
        total_initial_dur = sum(sc.duration_seconds for sc in script.scenes)
        if audio_dur > 0 and total_initial_dur > 0:
            scale_factor = audio_dur / total_initial_dur
            for sc in script.scenes:
                sc.duration_seconds = max(1.5, round(sc.duration_seconds * scale_factor, 2))

        actual_total_dur = sum(sc.duration_seconds for sc in script.scenes)

        # 4. Generate Subtitles (SRT and VTT)
        self._generate_synced_subtitles(script.scenes, srt_path, vtt_path)

        # 5. Configure Mascot Animation Engine
        render_cfg = (
            MascotRenderConfig.for_shorts(fps=fps)
            if script.format == "shorts"
            else MascotRenderConfig.for_longform(fps=fps)
        )
        render_cfg.ffmpeg_path = self.config.rendering.ffmpeg_path
        render_cfg.ffprobe_path = self.config.rendering.ffprobe_path

        engine = MascotAnimationEngine(config=render_cfg, assets_dir=self.assets_dir)

        # 6. Render Frames and Mux MP4
        engine.render_scenes_to_mp4(
            scenes=script.scenes,
            output_mp4=video_path,
            audio_path=audio_path,
            subtitle_path=srt_path,
        )

        # 7. Extract Thumbnail
        self._extract_thumbnail(video_path, thumb_path, offset_sec=min(1.5, actual_total_dur / 2))

        # 8. Video Motion & Quality Validation
        motion_score, samples, moves = self.validator.compute_motion_score(video_path, sample_interval_sec=1.0)
        motion_ok = motion_score >= 1.0 and moves >= 1

        probe_raw = probe_file(video_path, ffprobe_path=self.config.rendering.ffprobe_path)
        streams = probe_raw.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        fmt = probe_raw.get("format", {})
        dur_val = float(fmt.get("duration") or (video_stream.get("duration") if video_stream else 0.0) or actual_total_dur)

        q_pass = motion_ok and (video_stream is not None)
        q_issues = []
        if not motion_ok:
            q_issues.append(f"Low motion score: {motion_score:.2f}% ({moves} moves)")
        if video_stream is None:
            q_issues.append("No video stream found in rendered MP4")

        # 9. Create Result and Metadata Receipt
        result = MascotStoryResult(
            story_id=script.story_id,
            title=script.title,
            format=script.format,
            video_path=video_path,
            audio_path=audio_path,
            srt_path=srt_path,
            vtt_path=vtt_path,
            thumbnail_path=thumb_path,
            metadata_path=meta_path,
            duration_seconds=dur_val,
            fps=fps,
            motion_verified=motion_ok,
            motion_score=motion_score,
            quality_passed=q_pass,
            quality_issues=q_issues,
        )

        meta_dict = result.to_dict()
        meta_dict["created_at"] = datetime.now(timezone.utc).isoformat()
        meta_dict["license_statement"] = script.license_statement
        meta_dict["tags"] = script.tags
        meta_path.write_text(json.dumps(meta_dict, indent=2), encoding="utf-8")

        # 10. Optional YouTube Private Upload Gate (Strictly Human/Config Gated)
        if upload_private and q_pass:
            self._handle_private_upload(result, script)

        return result

    def _generate_synced_subtitles(self, scenes: list[MascotScene], srt_out: Path, vtt_out: Path) -> None:
        """Create synchronized SRT and VTT subtitles from scene timestamps."""
        srt_lines: list[str] = []
        vtt_lines: list[str] = ["WEBVTT\n"]

        def _fmt_srt(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int((sec - int(sec)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        def _fmt_vtt(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int((sec - int(sec)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

        cur_t = 0.2
        for idx, sc in enumerate(scenes, start=1):
            end_t = cur_t + sc.duration_seconds
            # SRT
            srt_lines.append(f"{idx}\n{_fmt_srt(cur_t)} --> {_fmt_srt(end_t)}\n{sc.dialogue}\n")
            # VTT
            vtt_lines.append(f"{idx}\n{_fmt_vtt(cur_t)} --> {_fmt_vtt(end_t)}\n{sc.dialogue}\n")
            cur_t = end_t

        srt_out.write_text("\n".join(srt_lines), encoding="utf-8")
        vtt_out.write_text("\n".join(vtt_lines), encoding="utf-8")

    def _extract_thumbnail(self, video_path: Path, thumb_out: Path, offset_sec: float = 1.0) -> None:
        """Extract high-quality JPEG thumbnail using FFmpeg."""
        cmd = [
            self.config.rendering.ffmpeg_path,
            "-y",
            "-ss", f"{offset_sec:.2f}",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_out),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except Exception as exc:
            log.warning("Thumbnail extraction failed: %s", exc)

    def _handle_private_upload(self, result: MascotStoryResult, script: StoryScript) -> None:
        """Safely upload video as PRIVATE to YouTube if authenticated."""
        token_dir = Path.home() / ".benxautomation"
        secret_file = token_dir / "client_secret.json"
        if not secret_file.is_file():
            result.youtube_status = "OAUTH_UNCONFIGURED"
            return

        try:
            from benxautomation.publisher.youtube import YouTubeOAuthManager, YouTubePublisher
            oauth_mgr = YouTubeOAuthManager(secret_file)
            pub_cfg = PublishingConfig(enabled=True, enforce_private=True)
            publisher = YouTubePublisher(pub_cfg, oauth_manager=oauth_mgr)

            desc = (
                f"{script.title}\n\n"
                f"{script.description}\n\n"
                f"Starring: BENX (Original 2D Mascot)\n"
                f"License: {script.license_statement}\n\n"
                f"Uploaded as PRIVATE for preview & quality approval."
            )
            up_res = publisher.upload(
                result.video_path,
                title=script.title[:95],
                description=desc,
                tags=script.tags,
                privacy_status="private",
            )
            vid_id = str(up_res.get("video_id") or up_res.get("id") or "")
            if vid_id:
                result.youtube_status = "UPLOADED_PRIVATE"
                result.youtube_video_id = vid_id
                result.youtube_url = f"https://youtu.be/{vid_id}"
                log.info("Uploaded mascot video to YouTube privately: %s", result.youtube_url)
        except Exception as exc:
            result.youtube_status = f"UPLOAD_ERROR: {exc}"
            log.error("Private upload failed: %s", exc)
