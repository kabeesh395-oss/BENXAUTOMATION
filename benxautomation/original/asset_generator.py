"""High-definition original asset generator for copyright-safe video production.

Generates sleek, custom, commercially-permitted diagrams and graphical cards
using Pillow for both vertical (1080x1920) and landscape (1920x1080) video formats.
Registers generated assets into assets/license_manifest.yaml with full provenance.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple
import yaml
from PIL import Image, ImageDraw, ImageFont

from benxautomation.logger import get_logger
from benxautomation.original.models import AssetSpec

log = get_logger(__name__)


class OriginalAssetGenerator:
    """Generates crisp, branded educational visuals and diagrammatic cards."""

    def __init__(self, assets_dir: Path, manifest_path: Path):
        self.assets_dir = Path(assets_dir)
        self.manifest_path = Path(manifest_path)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_required_assets(self) -> list[Path]:
        """Generate all distinct visual assets required for the 3 original topics."""
        specs = self._get_all_specs()
        created_paths: list[Path] = []
        for spec in specs:
            out_path = self.assets_dir / spec.filename
            if not out_path.is_file():
                self.create_graphic(spec, out_path)
                log.info("Generated original visual asset: %s", spec.filename)
            created_paths.append(out_path)

        self._update_manifest(specs)
        return created_paths

    def create_graphic(self, spec: AssetSpec, output_path: Path) -> Path:
        """Create a single high-resolution graphic card."""
        is_portrait = spec.format == "portrait"
        width = 1080 if is_portrait else 1920
        height = 1920 if is_portrait else 1080

        # Base canvas with gradient
        img = self._create_gradient_background(
            width, height, spec.primary_color, spec.secondary_color
        )
        draw = ImageDraw.Draw(img)

        # Draw decorative background grid & elements
        self._draw_ambient_decorations(draw, width, height, is_portrait)

        # Central diagram / data card
        self._draw_central_card(draw, spec, width, height, is_portrait)

        # Typography & content
        self._draw_text_elements(draw, spec, width, height, is_portrait)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG", optimize=True)
        return output_path

    def _create_gradient_background(
        self, width: int, height: int, color_top: str, color_bottom: str
    ) -> Image.Image:
        """Generate smooth vertical gradient."""
        c1 = self._parse_hex(color_top)
        c2 = self._parse_hex(color_bottom)

        base = Image.new("RGB", (width, height), c1)
        draw = ImageDraw.Draw(base)

        steps = 120
        step_height = height / steps
        for i in range(steps):
            ratio = i / float(steps)
            r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
            g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
            b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
            y0 = int(i * step_height)
            y1 = int((i + 1) * step_height)
            draw.rectangle([0, y0, width, y1], fill=(r, g, b))

        return base

    def _draw_ambient_decorations(
        self, draw: ImageDraw.Draw, width: int, height: int, is_portrait: bool
    ) -> None:
        """Draw subtle geometric grid lines and accent dots."""
        grid_color = (255, 255, 255, 18)
        grid_step = 90 if is_portrait else 120

        for x in range(0, width, grid_step):
            draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 8), width=1)
        for y in range(0, height, grid_step):
            draw.line([(0, y), (width, y)], fill=(255, 255, 255, 8), width=1)

        # Top border accent bar
        draw.rectangle([0, 0, width, 12], fill=(59, 130, 246))

    def _draw_central_card(
        self,
        draw: ImageDraw.Draw,
        spec: AssetSpec,
        width: int,
        height: int,
        is_portrait: bool,
    ) -> None:
        """Draw sleek glassmorphic container card and symbol."""
        if is_portrait:
            card_w = width - 120
            card_h = height - 480
            x0 = 60
            y0 = 240
        else:
            card_w = width - 240
            card_h = height - 200
            x0 = 120
            y0 = 100

        x1 = x0 + card_w
        y1 = y0 + card_h

        # Translucent container box
        draw.rounded_rectangle(
            [x0, y0, x1, y1],
            radius=24,
            fill=(15, 23, 42),
            outline=(51, 65, 85),
            width=3,
        )

        # Draw decorative icon / badge
        badge_y = y0 + (60 if is_portrait else 40)
        badge_x = x0 + (60 if is_portrait else 50)
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + 90, badge_y + 40],
            radius=8,
            fill=(37, 99, 235),
        )
        draw.text(
            (badge_x + 14, badge_y + 10),
            spec.icon_symbol[:8],
            fill=(255, 255, 255),
        )

    def _draw_text_elements(
        self,
        draw: ImageDraw.Draw,
        spec: AssetSpec,
        width: int,
        height: int,
        is_portrait: bool,
    ) -> None:
        """Render titles, bullet points, and provenance footer."""
        x_pad = 120 if is_portrait else 180
        y_cursor = 370 if is_portrait else 190

        # Title
        draw.text(
            (x_pad, y_cursor),
            spec.title,
            fill=(248, 250, 252),
        )
        y_cursor += 70 if is_portrait else 55

        # Subtitle
        draw.text(
            (x_pad, y_cursor),
            spec.subtitle,
            fill=(148, 163, 184),
        )
        y_cursor += 100 if is_portrait else 70

        # Divider
        draw.line([(x_pad, y_cursor), (width - x_pad, y_cursor)], fill=(51, 65, 85), width=2)
        y_cursor += 60 if is_portrait else 45

        # Bullet points
        for i, pt in enumerate(spec.bullet_points, start=1):
            bullet_y = y_cursor + (i - 1) * (140 if is_portrait else 90)
            # Dot
            draw.ellipse(
                [(x_pad, bullet_y + 6), (x_pad + 14, bullet_y + 20)],
                fill=(56, 189, 248),
            )
            draw.text(
                (x_pad + 35, bullet_y),
                f"{pt}",
                fill=(226, 232, 240),
            )

        # Footer watermark
        footer_text = "BENXAUTOMATION • Original Creator-Owned Educational Content • Verified Rights"
        footer_y = height - (140 if is_portrait else 60)
        draw.text(
            (width // 2 - 280, footer_y),
            footer_text,
            fill=(100, 116, 139),
        )

    def _parse_hex(self, hex_code: str) -> Tuple[int, int, int]:
        h = hex_code.lstrip("#")
        if len(h) == 3:
            h = "".join([c * 2 for c in h])
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

    def _update_manifest(self, specs: list[AssetSpec]) -> None:
        """Ensure all generated assets exist in license_manifest.yaml."""
        existing_manifest = {"assets": []}
        if self.manifest_path.is_file():
            try:
                data = yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "assets" in data:
                    existing_manifest = data
            except Exception as e:
                log.warning("Could not parse existing manifest: %s", e)

        files_in_manifest = {a.get("file") for a in existing_manifest.get("assets", []) if isinstance(a, dict)}

        updated = False
        for s in specs:
            if s.filename not in files_in_manifest:
                existing_manifest["assets"].append(
                    {
                        "file": s.filename,
                        "license": "original",
                        "attribution": f"Creator-owned original graphic for {s.title} (BENXAUTOMATION)",
                        "source_url": f"local://assets/{s.filename}",
                        "asset_origin": "in_house_code_generated",
                        "commercial_terms_verified": True,
                        "terms_reference": "Pillow HPND open-source software license; all output graphical artifacts created in-house",
                    }
                )
                files_in_manifest.add(s.filename)
                updated = True

        if updated:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            self.manifest_path.write_text(
                yaml.dump(existing_manifest, sort_keys=False, indent=2),
                encoding="utf-8",
            )
            log.info("Updated license_manifest.yaml with %d new original assets.", len(specs))

    def _get_all_specs(self) -> list[AssetSpec]:
        """Define all required specifications for the 3 topics."""
        specs: list[AssetSpec] = []

        # ── AI FUTURE ──
        # Longform
        specs.append(
            AssetSpec(
                filename="orig_ai_future_hero.png",
                title="The Future of Artificial Intelligence",
                subtitle="Scientific Acceleration and Problem Solving",
                format="landscape",
                primary_color="#0b132b",
                secondary_color="#1c2541",
                icon_symbol="AI/SCI",
                bullet_points=[
                    "Transitioning from mere search to active hypothesis generation",
                    "Simulating complex molecular biology and materials in seconds",
                    "Engineering-grade reasoning models with verifiable steps",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_ai_molecular.png",
                title="Molecular Biology & Simulation",
                subtitle="High-Dimensional Drug Discovery at Digital Scale",
                format="landscape",
                primary_color="#0f172a",
                secondary_color="#1e293b",
                icon_symbol="BIO-AI",
                bullet_points=[
                    "Predictive protein folding algorithms replacing trial-and-error",
                    "Accelerating therapeutic pipelines from decades to months",
                    "Simulating catalytic reactions under digital physics",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_ai_reasoning.png",
                title="Reasoning Inference Architectures",
                subtitle="Verifiable Step-by-Step Logic",
                format="landscape",
                primary_color="#090d16",
                secondary_color="#1b2a47",
                icon_symbol="LOGIC",
                bullet_points=[
                    "Deliberate backtracking and self-correction before output",
                    "Drastic reduction of hallucinations in technical domains",
                    "Deterministic verification in mathematics and software",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_ai_horizon.png",
                title="The Computing Horizon",
                subtitle="Collaborative Scientific Intelligence",
                format="landscape",
                primary_color="#03071e",
                secondary_color="#370617",
                icon_symbol="FUTURE",
                bullet_points=[
                    "Exponential compute scaling paired with energy efficiency",
                    "Human-AI collaboration across climate, physics, and medicine",
                    "Democratization of advanced technical research tools",
                ],
            )
        )

        # AI Shorts 1
        specs.append(
            AssetSpec(
                filename="orig_ai_short1_scene1.png",
                title="Traditional Research",
                subtitle="The Physical Laboratory Bottleneck",
                format="portrait",
                primary_color="#0f172a",
                secondary_color="#1e1b4b",
                icon_symbol="LAB",
                bullet_points=[
                    "Decades of physical trial and error",
                    "High cost and limited throughput",
                    "Slow experimental iterations",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_ai_short1_scene2.png",
                title="Digital Simulation",
                subtitle="Predicting Chemistry at Scale",
                format="portrait",
                primary_color="#030712",
                secondary_color="#1e293b",
                icon_symbol="NEURAL",
                bullet_points=[
                    "Proteins folded in seconds",
                    "Billions of candidate molecules evaluated",
                    "Physics-guided neural networks",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_ai_short1_scene3.png",
                title="Faster Therapeutics",
                subtitle="Compressing Discovery Timelines",
                format="portrait",
                primary_color="#022c22",
                secondary_color="#064e3b",
                icon_symbol="CURE",
                bullet_points=[
                    "Years compressed into weeks",
                    "Targeted solutions for rare diseases",
                    "The new era of computational science",
                ],
            )
        )

        # AI Shorts 2
        specs.append(
            AssetSpec(
                filename="orig_ai_short2_scene1.png",
                title="Pattern Matching",
                subtitle="The Limit of Simple Chatbots",
                format="portrait",
                primary_color="#18181b",
                secondary_color="#27272a",
                icon_symbol="CHAT",
                bullet_points=[
                    "Predicting the next plausible token",
                    "Prone to subtle hallucinations",
                    "Superficial conversational responses",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_ai_short2_scene2.png",
                title="Deliberate Thinking",
                subtitle="System Two Architecture",
                format="portrait",
                primary_color="#082f49",
                secondary_color="#0c4a6e",
                icon_symbol="SYSTEM2",
                bullet_points=[
                    "Explicit chain-of-thought verification",
                    "Backtracking on logical dead ends",
                    "Evaluating multiple solution paths",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_ai_short2_scene3.png",
                title="Engineering Precision",
                subtitle="Reliable Technical Outputs",
                format="portrait",
                primary_color="#0f172a",
                secondary_color="#1e3a8a",
                icon_symbol="EXACT",
                bullet_points=[
                    "Production-ready verified code",
                    "Rigorous mathematical proofs",
                    "Dependable enterprise automation",
                ],
            )
        )

        # ── COMPOUNDING WEALTH ──
        # Longform
        specs.append(
            AssetSpec(
                filename="orig_fin_compound_hero.png",
                title="The Mathematics of Compounding",
                subtitle="How Capital Multiplies Over Time",
                format="landscape",
                primary_color="#022c22",
                secondary_color="#064e3b",
                icon_symbol="GROWTH",
                bullet_points=[
                    "Geometric growth where accumulated interest earns interest",
                    "The hockey-stick trajectory of patient capital",
                    "Mathematical certainty vs speculative gambling",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_fin_time.png",
                title="The Critical Variable: Time",
                subtitle="Why Decades Matter More Than Timing",
                format="landscape",
                primary_color="#064e3b",
                secondary_color="#047857",
                icon_symbol="TIME",
                bullet_points=[
                    "Majority of compounding occurs in the final years",
                    "Starting early exponentially dwarfs starting late",
                    "Longevity in the market surpasses aggressive trading",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_fin_discipline.png",
                title="Emotional Discipline",
                subtitle="Surviving Market Drawdowns",
                format="landscape",
                primary_color="#14532d",
                secondary_color="#15803d",
                icon_symbol="CALM",
                bullet_points=[
                    "Panic selling permanently crystallizes temporary losses",
                    "Volatility is the fundamental admission fee for gains",
                    "Downturns offer the highest forward compound returns",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_fin_plan.png",
                title="Systematic Execution",
                subtitle="Building Generational Wealth",
                format="landscape",
                primary_color="#0f172a",
                secondary_color="#065f46",
                icon_symbol="PLAN",
                bullet_points=[
                    "Focusing on durable cash-generative businesses",
                    "Automated reinvestment of capital and dividends",
                    "Never interrupting the mathematical curve",
                ],
            )
        )

        # Finance Shorts 1
        specs.append(
            AssetSpec(
                filename="orig_fin_short1_scene1.png",
                title="Linear vs Exponential",
                subtitle="The Human Intuition Trap",
                format="portrait",
                primary_color="#022c22",
                secondary_color="#064e3b",
                icon_symbol="CURVE",
                bullet_points=[
                    "Linear intuition expects a flat diagonal line",
                    "Exponential curves start flat, then soar upward",
                    "Early efforts feel invisible but set the foundation",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_fin_short1_scene2.png",
                title="The Acceleration Phase",
                subtitle="When Interest Dwarfs Capital",
                format="portrait",
                primary_color="#064e3b",
                secondary_color="#047857",
                icon_symbol="SURGE",
                bullet_points=[
                    "Returns begin exceeding annual savings",
                    "Capital works harder than human labor",
                    "The snowball effect becomes unstoppable",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_fin_short1_scene3.png",
                title="The Golden Rule",
                subtitle="Never Interrupt the Math",
                format="portrait",
                primary_color="#047857",
                secondary_color="#10b981",
                icon_symbol="RULE #1",
                bullet_points=[
                    "Avoid unnecessary churn and friction",
                    "Keep fees, taxes, and emotions minimal",
                    "Let time multiply your wealth uninterrupted",
                ],
            )
        )

        # Finance Shorts 2
        specs.append(
            AssetSpec(
                filename="orig_fin_short2_scene1.png",
                title="Missing the Best Days",
                subtitle="The Peril of Market Timing",
                format="portrait",
                primary_color="#7f1d1d",
                secondary_color="#991b1b",
                icon_symbol="RISK",
                bullet_points=[
                    "Best trading days cluster around the worst crashes",
                    "Missing 10 top days over 20 years cuts returns in half",
                    "Timing the market reliably is statistically impossible",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_fin_short2_scene2.png",
                title="Price of Admission",
                subtitle="Volatility Is Normal",
                format="portrait",
                primary_color="#0f172a",
                secondary_color="#334155",
                icon_symbol="PRICE",
                bullet_points=[
                    "Periodic drawdowns are not structural defects",
                    "Enduring uncertainty earns the equity risk premium",
                    "Quiet patience beats constant reaction",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_fin_short2_scene3.png",
                title="Stay the Course",
                subtitle="Systematic Consistency",
                format="portrait",
                primary_color="#064e3b",
                secondary_color="#059669",
                icon_symbol="WIN",
                bullet_points=[
                    "Continuous disciplined dollar-cost averaging",
                    "Diversified across resilient productive assets",
                    "Financial freedom through mathematical patience",
                ],
            )
        )

        # ── CYBER DEFENSE ──
        # Longform
        specs.append(
            AssetSpec(
                filename="orig_cyber_hero.png",
                title="The Invisible Shield",
                subtitle="Inside Modern Cybersecurity & Intelligence",
                format="landscape",
                primary_color="#0f172a",
                secondary_color="#0284c7",
                icon_symbol="SHIELD",
                bullet_points=[
                    "Billions of cryptographic handshakes defending global networks",
                    "Continuous automated threat monitoring across critical systems",
                    "The shift from static perimeter firewalls to continuous verification",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_cyber_crypto.png",
                title="Public Key Cryptography",
                subtitle="The Mathematics of Privacy",
                format="landscape",
                primary_color="#030712",
                secondary_color="#1e1b4b",
                icon_symbol="CRYPTO",
                bullet_points=[
                    "Asymmetric keypairs mathematically linked via one-way functions",
                    "Unbreakable computational complexity under modern hardware",
                    "Ensuring confidentiality, integrity, and non-repudiation",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_cyber_zerotrust.png",
                title="Zero Trust Frameworks",
                subtitle="Never Trust, Always Verify",
                format="landscape",
                primary_color="#090d16",
                secondary_color="#0e7490",
                icon_symbol="0-TRUST",
                bullet_points=[
                    "Every user, device, and packet authenticated continuously",
                    "Micro-segmentation prevents lateral attacker movement",
                    "Least-privilege access restricted to essential workflows",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_cyber_quantum.png",
                title="Quantum Resilience",
                subtitle="The Future of Defensive Cryptography",
                format="landscape",
                primary_color="#18181b",
                secondary_color="#3b0764",
                icon_symbol="Q-SAFE",
                bullet_points=[
                    "Post-quantum lattice cryptography resisting Shor's algorithm",
                    "Hardening international infrastructure before quantum readiness",
                    "Defensive intelligence staying ahead of offensive advances",
                ],
            )
        )

        # Cyber Shorts 1
        specs.append(
            AssetSpec(
                filename="orig_cyber_short1_scene1.png",
                title="The Scramble",
                subtitle="Converting Plaintext to Ciphertext",
                format="portrait",
                primary_color="#0f172a",
                secondary_color="#0369a1",
                icon_symbol="CIPHER",
                bullet_points=[
                    "Your message is encoded before leaving the device",
                    "Intercepted data looks like complete random noise",
                    "Network eavesdroppers cannot read a single word",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_cyber_short1_scene2.png",
                title="Private Key Math",
                subtitle="The Exclusive Digital Decryption Key",
                format="portrait",
                primary_color="#0284c7",
                secondary_color="#0369a1",
                icon_symbol="KEYPAIR",
                bullet_points=[
                    "Only the intended recipient holds the private key",
                    "Not even the messaging provider can decrypt the content",
                    "True peer-to-peer cryptographic security",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_cyber_short1_scene3.png",
                title="256-Bit Fortress",
                subtitle="Astronomical Computational Security",
                format="portrait",
                primary_color="#047857",
                secondary_color="#059669",
                icon_symbol="AES-256",
                bullet_points=[
                    "2^256 possible key combinations",
                    "Requires more energy than our sun to brute force",
                    "Mathematical certainty protects your digital privacy",
                ],
            )
        )

        # Cyber Shorts 2
        specs.append(
            AssetSpec(
                filename="orig_cyber_short2_scene1.png",
                title="Castle Mindset",
                subtitle="Why Old Firewalls Failed",
                format="portrait",
                primary_color="#450a0a",
                secondary_color="#7f1d1d",
                icon_symbol="CASTLE",
                bullet_points=[
                    "Old networks assumed everything inside was friendly",
                    "Breaching one employee gave access to the entire company",
                    "Lateral movement let attackers silently spread everywhere",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_cyber_short2_scene2.png",
                title="Always Verify",
                subtitle="The Zero Trust Doctrine",
                format="portrait",
                primary_color="#0c4a6e",
                secondary_color="#075985",
                icon_symbol="VERIFY",
                bullet_points=[
                    "Assume the internal network is already compromised",
                    "Every request verified with strict device & identity tokens",
                    "No user or server has blanket trust",
                ],
            )
        )
        specs.append(
            AssetSpec(
                filename="orig_cyber_short2_scene3.png",
                title="Blast Radius: Zero",
                subtitle="Total Containment",
                format="portrait",
                primary_color="#022c22",
                secondary_color="#065f46",
                icon_symbol="LOCKED",
                bullet_points=[
                    "Compromised endpoints isolated in milliseconds",
                    "Critical databases remain fully protected",
                    "Modern resilience through intelligent architecture",
                ],
            )
        )

        return specs
