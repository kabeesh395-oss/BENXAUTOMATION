"""CLI entrypoint for BENXAUTOMATION topic-to-video automation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from benxautomation.config import AppConfig, load_config
from benxautomation.errors import BenxError, ScriptGenerationError
from benxautomation.logger import get_logger
from benxautomation.pipeline import PipelineResult, VideoPipeline

log = get_logger("benxautomation.cli")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with comprehensive topic-to-video options."""
    parser = argparse.ArgumentParser(
        prog="benxautomation",
        description="BENXAUTOMATION — Modular Topic-to-Video Automation System",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--topic",
        "-t",
        type=str,
        default=None,
        help="Topic for AI script generation.",
    )
    parser.add_argument(
        "--script",
        "-s",
        type=str,
        default=None,
        help="Manual narration script text (takes precedence over --topic).",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=None,
        help="Target video duration in seconds.",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        help="Voice name for TTS synthesis (e.g., en-US-AriaNeural).",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Language code (e.g., en, es, fr).",
    )
    parser.add_argument(
        "--format",
        choices=["shorts", "longform", "both"],
        default="both",
        help="Video output format: shorts (9:16), longform (16:9), or both (default: both).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("output"),
        help="Directory to save rendered videos and artifacts (default: output/).",
    )
    parser.add_argument(
        "--no-subtitles",
        action="store_true",
        help="Disable automatic subtitle generation.",
    )
    parser.add_argument(
        "--no-music",
        action="store_true",
        help="Disable background music mixing.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Script generation provider (e.g., openai, fallback).",
    )
    parser.add_argument(
        "--asset",
        "-a",
        type=Path,
        default=None,
        help="Path to specific image/video asset override.",
    )
    parser.add_argument(
        "--manifest",
        "-m",
        type=Path,
        default=None,
        help="Path to asset license manifest YAML.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate parameters, credentials, and plan without rendering video.",
    )

    # Legacy flags for backward compatibility
    parser.add_argument(
        "--shorts-only",
        action="store_true",
        help="Legacy flag: Render only Shorts (9:16).",
    )
    parser.add_argument(
        "--longform-only",
        action="store_true",
        help="Legacy flag: Render only Long-form (16:9).",
    )

    return parser


