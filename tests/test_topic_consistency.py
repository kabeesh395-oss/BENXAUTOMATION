"""Tests for topic-to-scene consistency validation and heading sanitization."""

from pathlib import Path
import pytest

from benxautomation.config import AppConfig
from benxautomation.pipeline import PipelineResult, VideoPipeline
from benxautomation.script.gemini_provider import GeminiScriptProvider
from benxautomation.script.models import ScriptResult, ScriptScene


class TestTopicConsistencyValidation:
    @pytest.fixture
    def pipeline(self):
        return VideoPipeline(AppConfig())

    def test_off_topic_heading_detected_and_rejected(self, pipeline):
        """Verify an off-topic heading like 'Mars is Better Mapped' is rejected for deep sea topic."""
        script_res = ScriptResult(
            topic="5 surprising facts about the deep sea",
            scenes=[
                ScriptScene(
                    scene_index=1,
                    title="Fact 1: Underwater Lakes",
                    narration="Deep ocean floor contains lakes and waves.",
                    visual_description="Submersible light on brine pool",
                ),
                ScriptScene(
                    scene_index=2,
                    title="Fact 2: Mars is Better Mapped",  # Off-topic heading!
                    narration="We have better maps of Mars than our own ocean floor.",
                    visual_description="Topographic map of Mars",
                ),
            ],
            full_script="Deep ocean floor contains lakes and waves. We have better maps of Mars than our own ocean floor.",
        )
        res = PipelineResult(script_result=script_res)
        _, content_passed, _, content_issues = pipeline.evaluate_quality(
            res,
            topic="5 surprising facts about the deep sea",
            render_shorts=False,
            render_longform=False,
        )
        assert content_passed is False
        assert any("inconsistent scene heading" in iss.lower() for iss in content_issues)
        assert any("Mars is Better Mapped" in iss for iss in content_issues)

    def test_consistent_ocean_heading_passes(self, pipeline):
        """Verify consistent ocean headings pass quality evaluation."""
        script_res = ScriptResult(
            topic="5 surprising facts about the deep sea",
            scenes=[
                ScriptScene(
                    scene_index=1,
                    title="Fact 1: Underwater Lakes",
                    narration="Deep ocean floor contains lakes and waves.",
                    visual_description="Submersible light on brine pool",
                ),
                ScriptScene(
                    scene_index=2,
                    title="Fact 2: Unmapped Ocean Floor",  # Consistent heading!
                    narration="We have better maps of outer space than our own ocean floor.",
                    visual_description="Dark ocean floor mapping animation",
                ),
            ],
            full_script="Deep ocean floor contains lakes and waves. We have better maps of outer space than our own ocean floor.",
        )
        res = PipelineResult(script_result=script_res)
        _, content_passed, _, content_issues = pipeline.evaluate_quality(
            res,
            topic="5 surprising facts about the deep sea",
            render_shorts=False,
            render_longform=False,
        )
        # Check no consistency issues
        consistency_issues = [iss for iss in content_issues if "inconsistent scene heading" in iss.lower()]
        assert len(consistency_issues) == 0

    def test_space_topic_detects_aquatic_heading_clash(self, pipeline):
        """Verify space topic rejects unrelated aquatic headings."""
        script_res = ScriptResult(
            topic="5 incredible facts about the solar system",
            scenes=[
                ScriptScene(
                    scene_index=1,
                    title="Fact 1: The Great Red Spot",
                    narration="Jupiter has a giant atmospheric storm.",
                    visual_description="Jupiter storm system",
                ),
                ScriptScene(
                    scene_index=2,
                    title="Fact 2: Deep Sea Submersible",  # Off-topic heading for space!
                    narration="Telescopes orbit outer space exploring planets.",
                    visual_description="Underwater vehicle",
                ),
            ],
            full_script="Jupiter has a giant atmospheric storm. Telescopes orbit outer space exploring planets.",
        )
        res = PipelineResult(script_result=script_res)
        _, content_passed, _, content_issues = pipeline.evaluate_quality(
            res,
            topic="5 incredible facts about the solar system",
            render_shorts=False,
            render_longform=False,
        )
        assert content_passed is False
        assert any("inconsistent scene heading" in iss.lower() for iss in content_issues)


class TestHeadingRefinement:
    def test_refines_mars_comparison_heading_in_ocean_topic(self):
        refined = GeminiScriptProvider._refine_topic_heading(
            title="Fact 2: Mars is Better Mapped",
            topic="5 surprising facts about the deep sea",
            narration="We have far better high-resolution maps of Mars and the Moon than our own ocean floor.",
        )
        assert refined == "Unmapped Ocean Floor"

    def test_preserves_on_topic_headings(self):
        title = "Underwater Lakes"
        refined = GeminiScriptProvider._refine_topic_heading(
            title=title,
            topic="5 surprising facts about the deep sea",
            narration="Deep ocean brine pools form lakes under the sea.",
        )
        assert refined == title
