"""Agent 7: Master Autonomous Orchestrator.

Coordinates Agent 1 through Agent 6 in an automated production pipeline:
Trend Hunter -> Script Director -> Sonic Studio -> 2D Animator -> Video Assembler -> SEO & Thumbnail -> Publisher.
Provides 1-click execution for daily viral Shorts and in-depth Longform documentaries.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from benxautomation.agents.animator import CartoonAnimatorAgent
from benxautomation.agents.audio_engineer import AudioEngineerAgent, AudioMixResult
from benxautomation.agents.script_director import ProductionScript, ScriptDirectorAgent
from benxautomation.agents.seo_growth import SEOGrowthAgent, SEOPackage
from benxautomation.agents.trend_scout import TopicIdea, TrendScoutAgent
from benxautomation.agents.video_assembler import AssemblyResult, VideoAssemblerAgent
from benxautomation.config import PublishingConfig
from benxautomation.logger import get_logger
from benxautomation.publisher.ledger import UploadLedger
from benxautomation.publisher.youtube import YouTubePublisher
from benxautomation.repurpose.scene_repurposer import LongformSceneRepurposer

log = get_logger(__name__)


@dataclass
class PipelineRunResult:
    """Consolidated summary of the autonomous pipeline run."""
    topic_id: str
    title: str
    format: str
    video_path: str
    audio_path: str
    thumbnail_path: str
    ass_path: str
    duration_seconds: float
    motion_verified: bool
    motion_score: float
    metadata_path: str
    published: bool = False
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    repurposed_shorts: List[Dict[str, Any]] = field(default_factory=list)


class MasterOrchestratorAgent:
    """Agent 7: The Master Orchestrator managing end-to-end autonomous video production."""

    def __init__(
        self,
        output_base_dir: Path | str = "output/autonomous_runs",
        publishing_config: Optional[PublishingConfig] = None,
    ):
        self.output_base = Path(output_base_dir)
        self.output_base.mkdir(parents=True, exist_ok=True)

        # Initialize Agents
        self.scout = TrendScoutAgent()
        self.director = ScriptDirectorAgent()
        self.animator = CartoonAnimatorAgent()
        self.audio = AudioEngineerAgent()
        self.assembler = VideoAssemblerAgent(animator=self.animator)
        self.seo = SEOGrowthAgent()
        self.repurposer = LongformSceneRepurposer(
            audio_engineer=self.audio,
            assembler=self.assembler,
            seo_agent=self.seo,
        )
        self.ledger = UploadLedger()
        self.publishing_config = publishing_config

    def run_pipeline(
        self,
        format_type: str = "shorts",
        category: Optional[str] = None,
        custom_topic: Optional[str] = None,
        publish_to_youtube: bool = False,
        privacy_status: str = "public",
        auto_repurpose_shorts: bool = True,
    ) -> PipelineRunResult:
        """Execute the complete multi-agent production lifecycle."""
        log.info("=== STARTING AUTONOMOUS MULTI-AGENT PRODUCTION (%s) ===", format_type.upper())

        # Step 1: Agent 1 - Trend Scout
        topic: TopicIdea = self.scout.select_viral_topic(
            format_type=format_type,
            category=category,
            custom_topic=custom_topic,
        )
        run_dir = self.output_base / f"{topic.id}_{format_type}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Agent 2 - Script Director
        script: ProductionScript = self.director.create_script(topic)
        log.info("Script created: %d scenes, estimated duration: %.1fs", len(script.scenes), script.total_estimated_duration)

        # Step 3: Agent 4 - Sonic Studio (Christopher @ +15%)
        audio_mix: AudioMixResult = self.audio.produce_audio(script, run_dir)

        # Step 4: Agent 3 + Agent 5 - 2D Animation & Video Assembly with Lip-Sync
        assembly: AssemblyResult = self.assembler.assemble_video(
            script=script,
            audio_mix=audio_mix,
            output_dir=run_dir,
            fps=24,
        )

        # Step 5: Agent 6 - SEO & High-CTR 2D Thumbnail
        seo_pkg: SEOPackage = self.seo.optimize_metadata(
            topic=topic,
            script=script,
            output_dir=run_dir,
        )

        # Step 6: Content Flywheel - Automatic Scene Repurposing into Viral Shorts
        repurposed_list: List[Dict[str, Any]] = []
        if script.format == "longform" and auto_repurpose_shorts and len(script.scenes) >= 2:
            log.info("=== AUTO-REPURPOSING LONGFORM SCENES INTO STANDALONE SHORTS ===")
            shorts_dir = run_dir / "repurposed_shorts"
            self.repurposer.output_dir = shorts_dir

            # Repurpose Scene 1 (viral hook) and Scene 3 (breakdown/revelation)
            scenes_to_clip = [1]
            if len(script.scenes) >= 3:
                scenes_to_clip.append(3)

            for s_idx in scenes_to_clip:
                try:
                    short_res = self.repurposer.repurpose_scene_to_short(
                        longform_script=script,
                        scene_index=s_idx,
                        fps=assembly.fps,
                    )
                    repurposed_list.append({
                        "scene_index": short_res.scene_index,
                        "character": short_res.character,
                        "title": short_res.short_title,
                        "video_path": str(short_res.video_path),
                        "thumbnail_path": str(short_res.thumbnail_path),
                        "duration_seconds": round(short_res.duration_seconds, 2),
                    })
                    log.info("Auto-repurposed Scene %d into Short: %s", s_idx, short_res.video_path)
                except Exception as exc:
                    log.warning("Could not repurpose scene %d into Short: %s", s_idx, exc)

        # Step 7: Package Metadata JSON
        meta_dict = {
            "topic_id": topic.id,
            "title": seo_pkg.title,
            "format": script.format,
            "video_path": str(assembly.video_path),
            "audio_path": str(audio_mix.mp3_path),
            "ass_path": str(assembly.ass_path),
            "thumbnail_path": str(seo_pkg.thumbnail_path),
            "duration_seconds": round(assembly.duration_seconds, 2),
            "fps": assembly.fps,
            "motion_verified": assembly.motion_validation.is_valid,
            "motion_score": round(assembly.motion_validation.motion_score, 2),
            "quality_passed": assembly.motion_validation.is_valid,
            "tags": seo_pkg.tags,
            "description": seo_pkg.description,
            "repurposed_shorts": repurposed_list,
            "published": False,
        }

        meta_path = run_dir / f"{topic.id}_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=2)

        # Step 8: YouTube Publishing (if requested & configured)
        yt_id = None
        yt_url = None
        published = False

        if publish_to_youtube and self.publishing_config and self.publishing_config.enabled:
            try:
                publisher = YouTubePublisher(self.publishing_config)
                pub_res = publisher.upload(
                    video_path=assembly.video_path,
                    title=seo_pkg.title,
                    description=seo_pkg.description,
                    tags=seo_pkg.tags,
                    privacy_status=privacy_status,
                    allow_duplicate=False,
                )
                yt_id = pub_res.get("video_id") or pub_res.get("id")
                if yt_id:
                    published = True
                    is_shorts = (script.format == "shorts")
                    yt_url = f"https://youtube.com/shorts/{yt_id}" if is_shorts else f"https://youtu.be/{yt_id}"
                    meta_dict["published"] = True
                    meta_dict["youtube_video_id"] = yt_id
                    meta_dict["youtube_url"] = yt_url

                # Also upload repurposed shorts if present
                for r_short in repurposed_list:
                    short_vpath = r_short.get("video_path")
                    if short_vpath and Path(short_vpath).is_file():
                        try:
                            s_title = r_short.get("title", f"{topic.title} #Shorts")
                            s_char = r_short.get("character", "ben")
                            s_desc = f"{s_title}\n\nWatch the full documentary on our channel!\n\n#Shorts #{s_char} #animation"
                            s_pub = publisher.upload(
                                video_path=Path(short_vpath),
                                title=s_title,
                                description=s_desc,
                                tags=["Shorts", "animation", s_char, "viral"],
                                privacy_status=privacy_status,
                                allow_duplicate=False,
                            )
                            s_id = s_pub.get("video_id") or s_pub.get("id")
                            if s_id:
                                r_short["youtube_video_id"] = s_id
                                r_short["youtube_url"] = f"https://youtube.com/shorts/{s_id}"
                                log.info("Repurposed short uploaded to YouTube: %s", r_short["youtube_url"])
                        except Exception as s_exc:
                            log.warning("Could not upload repurposed short %s: %s", short_vpath, s_exc)

                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_dict, f, indent=2)
            except Exception as exc:
                log.warning("Automated upload to YouTube skipped/failed: %s", exc)

        return PipelineRunResult(
            topic_id=topic.id,
            title=seo_pkg.title,
            format=script.format,
            video_path=str(assembly.video_path),
            audio_path=str(audio_mix.mp3_path),
            thumbnail_path=str(seo_pkg.thumbnail_path),
            ass_path=str(assembly.ass_path),
            duration_seconds=assembly.duration_seconds,
            motion_verified=assembly.motion_validation.is_valid,
            motion_score=assembly.motion_validation.motion_score,
            metadata_path=str(meta_path),
            published=published,
            youtube_video_id=yt_id,
            youtube_url=yt_url,
            repurposed_shorts=repurposed_list,
        )
