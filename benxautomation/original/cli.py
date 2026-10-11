"""CLI interface for BENXAUTOMATION original content production."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from benxautomation.config import load_config
from benxautomation.logger import get_logger
from benxautomation.original.engine import OriginalContentEngine
from benxautomation.original.models import DailyProductionSummary

log = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benxautomation.original",
        description="Copyright-Safe Original Educational Video Production Engine",
    )
    parser.add_argument(
        "--topics",
        type=str,
        default="all",
        help="Comma-separated topics (all, ai_future, compounding_wealth, cyber_defense).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/original_content"),
        help="Directory to save rendered videos and artifacts.",
    )
    parser.add_argument(
        "--max-shorts",
        type=int,
        default=2,
        help="Maximum Shorts to render per topic (default: 2).",
    )
    parser.add_argument(
        "--no-longform",
        action="store_true",
        help="Disable long-form video rendering.",
    )
    parser.add_argument(
        "--upload-private",
        action="store_true",
        help="Upload quality-approved videos strictly as PRIVATE to YouTube.",
    )
    return parser


def print_summary(summary: DailyProductionSummary) -> None:
    print("\n" + "=" * 65)
    print("      BENXAUTOMATION ORIGINAL CONTENT PRODUCTION REPORT")
    print("=" * 65)
    print(f"Timestamp:                 {summary.timestamp}")
    print(f"Shorts Generated (9:16):   {summary.total_shorts_generated}")
    print(f"Long-form Generated (16:9):{summary.total_longform_generated}")
    print(f"Quality Approved:          {summary.quality_approved_videos}")
    print(f"Quality Rejected:          {summary.quality_rejected_videos}")
    print("-" * 65)
    print(f"Private Uploads Completed: {summary.private_uploads_completed}")
    print(f"Uploads Blocked (Rights):  {summary.uploads_blocked_rights}")
    print(f"Uploads Blocked (Quality): {summary.uploads_blocked_quality}")
    print(f"Uploads Blocked (Quota):   {summary.uploads_blocked_quota}")
    print(f"Estimated Quota Used:      {summary.quota_units_used} units")
    print("=" * 65)
    print("\nProduced Videos:")
    for v in summary.videos:
        print(f" • [{v.get('format', '').upper():8}] {v.get('title', '')[:55]}")
        print(f"    Path:    {v.get('output_path')}")
        print(f"    Quality: {'PASS' if v.get('quality_passed') else 'FAIL'}")
        print(f"    Status:  {v.get('upload_status')}")
        if v.get("youtube_url"):
            print(f"    URL:     {v.get('youtube_url')} (Privacy: {v.get('youtube_privacy_status')})")
        print()
    print("=" * 65 + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    topic_ids = None
    if args.topics and args.topics.lower() != "all":
        topic_ids = [t.strip() for t in args.topics.split(",") if t.strip()]

    engine = OriginalContentEngine(output_dir=args.output_dir)

    try:
        summary = engine.run_all_topics(
            topic_ids=topic_ids,
            upload_private=bool(args.upload_private),
            max_shorts_per_topic=args.max_shorts,
            render_longform=not args.no_longform,
        )
        print_summary(summary)
        return 0
    except Exception as exc:
        log.error("Original content pipeline execution failed: %s", exc, exc_info=True)
        print(f"\n[ERROR] Pipeline failed: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
