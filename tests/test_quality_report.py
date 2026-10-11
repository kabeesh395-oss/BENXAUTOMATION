"""Unit tests for quality report evaluation, render validity, and script adequacy flags."""

import json
from pathlib import Path
import pytest

from benxautomation.config import AppConfig
from benxautomation.pipeline import PipelineResult, VideoPipeline
from benxautomation.renderer.base import RenderResult
from benxautomation.renderer.media_validator import MediaMetadata
from benxautomation.script.models import ScriptResult, ScriptScene


def _make_dummy_render_result(output_path: Path, width: int = 1080, height: int = 1920, duration: float = 15.0, format_name: str = "shorts_9x16") -> RenderResult:
    return RenderResult(
        output_path=output_path,
        width=width,
        height=height,
        duration_seconds=duration,
        format_name=format_name,
    )


def _make_dummy_media_meta(path: Path, is_playable: bool = True, has_video: bool = True, has_audio: bool = True) -> MediaMetadata:
    return MediaMetadata(
        path=path,
        file_size_bytes=1024,
        duration_seconds=15.0,
        width=1080,
        height=1920,
        has_video=has_video,
        has_audio=has_audio,
        is_playable=is_playable,
    )


def _make_dummy_script_res(
    topic: str = "Test Topic",
    scenes_count: int = 4,
    words_per_scene: int = 10,
    full_script_override: str | None = None,
) -> ScriptResult:
    scenes = []
    sample_narrations = [
        f"Welcome to this comprehensive overview of {topic} examining core scientific discoveries.",
        "Environmental conditions and physical factors create unique dynamics across this territory.",
        "Specialized observation equipment and sensing instruments capture detailed telemetry from the field.",
        "Further research continues to expand our understanding of this fascinating scientific domain.",
        "Scientists analyze these findings to synthesize broader conclusions for future research.",
    ]
    for i in range(1, scenes_count + 1):
        narr = sample_narrations[(i - 1) % len(sample_narrations)]
        scenes.append(
            ScriptScene(
                scene_index=i,
                title=f"Scene {i}",
                narration=narr,
                visual_description=f"Visual {i}",
                estimated_duration_seconds=5.0,
            )
        )
    full_script = full_script_override if full_script_override is not None else " ".join(s.narration for s in scenes)
    return ScriptResult(
        topic=topic,
        scenes=scenes,
        full_script=full_script,
        provider="test_provider",
        estimated_duration_seconds=20.0,
    )


