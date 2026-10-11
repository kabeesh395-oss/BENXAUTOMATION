"""Comprehensive quality report generator for repurposed vertical Shorts.

Verifies resolution, duration, audio/video streams, subtitle timing,
and non-empty files via FFprobe.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from benxautomation.logger import get_logger
from benxautomation.renderer.ffmpeg_utils import probe_file

log = get_logger(__name__)


@dataclass
class ClipQualityCheck:
    """Individual quality verification result for a single rendered Short."""
    clip_id: str
    video_path: str
    file_exists: bool = False
    file_size_bytes: int = 0
    duration_seconds: float = 0.0
    expected_duration: float = 0.0
    duration_match: bool = False
    has_video_stream: bool = False
    video_codec: str = ""
    width: int = 0
    height: int = 0
    is_vertical_9_16: bool = False
    has_audio_stream: bool = False
    audio_codec: str = ""
    audio_sample_rate: int = 0
    has_srt_subtitles: bool = False
    has_vtt_subtitles: bool = False
    has_thumbnail: bool = False
    has_metadata_json: bool = False
    passed: bool = False
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RepurposeQualityReporter:
    """Audits rendered Shorts against YouTube Shorts specifications."""

    def __init__(self, tolerance_seconds: float = 2.5) -> None:
        self.tolerance_seconds = tolerance_seconds

    def check_clip(
        self,
        video_path: Path,
        expected_duration: float,
        *,
        clip_id: str = "",
        srt_path: Optional[Path] = None,
        vtt_path: Optional[Path] = None,
        thumbnail_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
    ) -> ClipQualityCheck:
        """Inspect a single rendered MP4 clip using FFprobe and filesystem checks."""
        v_path = Path(video_path)
        cid = clip_id or v_path.stem
        check = ClipQualityCheck(
            clip_id=cid,
            video_path=str(v_path),
            expected_duration=expected_duration,
        )

        # 1. File existence and size check
        if not v_path.is_file():
            check.issues.append(f"Rendered video file not found: {v_path}")
            return check

        check.file_exists = True
        check.file_size_bytes = v_path.stat().st_size
        if check.file_size_bytes == 0:
            check.issues.append("Rendered video file is empty (0 bytes)")
            return check

        # 2. FFprobe stream inspection
        try:
            meta = probe_file(v_path)
        except Exception as exc:
            check.issues.append(f"FFprobe failed to inspect media: {exc}")
            return check

        streams = meta.get("streams", [])
        fmt = meta.get("format", {})

        actual_dur = float(fmt.get("duration", 0.0))
        check.duration_seconds = round(actual_dur, 2)

        if expected_duration > 0:
            diff = abs(actual_dur - expected_duration)
            check.duration_match = diff <= self.tolerance_seconds
            if not check.duration_match:
                check.issues.append(
                    f"Duration mismatch: actual {actual_dur:.1f}s vs expected {expected_duration:.1f}s "
                    f"(tolerance +/-{self.tolerance_seconds:.1f}s)"
                )
        else:
            check.duration_match = actual_dur > 0

        # Video stream check
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        if v_stream:
            check.has_video_stream = True
            check.video_codec = v_stream.get("codec_name", "")
            check.width = int(v_stream.get("width", 0))
            check.height = int(v_stream.get("height", 0))

            # Vertical 9:16 check (1080x1920 or aspect ratio ~ 0.5625)
            if check.height > 0:
                aspect = check.width / check.height
                check.is_vertical_9_16 = aspect <= 0.60
            if not check.is_vertical_9_16:
                check.issues.append(
                    f"Video is not vertical 9:16 format (resolution: {check.width}x{check.height})"
                )
        else:
            check.issues.append("No video stream found in rendered MP4")

        # Audio stream check
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if a_stream:
            check.has_audio_stream = True
            check.audio_codec = a_stream.get("codec_name", "")
            check.audio_sample_rate = int(a_stream.get("sample_rate", 0))
        else:
            check.issues.append("No audio stream found in rendered MP4")

        # Subtitle and auxiliary asset checks
        if srt_path and Path(srt_path).is_file() and Path(srt_path).stat().st_size > 0:
            check.has_srt_subtitles = True
        if vtt_path and Path(vtt_path).is_file() and Path(vtt_path).stat().st_size > 0:
            check.has_vtt_subtitles = True
        if thumbnail_path and Path(thumbnail_path).is_file() and Path(thumbnail_path).stat().st_size > 0:
            check.has_thumbnail = True
        if metadata_path and Path(metadata_path).is_file() and Path(metadata_path).stat().st_size > 0:
            check.has_metadata_json = True

        # Overall verdict
        check.passed = (
            check.file_exists
            and check.file_size_bytes > 0
            and check.has_video_stream
            and check.has_audio_stream
            and check.is_vertical_9_16
            and check.duration_match
        )
        return check

    def generate_report(
        self,
        checks: list[ClipQualityCheck],
        output_json_path: Optional[Path] = None,
    ) -> dict[str, Any]:
        """Compile complete job quality report and optionally write to JSON."""
        total = len(checks)
        passed_count = sum(1 for c in checks if c.passed)
        failed_count = total - passed_count
        overall_pass = total > 0 and failed_count == 0

        report = {
            "overall_status": "PASS" if overall_pass else "FAIL",
            "total_clips": total,
            "passed_clips": passed_count,
            "failed_clips": failed_count,
            "checks": [c.to_dict() for c in checks],
        }

        if output_json_path:
            out_p = Path(output_json_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info("Saved quality report to %s", out_p.name)

        return report
