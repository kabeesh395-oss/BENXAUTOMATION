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
        """Create structured scenes from manual text or split topic."""
        source_text = (self.manual_script_text or "").strip()
        if not source_text:
            source_text = request.topic.strip()

        if not source_text:
            raise ScriptGenerationError("Cannot create script from empty input.")

        # Split into sentences or sensible paragraphs
        raw_parts = [p.strip() for p in re.split(r'(?<=[.!?。！？])\s+|\n+', source_text) if p.strip()]
        if not raw_parts:
            raw_parts = [source_text]

        # Structure into Hook, Body points, and Outro
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
