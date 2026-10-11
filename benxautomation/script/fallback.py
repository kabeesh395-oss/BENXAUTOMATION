"""Offline and manual fallback script provider."""

from __future__ import annotations

import re
from typing import Optional

from benxautomation.errors import ScriptGenerationError
from benxautomation.script.models import ScriptRequest, ScriptResult, ScriptScene
from benxautomation.script.provider import ScriptProvider


class ManualFallbackScriptProvider(ScriptProvider):
    """Structures manual text scripts or offline topics into timed scenes without external APIs."""

    def __init__(self, manual_script_text: Optional[str] = None):
        self.manual_script_text = manual_script_text

    @property
    def provider_name(self) -> str:
        return "manual_fallback"

    def generate_script(self, request: ScriptRequest) -> ScriptResult:
        """Create structured scenes from manual text or offline deterministic template."""
        manual_text = (self.manual_script_text or "").strip()
        topic = (request.topic or "").strip()

        if manual_text:
            return self._structure_manual_script(manual_text, request)

        if not topic:
            raise ScriptGenerationError("Cannot create script from empty input.")

        return self._generate_offline_template(topic, request)

    def _structure_manual_script(self, manual_text: str, request: ScriptRequest) -> ScriptResult:
        """Preserve exact manual script text by structuring it into scenes without expanding or replacing."""
        raw_parts = [p.strip() for p in re.split(r'(?<=[.!?。！？])\s+|\n+', manual_text) if p.strip()]
        if not raw_parts:
            raw_parts = [manual_text]

        num_parts = len(raw_parts)
        dur = max(5.0, float(request.duration_seconds))
        per_scene_dur = dur / num_parts

        scenes: list[ScriptScene] = []
        for idx, part in enumerate(raw_parts, start=1):
            if idx == 1:
                title = "Hook"
                desc = f"Visual opening introducing {request.topic}"
            elif idx == num_parts:
                title = "Conclusion"
                desc = f"Summary or closing scene for {request.topic}"
            else:
                title = f"Point {idx - 1}"
                desc = f"Illustrative scene focusing on {part[:40]}..."

            scenes.append(
                ScriptScene(
                    scene_index=idx,
                    title=title,
                    narration=part,
                    visual_description=desc,
                    estimated_duration_seconds=round(per_scene_dur, 2),
                )
            )

        full_script = " ".join(s.narration for s in scenes)
        return ScriptResult(
            topic=request.topic,
            scenes=scenes,
            full_script=full_script,
            provider=self.provider_name,
            model=None,
            target_audience=request.target_audience,
            language=request.language,
            tone=request.tone,
            estimated_duration_seconds=dur,
            is_ai_generated=False,
        )

    def _generate_offline_template(self, topic: str, request: ScriptRequest) -> ScriptResult:
        """Generate a structured, clearly labelled offline template without claiming AI or verified facts."""
        clean_topic = topic.strip().rstrip(".!?")
        dur = max(5.0, float(request.duration_seconds))

        is_fact_list = bool(re.search(
            r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|top\s+\d+)\s+(surprising\s+)?(facts|reasons|tips|secrets|ways|things|habits|steps)\b",
            clean_topic,
            re.IGNORECASE,
        ))

        if is_fact_list:
            template_defs = [
                (
                    "Research Outline: Overview",
                    f"This is an unverified research outline for {clean_topic}. This offline template does not provide the requested verified facts, which require primary research.",
                    f"Title visual presenting exploratory research outline for {clean_topic}",
                ),
                (
                    "Research Outline: Sources",
                    "When investigating this topic, authoritative databases, scientific publications, and verified records must be referenced.",
                    f"Graphic representing research methodology and primary documentation for {clean_topic}",
                ),
                (
                    "Research Outline: Verification",
                    "Specific claims, data points, and factual figures must be independently verified from credible primary sources.",
                    f"Information visual noting verification and evidence requirements for {clean_topic}",
                ),
                (
                    "Research Outline: Next Steps",
                    "To complete this presentation, replace this structural outline with verified findings or a custom manual script.",
                    f"Concluding summary visual for completing research on {clean_topic}",
                ),
            ]
        elif dur < 15.0:
            template_defs = [
                (
                    "Topic Overview",
                    f"Exploring {clean_topic} reveals an extraordinary subject with significant areas of interest.",
                    f"Title card introducing overview of {clean_topic}",
                ),
                (
                    "Exploration & Analysis",
                    "Observational data and field research provide critical perspectives across this domain.",
                    f"Informational visual illustrating key areas of {clean_topic}",
                ),
                (
                    "Summary & Outlook",
                    "Ongoing investigation continues to expand our understanding of this subject.",
                    f"Concluding visual summarizing {clean_topic}",
                ),
            ]
        elif dur < 40.0:
            template_defs = [
                (
                    "Topic Introduction",
                    f"Exploring {clean_topic} reveals an extraordinary world beyond everyday experience.",
                    f"Title card introducing overview of {clean_topic}",
                ),
                (
                    "Context & Environment",
                    "Extreme environments and specialized adaptations shape the unique conditions found across this realm.",
                    f"Contextual visual illustrating features of {clean_topic}",
                ),
                (
                    "Exploration & Research",
                    "Exploration teams utilize specialized submersibles and remote sensing technology to observe and gather scientific data.",
                    f"Graphic highlighting exploration methodology for {clean_topic}",
                ),
                (
                    "Summary & Outlook",
                    "Ongoing research continues to uncover new findings, expanding our understanding of these mysterious frontiers.",
                    f"Concluding visual summarizing {clean_topic}",
                ),
            ]
        else:
            template_defs = [
                (
                    "Topic Introduction",
                    f"Exploring {clean_topic} reveals an extraordinary world beyond everyday experience.",
                    f"Title card introducing overview of {clean_topic}",
                ),
                (
                    "Context & Environment",
                    "Extreme environments and specialized adaptations shape the unique conditions found across this realm.",
                    f"Contextual visual illustrating features of {clean_topic}",
                ),
                (
                    "Detailed Analysis",
                    "Scientific observations and specialized surveys provide deeper insights into environmental interactions and biodiversity.",
                    f"Detailed breakdown visual for {clean_topic}",
                ),
                (
                    "Exploration & Research",
                    "Exploration teams utilize specialized submersibles and remote sensing technology to observe and gather scientific data.",
                    f"Graphic highlighting exploration methodology for {clean_topic}",
                ),
                (
                    "Summary & Outlook",
                    "Ongoing research continues to uncover new findings, expanding our understanding of these mysterious frontiers.",
                    f"Concluding visual summarizing {clean_topic}",
                ),
            ]

        num_scenes = len(template_defs)
        per_scene_dur = dur / num_scenes

        scenes: list[ScriptScene] = []
        for idx, (title, narration, desc) in enumerate(template_defs, start=1):
            scenes.append(
                ScriptScene(
                    scene_index=idx,
                    title=title,
                    narration=narration,
                    visual_description=desc,
                    estimated_duration_seconds=round(per_scene_dur, 2),
                )
            )

        full_script = " ".join(s.narration for s in scenes)
        return ScriptResult(
            topic=request.topic,
            scenes=scenes,
            full_script=full_script,
            provider=self.provider_name,
            model=None,
            target_audience=request.target_audience,
            language=request.language,
            tone=request.tone,
            estimated_duration_seconds=dur,
            is_ai_generated=False,
        )
