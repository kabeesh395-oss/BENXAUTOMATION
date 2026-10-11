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

    def test_test_cards_deprioritized_when_production_assets_present(self, tmp_path: Path):
        test_card = tmp_path / "sample_card.bmp"
        test_card.write_bytes(b"bmp_dummy")
        img1 = tmp_path / "deep_sea_abyss.jpg"
        img1.write_bytes(b"img1")
        img2 = tmp_path / "deep_sea_submersible.jpg"
        img2.write_bytes(b"img2")

        manifest = LicenseManifest(
            assets=[
                AssetEntry(file="sample_card.bmp", license="cc0", attribution="Generated test card asset"),
                AssetEntry(file="deep_sea_abyss.jpg", license="original", attribution="Deep sea abyss"),
                AssetEntry(file="deep_sea_submersible.jpg", license="original", attribution="Deep ocean exploration submersible vehicle"),
            ]
        )
        planner = ScenePlanner(assets_dir=tmp_path, manifest=manifest)
        script_res = ScriptResult(
            topic="5 surprising facts about the deep sea",
            scenes=[
                ScriptScene(scene_index=1, title="Overview", narration="Overview text", visual_description="Title card presenting exploratory research outline for 5 surprising facts about the deep sea"),
                ScriptScene(scene_index=2, title="Sources", narration="Sources text", visual_description="Graphic representing research methodology"),
                ScriptScene(scene_index=3, title="Verification", narration="Verification text", visual_description="Information visual noting verification"),
                ScriptScene(scene_index=4, title="Next Steps", narration="Closing text", visual_description="Concluding guide card for completing research"),
            ],
        )
        plan = planner.plan_visuals(script_res, total_audio_duration=20.0)
        # All scenes must use genuine production assets, never sample_card.bmp
        assert all(s.asset_path.name != "sample_card.bmp" for s in plan.scenes)
        assert all("deep_sea" in s.asset_path.name for s in plan.scenes)

    def test_multi_scene_allocates_distinct_assets_when_available(self, tmp_path: Path):
        for i in range(1, 5):
            (tmp_path / f"scene_{i}.jpg").write_bytes(f"img_{i}".encode())

        manifest = LicenseManifest(
            assets=[AssetEntry(file=f"scene_{i}.jpg", license="cc0") for i in range(1, 5)]
        )
        planner = ScenePlanner(assets_dir=tmp_path, manifest=manifest)
        script_res = ScriptResult(
            topic="Ocean Wonders",
            scenes=[
                ScriptScene(scene_index=i, title=f"Scene {i}", narration=f"Narration for scene {i}", visual_description=f"Visual {i}")
                for i in range(1, 5)
            ],
        )
        plan = planner.plan_visuals(script_res, total_audio_duration=12.0)
        assert len(plan.scenes) == 4
        assert plan.distinct_assets_count == 4
        assert plan.has_repeated_assets is False
        assert len({s.asset_path for s in plan.scenes}) == 4

    def test_scenes_receive_alternating_motion_effects(self, tmp_path: Path):
        for i in range(1, 5):
            (tmp_path / f"asset_{i}.jpg").write_bytes(b"data")

        manifest = LicenseManifest(
            assets=[AssetEntry(file=f"asset_{i}.jpg", license="cc0") for i in range(1, 5)]
        )
        planner = ScenePlanner(assets_dir=tmp_path, manifest=manifest)
        script_res = ScriptResult(
            topic="Motion Test",
            scenes=[
                ScriptScene(scene_index=i, title=f"Scene {i}", narration=f"N {i}", visual_description=f"V {i}")
                for i in range(1, 5)
            ],
        )
        plan = planner.plan_visuals(script_res, total_audio_duration=16.0)
        expected_effects = ["zoom_in", "pan_left", "zoom_out", "pan_right"]
        actual_effects = [s.motion_effect for s in plan.scenes]
        assert actual_effects == expected_effects
        assert plan.animation_type == "2d_motion"

    def test_global_matching_prevents_greedy_asset_starvation(self, tmp_path: Path):
        """Verify an earlier generic scene does not starve a subsequent scene of its exact matching asset."""
        gen_img = tmp_path / "deep_sea_jellyfish.jpg"
        gen_img.write_bytes(b"jelly")
        vent_img = tmp_path / "deep_sea_hydrothermal_vent.jpg"
        vent_img.write_bytes(b"vent")

        manifest = LicenseManifest(
            assets=[
                AssetEntry(file="deep_sea_jellyfish.jpg", license="cc0", attribution="Abyssal jellyfish cluster"),
                AssetEntry(file="deep_sea_hydrothermal_vent.jpg", license="cc0", attribution="Hydrothermal vent black smoker chimney"),
            ]
        )
        planner = ScenePlanner(assets_dir=tmp_path, manifest=manifest)
        script_res = ScriptResult(
            topic="5 surprising facts about the deep sea",
            scenes=[
                ScriptScene(
                    scene_index=1,
                    title="Fact 1: Ocean Overview",
                    narration="Much of the ocean is mysterious and unexplored.",
                    visual_description="General underwater scene",
                ),
                ScriptScene(
                    scene_index=2,
                    title="Fact 2: Water Hotter Than Lava",
                    narration="Hydrothermal vents blast superheated mineral water from deep sea chimneys.",
                    visual_description="Close up of black smoker hydrothermal vent chimney",
                ),
            ],
        )
        plan = planner.plan_visuals(script_res, total_audio_duration=10.0)
        assert len(plan.scenes) == 2
        # Scene 2 must get hydrothermal vent, NOT jellyfish
        assert plan.scenes[1].asset_path == vent_img
        # Scene 1 gets jellyfish
        assert plan.scenes[0].asset_path == gen_img