class TestQualityReportEvaluation:
    def test_quality_report_all_valid_success(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy_video_bytes")

        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file, is_playable=True),
            script_result=_make_dummy_script_res("Deep Ocean Exploration"),
            narration_path=tmp_path / "audio.mp3",
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic="Deep Ocean Exploration",
            render_shorts=True,
            render_longform=False,
        )

        assert render_ok is True
        assert content_ok is True
        assert len(r_issues) == 0
        assert len(c_issues) == 0

        # Verify JSON report output
        report = pipeline.generate_quality_report(
            res,
            output_dir=tmp_path,
            stem_name="test",
            topic="Deep Ocean Exploration",
            render_shorts=True,
            render_longform=False,
        )
        assert report["success"] is True
        assert report["render_success"] is True
        assert report["content_quality_passed"] is True
        assert report["script_adequate"] is True
        assert res.success is True
        assert res.render_success is True
        assert res.content_quality_passed is True

    def test_quality_report_unplayable_output_flag(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"corrupt_video_bytes")

        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            # is_playable set to False
            shorts_metadata=_make_dummy_media_meta(shorts_file, is_playable=False),
            script_result=_make_dummy_script_res("Deep Ocean Exploration"),
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic="Deep Ocean Exploration",
            render_shorts=True,
            render_longform=False,
        )

        assert render_ok is False
        assert content_ok is True
        assert any("failed playability decode check" in issue for issue in r_issues)

        report = pipeline.generate_quality_report(
            res,
            output_dir=tmp_path,
            stem_name="test_unplayable",
            topic="Deep Ocean Exploration",
            render_shorts=True,
            render_longform=False,
        )
        assert report["success"] is False
        assert report["render_success"] is False
        assert report["content_quality_passed"] is True
        assert res.success is False

    def test_quality_report_missing_output_file_flag(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        non_existent_file = tmp_path / "does_not_exist.mp4"

        res = PipelineResult(
            shorts_result=_make_dummy_render_result(non_existent_file),
            shorts_metadata=_make_dummy_media_meta(non_existent_file),
            script_result=_make_dummy_script_res("Test"),
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic="Test",
            render_shorts=True,
            render_longform=False,
        )

        assert render_ok is False
        assert any("missing on disk" in issue for issue in r_issues)

        report = pipeline.generate_quality_report(
            res,
            output_dir=tmp_path,
            stem_name="test_missing",
            topic="Test",
            render_shorts=True,
            render_longform=False,
        )
        assert report["success"] is False
        assert report["render_success"] is False
        assert res.success is False

    def test_quality_report_insufficient_script_topic_repetition(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy")

        topic = "5 surprising facts about the deep sea"
        # Script narration merely repeats the topic string
        script_res = ScriptResult(
            topic=topic,
            scenes=[ScriptScene(scene_index=1, title="Hook", narration=topic, visual_description="Visual 1")],
            full_script=topic,
        )

        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file),
            script_result=script_res,
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic=topic,
            render_shorts=True,
            render_longform=False,
        )

        # Render succeeds, but content quality fails!
        assert render_ok is True
        assert content_ok is False
        assert any("merely repeats the topic" in issue for issue in c_issues)

        report = pipeline.generate_quality_report(
            res,
            output_dir=tmp_path,
            stem_name="test_repetition",
            topic=topic,
            render_shorts=True,
            render_longform=False,
        )
        assert report["render_success"] is True
        assert report["content_quality_passed"] is False
        assert report["script_adequate"] is False
        assert report["success"] is False
        assert res.render_success is True
        assert res.content_quality_passed is False
        assert res.success is False

    def test_quality_report_insufficient_script_single_scene(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy")

        # 1 scene with non-matching text but insufficient scene breakdown
        script_res = ScriptResult(
            topic="Topic Alpha",
            scenes=[
                ScriptScene(
                    scene_index=1,
                    title="Single Scene",
                    narration="A single long narration sentence without scene structure.",
                    visual_description="Visual 1",
                )
            ],
            full_script="A single long narration sentence without scene structure.",
        )

        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file),
            script_result=script_res,
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic="Topic Alpha",
            render_shorts=True,
            render_longform=False,
        )

        assert render_ok is True
        assert content_ok is False
        assert any("Insufficient scene breakdown" in issue for issue in c_issues)

    def test_quality_report_empty_script(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy")

        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file),
            script_result=None,
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic="Topic Beta",
            render_shorts=True,
            render_longform=False,
        )

        assert render_ok is True
        assert content_ok is False
        assert any("Script narration is missing or empty" in issue for issue in c_issues)

    def test_quality_report_silent_mode_passes_content(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy")

        # No topic, no script_text, no script_result -> silent asset-only mode
        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file),
            script_result=None,
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic=None,
            script_text=None,
            render_shorts=True,
            render_longform=False,
        )

        assert render_ok is True
        assert content_ok is True
        assert len(r_issues) == 0
        assert len(c_issues) == 0

    def test_regression_deep_sea_generic_template_fails_content_validation(self, tmp_path: Path):
        """Prove that the exact output from output/offline_topic_test_v2/video_script.json fails content validation."""
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy_video_bytes")

        topic = "5 surprising facts about the deep sea"
        deep_sea_script = (
            "Welcome to this structured overview of 5 surprising facts about the deep sea. "
            "This offline template introduces the key discussion areas for this topic. "
            "When examining 5 surprising facts about the deep sea, understanding the foundational background "
            "and core themes provides essential context for deeper study. "
            "For fact-based exploration of 5 surprising facts about the deep sea, specific claims, statistics, "
            "and historical details require independent verification from authoritative primary sources. "
            "This concludes our offline template outline on 5 surprising facts about the deep sea. "
            "Use these structured points as an organized starting framework for further research."
        )
        scenes = [
            ScriptScene(scene_index=1, title="Offline Template: Introduction", narration="Welcome to this structured overview of 5 surprising facts about the deep sea. This offline template introduces the key discussion areas for this topic.", visual_description="visual 1"),
            ScriptScene(scene_index=2, title="Offline Template: Core Context", narration="When examining 5 surprising facts about the deep sea, understanding the foundational background and core themes provides essential context for deeper study.", visual_description="visual 2"),
            ScriptScene(scene_index=3, title="Offline Template: Verification Note", narration="For fact-based exploration of 5 surprising facts about the deep sea, specific claims, statistics, and historical details require independent verification from authoritative primary sources.", visual_description="visual 3"),
            ScriptScene(scene_index=4, title="Offline Template: Summary", narration="This concludes our offline template outline on 5 surprising facts about the deep sea. Use these structured points as an organized starting framework for further research.", visual_description="visual 4"),
        ]
        script_res = ScriptResult(
            topic=topic,
            scenes=scenes,
            full_script=deep_sea_script,
            provider="manual_fallback",
            is_ai_generated=False,
        )

        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file, is_playable=True),
            script_result=script_res,
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic=topic,
            render_shorts=True,
            render_longform=False,
        )

        # Video render succeeds (playable video)
        assert render_ok is True
        # Content validation MUST fail
        assert content_ok is False
        assert len(c_issues) > 0
        issues_text = " ".join(c_issues).lower()
        # Verifies detection of generic filler, excessive topic repetition, and unfulfilled fact-list
        assert "generic template filler" in issues_text
        assert "excessive topic repetition" in issues_text
        assert "facts" in issues_text or "outline" in issues_text

        # Quality report reflects failure
        report = pipeline.generate_quality_report(
            res,
            output_dir=tmp_path,
            stem_name="deep_sea_test",
            topic=topic,
            render_shorts=True,
            render_longform=False,
        )
        assert report["render_success"] is True
        assert report["content_quality_passed"] is False
        assert report["script_adequate"] is False
        assert report["success"] is False
        assert res.success is False
        assert res.render_success is True
        assert res.content_quality_passed is False

    def test_informative_multi_sentence_manual_script_passes(self, tmp_path: Path):
        """A genuinely informative multi-sentence script passes content validation."""
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy_video_bytes")

        topic = "Deep Ocean Exploration"
        manual_script = (
            "The deep sea remains largely unexplored by human science. "
            "At depths exceeding two hundred meters, sunlight fades completely into total darkness. "
            "Many abyssal creatures produce their own illumination through chemical bioluminescence. "
            "Specialized submersibles are engineered to withstand the extreme atmospheric pressure in ocean trenches."
        )
        scenes = [
            ScriptScene(scene_index=1, title="Hook", narration="The deep sea remains largely unexplored by human science.", visual_description="Dark ocean"),
            ScriptScene(scene_index=2, title="Point 1", narration="At depths exceeding two hundred meters, sunlight fades completely into total darkness.", visual_description="Twilight zone transition"),
            ScriptScene(scene_index=3, title="Point 2", narration="Many abyssal creatures produce their own illumination through chemical bioluminescence.", visual_description="Bioluminescent anglerfish"),
            ScriptScene(scene_index=4, title="Conclusion", narration="Specialized submersibles are engineered to withstand the extreme atmospheric pressure in ocean trenches.", visual_description="Research submarine in trench"),
        ]
        script_res = ScriptResult(
            topic=topic,
            scenes=scenes,
            full_script=manual_script,
            provider="manual_fallback",
            is_ai_generated=False,
        )

        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file, is_playable=True),
            script_result=script_res,
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res,
            topic=topic,
            script_text=manual_script,
            render_shorts=True,
            render_longform=False,
        )

        assert render_ok is True
        assert content_ok is True
        assert len(c_issues) == 0

        report = pipeline.generate_quality_report(
            res,
            output_dir=tmp_path,
            stem_name="manual_informative_test",
            topic=topic,
            script_text=manual_script,
            render_shorts=True,
            render_longform=False,
        )
        assert report["render_success"] is True
        assert report["content_quality_passed"] is True
        assert report["script_adequate"] is True
        assert report["success"] is True
        assert res.success is True

    def test_insufficient_facts_for_list_topic_fails_content_validation(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy_video_bytes")

        topic = "5 surprising facts about the deep sea"
        # Only 3 scenes provided for a 5-fact request
        scenes = [
            ScriptScene(scene_index=1, title="Fact 1: Ocean Depth", narration="The Mariana Trench reaches almost eleven thousand meters deep.", visual_description="Trench map"),
            ScriptScene(scene_index=2, title="Fact 2: Bioluminescence", narration="Most deep sea organisms generate their own light to survive.", visual_description="Glowing fish"),
            ScriptScene(scene_index=3, title="Fact 3: Hydrothermal Vents", narration="Underwater geysers erupt with mineral-rich boiling water.", visual_description="Vents"),
        ]
        script_res = ScriptResult(
            topic=topic,
            scenes=scenes,
            full_script=" ".join(s.narration for s in scenes),
            provider="gemini",
            is_ai_generated=True,
        )
        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file, is_playable=True),
            script_result=script_res,
            narration_path=tmp_path / "audio.mp3",
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res, topic=topic, render_shorts=True, render_longform=False
        )
        assert render_ok is True
        assert content_ok is False
        assert any("Missing list items" in iss for iss in c_issues)

        report = pipeline.generate_quality_report(
            res, output_dir=tmp_path, stem_name="insufficient_facts", topic=topic
        )
        assert report["success"] is False
        assert report["research_status"]["passed"] is False
        assert report["final_acceptance_status"]["passed"] is False

    def test_duplicate_facts_fails_content_validation(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy_video_bytes")

        topic = "5 surprising facts about the deep sea"
        scenes = [
            ScriptScene(scene_index=1, title="Fact 1: Bioluminescence", narration="Creatures in the deep ocean create their own light.", visual_description="Glow"),
            ScriptScene(scene_index=2, title="Fact 2: Extreme Pressure", narration="The pressure at the ocean floor can crush steel vessels.", visual_description="Submarine"),
            ScriptScene(scene_index=3, title="Fact 3: Bioluminescence", narration="Creatures in the deep ocean create their own light.", visual_description="Glow 2"),  # Duplicate title & narration
            ScriptScene(scene_index=4, title="Fact 4: Cold Temperatures", narration="Water temperatures near the bottom hover close to freezing.", visual_description="Ice"),
            ScriptScene(scene_index=5, title="Fact 5: Unexplored Depths", narration="Over eighty percent of the ocean floor remains unexplored.", visual_description="Map"),
        ]
        script_res = ScriptResult(
            topic=topic,
            scenes=scenes,
            full_script=" ".join(s.narration for s in scenes),
            provider="gemini",
            is_ai_generated=True,
        )
        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file, is_playable=True),
            script_result=script_res,
            narration_path=tmp_path / "audio.mp3",
        )

        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res, topic=topic, render_shorts=True, render_longform=False
        )
        assert content_ok is False
        assert any("Duplicate fact" in iss for iss in c_issues)

        report = pipeline.generate_quality_report(
            res, output_dir=tmp_path, stem_name="dup_facts", topic=topic
        )
        assert report["success"] is False
        assert report["research_status"]["duplicate_facts_detected"] is True

    def test_empty_narration_in_scene_fails_content_validation(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy_video_bytes")

        topic = "Deep Sea Life"
        scenes = [
            ScriptScene(scene_index=1, title="Intro", narration="Welcome to the deep ocean abyss.", visual_description="Deep"),
            ScriptScene(scene_index=2, title="Middle", narration="   ", visual_description="Empty"),
        ]
        script_res = ScriptResult(
            topic=topic,
            scenes=scenes,
            full_script="Welcome to the deep ocean abyss.",
            provider="gemini",
            is_ai_generated=True,
        )
        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file, is_playable=True),
            script_result=script_res,
        )
        render_ok, content_ok, r_issues, c_issues = pipeline.evaluate_quality(
            res, topic=topic, render_shorts=True, render_longform=False
        )
        assert content_ok is False
        assert any("empty or insufficient narration" in iss for iss in c_issues)

    def test_valid_five_facts_passes_all_stages(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        shorts_file = tmp_path / "video_shorts.mp4"
        shorts_file.write_bytes(b"dummy_video_bytes")
        sub_file = tmp_path / "video_subtitles.srt"
        sub_file.write_text("1\n00:00:00,000 --> 00:00:05,000\nSub title\n", encoding="utf-8")

        topic = "5 surprising facts about the deep sea"
        scenes = [
            ScriptScene(scene_index=1, title="Fact 1: Artifacts", narration="There are more artifacts in the deep sea than all museums combined.", visual_description="Ancient wreck", fact_number=1, source="UNESCO"),
            ScriptScene(scene_index=2, title="Fact 2: Hydrothermal Vents", narration="Deep sea hydrothermal vents support chemosynthesis independent of sunlight.", visual_description="Black smoker", fact_number=2, source="WHOI"),
            ScriptScene(scene_index=3, title="Fact 3: Sea Floor Mapping", narration="Less than twenty-five percent of our ocean floor has been mapped with modern sonar.", visual_description="Bathymetry", fact_number=3, source="NOAA"),
            ScriptScene(scene_index=4, title="Fact 4: Living Light", narration="Over seventy-five percent of abyssal creatures generate bioluminescence.", visual_description="Lanternfish", fact_number=4, source="MBARI"),
            ScriptScene(scene_index=5, title="Fact 5: Ocean Conveyor", narration="Abyssal conveyor currents take a millennium to circle the globe.", visual_description="Currents", fact_number=5, source="NASA JPL"),
        ]
        sources = [
            {"fact_number": 1, "source": "UNESCO"},
            {"fact_number": 2, "source": "WHOI"},
            {"fact_number": 3, "source": "NOAA"},
            {"fact_number": 4, "source": "MBARI"},
            {"fact_number": 5, "source": "NASA JPL"},
        ]
        script_res = ScriptResult(
            topic=topic,
            scenes=scenes,
            full_script=" ".join(s.narration for s in scenes),
            provider="gemini",
            model="gemini-3.5-flash",
            is_ai_generated=True,
            research_sources=sources,
            facts_count=5,
        )
        res = PipelineResult(
            shorts_result=_make_dummy_render_result(shorts_file),
            shorts_metadata=_make_dummy_media_meta(shorts_file, is_playable=True),
            script_result=script_res,
            narration_path=tmp_path / "audio.mp3",
            subtitle_path=sub_file,
        )

        report = pipeline.generate_quality_report(
            res,
            output_dir=tmp_path,
            stem_name="valid_five_facts",
            topic=topic,
            render_shorts=True,
            render_longform=False,
            calc_duration=35.0,
            actual_audio_dur=35.0,
            has_subtitles=True,
        )

        assert report["success"] is True
        assert report["final_acceptance_status"]["passed"] is True
        assert report["script_status"]["passed"] is True
        assert report["research_status"]["passed"] is True
        assert report["research_status"]["expected_facts_count"] == 5
        assert len(report["research_status"]["sources_recorded"]) == 5
        assert report["rendering_status"]["passed"] is True
        assert report["rendering_status"]["is_3d_animation"] is False
        assert report["audio_status"]["passed"] is True
        assert report["subtitle_status"]["passed"] is True

