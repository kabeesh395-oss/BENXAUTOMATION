"""CLI script to render the 30-second Funny Stickman (BEN & MAX) comedy sample video."""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benxautomation.animation.stickman_story import (
    FunnyStickmanScriptCatalog,
    StickmanStoryPipeline,
)
from benxautomation.renderer.ffmpeg_utils import probe_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("render_stickman_sample")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render 30-second Funny Stickman Sample Video")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/stickman_sample"),
        help="Directory to save the rendered stickman video and artifacts",
    )
    parser.add_argument(
        "--no-subs",
        action="store_true",
        help="Do not burn subtitles into video",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    log.info("=== BENXAUTOMATION Funny Stickman Production ===")

    # 1. Fetch original slapstick script
    script = FunnyStickmanScriptCatalog.get_quantum_banana_glitch()
    log.info("Loaded Script: '%s' (Format: %s, Scenes: %d)", script.title, script.format, len(script.scenes))

    # 2. Execute Story Animation Pipeline
    pipeline = StickmanStoryPipeline()
    result = pipeline.run_pipeline(
        script,
        output_dir=args.output_dir,
        burn_subtitles=not args.no_subs,
    )

    # 3. Verify real MP4 output with ffprobe
    probe = probe_file(result.video_path)
    if not probe or "format" not in probe:
        log.error("Failed to probe rendered video: %s", result.video_path)
        return 1

    v_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), None)

    width = v_stream.get("width") if v_stream else "N/A"
    height = v_stream.get("height") if v_stream else "N/A"
    codec = v_stream.get("codec_name") if v_stream else "N/A"
    duration = float(probe.get("format", {}).get("duration", 0.0))
    file_size_mb = result.video_path.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 60)
    print("[STICKMAN PRODUCTION VERIFICATION REPORT]")
    print("=" * 60)
    print(f"Title:           {result.title}")
    print(f"Video File:      {result.video_path}")
    print(f"File Size:       {file_size_mb:.2f} MB")
    print(f"Resolution:      {width}x{height} ({result.format})")
    print(f"Video Codec:     {codec}")
    print(f"Duration:        {duration:.2f} seconds")
    print(f"Frame Rate:      {result.fps} fps")
    print(f"Audio Track:     {'Present (' + a_stream.get('codec_name', '') + ')' if a_stream else 'Missing'}")
    print(f"Subtitles (ASS): {result.ass_path} ({'Burned' if not args.no_subs else 'Unburned'})")
    print(f"Thumbnail:       {result.thumbnail_path}")
    print(f"Motion Score:    {result.motion_score:.4f} (Verified: {result.motion_verified})")
    print(f"Quality Status:  {'PASSED' if result.quality_passed else 'FAILED'}")
    print(f"Upload Status:   {result.youtube_status} (Private Safeguard Enforced)")
    print("=" * 60 + "\n")

    return 0 if result.quality_passed else 1


if __name__ == "__main__":
    sys.exit(main())
