"""Render and validate official 16:9 horizontal long-form mascot animation."""

import json
import subprocess
from pathlib import Path

from benxautomation.animation.mascot_engine import MascotScene
from benxautomation.animation.motion_validator import MotionValidator
from benxautomation.animation.story_pipeline import StoryAnimationPipeline, StoryScript
from benxautomation.renderer.ffmpeg_utils import probe_file


def main():
    out_dir = Path("output/mascot_longform")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] Preparing 16:9 Long-Form story script...")
    story = StoryScript(
        story_id="benx_quantum_longform",
        title="BENX Quantum Architecture Primer",
        topic="Quantum Technology",
        format="longform",
        scenes=[
            MascotScene(
                scene_id="lf_sc1_hook",
                duration_seconds=3.5,
                dialogue="Welcome to the BENX technology lab. Today we explore quantum supremacy.",
                pose="gesture",
                expression="happy",
                view="front",
                camera_motion="DOLLY_IN_CLOSEUP",
                theme="cyber_grid",
                action_text="QUANTUM SUPREMACY",
            ),
            MascotScene(
                scene_id="lf_sc2_explainer",
                duration_seconds=4.0,
                dialogue="Superconducting circuits process multi-state qubits exponentially faster than silicon.",
                pose="pointing_right",
                expression="serious",
                view="three_quarter_left",
                camera_motion="PAN_LEFT_TO_RIGHT",
                theme="cyber_grid",
                action_text="SUPERCONDUCTING CIRCUITS",
            ),
        ],
    )

    pipeline = StoryAnimationPipeline(
        output_dir=out_dir,
        assets_dir=Path("assets/mascot"),
    )

    print(f"[2/4] Rendering 16:9 horizontal animation: '{story.title}'...")
    result = pipeline.produce_story_animation(story, fps=24)

    print(f"[3/4] Render finished: {result.video_path}")
    print(f"      File size: {result.video_path.stat().st_size} bytes")
    print(f"      Duration: {result.duration_seconds:.2f}s")

    print("[4/4] Probing with FFprobe and running full decode test...")
    probe_raw = probe_file(result.video_path)
    video_stream = next((s for s in probe_raw.get("streams", []) if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in probe_raw.get("streams", []) if s.get("codec_type") == "audio"), None)

    # Full decode integrity check
    decode_cmd = ["ffmpeg", "-v", "error", "-i", str(result.video_path), "-f", "null", "-"]
    decode_res = subprocess.run(decode_cmd, capture_output=True, text=True)
    decode_ok = decode_res.returncode == 0 and len(decode_res.stderr.strip()) == 0

    mv = MotionValidator()
    motion_score, samples, moves = mv.compute_motion_score(result.video_path, sample_interval_sec=1.0)

    # Extract 1 representative inspection frame
    sample_frame_path = out_dir / "longform_inspection_frame.png"
    subprocess.run([
        "ffmpeg", "-y", "-ss", "2.0", "-i", str(result.video_path),
        "-vframes", "1", str(sample_frame_path)
    ], check=True, capture_output=True)

    summary = {
        "format": "16:9",
        "video_path": str(result.video_path),
        "file_size_bytes": result.video_path.stat().st_size,
        "duration_seconds": result.duration_seconds,
        "width": int(video_stream.get("width")) if video_stream else 0,
        "height": int(video_stream.get("height")) if video_stream else 0,
        "codec_video": video_stream.get("codec_name") if video_stream else None,
        "codec_audio": audio_stream.get("codec_name") if audio_stream else None,
        "full_decode_passed": decode_ok,
        "full_decode_stderr": decode_res.stderr.strip(),
        "motion_score_percent": round(motion_score, 2),
        "sampled_frames": samples,
        "significant_movement_events": moves,
        "motion_verified": motion_score >= 1.0 and moves >= 1,
        "thumbnail_path": str(result.thumbnail_path),
        "srt_path": str(result.srt_path),
        "ass_path": str(result.ass_path) if result.ass_path else None,
        "inspection_frame": str(sample_frame_path),
    }

    report_file = out_dir / "longform_validation_report.json"
    report_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n[LONGFORM VALIDATION SUCCESSFUL]")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
