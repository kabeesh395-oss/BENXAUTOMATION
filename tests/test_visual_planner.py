"""Unit tests for ScenePlanner and visual asset selection."""

from pathlib import Path
import pytest

from benxautomation.asset_manifest import AssetEntry, LicenseManifest
from benxautomation.errors import ScenePlanningError
from benxautomation.script.models import ScriptResult, ScriptScene
from benxautomation.visuals import ScenePlanner


class TestScenePlanner:
    def test_empty_scenes_raises_error(self, tmp_path: Path):
        planner = ScenePlanner(assets_dir=tmp_path)
        script_res = ScriptResult(topic="Empty", scenes=[])
        with pytest.raises(ScenePlanningError, match="no scenes"):
            planner.plan_visuals(script_res, total_audio_duration=10.0)

    def test_zero_duration_raises_error(self, tmp_path: Path):
        planner = ScenePlanner(assets_dir=tmp_path)
        script_res = ScriptResult(
            topic="Test",
            scenes=[ScriptScene(scene_index=1, title="H", narration="Text", visual_description="V")],
        )
        with pytest.raises(ScenePlanningError, match="greater than zero"):
            planner.plan_visuals(script_res, total_audio_duration=0.0)

    def test_single_asset_override(self, tmp_path: Path):
        override_file = tmp_path / "custom.png"
        override_file.write_bytes(b"data")

        planner = ScenePlanner(assets_dir=tmp_path)
        script_res = ScriptResult(
            topic="Custom",
            scenes=[
                ScriptScene(scene_index=1, title="S1", narration="N1", visual_description="V1"),
                ScriptScene(scene_index=2, title="S2", narration="N2", visual_description="V2"),
            ],
        )

        plan = planner.plan_visuals(script_res, total_audio_duration=12.0, single_asset_override=override_file)
        assert len(plan.scenes) == 2
        assert plan.is_multi_scene is False
        assert plan.scenes[0].asset_path == override_file
        assert plan.scenes[1].asset_path == override_file
        assert sum(s.duration_seconds for s in plan.scenes) == pytest.approx(12.0, 0.05)

    def test_multi_scene_matching_from_manifest(self, tmp_path: Path):
        img1 = tmp_path / "deep_sea_abyss.jpg"
        img1.write_bytes(b"img1")
        img2 = tmp_path / "deep_sea_submersible.jpg"
        img2.write_bytes(b"img2")

        manifest = LicenseManifest(
            assets=[
                AssetEntry(
                    file="deep_sea_abyss.jpg",
                    license="cc0",
                    attribution="Abyss photo",
                    source_url="local://deep_sea_abyss.jpg",
                ),
                AssetEntry(
                    file="deep_sea_submersible.jpg",
                    license="cc0",
                    attribution="Submersible vehicle",
                    source_url="local://deep_sea_submersible.jpg",
                ),
            ]
        )

        planner = ScenePlanner(assets_dir=tmp_path, manifest=manifest)
        script_res = ScriptResult(
            topic="Deep Ocean",
            scenes=[
                ScriptScene(
                    scene_index=1,
                    title="Abyss Depth",
                    narration="The deep sea abyss is dark and full of wonder.",
                    visual_description="Dark abyss with bioluminescence",
                ),
                ScriptScene(
                    scene_index=2,
                    title="Submersible Dive",
                    narration="A research submersible dives deeper into the trench.",
                    visual_description="Submersible vehicle exploring",
                ),
            ],
        )

        plan = planner.plan_visuals(script_res, total_audio_duration=15.0)
        assert len(plan.scenes) == 2
        assert plan.is_multi_scene is True
        # Scene 1 should match abyss
        assert plan.scenes[0].asset_path == img1
        # Scene 2 should match submersible
        assert plan.scenes[1].asset_path == img2
        assert plan.scenes[0].license == "cc0"
        assert sum(s.duration_seconds for s in plan.scenes) == pytest.approx(15.0, 0.05)

    def test_missing_asset_raises(self, tmp_path: Path):
        manifest = LicenseManifest(
            assets=[
                AssetEntry(file="missing.jpg", license="cc0"),
            ]
        )
        planner = ScenePlanner(assets_dir=tmp_path, manifest=manifest)
        script_res = ScriptResult(
            topic="Test",
            scenes=[ScriptScene(scene_index=1, title="S", narration="N", visual_description="V")],
        )
        with pytest.raises(ScenePlanningError, match="No visual assets found"):
            planner.plan_visuals(script_res, total_audio_duration=5.0)

    def test_empty_asset_file_raises(self, tmp_path: Path):
        empty_img = tmp_path / "empty.png"
        empty_img.write_bytes(b"")  # 0 bytes
        planner = ScenePlanner(assets_dir=tmp_path)
        script_res = ScriptResult(
            topic="Test",
            scenes=[ScriptScene(scene_index=1, title="S", narration="N", visual_description="V")],
        )
        with pytest.raises(ScenePlanningError, match="No visual assets found"):
            planner.plan_visuals(script_res, total_audio_duration=5.0)
