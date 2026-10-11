"""CLI for Podcast-to-Shorts Automation System."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benxautomation.logger import get_logger
from benxautomation.podcast.models import (
    HighlightCandidate,
    PodcastPipelineConfig,
    RightsDeclaration,
    SubtitleStyle,
)
from benxautomation.podcast.pipeline import PodcastToShortsPipeline

log = get_logger("benxautomation.podcast.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benxautomation.podcast",
        description="BENXAUTOMATION — Podcast & Livestream to Shorts Automation System",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # 1. dashboard
    dash_p = subparsers.add_parser("dashboard", help="Start the interactive web dashboard")
    dash_p.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    dash_p.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    # 2. status
    subparsers.add_parser("status", help="Check FFmpeg, transcription, and YouTube OAuth status")

    # 3. process
    proc_p = subparsers.add_parser("process", help="Process podcast/replay into vertical Shorts")
    proc_p.add_argument("--source", "-s", required=True, help="YouTube video URL or local file path")
    proc_p.add_argument("--language", "-l", default="en", help="Language code (en, ta, ta-en)")
    proc_p.add_argument("--max-clips", type=int, default=3, help="Max highlight clips to detect")
    proc_p.add_argument("--min-duration", type=float, default=15.0, help="Min clip duration (seconds)")
    proc_p.add_argument("--max-duration", type=float, default=60.0, help="Max clip duration (seconds)")
    proc_p.add_argument("--reframing", choices=["blur_pad", "center_crop"], default="blur_pad", help="Reframing mode")
    proc_p.add_argument("--ownership-type", default="creator_owned", help="Rights ownership type")
    proc_p.add_argument("--rights-holder", default="", help="Name of copyright owner / author")
    proc_p.add_argument("--license-evidence", default="", help="License documentation reference or statement")
    proc_p.add_argument("--music-source", default="no_music", choices=["no_music", "royalty_free", "cleared", "unlicensed"])
    proc_p.add_argument("--attribution-text", default="", help="Attribution text for description")
    proc_p.add_argument("--confirm-rights", action="store_true", help="Explicitly declare ownership/permission")
    proc_p.add_argument("--accept-disclaimer", action="store_true", help="Accept statutory legal disclaimer")
    proc_p.add_argument("--render", action="store_true", help="Render vertical 9:16 MP4 clips")
    proc_p.add_argument("--upload-private", action="store_true", help="Upload approved clips to YouTube (strictly private)")

    # 4. batch
    batch_p = subparsers.add_parser("batch", help="Batch queue management for multiple sources")
    batch_p.add_argument("--add", nargs="+", help="Add one or more sources (URLs or local files) to queue")
    batch_p.add_argument("--file", help="Path to text file containing list of sources (one per line)")
    batch_p.add_argument("--run", action="store_true", help="Execute all pending batch jobs")
    batch_p.add_argument("--status", action="store_true", help="Show batch queue status")
    batch_p.add_argument("--clips-per-source", type=int, default=3, help="Target clips per source")
    batch_p.add_argument("--ownership-type", default="creator_owned", help="Rights ownership type")
    batch_p.add_argument("--confirm-rights", action="store_true", help="Confirm ownership rights")
    batch_p.add_argument("--accept-disclaimer", action="store_true", help="Accept copyright disclaimer")
    batch_p.add_argument("--upload-private", action="store_true", help="Upload approved clips to YouTube privately")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command or args.command == "dashboard":
        import uvicorn
        from benxautomation.podcast.server import app
        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 8000)
        print(f"\n=======================================================")
        print(f"BENX Podcast-to-Shorts Studio Dashboard")
        print(f"Open browser at: http://{host}:{port}")
        print(f"=======================================================\n")
        uvicorn.run(app, host=host, port=port)
        return 0

    pipeline = PodcastToShortsPipeline()

    if args.command == "status":
        from benxautomation.renderer.ffmpeg_utils import ffmpeg_is_available, ffprobe_is_available
        print("\n--- BENXAUTOMATION PODCAST STATUS ---")
        print(f"FFmpeg Available:   {ffmpeg_is_available()}")
        print(f"FFprobe Available:  {ffprobe_is_available()}")
        if pipeline.publisher and pipeline.publisher.oauth_manager:
            try:
                ch = pipeline.publisher.oauth_manager.verify_channel()
                print(f"YouTube OAuth:      CONNECTED ({ch.title} - @{ch.custom_url})")
            except Exception as e:
                print(f"YouTube OAuth:      ERROR ({e})")
        else:
            print("YouTube OAuth:      NOT CONFIGURED")
        return 0

    if args.command == "process":
        # 1. Ingest
        print(f"\n[1/6] Ingesting source: {args.source}")
        inp = pipeline.ingest(args.source)
        print(f"      Title: {inp.title}")
        print(f"      Duration: {inp.duration_seconds:.1f}s")

        # 2. Transcribe
        print(f"\n[2/6] Transcribing and synchronizing subtitles ({args.language})...")
        transcript = pipeline.transcribe(inp, language=args.language)
        print(f"      Segments extracted: {len(transcript.segments)}")

        # 3. Detect highlights
        print(f"\n[3/6] Detecting high-retention highlights...")
        pipeline.config.min_clip_duration = args.min_duration
        pipeline.config.max_clip_duration = args.max_duration
        candidates = pipeline.detect_highlights(transcript, max_candidates=args.max_clips)
        print(f"      Discovered {len(candidates)} highlight candidate(s):")
        for i, c in enumerate(candidates, 1):
            print(f"      [{i}] {c.clip_id}: {c.start_seconds:.1f}s - {c.end_seconds:.1f}s ({c.duration:.1f}s)")
            print(f"          Hook: \"{c.hook}\"")
            print(f"          Score: {c.score:.0f}% | Summary: {c.summary}")

        if not args.render:
            print("\nAnalysis complete. Run with --render to generate 9:16 vertical MP4s.")
            return 0

        # 4. Rights verification
        print("\n[4/6] Verifying rights declaration & copyright compliance...")
        rights_decl = RightsDeclaration(
            ownership_type=args.ownership_type,
            rights_holder=args.rights_holder or inp.channel_or_author,
            license_evidence=args.license_evidence or "Creator owned self-produced footage",
            music_source=args.music_source,
            attribution_text=args.attribution_text or f"Source: {inp.title} by {inp.channel_or_author}",
            user_confirmed_rights=args.confirm_rights,
            disclaimer_accepted=args.accept_disclaimer,
        )
        pipeline.rights_reviewer.assert_publishing_allowed(rights_decl)
        print("      Rights declaration verified.")

        # 5. Render
        print("\n[5/6] Rendering vertical 9:16 Shorts with synchronized subtitles...")
        rendered_meta_list = []
        for cand in candidates:
            cand.approved = True
            meta = pipeline.render_clip(
                podcast_input=inp,
                transcript=transcript,
                candidate=cand,
                rights_declaration=rights_decl,
                reframing_mode=args.reframing,
            )
            print(f"      Rendered: {meta.video_path} ({meta.duration_seconds:.1f}s)")
            print(f"      SRT: {meta.srt_path}")
            print(f"      VTT: {meta.vtt_path}")
            print(f"      Thumbnail: {meta.thumbnail_path}")
            rendered_meta_list.append(meta)

        # 6. Upload
        if args.upload_private:
            print("\n[6/6] Uploading to YouTube with private test visibility...")
            for meta in rendered_meta_list:
                res = pipeline.upload_to_youtube(meta, privacy_status="private", user_approved=True)
                print(f"      Uploaded '{meta.title}' -> Video ID: {res.get('video_id') or res.get('id')} ({res.get('url')})")
        else:
            print("\nUpload skipped (run with --upload-private to publish to YouTube).")

        print("\n=======================================================")
        print("PIPELINE EXECUTION COMPLETE - ALL SHORT ASSETS GENERATED")
        print("=======================================================\n")
        return 0

    if args.command == "batch":
        from benxautomation.podcast.batch_processor import PodcastBatchProcessor
        processor = PodcastBatchProcessor(pipeline=pipeline)

        rights_decl = RightsDeclaration(
            ownership_type=args.ownership_type,
            rights_holder="Batch Creator",
            license_evidence="Verified rights declaration",
            music_source="royalty_free",
            attribution_text="Batch Source Attribution",
            user_confirmed_rights=args.confirm_rights,
            disclaimer_accepted=args.accept_disclaimer,
        )

        sources_to_add: list[str] = []
        if args.add:
            sources_to_add.extend(args.add)
        if args.file and Path(args.file).is_file():
            lines = [l.strip() for l in Path(args.file).read_text(encoding="utf-8").splitlines() if l.strip()]
            sources_to_add.extend(lines)

        for src in sources_to_add:
            jid = processor.add_job(
                src,
                rights_decl,
                clips_target=args.clips_per_source,
            )
            print(f"Queued job #{jid} for source: {src}")

        if args.status or not args.run:
            summary = processor.get_summary()
            jobs = processor.list_jobs()
            print("\n--- PODCAST BATCH QUEUE STATUS ---")
            print(f"Jobs Summary: {summary}")
            for j in jobs:
                print(f"  Job #{j.id} [{j.status}] - {j.source} -> {len(j.rendered_clips)} clips")
            if not args.run:
                print("\nRun with --run to execute pending jobs.")
                return 0

        if args.run:
            print("\nExecuting pending batch jobs...")
            results = processor.process_all_pending(upload_private=args.upload_private)
            print(f"\nBatch execution completed! Total processed: {len(results)}")
            for r in results:
                print(f"  Job #{r['job_id']}: {r['status']} ({len(r.get('rendered_clips', []))} clips)")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
