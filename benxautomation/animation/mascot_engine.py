"""BENX Mascot 2D Animation Engine.

Renders character-driven 2D animation with continuous movement:
- Layered compositing: head, visor, expressions, visemes, torso, arms
- Micro-motions: harmonic breathing, natural blink cycles, dynamic speech visemes
- Camera dynamics: dolly-in, pan, subtle orbit drift
- Dynamic backdrops: animated cyber grid, floating energy particles, tech HUD
- High-efficiency FFmpeg frame encoding for both 9:16 Shorts and 16:9 Long-form
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from benxautomation.animation.mascot_assets import MascotAssetBuilder

log = logging.getLogger(__name__)


@dataclass
class MascotRenderConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 24
    aspect_ratio: str = "9:16"
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    crf: int = 18
    preset: str = "medium"

    @classmethod
    def for_shorts(cls, fps: int = 24) -> MascotRenderConfig:
        return cls(width=1080, height=1920, fps=fps, aspect_ratio="9:16")

    @classmethod
    def for_longform(cls, fps: int = 24) -> MascotRenderConfig:
        return cls(width=1920, height=1080, fps=fps, aspect_ratio="16:9")


@dataclass
class MascotScene:
    scene_id: str
    duration_seconds: float
    dialogue: str
    pose: str = "idle"
    expression: str = "happy"
    view: str = "front"
    camera_motion: str = "STATIC_MEDIUM"
    theme: str = "cyber_grid"
    action_text: str = ""
    start_time: float = 0.0

    def validate(self) -> Tuple[bool, list[str]]:
        errors: list[str] = []
        if self.duration_seconds <= 0.0:
            errors.append(f"Scene {self.scene_id}: duration must be positive ({self.duration_seconds}s).")
        valid_poses = {"idle", "gesture", "pointing_right", "pointing_up", "thinking_chin", "shrug", "cheer"}
        if self.pose not in valid_poses:
            errors.append(f"Scene {self.scene_id}: unknown pose '{self.pose}'. Expected one of {valid_poses}.")
        valid_exprs = {"happy", "surprised", "confused", "serious", "excited", "sad"}
        if self.expression not in valid_exprs:
            errors.append(f"Scene {self.scene_id}: unknown expression '{self.expression}'. Expected one of {valid_exprs}.")
        valid_views = {"front", "three_quarter_left", "three_quarter_right"}
        if self.view not in valid_views:
            errors.append(f"Scene {self.scene_id}: unknown view '{self.view}'. Expected one of {valid_views}.")
        return len(errors) == 0, errors


class MascotRig:
    """Manages loaded character layer components in memory for fast compositing."""

    def __init__(self, assets_dir: Path = Path("assets/mascot")) -> None:
        self.assets_dir = Path(assets_dir)
        self._ensure_assets()
        self.layers: dict[str, Image.Image] = {}
        self._load_layers()

    def _ensure_assets(self) -> None:
        manifest_file = self.assets_dir / "rig_manifest.json"
        if not manifest_file.is_file():
            builder = MascotAssetBuilder(self.assets_dir)
            builder.generate_all()

    def _load_layers(self) -> None:
        for p in self.assets_dir.glob("*.png"):
            key = p.stem
            try:
                self.layers[key] = Image.open(p).convert("RGBA")
            except Exception as exc:
                log.warning("Could not load mascot layer %s: %s", p, exc)

    def composite_character(
        self,
        pose: str,
        expression: str,
        viseme: str,
        view: str,
        is_blinking: bool,
    ) -> Image.Image:
        """Compose character parts into a single RGBA canvas."""
        char_canvas = Image.new("RGBA", (600, 600), (0, 0, 0, 0))

        # 1. Torso layer
        torso_key = f"torso_{view}" if f"torso_{view}" in self.layers else "torso_front"
        if torso_key in self.layers:
            char_canvas.alpha_composite(self.layers[torso_key])

        # 2. Arms layer
        arm_key = f"arms_{pose}" if f"arms_{pose}" in self.layers else "arms_idle"
        if arm_key in self.layers:
            char_canvas.alpha_composite(self.layers[arm_key])

        # 3. Head Base
        if "head_base" in self.layers:
            char_canvas.alpha_composite(self.layers["head_base"])

        # 4. Visor Plate
        if "visor_plate" in self.layers:
            char_canvas.alpha_composite(self.layers["visor_plate"])

        # 5. Eyes (blink takes priority)
        eye_key = "eyes_blink" if is_blinking else f"eyes_{expression}"
        if eye_key in self.layers:
            char_canvas.alpha_composite(self.layers[eye_key])
        elif "eyes_happy" in self.layers:
            char_canvas.alpha_composite(self.layers["eyes_happy"])

        # 6. Mouth / Viseme
        mouth_key = f"mouth_{viseme}" if f"mouth_{viseme}" in self.layers else "mouth_rest"
        if mouth_key in self.layers:
            char_canvas.alpha_composite(self.layers[mouth_key])

        return char_canvas


class MascotAnimationEngine:
    """Renders animated multi-scene videos featuring the BENX character mascot."""

    def __init__(
        self,
        config: Optional[MascotRenderConfig] = None,
        assets_dir: Path = Path("assets/mascot"),
    ) -> None:
        self.config = config or MascotRenderConfig.for_shorts()
        self.assets_dir = Path(assets_dir)
        self.rig = MascotRig(self.assets_dir)

    def _determine_viseme(self, scene_time: float, has_dialogue: bool) -> str:
        """Procedural viseme selection creating natural speech cadence."""
        if not has_dialogue:
            return "rest"

        # Cadence cycle at ~5 syllables/sec
        cycle = (scene_time * 5.0) % 4.0
        if cycle < 1.0:
            return "a"
        elif cycle < 2.0:
            return "e"
        elif cycle < 3.0:
            return "o"
        elif cycle < 3.6:
            return "wide"
        else:
            return "rest"

    def _is_blinking(self, total_time: float) -> bool:
        """Natural human-like blink every 3.2 seconds lasting 120ms."""
        blink_period = 3.2
        phase = total_time % blink_period
        return phase < 0.12

    def render_background(self, theme: str, time_sec: float, width: int, height: int) -> Image.Image:
        """Render animated dynamic procedural background with moving grid and particles."""
        bg = Image.new("RGBA", (width, height), (5, 8, 17, 255))
        draw = ImageDraw.Draw(bg)

        # 1. Subtle radial gradient glow in center
        cx, cy = width // 2, height // 2
        for r in range(min(width, height) // 2, 0, -40):
            alpha = int(25 * (1.0 - r / (min(width, height) / 2)))
            draw.ellipse(
                [(cx - r, cy - r), (cx + r, cy + r)],
                fill=(0, 242, 254, alpha),
            )

        # 2. Dynamic perspective grid / horizontal sweep
        grid_offset = int((time_sec * 60) % 80)
        grid_color = (28, 37, 65, 120)
        teal_accent = (0, 242, 254, 80)

        # Horizontal scan lines
        for y in range(grid_offset, height, 80):
            draw.line([(0, y), (width, y)], fill=grid_color, width=1)

        # Vertical tech lines
        for x in range(0, width, 120):
            draw.line([(x, 0), (x, height)], fill=grid_color, width=1)

        # 3. Floating energy particles (guarantees frame-to-frame pixel delta)
        np.random.seed(42)  # Deterministic particle seeds
        num_particles = 35
        for i in range(num_particles):
            base_x = (i * 97) % width
            base_y = (i * 131) % height
            # Drift upward and horizontally with harmonic wave
            drift_y = (base_y - time_sec * 45 * ((i % 3) + 1)) % height
            drift_x = (base_x + math.sin(time_sec * 1.5 + i) * 20) % width
            size = 3 + (i % 4)
            color = teal_accent if (i % 2 == 0) else (79, 172, 254, 90)
            draw.ellipse(
                [(drift_x, drift_y), (drift_x + size, drift_y + size)],
                fill=color,
            )

        return bg

    def render_frame(
        self,
        scene: MascotScene,
        scene_time: float,
        global_time: float,
    ) -> Image.Image:
        """Render a single high-definition animation frame."""
        width = self.config.width
        height = self.config.height

        # 1. Render animated backdrop
        frame = self.render_background(scene.theme, global_time, width, height)

        # 2. Compute character dynamic states
        # Harmonic breathing oscillation: ±6 pixels vertical movement
        breath_y = math.sin(global_time * 2.0 * math.pi * 0.8) * 6.0
        breath_squash = 1.0 + (math.sin(global_time * 2.0 * math.pi * 0.8) * 0.015)

        blinking = self._is_blinking(global_time)
        viseme = self._determine_viseme(scene_time, bool(scene.dialogue.strip()))

        # 3. Composite character rig
        char_img = self.rig.composite_character(
            pose=scene.pose,
            expression=scene.expression,
            viseme=viseme,
            view=scene.view,
            is_blinking=blinking,
        )

        # Apply squash & stretch and scale for canvas
        base_char_scale = 1.45 if self.config.aspect_ratio == "9:16" else 1.2
        target_w = int(char_img.width * base_char_scale)
        target_h = int(char_img.height * base_char_scale * breath_squash)
        scaled_char = char_img.resize((target_w, target_h), Image.Resampling.BILINEAR)

        # 4. Camera Dynamics (Dolly-in / Pan / Static)
        cam_zoom = 1.0
        cam_pan_x = 0.0
        progress = min(1.0, max(0.0, scene_time / max(0.1, scene.duration_seconds)))

        if scene.camera_motion == "DOLLY_IN_CLOSEUP":
            cam_zoom = 1.0 + (progress * 0.15)  # 1.0x -> 1.15x
        elif scene.camera_motion == "PAN_LEFT_TO_RIGHT":
            cam_pan_x = (progress - 0.5) * 60.0  # -30px to +30px

        if cam_zoom != 1.0:
            zw = int(scaled_char.width * cam_zoom)
            zh = int(scaled_char.height * cam_zoom)
            scaled_char = scaled_char.resize((zw, zh), Image.Resampling.BILINEAR)

        # 5. Position character on screen
        char_x = int((width - scaled_char.width) / 2 + cam_pan_x)
        char_base_y = int(height * 0.32) if self.config.aspect_ratio == "9:16" else int(height * 0.15)
        char_y = int(char_base_y + breath_y)

        # Paste character onto background
        frame.alpha_composite(scaled_char, (char_x, char_y))

        # 6. Render UI / Action text overlay if specified
        if scene.action_text:
            overlay_draw = ImageDraw.Draw(frame)
            banner_w = int(width * 0.85)
            bx1 = (width - banner_w) // 2
            bx2 = bx1 + banner_w
            by1 = int(height * 0.78)
            by2 = by1 + 75
            overlay_draw.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=18, fill=(11, 19, 43, 220), outline=(0, 242, 254, 255), width=3)
            # Center action text
            overlay_draw.text((bx1 + 30, by1 + 24), scene.action_text.upper(), fill=(255, 255, 255, 255))

        return frame.convert("RGB")

    def render_scenes_to_mp4(
        self,
        scenes: list[MascotScene],
        output_mp4: Path,
        audio_path: Optional[Path] = None,
        subtitle_path: Optional[Path] = None,
    ) -> Path:
        """Render complete multi-scene animated video to MP4 using FFmpeg."""
        output_mp4 = Path(output_mp4)
        output_mp4.parent.mkdir(parents=True, exist_ok=True)

        # 1. Validate scenes
        for sc in scenes:
            valid, errs = sc.validate()
            if not valid:
                raise ValueError(f"Invalid scene configuration: {', '.join(errs)}")

        total_duration = sum(sc.duration_seconds for sc in scenes)
        fps = self.config.fps
        total_frames = max(1, math.ceil(total_duration * fps))

        log.info(
            "Rendering BENX Mascot animation: %d scenes, %.2fs duration, %d frames @ %d FPS (%dx%d)...",
            len(scenes),
            total_duration,
            total_frames,
            fps,
            self.config.width,
            self.config.height,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            frames_dir = tmp_path / "frames"
            frames_dir.mkdir(parents=True, exist_ok=True)

            # 2. Render all frames to temporary directory
            cur_frame = 0
            global_time = 0.0

            for scene_idx, scene in enumerate(scenes):
                scene_frames = max(1, math.ceil(scene.duration_seconds * fps))
                for f_idx in range(scene_frames):
                    scene_t = f_idx / fps
                    global_t = global_time + scene_t

                    frame_img = self.render_frame(scene, scene_t, global_t)
                    frame_path = frames_dir / f"frame_{cur_frame:05d}.png"
                    frame_img.save(frame_path, "PNG")

                    cur_frame += 1

                global_time += scene.duration_seconds

            # 3. Assemble with FFmpeg
            frame_pattern = str(frames_dir / "frame_%05d.png")
            cmd = [
                self.config.ffmpeg_path,
                "-y",
                "-r", str(fps),
                "-i", frame_pattern,
            ]

            if audio_path and Path(audio_path).is_file():
                cmd.extend(["-i", str(audio_path)])
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            else:
                # Generate silent audio track if none supplied to keep container spec valid
                cmd.extend([
                    "-f", "lavfi",
                    "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-c:a", "aac",
                ])

            # Video encoding parameters
            vf_filters: list[str] = []
            if subtitle_path and Path(subtitle_path).is_file():
                # Escape path for FFmpeg subtitles filter
                sub_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
                vf_filters.append(f"subtitles='{sub_escaped}'")

            if vf_filters:
                cmd.extend(["-vf", ",".join(vf_filters)])

            cmd.extend([
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", self.config.preset,
                "-crf", str(self.config.crf),
                "-t", f"{total_duration:.2f}",
                "-movflags", "+faststart",
                str(output_mp4),
            ])

            log.debug("FFmpeg mascot animation command: %s", " ".join(cmd))
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                log.error("FFmpeg rendering failed: %s", res.stderr)
                raise RuntimeError(f"FFmpeg mascot rendering failed: {res.stderr[:300]}")

        if not output_mp4.is_file() or output_mp4.stat().st_size == 0:
            raise RuntimeError(f"Rendered video missing or empty at {output_mp4}")

        log.info("Successfully rendered BENX mascot animation to %s (size: %d bytes)", output_mp4, output_mp4.stat().st_size)
        return output_mp4
