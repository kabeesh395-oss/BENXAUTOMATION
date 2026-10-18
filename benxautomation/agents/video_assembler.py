"""Agent 5: Master Video Assembler & Quality Inspector.

Renders full 2D cartoon animated sequences, blends smooth crossfades,
burns mobile-safe ASS animated subtitles, muxes audio, and verifies motion score.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from PIL import Image

from benxautomation.agents.animator import CartoonAnimatorAgent
from benxautomation.agents.audio_engineer import AudioMixResult
from benxautomation.agents.script_director import ProductionScript, ScriptScene
from benxautomation.logger import get_logger
from benxautomation.animation.motion_validator import MotionValidationResult, MotionValidator

log = get_logger(__name__)


@dataclass
class AssemblyResult:
    """Output of VideoAssemblerAgent processing."""
    video_path: Path
    ass_path: Path
    duration_seconds: float
    total_frames: int
    fps: int
    resolution: Tuple[int, int]
    motion_validation: MotionValidationResult


class VideoAssemblerAgent:
    """Agent 5: Compiles animated frames, subtitles, and audio into final video."""

    def __init__(self, animator: CartoonAnimatorAgent | None = None):
        self.animator = animator or CartoonAnimatorAgent()
        self.validator = MotionValidator()

    def assemble_video(
        self,
        script: ProductionScript,
        audio_mix: AudioMixResult,
        output_dir: Path,
        fps: int = 24,
    ) -> AssemblyResult:
        """Render complete cartoon animation video and validate broadcast quality."""
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_video = output_dir / f"{script.topic_id}_raw.mp4"
        final_video = output_dir / f"{script.topic_id}_final.mp4"
        ass_path = output_dir / f"{script.topic_id}.ass"
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        is_shorts = (script.format == "shorts")
        target_size = (1080, 1920) if is_shorts else (1920, 1080)
        total_duration = audio_mix.total_duration
        total_frames = int(math.ceil(total_duration * fps))

        log.info(
            "Assembling %s (%s, %dx%d, %d frames @ %dfps, duration: %.2fs)...",
            script.topic_id,
            script.format.upper(),
            target_size[0],
            target_size[1],
            total_frames,
            fps,
            total_duration,
        )

        # 1. Compute frame-by-frame Audio RMS for Lip-Sync
        rms_values = self.animator.compute_audio_rms(audio_mix.wav_path, fps=fps)

        # 2. Render each animated frame with smooth crossfades and lip-sync
        scenes = script.scenes
        timestamps = audio_mix.scene_timestamps

        crossfade_frames = 10  # 0.42s smooth dissolve
        prev_scene_rendered: Image.Image | None = None
        current_scene_idx = 0

        for f_idx in range(total_frames):
            t_current = f_idx / fps

            # Find active scene
            active_scene_idx = 0
            for idx, (s_start, s_end, _) in enumerate(timestamps):
                if s_start <= t_current < s_end:
                    active_scene_idx = idx
                    break
            else:
                active_scene_idx = len(scenes) - 1

            scene = scenes[active_scene_idx]
            s_start, s_end, _ = timestamps[active_scene_idx] if active_scene_idx < len(timestamps) else (0, total_duration, "")
            scene_total_frames = int(max(1, (s_end - s_start) * fps))
            frame_in_scene = int(max(0, (t_current - s_start) * fps))

            # Audio speech detection
            rms = rms_values[f_idx] if f_idx < len(rms_values) else 0.0
            is_speaking = rms > 0.025

            # Render current scene frame
            curr_frame = self.animator.animate_scene_frame(
                scene=scene,
                frame_idx_in_scene=frame_in_scene,
                total_scene_frames=scene_total_frames,
                is_speaking=is_speaking,
                global_frame_idx=f_idx,
                target_size=target_size,
            )

            # Smooth Crossfade on scene transitions
            if active_scene_idx != current_scene_idx:
                current_scene_idx = active_scene_idx
                # We crossed a scene boundary

            if frame_in_scene < crossfade_frames and prev_scene_rendered is not None:
                alpha = frame_in_scene / float(crossfade_frames)
                blended = Image.blend(prev_scene_rendered, curr_frame, alpha)
                frame_to_save = blended
            else:
                frame_to_save = curr_frame

            prev_scene_rendered = curr_frame.copy()

            frame_file = frames_dir / f"frame_{f_idx:05d}.jpg"
            frame_to_save.save(frame_file, quality=92)

        log.info("Successfully rendered %d cartoon animation frames.", total_frames)

        # 3. Create High-Contrast Mobile-Safe ASS Subtitles
        self._generate_ass_subtitles(
            timestamps=timestamps,
            ass_path=ass_path,
            target_size=target_size,
            is_shorts=is_shorts,
        )

        # 4. Compile with FFmpeg: Frames + Audio + Burned Subtitles
        self._encode_ffmpeg_video(
            frames_dir=frames_dir,
            audio_path=audio_mix.mp3_path,
            ass_path=ass_path,
            output_path=final_video,
            fps=fps,
            total_duration=total_duration,
        )

        # 5. Motion Validation & Quality Control
        motion_res = self.validator.validate(
            final_video,
            expected_width=target_size[0],
            expected_height=target_size[1],
            min_duration=10.0,
            max_duration=max(600.0, total_duration + 10.0),
        )
        log.info(
            "Motion Validation: Passed=%s, Score=%.2f%%, Decode=%s",
            motion_res.is_valid,
            motion_res.motion_score,
            motion_res.decode_passed,
        )

        return AssemblyResult(
            video_path=final_video,
            ass_path=ass_path,
            duration_seconds=total_duration,
            total_frames=total_frames,
            fps=fps,
            resolution=target_size,
            motion_validation=motion_res,
        )

    def _generate_ass_subtitles(
        self,
        timestamps: List[Tuple[float, float, str]],
        ass_path: Path,
        target_size: Tuple[int, int],
        is_shorts: bool,
    ) -> None:
        """Create mobile-safe ASS subtitles styled for high YouTube engagement."""
        margin_v = 330 if is_shorts else 80
        font_size = 56 if is_shorts else 48

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_size[0]}
PlayResY: {target_size[1]}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,2,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for start_s, end_s, text in timestamps:
            # Clean and split into bite-sized phrases
            start_fmt = self._format_ass_time(start_s)
            end_fmt = self._format_ass_time(end_s)
            clean_text = text.replace("\n", " ").strip()
            events.append(f"Dialogue: 0,{start_fmt},{end_fmt},Default,,0,0,0,,{clean_text}")

        ass_content = header + "\n".join(events) + "\n"
        ass_path.write_text(ass_content, encoding="utf-8")

    def _format_ass_time(self, seconds: float) -> str:
        """Format seconds to ASS timestamp (H:MM:SS.CC)."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds - int(seconds)) * 100))
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _encode_ffmpeg_video(
        self,
        frames_dir: Path,
        audio_path: Path,
        ass_path: Path,
        output_path: Path,
        fps: int,
        total_duration: float,
    ) -> None:
        """Encode video with burned subtitles and high-quality AAC audio."""
        ass_esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
        vf_filter = f"subtitles='{ass_esc}'"

        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%05d.jpg"),
            "-i",
            str(audio_path),
            "-vf",
            vf_filter,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_path),
        ]
        log.info("Running FFmpeg video assembly...")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            log.warning("Subtitled encode failed, falling back to clean encode: %s", res.stderr[-300:])
            # Fallback encode without burned subtitles
            cmd_fb = [
                "ffmpeg",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(frames_dir / "frame_%05d.jpg"),
                "-i",
                str(audio_path),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(output_path),
            ]
            subprocess.run(cmd_fb, check=True)
