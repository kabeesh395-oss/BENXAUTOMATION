"""Unit tests for Longform-to-Shorts Scene Repurposer."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from benxautomation.agents.audio_engineer import AudioMixResult
from benxautomation.agents.script_director import ProductionScript, ScriptScene
from benxautomation.agents.video_assembler import AssemblyResult
from benxautomation.animation.motion_validator import MotionValidationResult
from benxautomation.repurpose.scene_repurposer import LongformSceneRepurposer, RepurposedShortResult


def test_repurpose_scene_to_short_structure():
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir)

        mock_audio = MagicMock()
        mock_audio.produce_audio.return_value = AudioMixResult(
            mp3_path=out_path / "mock.mp3",
            wav_path=out_path / "mock.wav",
            total_duration=5.0,
            scene_timestamps=[(0.0, 5.0, "Scene 1")],
        )

        mock_assembler = MagicMock()
        mock_assembler.assemble_video.return_value = AssemblyResult(
            video_path=out_path / "short_final.mp4",
            ass_path=out_path / "short.ass",
            duration_seconds=5.0,
            total_frames=120,
            fps=24,
            resolution=(1080, 1920),
            motion_validation=MotionValidationResult(
                is_valid=True,
                motion_score=9.5,
                total_frames_sampled=24,
                moving_scene_transitions=2,
                duration_seconds=5.0,
                width=1080,
                height=1920,
                decode_passed=True,
                reasons=[],
            ),
        )

        mock_seo = MagicMock()
        mock_meta = MagicMock()
        mock_meta.thumbnail_path = out_path / "thumb.jpg"
        mock_meta.description_path = out_path / "desc.txt"
        mock_seo.generate_metadata_and_thumbnail.return_value = mock_meta

        repurposer = LongformSceneRepurposer(
            output_dir=out_path,
            audio_engineer=mock_audio,
            assembler=mock_assembler,
            seo_agent=mock_seo,
        )

        longform_script = ProductionScript(
            topic_id="quantum_doc",
            title="The Quantum Computing Revolution",
            format="longform",
            scenes=[
                ScriptScene(
                    scene_index=1,
                    character="dr_quantum",
                    expression="shocked",
                    dialogue="A single quantum qubit can exist in two realities at the exact same time!",
                    visual_description="Dr Quantum holding glowing atomic model",
                    background_theme="quantum_lab",
                    sfx="spark",
                    estimated_duration=12.0,
                    pose="holding_prop",
                    badge_text="QUANTUM SUPERPOSITION",
                )
            ],
            total_estimated_duration=12.0,
        )

        res = repurposer.repurpose_scene_to_short(longform_script, scene_index=1)

        assert isinstance(res, RepurposedShortResult)
        assert res.scene_index == 1
        assert res.character == "dr_quantum"
        assert res.video_path == out_path / "short_final.mp4"
        assert "A single quantum qubit" in res.short_title
