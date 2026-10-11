"""CLI entrypoint for long-form-to-Shorts repurposing automation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benxautomation.logger import get_logger
from benxautomation.repurpose.config import RepurposingConfig
from benxautomation.repurpose.engine import RepurposingEngine
from benxautomation.repurpose.manifest import RepurposeManifest

log = get_logger("benxautomation.repurpose.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benxautomation.repurpose",
        description="BENXAUTOMATION — Vizard AI-inspired Long-Form-to-Shorts Repurposing Engine",
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="YouTube video URL or local file path to repurpose.",
    )
    parser.add_argument(
        "--clips",
        "-n",
        type=int,
        default=3,
        help="Target number of candidate Shorts to generate (default: 3).",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=15.0,
        help="Minimum clip duration in seconds (default: 15.0).",
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=60.0,
        help="Maximum clip duration in seconds (default: 60.0).",
    )
    parser.add_argument(
        "--reframing",
        choices=["blur_pad", "center_crop"],
        default="blur_pad",
        help="Vertical reframing mode: blur_pad or center_crop (default: blur_pad).",
    )
    parser.add_argument(
        "--remove-silence",
        action="store_true",
        help="Enable automatic silence removal / pause trimming.",
    )
    parser.add_argument(
        "--bgm",
        type=str,
        default=None,
        help="Optional path to background music audio file.",
    )
    parser.add_argument(
        "--bgm-volume",
        type=float,
        default=0.15,
        help="Volume of background music (0.0 to 1.0, default: 0.15).",
    )
    parser.add_argument(
        "--language",
        "-l",
        default="en",
        help="Language code (default: en).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("output/repurposed"),
        help="Base directory for repurposed jobs (default: output/repurposed).",
    )
    parser.add_argument(
        "--job-id",
        type=str,
        default=None,
        help="Explicit job identifier for output folder naming.",
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
        help="Path to an existing or edited manifest.json to render approved clips.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate parameters, media streams, and plan without invoking FFmpeg rendering.",
    )
    parser.add_argument(
        "--mode",
        choices=["dry_run", "render_only", "upload_private"],
        default=None,
        help="Execution mode: dry_run (validate only), render_only (render without upload), upload_private (upload to YouTube strictly as PRIVATE).",
    )
    parser.add_argument(
        "--upload-private",
        action="store_true",
        help="Upload approved rendered clips strictly as PRIVATE to YouTube for testing.",
    )
    parser.add_argument(
        "--ownership-type",
        choices=["creator_owned", "licensed", "permitted", "public_domain"],
        default="creator_owned",
        help="Rights ownership type (default: creator_owned).",
    )
    parser.add_argument(
        "--rights-holder",
        type=str,
        default="",
        help="Name of verified copyright holder or licensor.",
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
    parser.add_argument(
        "--no-subtitles",
        action="store_true",
        help="Disable burning subtitles into rendered video.",
    )
    return parser


def print_repurpose_summary(manifest: RepurposeManifest, report: dict) -> None:
    """Print clean summary of repurposed clips and quality report."""
    print("\n" + "=" * 65)
    print("BENXAUTOMATION — Repurposing Job Summary")
    print("=" * 65)
    print(f"Job ID:           {manifest.job_id}")
    print(f"Source:           {manifest.source_title} ({manifest.source_duration:.1f}s)")
    print(f"Status:           {manifest.status.upper()}")
    print(f"Output Directory: output/repurposed/{manifest.job_id}/")

    print("\nCandidate Shorts:")
    for i, c in enumerate(manifest.clips, 1):
        status_tag = f"[{c.status.upper()}]"
        approved_tag = "APPROVED" if c.approved else "REJECTED"
        print(f"  {i}. {c.clip_id} ({c.start_seconds:.1f}s - {c.end_seconds:.1f}s, {c.duration:.1f}s) {status_tag} ({approved_tag})")
        print(f"     Hook: \"{c.hook}\"")
        if c.output_video:
            print(f"     Video: {c.output_video}")
            if c.metadata_path:
                print(f"     Meta:  {c.metadata_path}")
        if getattr(c, "youtube_upload_status", "NOT_UPLOADED") != "NOT_UPLOADED":
            print(f"     Upload: {c.youtube_upload_status} ({getattr(c, 'youtube_video_url', 'N/A') or 'N/A'})")

    if report and "overall_status" in report:
        print("\nQuality Report Validation:")
        print(f"  Verdict:        {report['overall_status']}")
        print(f"  Passed Clips:   {report.get('passed_clips', 0)} / {report.get('total_clips', 0)}")
        for chk in report.get("checks", []):
            cid = chk.get("clip_id")
            passed = "PASS" if chk.get("passed") else "FAIL"
            print(f"    - {cid}: {passed} ({chk.get('width', 0)}x{chk.get('height', 0)}, {chk.get('duration_seconds', 0):.1f}s)")
            if chk.get("issues"):
                for iss in chk["issues"]:
                    print(f"        Issue: {iss}")

    print("=" * 65 + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.source and not args.apply_manifest:
        parser.print_help()
        print("\n[ERROR] Either --source <URL_or_file> or --apply-manifest <path> is required.\n", file=sys.stderr)
        return 1

    # Resolve mode
    if args.mode == "dry_run":
        args.dry_run = True
    elif args.mode == "upload_private":
        args.upload_private = True
    elif args.mode == "render_only":
        args.dry_run = False
        args.upload_private = False

    cfg = RepurposingConfig(
        min_clip_duration=args.min_duration,
        max_clip_duration=args.max_duration,
        max_clips=max(1, min(args.clips, 10)),
        reframing_mode=args.reframing,
        remove_silence=args.remove_silence,
        bgm_path=args.bgm,
        bgm_volume=args.bgm_volume,
        language=args.language,
        burn_subtitles=not args.no_subtitles,
        output_dir=str(args.output_dir),
        dry_run=args.dry_run,
        upload_private=args.upload_private,
        ownership_type=args.ownership_type,
        rights_holder=args.rights_holder,
        license_evidence=args.license_evidence,
        confirm_rights=args.confirm_rights,
        accept_disclaimer=args.accept_disclaimer,
    )
    engine = RepurposingEngine(cfg)

    try:
        if args.apply_manifest:
            m_path = Path(args.apply_manifest)
            if not m_path.is_file():
                print(f"\n[ERROR] Manifest file not found: {m_path}\n", file=sys.stderr)
                return 1
            manifest = RepurposeManifest.load(m_path)
            print(f"\nApplying manifest {manifest.job_id} ({len(manifest.get_approved_clips())} approved clips)...")
            manifest, report = engine.render_from_manifest(
                manifest,
                source_video_path=Path(args.source) if args.source else None,
                dry_run=args.dry_run,
            )
        else:
            manifest, report = engine.run(
                args.source,
                job_id=args.job_id,
                draft_only=args.draft,
                max_clips=args.clips,
                language=args.language,
                dry_run=args.dry_run,
            )

        print_repurpose_summary(manifest, report)
        return 0

    except Exception as exc:
        log.error("Repurposing failed: %s", exc, exc_info=True)
        print(f"\n[ERROR] Repurposing failed: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
