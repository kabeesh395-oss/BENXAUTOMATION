"""CLI entrypoint for BENXAUTOMATION MVP."""

import argparse
import sys
from pathlib import Path

from benxautomation.config import AppConfig, load_config
from benxautomation.logger import get_logger
from benxautomation.pipeline import VideoPipeline

log = get_logger("benxautomation.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benxautomation",
        description="BENXAUTOMATION — Modular YouTube Video Automation MVP",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--asset",
        "-a",
        type=Path,
        required=True,
        help="Path to input image or video asset.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("output"),
        help="Directory to save rendered videos (default: output/).",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=None,
        help="Override video duration in seconds.",
    )
    parser.add_argument(
        "--manifest",
        "-m",
        type=Path,
        default=None,
        help="Path to asset license manifest YAML.",
    )
    parser.add_argument(
        "--topic",
        "-t",
        type=str,
        default=None,
        help="Video topic or subject text (used directly as narration text when --script is not provided).",
    )
    parser.add_argument(
        "--script",
        "-s",
        type=str,
        default=None,
        help="Custom narration script text.",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        help="Voice name for TTS synthesis (default: en-US-AriaNeural).",
    )
    parser.add_argument(
        "--no-subtitles",
        action="store_true",
        help="Disable automatic subtitle generation.",
    )
    parser.add_argument(
        "--shorts-only",
        action="store_true",
        help="Render only Shorts (9:16).",
    )
    parser.add_argument(
        "--longform-only",
        action="store_true",
        help="Render only Long-form (16:9).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config) if args.config else AppConfig()
    except Exception as exc:
        log.error("Configuration error: %s", exc)
        return 1

    pipeline = VideoPipeline(config)
    render_shorts = not args.longform_only
    render_longform = not args.shorts_only
    script_text = args.script or args.topic

    try:
        res = pipeline.run(
            asset_path=args.asset,
            output_dir=args.output_dir,
            duration_seconds=args.duration,
            script_text=script_text,
            voice_name=args.voice,
            enable_subtitles=not args.no_subtitles,
            render_shorts=render_shorts,
            render_longform=render_longform,
            manifest_path=args.manifest,
        )
        if res.audio_path:
            log.info("Generated Narration: %s", res.audio_path)
        if res.subtitle_path:
            log.info("Generated Subtitles: %s", res.subtitle_path)
        if res.shorts_result:
            log.info("Rendered Shorts: %s", res.shorts_result.output_path)
        if res.longform_result:
            log.info("Rendered Longform: %s", res.longform_result.output_path)
        return 0
    except Exception as exc:
        log.error("Pipeline failure: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
