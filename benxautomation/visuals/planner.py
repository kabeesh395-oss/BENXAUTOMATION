"""Scene planner: matches script scenes to licensed local assets and calculates timing."""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import List, Optional

from benxautomation.asset_manifest import LicenseManifest
from benxautomation.errors import ScenePlanningError
from benxautomation.logger import get_logger
from benxautomation.script.models import ScriptResult, ScriptScene
from benxautomation.visuals.models import ScenePlan, VisualPlan

log = get_logger(__name__)


class ScenePlanner:
    """Plans visual assets for each scene of a script."""

    def __init__(
        self,
        *,
        assets_dir: Path,
        manifest: Optional[LicenseManifest] = None,
        fallback_asset: Optional[Path] = None,
    ):
        self.assets_dir = Path(assets_dir)
        self.manifest = manifest
        self.fallback_asset = Path(fallback_asset) if fallback_asset else None

    def _get_available_assets(self) -> list[dict]:
        """Collect available valid assets from manifest or assets_dir."""
        available: list[dict] = []

        if self.manifest and self.manifest.assets:
            for item in self.manifest.assets:
                p = self.assets_dir / item.file
                if p.is_file() and p.stat().st_size > 0:
                    available.append({
                        "path": p,
                        "file": item.file,
                        "license": item.license,
                        "attribution": item.attribution,
                        "source_url": item.source_url or f"local://{item.file}",
                    })

        if not available and self.assets_dir.is_dir():
            # Scan directory for common image / video assets
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp", "*.mp4"):
                for p in self.assets_dir.glob(ext):
                    if p.is_file() and p.stat().st_size > 0:
                        available.append({
                            "path": p,
                            "file": p.name,
                            "license": "local",
                            "attribution": f"Local file: {p.name}",
                            "source_url": f"local://{p.name}",
                        })

        if not available and self.fallback_asset and self.fallback_asset.is_file():
            available.append({
                "path": self.fallback_asset,
                "file": self.fallback_asset.name,
                "license": "local_fallback",
                "attribution": "Default fallback asset",
                "source_url": f"local://{self.fallback_asset.name}",
            })

        return available

    @staticmethod
    def _is_test_placeholder(asset: dict) -> bool:
        """Return True if the asset is a test fixture or placeholder card."""
        name = asset.get("file", "").lower()
        attr = (asset.get("attribution") or "").lower()
        return "sample_card" in name or "test card" in attr or name.startswith("sample_")

    @staticmethod
    def _score_asset_for_scene(
        scene: ScriptScene,
        asset: dict,
        topic: str = "",
        stop_words: set[str] | None = None,
    ) -> int:
        """Compute keyword relevance score between a scene and an asset candidate."""
        if stop_words is None:
            stop_words = {
                "test", "sample", "card", "asset", "generated", "file", "local",
                "benxautomation", "for", "the", "and", "with", "this", "that", "from",
                "into", "over", "under", "about", "scene", "fact", "number", "point",
            }

        name_stem = asset["path"].stem.lower().replace("_", " ")
        attr = (asset.get("attribution") or "").lower()
        asset_words = (set(re.findall(r"\b\w{4,}\b", f"{name_stem} {attr}"))) - stop_words

        if not asset_words:
            return 0

        title_words = set(re.findall(r"\b\w{4,}\b", scene.title.lower())) - stop_words
        desc_words = set(re.findall(r"\b\w{4,}\b", scene.visual_description.lower())) - stop_words
        narr_words = set(re.findall(r"\b\w{4,}\b", scene.narration.lower())) - stop_words
        topic_words = set(re.findall(r"\b\w{4,}\b", topic.lower())) - stop_words

        score = 0
        for w in asset_words:
            if w in title_words:
                score += 8  # Direct match with scene title/heading
            if w in desc_words:
                score += 6  # Match with intended visual description
            if w in narr_words:
                score += 4  # Match with spoken narration keywords
            if w in topic_words:
                score += 1  # General topic alignment

        return score

    def _assign_assets_globally(
        self,
        scenes: list[ScriptScene],
        available_assets: list[dict],
        topic: str = "",
    ) -> list[dict]:
        """Globally optimize asset allocation across all scenes to prevent greedy misallocation."""
        if not available_assets:
            raise ScenePlanningError("No valid assets available for scene planning.")

        # Exclude test placeholders if real production media is available
        production_assets = [a for a in available_assets if not self._is_test_placeholder(a)]
        pool = production_assets if production_assets else available_assets

        stop_words = {
            "test", "sample", "card", "asset", "generated", "file", "local",
            "benxautomation", "for", "the", "and", "with", "this", "that", "from",
            "into", "over", "under", "about", "scene", "fact", "number", "point",
        }

        # Calculate score matrix: scores[scene_idx][asset_idx]
        scored_pairs: list[tuple[int, int, int]] = []  # (score, scene_idx, asset_idx)
        for s_idx, scene in enumerate(scenes):
            for a_idx, asset in enumerate(pool):
                score = self._score_asset_for_scene(scene, asset, topic=topic, stop_words=stop_words)
                scored_pairs.append((score, s_idx, a_idx))

        # Sort candidate assignments by descending score
        scored_pairs.sort(key=lambda x: x[0], reverse=True)

        assigned_assets: list[Optional[dict]] = [None] * len(scenes)
        used_asset_indices: set[int] = set()

        # Phase 1: Assign pairs with positive score greedily by highest score
        for score, s_idx, a_idx in scored_pairs:
            if score <= 0:
                break
            if assigned_assets[s_idx] is None and a_idx not in used_asset_indices:
                assigned_assets[s_idx] = pool[a_idx]
                used_asset_indices.add(a_idx)

        # Phase 2: For any remaining unassigned scenes, allocate from remaining unused pool assets
        remaining_asset_indices = [i for i in range(len(pool)) if i not in used_asset_indices]
        for s_idx in range(len(scenes)):
            if assigned_assets[s_idx] is None:
                if remaining_asset_indices:
                    # Pick remaining unused asset that has highest topic score, or cyclically
                    best_rem_idx = remaining_asset_indices.pop(0)
                    assigned_assets[s_idx] = pool[best_rem_idx]
                    used_asset_indices.add(best_rem_idx)
                else:
                    # Pool exhausted; cycle through pool to avoid visual monotony
                    assigned_assets[s_idx] = pool[s_idx % len(pool)]

        return [a for a in assigned_assets if a is not None]

    def _match_asset_for_scene(
        self,
        scene_title: str,
        scene_desc: str,
        scene_narration: str,
        available_assets: list[dict],
        scene_idx: int,
        topic: str = "",
        used_asset_paths: set[Path] | None = None,
    ) -> dict:
        """Find the most relevant asset, prioritizing production media and scene diversity."""
        dummy_scene = ScriptScene(
            scene_index=scene_idx,
            title=scene_title,
            narration=scene_narration,
            visual_description=scene_desc,
        )
        return self._assign_assets_globally([dummy_scene], available_assets, topic=topic)[0]

    def plan_visuals(
        self,
        script_result: ScriptResult,
        total_audio_duration: float,
        *,
        fps: int = 30,
        single_asset_override: Optional[Path] = None,
    ) -> VisualPlan:
        """Create a complete VisualPlan for the given script and audio duration."""
        scenes = script_result.scenes
        if not scenes:
            raise ScenePlanningError("Cannot plan visuals for a script with no scenes.")

        if total_audio_duration <= 0:
            raise ScenePlanningError("Total audio duration must be greater than zero.")

        # Single asset override mode
        if single_asset_override:
            if not single_asset_override.is_file():
                raise ScenePlanningError(f"Override asset not found: {single_asset_override}")
            available = [{
                "path": single_asset_override,
                "file": single_asset_override.name,
                "license": "override",
                "attribution": "User-supplied asset",
                "source_url": str(single_asset_override),
            }]
            is_multi = False
        else:
            available = self._get_available_assets()
            if not available:
                raise ScenePlanningError(
                    f"No visual assets found in {self.assets_dir} or manifest. "
                    "Provide an asset with --asset or add assets to assets/."
                )
            is_multi = len(available) > 1 and len(scenes) > 1

        # Calculate durations proportionally at given FPS to ensure video covers full audio
        total_frames = max(1, math.ceil(total_audio_duration * fps))
        target_video_duration = total_frames / fps

        total_chars = sum(len(s.narration) for s in scenes) or 1
        scene_plans: list[ScenePlan] = []
        accumulated_frames = 0
        MOTION_EFFECTS = ["zoom_in", "pan_left", "zoom_out", "pan_right"]

        matched_assets = (
            [available[0]] * len(scenes)
            if not is_multi
            else self._assign_assets_globally(scenes, available, topic=script_result.topic)
        )

        for idx, scene in enumerate(scenes, start=1):
            if idx == len(scenes):
                scene_frames = max(1, total_frames - accumulated_frames)
            else:
                fraction = len(scene.narration) / total_chars
                scene_frames = max(1, int(round(fraction * total_frames)))
                accumulated_frames += scene_frames

            scene_dur = round(scene_frames / fps, 3)
            matched = matched_assets[idx - 1]

            # Verify asset file exists, is non-empty, and is readable
            asset_file = matched["path"]
            if not asset_file.is_file() or asset_file.stat().st_size == 0:
                raise ScenePlanningError(f"Selected scene asset is missing or empty: {asset_file}")
            try:
                with asset_file.open("rb") as f:
                    _ = f.read(64)
            except Exception as exc:
                raise ScenePlanningError(f"Selected scene asset is unreadable: {asset_file} ({exc})")

            motion_effect = MOTION_EFFECTS[(idx - 1) % len(MOTION_EFFECTS)]

            scene_plans.append(
                ScenePlan(
                    scene_index=idx,
                    title=scene.title,
                    narration=scene.narration,
                    visual_description=scene.visual_description,
                    duration_seconds=scene_dur,
                    asset_path=asset_file,
                    source=matched.get("source_url", "local"),
                    license=matched.get("license", "unspecified"),
                    attribution=matched.get("attribution", ""),
                    source_url=matched.get("source_url", ""),
                    motion_effect=motion_effect,
                )
            )

        total_dur = sum(s.duration_seconds for s in scene_plans)
        distinct_assets = {s.asset_path for s in scene_plans}
        has_repeated = len(scene_plans) > len(distinct_assets)

        log.info(
            "Planned %d scenes (total %.3fs, target %.3fs, multi_scene=%s, distinct_assets=%d, repeated=%s)",
            len(scene_plans),
            total_dur,
            target_video_duration,
            is_multi,
            len(distinct_assets),
            has_repeated,
        )

        return VisualPlan(
            scenes=scene_plans,
            total_duration_seconds=total_dur,
            is_multi_scene=is_multi,
            distinct_assets_count=len(distinct_assets),
            has_repeated_assets=has_repeated,
            animation_type="2d_motion",
        )
