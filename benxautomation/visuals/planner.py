"""Scene planner: matches script scenes to licensed local assets and calculates timing."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from benxautomation.asset_manifest import LicenseManifest
from benxautomation.errors import ScenePlanningError
from benxautomation.logger import get_logger
from benxautomation.script.models import ScriptResult
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

    def _match_asset_for_scene(
        self,
        scene_title: str,
        scene_desc: str,
        scene_narration: str,
        available_assets: list[dict],
        scene_idx: int,
    ) -> dict:
        """Find the most relevant asset, or cycle through available assets."""
        if not available_assets:
            raise ScenePlanningError("No valid assets available for scene planning.")

        text_to_match = f"{scene_title} {scene_desc} {scene_narration}".lower()

        # Score assets by keyword overlap
        best_match = None
        best_score = -1

        for asset in available_assets:
            score = 0
            name_stem = asset["path"].stem.lower().replace("_", " ")
            attr = asset.get("attribution", "").lower()

            words = set(name_stem.split() + attr.split())
            for w in words:
                if len(w) > 3 and w in text_to_match:
                    score += 2

            if score > best_score:
                best_score = score
                best_match = asset

        # If keyword scoring didn't find a strong match, cycle through assets to avoid visual monotony
        if best_score <= 0:
            best_match = available_assets[(scene_idx - 1) % len(available_assets)]

        return best_match or available_assets[0]

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
        import math
        total_frames = max(1, math.ceil(total_audio_duration * fps))
        target_video_duration = total_frames / fps

        total_chars = sum(len(s.narration) for s in scenes) or 1
        scene_plans: list[ScenePlan] = []
        accumulated_frames = 0

        for idx, scene in enumerate(scenes, start=1):
            if idx == len(scenes):
                scene_frames = max(1, total_frames - accumulated_frames)
            else:
                fraction = len(scene.narration) / total_chars
                scene_frames = max(1, int(round(fraction * total_frames)))
                accumulated_frames += scene_frames

            scene_dur = round(scene_frames / fps, 3)

            matched = (
                available[0]
                if not is_multi
                else self._match_asset_for_scene(
                    scene.title,
                    scene.visual_description,
                    scene.narration,
                    available,
                    idx,
                )
            )

            # Verify asset file exists, is non-empty, and is readable
            asset_file = matched["path"]
            if not asset_file.is_file() or asset_file.stat().st_size == 0:
                raise ScenePlanningError(f"Selected scene asset is missing or empty: {asset_file}")
            try:
                with asset_file.open("rb") as f:
                    _ = f.read(64)
            except Exception as exc:
                raise ScenePlanningError(f"Selected scene asset is unreadable: {asset_file} ({exc})")

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
                )
            )

        total_dur = sum(s.duration_seconds for s in scene_plans)
        log.info(
            "Planned %d scenes (total %.3fs, target %.3fs, multi_scene=%s, assets_used=%d)",
            len(scene_plans),
            total_dur,
            target_video_duration,
            is_multi,
            len({s.asset_path for s in scene_plans}),
        )

        return VisualPlan(
            scenes=scene_plans,
            total_duration_seconds=total_dur,
            is_multi_scene=is_multi,
        )
