"""Motion and quality validator for animated videos.

Mathematically verifies that rendered MP4s contain genuine character/scene movement
and rejects static-image-only or corrupt outputs.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class MotionValidationResult:
    is_valid: bool
    motion_score: float
    total_frames_sampled: int
    moving_scene_transitions: int
    duration_seconds: float
    width: int
    height: int
    decode_passed: bool
    reasons: list[str]


class MotionValidator:
    """Verifies that an MP4 contains genuine multi-scene animation and zero stream errors."""

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe") -> None:
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

    def inspect_stream(self, video_path: Path) -> dict:
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_entries", "stream=width,height,r_frame_rate,duration,nb_frames:format=duration",
            "-of", "json",
            str(video_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)

    def verify_full_decode(self, video_path: Path) -> bool:
        cmd = [
            self.ffmpeg_path,
            "-v", "error",
            "-i", str(video_path),
            "-f", "null",
            "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0 and len(res.stderr.strip()) == 0

    def compute_motion_score(self, video_path: Path, sample_interval_sec: float = 1.0) -> Tuple[float, int, int]:
        """Extract frames at 1s intervals and compute mean inter-frame pixel differences."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            frame_pattern = tmp_path / "sample_%04d.png"

            # Extract 1 frame per second
            cmd = [
                self.ffmpeg_path,
                "-v", "error",
                "-i", str(video_path),
                "-vf", f"fps=1/{sample_interval_sec}",
                str(frame_pattern),
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            extracted_frames = sorted(list(tmp_path.glob("sample_*.png")))
            if len(extracted_frames) < 2:
                return 0.0, len(extracted_frames), 0

            deltas: list[float] = []
            significant_moves = 0

            prev_arr: Optional[np.ndarray] = None
            for f in extracted_frames:
                with Image.open(f) as img:
                    arr = np.array(img.convert("L"), dtype=np.float32)

                if prev_arr is not None:
                    # Normalized mean absolute difference [0.0 - 100.0%]
                    diff = np.mean(np.abs(arr - prev_arr)) / 255.0 * 100.0
                    deltas.append(float(diff))
                    if diff > 1.5:  # Significant movement threshold
                        significant_moves += 1
                prev_arr = arr

            avg_delta = float(np.mean(deltas)) if deltas else 0.0
            return avg_delta, len(extracted_frames), significant_moves

    def validate_animation(
        self,
        video_path: Path,
        expected_width: int = 1080,
        expected_height: int = 1920,
        min_duration: float = 25.0,
        max_duration: float = 45.0,
        min_motion_score: float = 1.0,
    ) -> MotionValidationResult:
        reasons: list[str] = []

        if not video_path.is_file() or video_path.stat().st_size == 0:
            return MotionValidationResult(
                is_valid=False,
                motion_score=0.0,
                total_frames_sampled=0,
                moving_scene_transitions=0,
                duration_seconds=0.0,
                width=0,
                height=0,
                decode_passed=False,
                reasons=["Video file does not exist or is empty."],
            )

        # 1. Full decode test
        decode_pass = self.verify_full_decode(video_path)
        if not decode_pass:
            reasons.append("FFmpeg decode reported stream errors.")

        # 2. Probe stream metadata
        meta = self.inspect_stream(video_path)
        streams = meta.get("streams", [])
        video_stream = next((s for s in streams if "width" in s and s.get("width")), {})
        w = int(video_stream.get("width", 0))
        h = int(video_stream.get("height", 0))
        dur_str = meta.get("format", {}).get("duration") or video_stream.get("duration", "0")
        dur = float(dur_str)

        if w != expected_width or h != expected_height:
            reasons.append(f"Invalid dimensions {w}x{h}, expected {expected_width}x{expected_height}.")

        if not (min_duration <= dur <= max_duration):
            reasons.append(f"Duration {dur:.2f}s is out of range [{min_duration:.1f}s - {max_duration:.1f}s].")

        # 3. Motion score calculation
        motion_score, samples, moves = self.compute_motion_score(video_path)
        if motion_score < min_motion_score or moves < 3:
            reasons.append(
                f"Motion score {motion_score:.2f}% (significant moves {moves}) is below threshold {min_motion_score}%. "
                "Output appears to be a static image or lacks genuine character animation."
            )

        is_valid = len(reasons) == 0
        return MotionValidationResult(
            is_valid=is_valid,
            motion_score=motion_score,
            total_frames_sampled=samples,
            moving_scene_transitions=moves,
            duration_seconds=dur,
            width=w,
            height=h,
            decode_passed=decode_pass,
            reasons=reasons,
        )

    # Convenience alias for validate
    validate = validate_animation

