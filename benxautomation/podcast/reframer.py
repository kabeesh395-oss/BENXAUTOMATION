"""Video reframing and rendering engine for Podcast-to-Shorts.

Renders vertical 9:16 (1080x1920) real MP4 videos using FFmpeg with blur-padded
or center-cropped reframing, preserving authentic speaker appearance and audio.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from benxautomation.logger import get_logger
from benxautomation.podcast.errors import PodcastRenderingError
from benxautomation.podcast.models import (
    HighlightCandidate,
    PodcastPipelineConfig,
    SubtitleStyle,
)
from benxautomation.renderer.ffmpeg_utils import find_ffmpeg, probe_file, run_ffmpeg

log = get_logger(__name__)


def _escape_ffmpeg_filter_path(path: Path) -> str:
    """Format path for FFmpeg filter arguments (especially on Windows)."""
    p_str = str(path.resolve()).replace("\\", "/")
    # Escape colons for drive letters in Windows (e.g. C: -> C\:)
    p_str = p_str.replace(":", "\\:")
    return p_str


class VideoReframer:
    """Reframes horizontal video to vertical 9:16 (1080x1920) Shorts."""

    def __init__(self, config: Optional[PodcastPipelineConfig] = None) -> None:
        self.config = config or PodcastPipelineConfig()

    def render_short_clip(
        self,
        source_video: Path,
        candidate: HighlightCandidate,
        output_mp4: Path,
        *,
        subtitles_file: Optional[Path] = None,
        style: Optional[SubtitleStyle] = None,
        reframing_mode: Optional[str] = None,
    ) -> Path:
        """Render a vertical 9:16 short clip from source video."""
        if not source_video.is_file():
            raise PodcastRenderingError(f"Source video file not found: {source_video}")

        mode = reframing_mode or self.config.reframing_mode
        w = self.config.vertical_width
        h = self.config.vertical_height
        fps = self.config.fps

        start_s = candidate.start_seconds
        dur_s = candidate.duration

        output_mp4.parent.mkdir(parents=True, exist_ok=True)

        # 1. Inspect source streams for video presence and aspect ratio
        meta = probe_file(source_video)
        streams = meta.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)

        input_args: list[str] = []
        if video_stream:
            in_w = int(video_stream.get("width", 1920))
            in_h = int(video_stream.get("height", 1080))
            aspect = in_w / max(1, in_h)

            if aspect <= 0.65:
                # Already portrait (e.g. 9:16)
                filter_v = (
                    f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[vbase]"
                )
            elif mode == "center_crop":
                filter_v = (
                    f"[0:v]crop=ih*9/16:ih:(iw-ow)/2:0,"
                    f"scale={w}:{h}:flags=bicubic,setsar=1,fps={fps}[vbase]"
                )
            else:  # "blur_pad"
                filter_v = (
                    f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                    f"crop={w}:{h},boxblur=25:5[bg];"
                    f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
                    f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={fps}[vbase]"
                )
            input_args = ["-ss", f"{start_s:.3f}", "-t", f"{dur_s:.3f}", "-i", str(source_video)]
            map_a = "0:a?"
        else:
            # Audio-only source: construct ambient visual card background
            filter_v = (
                f"color=c=0x0b0f19:s={w}x{h}:r={fps}:d={dur_s:.3f}[bg];"
                f"[bg]drawbox=x=80:y=200:w={w-160}:h={h-400}:color=0x1e293b@0.8:t=fill[vbase]"
            )
            input_args = [
                "-ss", f"{start_s:.3f}", "-t", f"{dur_s:.3f}", "-i", str(source_video),
                "-f", "lavfi", "-t", f"{dur_s:.3f}", "-i", f"color=c=0x0b0f19:s={w}x{h}:r={fps}"
            ]
            filter_v = (
                f"[1:v]drawbox=x=80:y=200:w={w-160}:h={h-400}:color=0x1e293b@0.8:t=fill[vbase]"
            )
            map_a = "0:a?"

        # Subtitle burning stage
        final_video_label = "[vbase]"
        if subtitles_file and subtitles_file.is_file():
            try:
                esc_path = _escape_ffmpeg_filter_path(subtitles_file)
                # Use subtitles or ass filter
                if subtitles_file.suffix.lower() == ".ass":
                    sub_filter = f"{final_video_label}ass='{esc_path}'[vout]"
                else:
                    sub_filter = f"{final_video_label}subtitles='{esc_path}'[vout]"
                full_filter = f"{filter_v};{sub_filter}"
                map_v = "[vout]"
            except Exception as e:
                log.warning("Could not build subtitle filter (%s); rendering clean video", e)
                full_filter = filter_v
                map_v = "[vbase]"
        else:
            full_filter = filter_v
            map_v = "[vbase]"

        args = (
            input_args
            + [
                "-filter_complex", full_filter,
                "-map", map_v,
                "-map", map_a,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_mp4),
            ]
        )

        log.info(
            "Rendering Short clip '%s': start=%.1fs, dur=%.1fs, mode=%s -> %s",
            candidate.clip_id,
            start_s,
            dur_s,
            mode,
            output_mp4.name,
        )

        try:
            run_ffmpeg(args)
        except Exception as exc:
            # Fallback if subtitle burning filter failed (e.g. system font configuration)
            if subtitles_file and map_v == "[vout]":
                log.warning("FFmpeg subtitle burning failed. Retrying without burned subtitles...")
                clean_args = [
                    "-ss", f"{start_s:.3f}",
                    "-t", f"{dur_s:.3f}",
                    "-i", str(source_video),
                    "-filter_complex", filter_v,
                    "-map", "[vbase]",
                    "-map", "0:a?",
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "22",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    str(output_mp4),
                ]
                run_ffmpeg(clean_args)
            else:
                raise PodcastRenderingError(f"Rendering failed: {exc}") from exc

        if not output_mp4.is_file() or output_mp4.stat().st_size == 0:
            raise PodcastRenderingError(f"Rendering produced empty output file: {output_mp4}")

        log.info("Successfully rendered MP4 (%d bytes): %s", output_mp4.stat().st_size, output_mp4.name)
        return output_mp4
