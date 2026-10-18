"""Daily Autonomous Scheduler for BENXAUTOMATION Multi-Agent Production.

Automates daily content generation using the 7-Agent Production System:
- Trend Scout (Agent 1) picks fresh viral topics across the 5-Character Universe.
- Script Director (Agent 2) authors narrative scripts with dynamic emotions.
- Sonic Studio (Agent 4) generates Christopher voice narration (+15% tempo) & BGM.
- Cartoon Animator (Agent 3) & Video Assembler (Agent 5) render 2D OverSimplified animation.
- SEO & Growth (Agent 6) produces high-CTR thumbnails and viral metadata.
- Content Flywheel: Automatically extracts viral clips into 9:16 vertical Shorts with burned captions.
- Publisher: Securely uploads to YouTube as Unlisted/Public according to configuration.

Usage:
  python scripts/daily_autonomous_scheduler.py --run-now
  python scripts/daily_autonomous_scheduler.py --mode longform --publish --privacy unlisted
  python scripts/daily_autonomous_scheduler.py --daemon --schedule-time 09:00
  python scripts/daily_autonomous_scheduler.py --status
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benxautomation.agents.orchestrator import MasterOrchestratorAgent, PipelineRunResult
from benxautomation.config import PublishingConfig

# Set up dedicated file and console logger
LOG_FILE = REPO_ROOT / "output" / "daily_scheduler.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("benxautomation.daily_scheduler")

HISTORY_FILE = REPO_ROOT / "output" / "daily_scheduler_history.json"

CHARACTER_ROTATION = ["ben", "max", "dr_quantum", "mr_cash", "the_king"]
CATEGORY_ROTATION = ["tech", "logic", "science", "finance", "history"]


def load_history() -> List[Dict[str, Any]]:
    """Load past autonomous run records to prevent topic duplication."""
    if not HISTORY_FILE.is_file():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Could not read history file: %s", exc)
        return []


def save_history(entry: Dict[str, Any]) -> None:
    """Append a new run record to history."""
    history = load_history()
    history.append(entry)
    # Keep last 100 runs
    if len(history) > 100:
        history = history[-100:]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to save history: %s", exc)


def get_next_recommended_category(history: List[Dict[str, Any]]) -> str:
    """Rotate categories evenly across days."""
    if not history:
        return CATEGORY_ROTATION[0]
    last_cat = history[-1].get("category")
    if last_cat in CATEGORY_ROTATION:
        idx = (CATEGORY_ROTATION.index(last_cat) + 1) % len(CATEGORY_ROTATION)
        return CATEGORY_ROTATION[idx]
    return CATEGORY_ROTATION[len(history) % len(CATEGORY_ROTATION)]


def execute_daily_production(
    format_type: str = "longform",
    category: Optional[str] = None,
    publish: bool = False,
    privacy: str = "unlisted",
) -> PipelineRunResult:
    """Execute one full daily multi-agent production batch."""
    logger.info("=======================================================")
    logger.info("STARTING DAILY AUTONOMOUS MULTI-AGENT PRODUCTION JOB")
    logger.info("Format: %s | Publish: %s | Privacy: %s", format_type.upper(), publish, privacy)
    logger.info("=======================================================")

    history = load_history()
    if not category:
        category = get_next_recommended_category(history)
    logger.info("Selected Universe Category: %s", category.upper())

    pub_config = None
    if publish:
        client_secret = REPO_ROOT / "client_secret.json"
        pub_config = PublishingConfig(
            enabled=True,
            enforce_private=False,
            youtube_client_secret_path=str(client_secret) if client_secret.is_file() else None,
            default_privacy=privacy,
        )

    orchestrator = MasterOrchestratorAgent(
        output_base_dir=REPO_ROOT / "output" / "autonomous_runs",
        publishing_config=pub_config,
    )

    start_time = time.time()
    result = orchestrator.run_pipeline(
        format_type=format_type,
        category=category,
        publish_to_youtube=publish,
        privacy_status=privacy,
        auto_repurpose_shorts=True,
    )
    elapsed = time.time() - start_time

    # Record run in history
    history_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "topic_id": result.topic_id,
        "title": result.title,
        "category": category,
        "format": result.format,
        "duration_seconds": round(result.duration_seconds, 2),
        "motion_score": round(result.motion_score, 2),
        "video_path": result.video_path,
        "thumbnail_path": result.thumbnail_path,
        "repurposed_shorts_count": len(result.repurposed_shorts),
        "published": result.published,
        "youtube_video_id": result.youtube_video_id,
        "youtube_url": result.youtube_url,
        "render_time_seconds": round(elapsed, 1),
    }
    save_history(history_entry)

    logger.info("=======================================================")
    logger.info("DAILY PRODUCTION COMPLETED SUCCESSFULLY in %.1fs", elapsed)
    logger.info("Title: %s", result.title)
    logger.info("Master Video: %s", result.video_path)
    logger.info("Auto-Repurposed Shorts: %d", len(result.repurposed_shorts))
    for s in result.repurposed_shorts:
        logger.info(" - Short (Scene %d / %s): %s", s.get("scene_index", 0), s.get("character", ""), s.get("video_path", ""))
    if result.published:
        logger.info("YouTube URL: %s", result.youtube_url)
    logger.info("=======================================================")

    return result


def show_status() -> None:
    """Print current schedule status and recent production logs."""
    history = load_history()
    print("\n" + "=" * 65)
    print("BENXAUTOMATION DAILY AUTONOMOUS SCHEDULER STATUS")
    print("=" * 65)
    print(f"Total Productions Completed: {len(history)}")
    if history:
        print("\nLast 5 Production Runs:")
        for entry in history[-5:]:
            ts = entry.get("timestamp", "")[:16]
            title = entry.get("title", "Untitled")[:40]
            fmt = entry.get("format", "").upper()
            shorts = entry.get("repurposed_shorts_count", 0)
            pub = "YES (" + str(entry.get("youtube_video_id")) + ")" if entry.get("published") else "Local Draft"
            print(f" [{ts}] [{fmt}] {title:<40} | Shorts: {shorts} | Pub: {pub}")
    else:
        print("No autonomous runs recorded yet.")
    print("=" * 65 + "\n")


def run_daemon(schedule_time: str, format_type: str, publish: bool, privacy: str) -> None:
    """Run an autonomous loop that triggers every day at the given HH:MM."""
    logger.info("Starting Daily Autonomous Scheduler Daemon...")
    logger.info("Scheduled Daily Trigger Time: %s", schedule_time)

    target_hour, target_minute = map(int, schedule_time.split(":"))
    last_run_day: Optional[int] = None

    while True:
        now = datetime.datetime.now()
        current_day = now.day

        if now.hour == target_hour and now.minute == target_minute and last_run_day != current_day:
            logger.info("Daily trigger matched at %02d:%02d. Launching production...", now.hour, now.minute)
            try:
                execute_daily_production(
                    format_type=format_type,
                    publish=publish,
                    privacy=privacy,
                )
                last_run_day = current_day
            except Exception as exc:
                logger.error("Error during scheduled daily run: %s", exc, exc_info=True)

        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(description="BENXAUTOMATION Daily Autonomous Scheduler")
    parser.add_argument("--run-now", action="store_true", help="Execute one production run immediately")
    parser.add_argument("--mode", choices=["longform", "shorts"], default="longform", help="Video format (longform automatically produces 2 Shorts)")
    parser.add_argument("--category", choices=["tech", "logic", "science", "finance", "history"], default=None)
    parser.add_argument("--publish", action="store_true", help="Upload produced videos to YouTube")
    parser.add_argument("--privacy", choices=["public", "private", "unlisted"], default="unlisted", help="YouTube visibility for automated uploads")
    parser.add_argument("--daemon", action="store_true", help="Keep running in background as a continuous daily scheduler")
    parser.add_argument("--schedule-time", default="09:00", help="Time of day for daily run (HH:MM in 24hr format, default: 09:00)")
    parser.add_argument("--status", action="store_true", help="Display scheduler run history and stats")

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.daemon:
        run_daemon(
            schedule_time=args.schedule_time,
            format_type=args.mode,
            publish=args.publish,
            privacy=args.privacy,
        )
        return

    # Default or --run-now: execute immediately
    execute_daily_production(
        format_type=args.mode,
        category=args.category,
        publish=args.publish,
        privacy=args.privacy,
    )


if __name__ == "__main__":
    main()
