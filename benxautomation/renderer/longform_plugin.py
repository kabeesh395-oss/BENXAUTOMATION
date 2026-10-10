"""Long-form renderer plugin — generates 16:9 landscape videos."""

from __future__ import annotations

from pathlib import Path

from benxautomation.config import LongformConfig
from benxautomation.errors import AssetError, RenderingError
from benxautomation.logger import get_logger
from benxautomation.renderer.base import RendererPlugin, RenderResult
from benxautomation.renderer.ffmpeg_utils import run_ffmpeg

log = get_logger(__name__)


class LongformRendererPlugin(RendererPlugin):
    """Render a source image/video into a 16:9 landscape MP4.

    Uses FFmpeg to scale/pad the input into a 1920×1080 video
    with a solid background and centered content.
    """

    def __init__(self, config: LongformConfig, *, ffmpeg_path: str = "ffmpeg"):
        self._cfg = config
        self._ffmpeg_path = ffmpeg_path

    @property
    def format_name(self) -> str:
        return "longform_16x9"

    def render(
        self,
        input_path: Path,
        output_path: Path,
        *,
        duration_seconds: int | None = None,
        audio_path: Path | None = None,
        subtitle_path: Path | None = None,
        scenes: list | None = None,
    ) -> RenderResult:
        dur = duration_seconds or self._cfg.duration_seconds
        w, h = self._cfg.width, self._cfg.height

        output_path.parent.mkdir(parents=True, exist_ok=True)

        fps = self._cfg.fps
        if scenes and len(scenes) > 1:
            for s in scenes:
                p = getattr(s, "asset_path", s)
                if not Path(p).is_file():
                    raise AssetError(f"Scene asset not found: {p}")

            args: list[str] = []
            filter_parts: list[str] = []
            concat_inputs: list[str] = []

            for idx, sc in enumerate(scenes):
                sc_path = getattr(sc, "asset_path", sc)
                sc_dur = getattr(sc, "duration_seconds", float(dur) / len(scenes))
                args.extend(["-framerate", str(fps), "-loop", "1", "-t", f"{sc_dur:.3f}", "-i", str(sc_path)])
                filter_parts.append(
                    f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}[v{idx}]"
                )
                concat_inputs.append(f"[v{idx}]")

            filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(scenes)}:v=1:a=0[vcat]")
            last_v = "[vcat]"

            if subtitle_path and subtitle_path.is_file():
                sub_escaped = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
                filter_parts.append(f"[vcat]subtitles='{sub_escaped}'[vout]")
                last_v = "[vout]"

            if audio_path and audio_path.is_file():
                audio_idx = len(scenes)
                args.extend(["-i", str(audio_path)])
                args.extend(["-filter_complex", ";".join(filter_parts)])
                args.extend(["-map", last_v, "-map", f"{audio_idx}:a", "-c:a", "aac", "-b:a", "128k"])
            else:
                args.extend(["-filter_complex", ";".join(filter_parts)])
                args.extend(["-map", last_v, "-an"])

            total_scene_dur = sum(getattr(sc, "duration_seconds", float(dur) / len(scenes)) for sc in scenes)
            render_dur = max(float(dur), total_scene_dur)

            args.extend([
                "-t", f"{render_dur:.3f}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                str(output_path),
            ])
            log.info("Rendering multi-scene Longform %dx%d, %.3fs (%d scenes, audio=%s, subs=%s) → %s",
                     w, h, render_dur, len(scenes), bool(audio_path), bool(subtitle_path), output_path)
            run_ffmpeg(args, ffmpeg_path=self._ffmpeg_path)
            final_duration = render_dur
        else:
            if not input_path.is_file():
                raise AssetError(f"Input asset not found: {input_path}")

            vf_filters = [
                f"scale={w}:{h}:force_original_aspect_ratio=decrease",
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
            ]

            if subtitle_path and subtitle_path.is_file():
                sub_escaped = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
                vf_filters.append(f"subtitles='{sub_escaped}'")

            args = [
                "-framerate", str(fps),
                "-loop", "1",
                "-i", str(input_path),
            ]

            if audio_path and audio_path.is_file():
                args.extend(["-i", str(audio_path)])
                args.extend(["-c:a", "aac", "-b:a", "128k"])
            else:
                args.append("-an")

            render_dur = float(dur)
            args.extend([
                "-t", f"{render_dur:.3f}",
                "-vf", ",".join(vf_filters),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                str(output_path),
            ])

            log.info("Rendering long-form %dx%d, %.3fs (audio=%s, subs=%s) → %s",
                     w, h, render_dur, bool(audio_path), bool(subtitle_path), output_path)
            run_ffmpeg(args, ffmpeg_path=self._ffmpeg_path)
            final_duration = render_dur

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RenderingError(f"Render produced empty output: {output_path}")

        return RenderResult(
            output_path=output_path,
            width=w,
            height=h,
            duration_seconds=float(final_duration),
            format_name=self.format_name,
        )
