"""Script to render an official sample BENX Mascot animation video and validate with FFprobe and MotionValidator."""

from pathlib import Path
import json
from benxautomation.animation.story_pipeline import StoryAnimationPipeline, LocalStoryScriptCatalog
from benxautomation.renderer.ffmpeg_utils import probe_file
from benxautomation.animation.motion_validator import MotionValidator

def main():
    out_dir = Path("output/mascot_sample")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] Preparing story script with BENX Mascot character across 4 scenes...")
    story = LocalStoryScriptCatalog.get_preset_story("ai_quantum_leap", fmt="shorts")

    pipeline = StoryAnimationPipeline(
        output_dir=out_dir,
        assets_dir=Path("assets/mascot"),
    )

    print(f"[2/4] Rendering full 9:16 vertical animation: '{story.title}'...")
    result = pipeline.produce_story_animation(story, fps=24)

    print(f"[3/4] Render finished: {result.video_path}")
    print(f"      File size: {result.video_path.stat().st_size} bytes")
    print(f"      Duration: {result.duration_seconds:.2f}s")

    print("[4/4] Validating with FFprobe and MotionValidator...")
    probe_raw = probe_file(result.video_path)
    video_stream = next((s for s in probe_raw.get("streams", []) if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in probe_raw.get("streams", []) if s.get("codec_type") == "audio"), None)

    mv = MotionValidator()
    motion_score, samples, moves = mv.compute_motion_score(result.video_path, sample_interval_sec=1.0)

    summary = {
        "video_path": str(result.video_path),
        "file_size_bytes": result.video_path.stat().st_size,
        "duration_seconds": result.duration_seconds,
        "width": video_stream.get("width") if video_stream else 0,
        "height": video_stream.get("height") if video_stream else 0,
        "codec_video": video_stream.get("codec_name") if video_stream else None,
        "codec_audio": audio_stream.get("codec_name") if audio_stream else None,
        "motion_score_percent": round(motion_score, 2),
        "sampled_frames": samples,
        "significant_movement_events": moves,
        "motion_verified": motion_score >= 1.0 and moves >= 3,
        "thumbnail_path": str(result.thumbnail_path),
        "srt_path": str(result.srt_path),
        "vtt_path": str(result.vtt_path),
    }

    report_file = out_dir / "sample_validation_report.json"
    report_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n[VALIDATION SUCCESSFUL]")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
