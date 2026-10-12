"""CLI entrypoint for BENXAUTOMATION topic-to-video automation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from benxautomation.config import AppConfig, load_config
from benxautomation.errors import BenxError, PublishingDisabledError, ScriptGenerationError
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
    parser.add_argument(
        "--workflow",
        choices=["topic", "repurpose", "original", "animated"],
        default=None,
        help="Pipeline workflow: 'topic' (AI topic-to-video), 'repurpose' (long-form to Shorts), 'original' (copyright-safe educational videos), or 'animated' (Blender/Godot cartoon animation).",
    )
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Generate and inspect only a single sample animated video.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=25,
        help="Number of animated videos to generate (default: 25).",
    )
    parser.add_argument(
        "--mode",
        choices=["dry_run", "render_only", "upload_private", "draft"],
        default=None,
        help="Pipeline execution mode: dry_run, render_only, upload_private, or draft.",
    )
    parser.add_argument(
        "--upload-private",
        action="store_true",
        help="Upload rendered videos strictly as PRIVATE to YouTube.",
    )
    parser.add_argument(
        "--upload-public",
        action="store_true",
        help="Upload rendered videos as PUBLIC to YouTube once daily quota permits.",
    )

    # Long-form-to-Shorts repurposing options (Vizard AI-inspired workflow)
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="YouTube video URL or local file path to repurpose into vertical Shorts.",
    )

    parser.add_argument(
        "--clips",
        type=int,
        default=3,
        help="Target number of candidate Shorts to generate from source (default: 3).",
    )
    parser.add_argument(
        "--min-clip-duration",
        type=float,
        default=15.0,
        help="Minimum repurposed clip duration in seconds (default: 15.0).",
    )
    parser.add_argument(
        "--max-clip-duration",
        type=float,
        default=60.0,
        help="Maximum repurposed clip duration in seconds (default: 60.0).",
    )
    parser.add_argument(
        "--reframing",
        choices=["blur_pad", "center_crop"],
        default="blur_pad",
        help="Vertical reframing mode for repurposed video: blur_pad or center_crop (default: blur_pad).",
    )
    parser.add_argument(
        "--remove-silence",
        action="store_true",
        help="Enable automatic silence removal / pause trimming in repurposed clips.",
    )
    parser.add_argument(
        "--bgm",
        type=str,
        default=None,
        help="Path to background music audio file for repurposed clips.",
    )
    parser.add_argument(
        "--bgm-volume",
        type=float,
        default=0.15,
        help="Volume level for background music (0.0 to 1.0, default: 0.15).",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Generate candidate clips and draft manifest for review without rendering full videos.",
    )
    parser.add_argument(
        "--apply-manifest",
        type=Path,
        default=None,
        help="Path to manifest.json to render approved repurposed clips.",
    )
    parser.add_argument(
        "--job-id",
        type=str,
        default=None,
        help="Explicit job identifier for repurposed outputs directory.",
    )
    parser.add_argument(
        "--ownership-type",
        choices=["creator_owned", "licensed", "permitted", "public_domain"],
        default="creator_owned",
        help="Rights ownership type for source footage (default: creator_owned).",
    )
    parser.add_argument(
        "--rights-holder",
        type=str,
        default="",
        help="Name of copyright owner / licensor granting footage rights.",
    )
    parser.add_argument(
        "--license-evidence",
        type=str,
        default="",
        help="License agreement reference, URL, or invoice ID documentation.",
    )
    parser.add_argument(
        "--confirm-rights",
        action="store_true",
        help="Explicitly confirm ownership, licensing, or authorization rights for source footage.",
    )
    parser.add_argument(
        "--accept-disclaimer",
        action="store_true",
        help="Acknowledge and accept the legal copyright compliance disclaimer.",
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
        try:
            dur_str = f"{float(meta.duration_seconds):.2f}s" if (meta and hasattr(meta, "duration_seconds")) else "unknown"
        except (ValueError, TypeError):
            dur_str = str(getattr(meta, "duration_seconds", "unknown"))
        print(f"Shorts Video:     {result.shorts_result.output_path} ({dur_str}, 1080x1920)")

    if result.longform_result:
        meta = result.longform_metadata
        try:
            dur_str = f"{float(meta.duration_seconds):.2f}s" if (meta and hasattr(meta, "duration_seconds")) else "unknown"
        except (ValueError, TypeError):
            dur_str = str(getattr(meta, "duration_seconds", "unknown"))
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

    # Mode routing
    if args.mode == "dry_run":
        args.dry_run = True
    elif args.mode == "upload_private":
        args.upload_private = True
    elif args.mode == "render_only":
        args.dry_run = False
        args.upload_private = False
    elif args.mode == "draft":
        args.draft = True

    # Format resolution
    render_shorts = True
    render_longform = True
    if args.shorts_only or args.format == "shorts":
        render_shorts = True
        render_longform = False
    elif args.longform_only or args.format == "longform":
        render_shorts = False
        render_longform = True

    # Original content workflow routing
    if getattr(args, "workflow", None) == "original":
        log.info("Original content workflow requested via CLI...")
        from benxautomation.original.cli import print_summary as print_orig_summary
        from benxautomation.original.engine import OriginalContentEngine

        engine = OriginalContentEngine(
            output_dir=args.output_dir if args.output_dir != Path("output") else Path("output/original_content")
        )
        summary = engine.run_all_topics(
            upload_private=bool(args.upload_private),
            max_shorts_per_topic=getattr(args, "clips", 2) or 2,
            render_longform=render_longform,
        )
        print_orig_summary(summary)
        return 0

    # Animated cartoon workflow routing (Blender + Godot + FFmpeg)
    if getattr(args, "workflow", None) == "animated":
        log.info("Animated cartoon workflow requested via CLI...")
        from benxautomation.animation.pipeline import AnimationPipeline

        anim_out_dir = (
            args.output_dir
            if args.output_dir and args.output_dir != Path("output")
            else Path("output/animated_shorts")
        )
        pipeline = AnimationPipeline(output_dir=anim_out_dir)
        results = pipeline.run_batch(
            count=args.count or 25,
            upload_private=bool(args.upload_private),
            upload_public=bool(args.upload_public),
            sample_only=bool(args.sample_only),
        )

        print("\n" + "=" * 60)
        print("BENXAUTOMATION — Animated Shorts Execution Summary")
        print("=" * 60)
        for r in results:
            stat = "PASS" if r.quality_passed and r.motion_verified else "FAIL"
            print(f"[{stat}] {r.title} ({r.duration_seconds:.1f}s, Motion Score: {r.motion_score:.1f}%)")
            print(f"       Video: {r.video_path}")
            if r.youtube_video_id:
                print(f"       YouTube: {r.youtube_url} ({r.youtube_status})")
            elif r.youtube_status != "PENDING":
                print(f"       YouTube Status: {r.youtube_status}")
        print("=" * 60 + "\n")
        return 0

    # Repurposing workflow routing (if --workflow repurpose or --source or --apply-manifest is provided)
    is_repurpose = (
        getattr(args, "workflow", None) == "repurpose"
        or bool(getattr(args, "source", None))
        or bool(getattr(args, "apply_manifest", None))
    )
    if is_repurpose:
        log.info("Repurposing workflow requested via CLI...")
        from benxautomation.repurpose.cli import print_repurpose_summary
        from benxautomation.repurpose.config import RepurposingConfig
        from benxautomation.repurpose.engine import RepurposingEngine
        from benxautomation.repurpose.manifest import RepurposeManifest

        repurpose_out_dir = (
            str(args.output_dir)
            if args.output_dir and args.output_dir != Path("output")
            else "output/repurposed"
        )

        r_cfg = RepurposingConfig(
            min_clip_duration=args.min_clip_duration or 15.0,
            max_clip_duration=args.max_clip_duration or 60.0,
            max_clips=max(1, min(args.clips or 3, 10)),
            reframing_mode=args.reframing or "blur_pad",
            remove_silence=bool(args.remove_silence),
            bgm_path=args.bgm,
            bgm_volume=args.bgm_volume or 0.15,
            language=args.language or "en",
            burn_subtitles=not args.no_subtitles,
            output_dir=repurpose_out_dir,
            dry_run=bool(args.dry_run),

            upload_private=bool(getattr(args, "upload_private", False)),
            ownership_type=getattr(args, "ownership_type", "creator_owned") or "creator_owned",
            rights_holder=getattr(args, "rights_holder", "") or "",
            license_evidence=getattr(args, "license_evidence", "") or "",
            confirm_rights=bool(getattr(args, "confirm_rights", False)),
            accept_disclaimer=bool(getattr(args, "accept_disclaimer", False)),
        )
        engine = RepurposingEngine(r_cfg)

        try:
            if args.apply_manifest:
                m_path = Path(args.apply_manifest)
                if not m_path.is_file():
                    log.error("Manifest file not found: %s", m_path)
                    print(f"\n[ERROR] Manifest file not found: {m_path}\n", file=sys.stderr)
                    return 1
                manifest = RepurposeManifest.load(m_path)
                manifest, report = engine.render_from_manifest(
                    manifest,
                    source_video_path=Path(args.source) if args.source else None,
                    dry_run=bool(args.dry_run),
                )
            else:
                manifest, report = engine.run(
                    args.source,
                    job_id=args.job_id,
                    draft_only=bool(args.draft),
                    max_clips=args.clips or 3,
                    language=args.language or "en",
                    dry_run=bool(args.dry_run),
                )

            print_repurpose_summary(manifest, report)
            return 0
        except Exception as exc:
            log.error("Repurposing pipeline error: %s", exc, exc_info=True)
            print(f"\n[ERROR] Repurposing failed: {exc}\n", file=sys.stderr)
            return 1

    # Precedence check: if neither topic nor script nor asset provided
    if not args.topic and not args.script and not args.asset:
        log.error(
            "Missing input: Please provide --topic <topic> or --script <text> "
            "(or --asset <file> for single-asset video, or --source <URL_or_file> to repurpose)."
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

        # Upload strictly as PRIVATE if requested or configured
        should_upload_private = getattr(args, "upload_private", False) or getattr(config.publishing, "auto_upload_private", False)
        if should_upload_private:
            log.info("Automatic private YouTube upload requested...")
            from benxautomation.config import PublishingConfig
            from benxautomation.publisher.youtube import YouTubeOAuthManager, YouTubePublisher

            token_dir = Path.home() / ".benxautomation"
            client_secret_file = token_dir / "client_secret.json"

            oauth_mgr = None
            if client_secret_file.is_file():
                try:
                    oauth_mgr = YouTubeOAuthManager(client_secret_file)
                except Exception as e:
                    log.warning("Could not initialize YouTubeOAuthManager: %s", e)

            if not oauth_mgr:
                print("\n[UPLOAD STATUS] YouTube OAuth credentials not configured.")
                print("Videos rendered and saved locally; private upload skipped safely.")
            else:
                pub_cfg = PublishingConfig(enabled=True, enforce_private=True)
                publisher = YouTubePublisher(pub_cfg, oauth_manager=oauth_mgr)

                videos_to_upload: list[tuple[Path, str, bool]] = []
                if res.shorts_result and res.shorts_result.output_path.is_file():
                    videos_to_upload.append((res.shorts_result.output_path, f"{args.topic or 'Short'} #Shorts", True))
                if res.longform_result and res.longform_result.output_path.is_file():
                    videos_to_upload.append((res.longform_result.output_path, f"{args.topic or 'Video'}", False))

                from benxautomation.renderer.media_validator import MediaValidator

                validator = MediaValidator()

                for vid_path, title, is_short in videos_to_upload:
                    try:
                        print(f"Running quality gate and uploading {vid_path.name} strictly as PRIVATE to YouTube...")
                        passed, issues, meta = validator.validate_for_private_upload(
                            vid_path,
                            is_short=is_short,
                            min_duration_seconds=3.0,
                        )
                        if not passed:
                            print(f"  [QUALITY REJECTION] {vid_path.name} failed checks: {issues}", file=sys.stderr)
                            rej_p = vid_path.parent / f"{vid_path.stem}_upload_rejection.json"
                            try:
                                rej_p.write_text(
                                    json.dumps({"file": str(vid_path), "issues": issues, "status": "QUALITY_CHECK_FAILED"}, indent=2),
                                    encoding="utf-8",
                                )
                            except Exception as rej_err:
                                log.debug("Could not write rejection report: %s", rej_err)
                            continue

                        up_res = publisher.upload(
                            vid_path,
                            title=title,
                            description=f"Automated video: {args.topic or 'Discussion'}\n\nGenerated with BENXAUTOMATION.",
                            tags=["shorts" if is_short else "video", "automation", "ai"],
                            privacy_status="private",
                        )
                        vid_id = str(up_res.get("video_id") or up_res.get("id") or "")
                        if not vid_id:
                            raise PublishingDisabledError("YouTube upload did not return a valid video ID.")

                        verified_privacy = up_res.get("privacy_status")
                        if not verified_privacy:
                            try:
                                v_info = publisher.verify_video(vid_id)
                                verified_privacy = v_info.get("privacy_status")
                            except Exception:
                                pass

                        if verified_privacy and str(verified_privacy).lower() != "private":
                            raise PublishingDisabledError(
                                f"CRITICAL: Uploaded video {vid_id} privacy is '{verified_privacy}', NOT 'private'. Safety guard violated."
                            )

                        receipt_p = vid_path.parent / f"{vid_path.stem}_upload_receipt.json"
                        try:
                            receipt_p.write_text(
                                json.dumps({"video_id": vid_id, "url": f"https://youtu.be/{vid_id}", "privacy_status": "private"}, indent=2),
                                encoding="utf-8",
                            )
                        except Exception:
                            pass

                        print(f"  [UPLOAD CONFIRMED PRIVATE] '{title}' -> Video ID: {vid_id} (https://youtu.be/{vid_id})")
                    except Exception as up_err:
                        log.error("Private upload failed for %s: %s", vid_path.name, up_err)
                        print(f"  Upload failed for {vid_path.name}: {up_err}", file=sys.stderr)



        return 0

    except ScriptGenerationError as exc:
        log.error("Script generation failed: %s", exc)
        print(f"\n[ERROR] Script generation failed: {exc}", file=sys.stderr)
        print("Tip: If you do not have an AI API key configured, use --script \"Your custom narration\" or --provider fallback instead.\n", file=sys.stderr)
        return 1

    except BenxError as exc:
        log.error("Pipeline failure: %s", exc)
        print(f"\n[ERROR] Pipeline failure: {exc}\n", file=sys.stderr)
        return 1

    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=True)
        print(f"\n[ERROR] Unexpected error: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