def print_summary_report(result: PipelineResult) -> None:
    """Print clean summary with exact paths of all generated artifacts."""
    print("\n" + "=" * 60)
    print("BENXAUTOMATION — Execution Summary")
    print("=" * 60)

    if result.script_result:
        src = "AI Generated" if result.script_result.is_ai_generated else "Manual / Fallback"
        print(f"Topic:            {result.script_result.topic}")
        print(f"Script Source:    {src} (provider: {result.script_result.provider})")
        if result.script_path:
            print(f"Script File:      {result.script_path}")

    if result.scene_plan_path:
        print(f"Scene Plan:       {result.scene_plan_path}")
        if result.visual_plan:
            print(f"Scenes Planned:   {len(result.visual_plan.scenes)} scenes ({result.visual_plan.distinct_assets_count} distinct assets)")
            print(f"Visual Motion:    2D Dynamic Motion ({', '.join(s.motion_effect for s in result.visual_plan.scenes)})")

    if result.narration_path:
        print(f"Narration Audio:  {result.narration_path}")

    if result.bgm_path:
        print(f"BGM Mixed:        {result.bgm_path}")
    elif result.audio_path and result.audio_path != result.narration_path:
        print(f"Audio Output:     {result.audio_path}")

    if result.subtitle_path:
        print(f"Subtitles:        {result.subtitle_path}")

    if result.shorts_result:
        meta = result.shorts_metadata
        dur_str = f"{meta.duration_seconds:.2f}s" if meta else "unknown"
        print(f"Shorts Video:     {result.shorts_result.output_path} ({dur_str}, 1080x1920)")

    if result.longform_result:
        meta = result.longform_metadata
        dur_str = f"{meta.duration_seconds:.2f}s" if meta else "unknown"
        print(f"Long-form Video:  {result.longform_result.output_path} ({dur_str}, 1920x1080)")

    if result.quality_report_path:
        print(f"Quality Report:   {result.quality_report_path}")

    q = getattr(result, "quality_report", None)
    if not q and result.quality_report_path and result.quality_report_path.is_file():
        try:
            q = json.loads(result.quality_report_path.read_text(encoding="utf-8"))
        except Exception:
            q = None

    if q:
        render_ok = q.get("render_success", False)
        content_ok = q.get("content_quality_passed", False)
        issues = q.get("quality_issues", []) or q.get("content_issues", []) or q.get("render_issues", [])

        print("-" * 60)
        print(f"Render Validation:  {'PASS' if render_ok else 'FAIL'}")
        if content_ok:
            print("Content Quality:    PASS")
        else:
            print("Content Quality:    UNVERIFIED DRAFT / OUTLINE (Verification required)")
        if issues:
            print("Quality Notes:")
            for issue in issues:
                print(f"  - {issue}")
    elif hasattr(result, "render_success"):
        print("-" * 60)
        print(f"Render Validation:  {'PASS' if result.render_success else 'FAIL'}")
        if getattr(result, "content_quality_passed", False):
            print("Content Quality:    PASS")
        else:
            print("Content Quality:    UNVERIFIED DRAFT / OUTLINE (Verification required)")
        issues = getattr(result, "quality_issues", [])
        if issues:
            print("Quality Notes:")
            for issue in issues:
                print(f"  - {issue}")

    print("=" * 60 + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config) if args.config else AppConfig()
    except Exception as exc:
        log.error("Configuration error: %s", exc)
        return 1

    # Format resolution
    render_shorts = True
    render_longform = True
    if args.shorts_only or args.format == "shorts":
        render_shorts = True
        render_longform = False
    elif args.longform_only or args.format == "longform":
        render_shorts = False
        render_longform = True

    # Precedence check: if neither topic nor script nor asset provided
    if not args.topic and not args.script and not args.asset:
        log.error(
            "Missing input: Please provide --topic <topic> or --script <text> "
            "(or --asset <file> for single-asset video)."
        )
        return 1

    if args.dry_run:
        log.info("Dry-run requested: validating inputs and configuration...")
        if args.topic and not args.script and (args.provider == "openai" or config.script.provider == "openai"):
            import os
            key_var = config.script.api_key_env
            if not os.environ.get(key_var):
                log.error(
                    "Dry-run error: %s environment variable is not set. "
                    "Set %s or use --script for manual narration.",
                    key_var, key_var
                )
                return 1
        log.info("Dry-run validation successful.")
        return 0

    pipeline = VideoPipeline(config)

    try:
        res = pipeline.run(
            asset_path=args.asset,
            output_dir=args.output_dir,
            topic=args.topic,
            script_text=args.script,
            duration_seconds=args.duration,
            voice_name=args.voice,
            language=args.language,
            enable_subtitles=not args.no_subtitles,
            enable_music=not args.no_music,
            render_shorts=render_shorts,
            render_longform=render_longform,
            manifest_path=args.manifest,
            provider_name=args.provider,
        )

        print_summary_report(res)
        return 0

    except ScriptGenerationError as exc:
        log.error("Script generation failed: %s", exc)
        print(f"\n[ERROR] Script generation failed: {exc}", file=sys.stderr)
        print("Tip: If you do not have an AI API key configured, use --script \"Your custom narration\" instead.\n", file=sys.stderr)
        return 2

    except BenxError as exc:
        log.error("Pipeline failure: %s", exc)
        print(f"\n[ERROR] Pipeline failure: {exc}\n", file=sys.stderr)
        return 2

    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=True)
        print(f"\n[ERROR] Unexpected error: {exc}\n", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
