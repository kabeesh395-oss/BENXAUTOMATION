"""Executable runner for the Multi-Agent Autonomous Video Production System.

Usage:
  python scripts/run_autonomous_agent_pipeline.py --mode shorts
  python scripts/run_autonomous_agent_pipeline.py --mode longform
  python scripts/run_autonomous_agent_pipeline.py --mode shorts --publish
"""

import argparse
import sys
from pathlib import Path

from benxautomation.agents.orchestrator import MasterOrchestratorAgent
from benxautomation.config import PublishingConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="BENXAUTOMATION Multi-Agent Production Runner")
    parser.add_argument("--mode", choices=["shorts", "longform"], default="shorts", help="Video format to produce")
    parser.add_argument("--category", choices=["tech", "logic", "finance", "history", "science"], default=None)
    parser.add_argument("--topic", type=str, default=None, help="Custom topic override if desired")
    parser.add_argument("--publish", action="store_true", help="Upload directly to YouTube once verified")
    parser.add_argument("--privacy", choices=["public", "private", "unlisted"], default="public")
    args = parser.parse_args()

    pub_config = None
    if args.publish:
        pub_config = PublishingConfig(
            enabled=True,
            enforce_private=False,
            youtube_client_secret_path="client_secret.json",
            default_privacy=args.privacy,
        )

    orchestrator = MasterOrchestratorAgent(publishing_config=pub_config)
    result = orchestrator.run_pipeline(
        format_type=args.mode,
        category=args.category,
        custom_topic=args.topic,
        publish_to_youtube=args.publish,
        privacy_status=args.privacy,
    )

    print("\n" + "=" * 65)
    print(">> MULTI-AGENT AUTONOMOUS PRODUCTION COMPLETE!")
    safe_title = result.title.encode("ascii", "replace").decode("ascii")
    print(f"Title:            {safe_title}")
    print(f"Format:           {result.format.upper()}")
    print(f"Duration:         {result.duration_seconds:.2f}s")
    print(f"Motion Score:     {result.motion_score:.2f}% (Valid: {result.motion_verified})")
    print(f"Video File:       {result.video_path}")
    print(f"Thumbnail File:   {result.thumbnail_path}")
    print(f"Metadata File:    {result.metadata_path}")
    if result.published:
        print(f"YouTube Status:   PUBLISHED (ID: {result.youtube_video_id})")
        print(f"YouTube Link:     {result.youtube_url}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
