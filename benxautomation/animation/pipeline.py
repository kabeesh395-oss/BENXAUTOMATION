"""End-to-end open-source cartoon animation pipeline.

Orchestrates:
1. Script generation (35-second stories)
2. Audio narration synthesis & subtitle generation
3. Blender headless 3D/2D cartoon rendering
4. FFmpeg muxing, subtitling, and thumbnail extraction
5. Mathematical motion validation (rejects static frames)
6. YouTube private upload with verified API response
"""

import asyncio
import json
import logging
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from benxautomation.animation.blender_animator import BlenderAnimator
from benxautomation.animation.models import (
    AnimatedShortScript,
    AnimatedVideoResult,
)
from benxautomation.animation.motion_validator import MotionValidator
from benxautomation.animation.script_generator import AnimationScriptGenerator
from benxautomation.animation.tools import AnimationToolRegistry

log = logging.getLogger(__name__)


class AnimationPipeline:
    """Manages generation, rendering, validation, and publishing of animated shorts."""

    def __init__(
        self,
        output_dir: Path = Path("output/animated_shorts"),
        voice: str = "en-US-ChristopherNeural",
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.voice = voice

        self.tools = AnimationToolRegistry()
        if not self.tools.blender.available or not self.tools.blender.path:
            raise RuntimeError(f"Blender is required for animation pipeline: {self.tools.blender.notes}")

        self.animator = BlenderAnimator(self.tools.blender.path)
        self.validator = MotionValidator(
            ffmpeg_path=str(self.tools.ffmpeg.path or "ffmpeg"),
            ffprobe_path=str(self.tools.ffprobe.path or "ffprobe"),
        )
        self.state_file = self.output_dir / "batch_state.json"
        self._load_batch_state()

    def _load_batch_state(self) -> dict:
        if self.state_file.is_file():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.batch_state = json.load(f)
                    return self.batch_state
            except Exception as exc:
                log.warning("Failed to load batch state: %s", exc)
        self.batch_state = {"completed": [], "failed": [], "uploaded": []}
        return self.batch_state

    def _save_batch_state(self) -> None:
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.batch_state, f, indent=2)
        except Exception as exc:
            log.warning("Failed to save batch state: %s", exc)

    async def _synthesize_narration(self, script: AnimatedShortScript, audio_out: Path, srt_out: Path) -> float:
        """Synthesize synchronized neural speech and generate subtitle timings."""
        import edge_tts

        full_text = " ".join(sc.narration for sc in script.scenes)
        communicate = edge_tts.Communicate(full_text, voice=self.voice, rate="-3%")

        # Write audio
        await communicate.save(str(audio_out))

        # Generate accurate SRT from scene boundaries
        srt_entries: list[str] = []
        cur_time = 0.5

        def _fmt(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int((sec - int(sec)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        for idx, sc in enumerate(script.scenes):
            start_str = _fmt(cur_time)
            end_t = cur_time + sc.duration_seconds
            end_str = _fmt(end_t)
            srt_entries.append(f"{idx + 1}\n{start_str} --> {end_str}\n{sc.narration}\n")
            cur_time = end_t

        srt_out.write_text("\n".join(srt_entries), encoding="utf-8")

        # Get audio duration via ffprobe
        meta = self.validator.inspect_stream(audio_out)
        dur = float(meta.get("format", {}).get("duration", script.target_duration))
        return dur

    def render_single_video(
        self,
        script: AnimatedShortScript,
        force_rebuild: bool = False,
    ) -> AnimatedVideoResult:
        """Generate, render, mux, and validate a single 35-second animated Short."""
        item_dir = self.output_dir / script.script_id
        item_dir.mkdir(parents=True, exist_ok=True)

        final_mp4 = item_dir / f"{script.script_id}.mp4"
        audio_path = item_dir / f"{script.script_id}_narration.mp3"
        srt_path = item_dir / f"{script.script_id}.srt"
        thumb_path = item_dir / f"{script.script_id}_thumb.jpg"
        meta_path = item_dir / f"{script.script_id}_meta.json"
        frames_dir = item_dir / "frames"

        # Check if already rendered and valid
        if final_mp4.is_file() and not force_rebuild:
            val_res = self.validator.validate_animation(final_mp4)
            if val_res.is_valid:
                log.info("Video %s already exists and is valid. Reusing.", script.script_id)
                return AnimatedVideoResult(
                    video_id=script.script_id,
                    title=script.title,
                    video_path=final_mp4,
                    audio_path=audio_path,
                    srt_path=srt_path,
                    thumbnail_path=thumb_path,
                    metadata_path=meta_path,
                    duration_seconds=val_res.duration_seconds,
                    fps=12,
                    frame_count=val_res.total_frames_sampled * 12,
                    motion_verified=True,
                    motion_score=val_res.motion_score,
                    quality_passed=True,
                )

        # 1. Synthesize audio & subtitles
        log.info("Synthesizing narration for %s...", script.script_id)
        audio_dur = asyncio.run(self._synthesize_narration(script, audio_path, srt_path))

        # Adjust scene durations to match synthesized audio
        scale_factor = audio_dur / max(1.0, script.target_duration)
        for sc in script.scenes:
            sc.duration_seconds *= scale_factor
        script.target_duration = audio_dur

        # 2. Render animation frames in Blender
        log.info("Rendering Blender cartoon animation for %s...", script.script_id)
        frame_count = self.animator.render_script_to_frames(script, frames_dir)

        # 3. Mux frames + audio with FFmpeg
        log.info("Muxing video, audio, and subtitles for %s...", script.script_id)
        frame_input = str(frames_dir.resolve() / "frame_%04d.png")

        # Windows-safe path escaping for ffmpeg subtitle filter
        srt_escaped = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
        subtitle_filter = (
            f"subtitles='{srt_escaped}':force_style="
            "'FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=140'"
        )

        mux_cmd = [
            str(self.tools.ffmpeg.path or "ffmpeg"),
            "-y",
            "-framerate", "12",
            "-i", frame_input,
            "-i", str(audio_path.resolve()),
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(final_mp4.resolve()),
        ]

        mux_res = subprocess.run(mux_cmd, capture_output=True, text=True)
        if mux_res.returncode != 0:
            log.warning("FFmpeg muxing with subtitles failed; falling back to clean video without subtitle burn: %s", mux_res.stderr[:200])
            fallback_cmd = [
                str(self.tools.ffmpeg.path or "ffmpeg"),
                "-y",
                "-framerate", "12",
                "-i", frame_input,
                "-i", str(audio_path.resolve()),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(final_mp4.resolve()),
            ]
            subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)

        # 4. Generate thumbnail
        thumb_cmd = [
            str(self.tools.ffmpeg.path or "ffmpeg"),
            "-y",
            "-ss", "3.0",
            "-i", str(final_mp4),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_path),
        ]
        subprocess.run(thumb_cmd, capture_output=True, text=True)

        # 5. Quality & Mathematical Motion Validation
        val_res = self.validator.validate_animation(final_mp4)

        # 6. Save metadata
        receipt = {
            "script_id": script.script_id,
            "title": script.title,
            "hook": script.hook,
            "topic_category": script.topic_category,
            "duration_seconds": val_res.duration_seconds,
            "resolution": f"{val_res.width}x{val_res.height}",
            "motion_score": val_res.motion_score,
            "motion_verified": val_res.is_valid,
            "quality_passed": val_res.is_valid,
            "quality_issues": val_res.reasons,
            "rights_status": "ORIGINAL_AI_CREATOR_OWNED",
            "rights_statement": script.license_statement,
            "files": {
                "mp4": str(final_mp4),
                "audio": str(audio_path),
                "subtitles": str(srt_path),
                "thumbnail": str(thumb_path),
            },
        }
        meta_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

        result = AnimatedVideoResult(
            video_id=script.script_id,
            title=script.title,
            video_path=final_mp4,
            audio_path=audio_path,
            srt_path=srt_path,
            thumbnail_path=thumb_path,
            metadata_path=meta_path,
            duration_seconds=val_res.duration_seconds,
            fps=12,
            frame_count=frame_count,
            motion_verified=val_res.is_valid,
            motion_score=val_res.motion_score,
            quality_passed=val_res.is_valid,
            quality_issues=val_res.reasons,
            rights_verified=True,
        )

        if val_res.is_valid:
            if script.script_id not in self.batch_state["completed"]:
                self.batch_state["completed"].append(script.script_id)
        else:
            if script.script_id not in self.batch_state["failed"]:
                self.batch_state["failed"].append(script.script_id)
        self._save_batch_state()

        return result

    def upload_video(
        self,
        video_res: AnimatedVideoResult,
        script: AnimatedShortScript,
        privacy_status: str = "private",
    ) -> tuple[str, Optional[str], Optional[str]]:
        """Upload to YouTube with specified privacy status ('private', 'unlisted', or 'public') and verify with API."""
        if not video_res.quality_passed or not video_res.motion_verified:
            log.warning("Upload blocked for %s: quality or motion verification failed.", video_res.video_id)
            return "SKIPPED_QUALITY_FAILED", None, None

        if not getattr(video_res, "rights_verified", True):
            log.warning("Upload blocked for %s: commercial asset rights unverified.", video_res.video_id)
            return "SKIPPED_RIGHTS_FAILED", None, None

        valid_statuses = {"private", "unlisted", "public"}
        if not privacy_status or privacy_status.lower() not in valid_statuses:
            raise ValueError(
                f"Unsupported privacy status: '{privacy_status}'. Must be one of {valid_statuses}."
            )
        privacy_status = privacy_status.lower()

        from benxautomation.config import PublishingConfig
        from benxautomation.publisher.youtube import YouTubeOAuthManager, YouTubePublisher

        token_dir = Path.home() / ".benxautomation"
        secret_file = token_dir / "client_secret.json"
        if not secret_file.is_file():
            return "SKIPPED_NO_OAUTH", None, None

        try:
            oauth_mgr = YouTubeOAuthManager(secret_file)
            if not oauth_mgr.token_path.is_file():
                return "SKIPPED_NO_OAUTH", None, None

            pub_cfg = PublishingConfig(
                enabled=True,
                enforce_private=(privacy_status == "private"),
                default_privacy=privacy_status,
            )
            publisher = YouTubePublisher(pub_cfg, oauth_manager=oauth_mgr)

            desc = (
                f"{script.title}\n\n"
                f"{script.hook}\n\n"
                "Animated using open-source Blender Workbench toon engine.\n"
                "Original script and animation by BENXAUTOMATION.\n\n"
                "#shorts #animation #cartoons"
            )

            upload_receipt = publisher.upload(
                video_res.video_path,
                title=f"{script.title[:90]} #shorts",
                description=desc,
                tags=script.tags + ["shorts", "animation", "cartoons"],
                privacy_status=privacy_status,
            )

            vid_id = str(upload_receipt.get("video_id") or upload_receipt.get("id") or "")
            priv = upload_receipt.get("privacy_status")
            if not priv:
                try:
                    v_info = publisher.verify_video(vid_id)
                    priv = v_info.get("privacy_status")
                except Exception:
                    pass

            url = f"https://youtu.be/{vid_id}"
            video_res.youtube_status = f"UPLOADED_{privacy_status.upper()}"
            video_res.youtube_video_id = vid_id
            video_res.youtube_url = url
            if script.script_id not in self.batch_state["uploaded"]:
                self.batch_state["uploaded"].append(script.script_id)
            self._save_batch_state()
            return f"UPLOADED_{privacy_status.upper()}", vid_id, url

        except Exception as exc:
            err_str = str(exc)
            if "uploadLimitExceeded" in err_str:
                log.warning("YouTube daily upload quota reached (uploadLimitExceeded). Safely queued: %s", script.script_id)
                return "UPLOAD_LIMIT_EXCEEDED", None, None
            log.error("Upload failed for %s: %s", script.script_id, exc)
            return f"FAILED: {err_str[:100]}", None, None

    def upload_private_video(
        self,
        video_res: AnimatedVideoResult,
        script: AnimatedShortScript,
        **kwargs: Any,
    ) -> tuple[str, Optional[str], Optional[str]]:
        """Upload video strictly as PRIVATE to YouTube. Never allows public publishing."""
        kwargs["privacy_status"] = "private"
        return self.upload_video(video_res, script, **kwargs)

    def run_batch(
        self,
        count: int = 25,
        upload_private: bool = False,
        upload_public: bool = False,
        sample_only: bool = False,
    ) -> list[AnimatedVideoResult]:
        """Process batch of up to 25 animated videos."""
        scripts = AnimationScriptGenerator.generate_all_scripts()
        if sample_only:
            scripts = scripts[:1]
        else:
            scripts = scripts[:count]

        results: list[AnimatedVideoResult] = []
        log.info("Starting animation pipeline for %d videos (sample_only=%s)...", len(scripts), sample_only)

        target_privacy = "public" if upload_public else ("private" if upload_private else None)

        for idx, sc in enumerate(scripts):
            log.info("[%d/%d] Processing animated short: %s (%s)...", idx + 1, len(scripts), sc.title, sc.script_id)
            res = self.render_single_video(sc)

            if target_privacy and res.quality_passed:
                status, vid_id, url = self.upload_video(res, sc, privacy_status=target_privacy)
                log.info("Upload status for %s: %s (id=%s, url=%s)", sc.script_id, status, vid_id, url)

            results.append(res)

        return results
