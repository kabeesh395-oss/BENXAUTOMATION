"""Longform-to-Shorts Scene Repurposer.

Enables the content flywheel: automatically extracts the highest-retention scenes
from a 6-9 minute Long-form documentary script and renders them into standalone,
vertical (9:16) YouTube Shorts with viral hooks, mobile-safe burned subtitles,
and seamless loop endings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from benxautomation.agents.audio_engineer import AudioEngineerAgent, AudioMixResult
from benxautomation.agents.script_director import ProductionScript, ScriptScene
from benxautomation.agents.seo_growth import SEOGrowthAgent
from benxautomation.agents.trend_scout import TopicIdea
from benxautomation.agents.video_assembler import AssemblyResult, VideoAssemblerAgent
from benxautomation.logger import get_logger

log = get_logger(__name__)


@dataclass
class RepurposedShortResult:
    """Artifacts generated for a single repurposed Short from a Long-form scene."""
    scene_index: int
    short_title: str
    video_path: Path
    thumbnail_path: Path
    description_path: Path
    duration_seconds: float
    character: str


class LongformSceneRepurposer:
    """Repurposes chapters from Long-form 16:9 episodes into 9:16 YouTube Shorts."""

    def __init__(
        self,
        output_dir: Path | str = "output/repurposed_shorts",
        audio_engineer: Optional[AudioEngineerAgent] = None,
        assembler: Optional[VideoAssemblerAgent] = None,
        seo_agent: Optional[SEOGrowthAgent] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.audio_engineer = audio_engineer or AudioEngineerAgent()
        self.assembler = assembler or VideoAssemblerAgent()
        self.seo_agent = seo_agent or SEOGrowthAgent()

    def repurpose_scene_to_short(
        self,
        longform_script: ProductionScript,
        scene_index: int,
        custom_hook: Optional[str] = None,
        fps: int = 24,
    ) -> RepurposedShortResult:
        """Extract a single high-retention scene and produce a standalone 9:16 Short."""
        matching_scenes = [s for s in longform_script.scenes if s.scene_index == scene_index]
        if not matching_scenes:
            raise ValueError(f"Scene index {scene_index} not found in longform script '{longform_script.title}'")

        target_scene = matching_scenes[0]
        char = target_scene.character

        # Formulate Short Title and Hook
        hook = custom_hook or target_scene.dialogue.split(".")[0].split("!")[0] + "!"
        short_title = f"{hook} 😱 #{char.capitalize()} #Shorts"
        short_id = f"{longform_script.topic_id}_scene_{scene_index}_short"

        log.info("Repurposing Longform scene %d (%s) into Short '%s'...", scene_index, char, short_title)

        # Build a 2-scene mini-Short script preserving the dialogue and loop
        short_scenes = [
            ScriptScene(
                scene_index=1,
                character=char,
                expression=target_scene.expression or "shocked",
                dialogue=target_scene.dialogue,
                visual_description=target_scene.visual_description,
                background_theme=target_scene.background_theme or "ben_studio",
                sfx=target_scene.sfx or "alert",
                estimated_duration=max(15.0, min(35.0, target_scene.estimated_duration)),
                pose=target_scene.pose or "pointing",
                badge_text=target_scene.badge_text or f"{char.upper()} REVEAL",
            ),
            ScriptScene(
                scene_index=2,
                character="ben" if char != "ben" else "max",
                expression="smirk",
                dialogue="Subscribe for the full untold story, and remember to",
                visual_description="Host winking and pointing back into loop",
                background_theme="ben_studio",
                sfx="whoosh",
                estimated_duration=3.5,
                pose="thumbs_up",
                badge_text="SUBSCRIBE FOR FULL STORY",
            ),
        ]

        short_script = ProductionScript(
            topic_id=short_id,
            title=short_title,
            format="shorts",
            scenes=short_scenes,
            total_estimated_duration=sum(s.estimated_duration for s in short_scenes),
            loop_sentence=hook,
        )

        run_dir = self.output_dir / short_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1. Synthesize neural audio
        audio_mix = self.audio_engineer.produce_audio(short_script, output_dir=run_dir)

        # 2. Assemble vertical video with burned ASS subtitles & motion validation
        assembly = self.assembler.assemble_video(
            script=short_script,
            audio_mix=audio_mix,
            output_dir=run_dir,
            fps=fps,
        )

        # 3. Generate high-CTR 2D Thumbnail & Metadata
        thumb_topic = TopicIdea(
            id=short_id,
            title=short_title,
            hook=hook,
            category="entertainment",
            target_character=char,
            format="shorts",
            target_duration=assembly.duration_seconds,
            curiosity_score=9.9,
            core_premise=target_scene.dialogue,
        )
        meta = self.seo_agent.generate_metadata_and_thumbnail(thumb_topic, output_dir=run_dir, script=short_script)
        desc_path = run_dir / f"{short_id}_description.txt"
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(str(meta.description) if hasattr(meta, "description") else "Subscribe for full story!")

        log.info("Repurposed Short generated successfully: %s", assembly.video_path)
        return RepurposedShortResult(
            scene_index=scene_index,
            short_title=short_title,
            video_path=assembly.video_path,
            thumbnail_path=meta.thumbnail_path,
            description_path=desc_path,
            duration_seconds=assembly.duration_seconds,
            character=char,
        )

    def repurpose_all_scenes(
        self,
        longform_script: ProductionScript,
        max_shorts: int = 3,
    ) -> List[RepurposedShortResult]:
        """Automatically repurpose top scenes from Long-form into multiple YouTube Shorts."""
        results: List[RepurposedShortResult] = []
        candidate_scenes = [
            s for s in longform_script.scenes
            if s.estimated_duration >= 10.0 and s.expression in ("shocked", "panic", "warning", "smirk", "triumph")
        ]
        if not candidate_scenes:
            candidate_scenes = longform_script.scenes[:max_shorts]

        for s in candidate_scenes[:max_shorts]:
            try:
                res = self.repurpose_scene_to_short(longform_script, scene_index=s.scene_index)
                results.append(res)
            except Exception as exc:
                log.error("Failed to repurpose scene %d: %s", s.scene_index, exc)

        return results
