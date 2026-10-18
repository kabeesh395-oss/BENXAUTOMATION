"""Agent 6: SEO, Viral Growth & High-CTR Thumbnail Designer.

Optimizes YouTube titles, descriptions, and tags in full compliance with YouTube Guidelines,
and synthesizes bold 2D cartoon thumbnails with expressive characters and high-contrast text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

from benxautomation.agents.script_director import ProductionScript
from benxautomation.agents.trend_scout import TopicIdea
from benxautomation.logger import get_logger

log = get_logger(__name__)


@dataclass
class SEOPackage:
    """Complete metadata and thumbnail package ready for YouTube publication."""
    title: str
    description: str
    tags: List[str]
    thumbnail_path: Path
    category_id: str = "28"  # Science & Technology


class SEOGrowthAgent:
    """Agent 6: Crafts YouTube metadata and high-CTR cartoon thumbnails."""

    def __init__(self, asset_dir: Path | str = "assets/characters/universe_debut"):
        self.asset_dir = Path(asset_dir)

    def optimize_metadata(
        self,
        topic: TopicIdea,
        script: ProductionScript,
        output_dir: Path,
    ) -> SEOPackage:
        """Generate high-CTR title, compliant description, tags, and a custom 2D thumbnail."""
        output_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = output_dir / f"{topic.id}_thumb.jpg"

        # 1. High-CTR Title
        title = topic.title
        if script.format == "shorts" and "#shorts" not in title.lower():
            title = f"{title} | Cartoon Shorts"

        # 2. Compliant Description with Chapter breakdown & Hashtags
        desc_lines = [
            f"{topic.hook}",
            "",
            f"In this episode, BEN breaks down {topic.core_premise}",
            "",
            "🚨 SUBSCRIBE for daily animated tech hacks, ancient history, and mind-blowing science!",
            "",
        ]

        if topic.chapters:
            desc_lines.append("⏱️ CHAPTERS:")
            for ch in topic.chapters:
                desc_lines.append(f"• {ch}")
            desc_lines.append("")

        desc_lines.extend([
            "Starring the Character Universe:",
            "🕶️ BEN: Tech & Everyday Dilemmas",
            "🤖 MAX: Logic & Cyber Architecture",
            "💰 Mr. Cash: Wealth & Corporate Secrets",
            "👑 The King: Ancient Empires & Bizarre Laws",
            "🔬 Dr. Quantum: Physics & Mind-Bending Realities",
            "",
            " ".join(f"#{tag}" for tag in topic.tags[:6]),
        ])
        description = "\n".join(desc_lines)

        # 3. Generate High-CTR Thumbnail
        self.generate_thumbnail(
            topic=topic,
            output_path=thumb_path,
            is_shorts=(script.format == "shorts"),
        )

        return SEOPackage(
            title=title,
            description=description,
            tags=topic.tags,
            thumbnail_path=thumb_path,
        )

    def generate_metadata_and_thumbnail(
        self,
        topic: TopicIdea,
        output_dir: Path,
        script: Optional[ProductionScript] = None,
    ) -> SEOPackage:
        """Convenience wrapper for generating SEO metadata and high-CTR thumbnail."""
        if script is None:
            script = ProductionScript(topic_id=topic.id, title=topic.title, format=topic.format)
        return self.optimize_metadata(topic=topic, script=script, output_dir=output_dir)

    def generate_thumbnail(
        self,
        topic: TopicIdea,
        output_path: Path,
        is_shorts: bool = True,
    ) -> Path:
        """Synthesize high-contrast 2D cartoon thumbnail with bold text banner."""
        target_size = (1080, 1920) if is_shorts else (1280, 720)
        tw, th = target_size

        # Load character face
        char_file = self.asset_dir / "ben_intro_open.jpg"
        if not char_file.exists():
            char_file = self.asset_dir / "ben_intro.jpg"

        if char_file.exists():
            base = Image.open(char_file).convert("RGB")
            # Fit & center
            scale = max(tw / base.width, th / base.height)
            nw, nh = int(base.width * scale), int(base.height * scale)
            scaled = base.resize((nw, nh), Image.Resampling.LANCZOS)
            cx = (nw - tw) // 2
            cy = (nh - th) // 2
            thumb = scaled.crop((cx, cy, cx + tw, cy + th))
        else:
            thumb = Image.new("RGB", target_size, (255, 255, 255))

        draw = ImageDraw.Draw(thumb)

        # Draw Bold High-Contrast Text Box Banner
        banner_h = int(th * 0.16)
        banner_y = int(th * 0.08) if is_shorts else int(th * 0.72)

        draw.rectangle([0, banner_y, tw, banner_y + banner_h], fill=(239, 68, 68), outline=(0, 0, 0), width=8)

        # 3-word punchy thumbnail text
        words = topic.title.split()[:4]
        punchy_text = " ".join(words).upper().replace("!", "").replace("😱", "")

        font = None
        try:
            font = ImageFont.truetype("arialbd.ttf", 68 if is_shorts else 54)
        except Exception:
            pass

        bbox = draw.textbbox((0, 0), punchy_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        tx = (tw - text_w) // 2
        ty = banner_y + (banner_h - text_h) // 2 - 4

        # Text with black drop shadow
        draw.text((tx + 4, ty + 4), punchy_text, fill=(0, 0, 0), font=font)
        draw.text((tx, ty), punchy_text, fill=(255, 255, 255), font=font)

        thumb.save(output_path, quality=95)
        log.info("High-CTR 2D Thumbnail generated: %s", output_path)
        return output_path
