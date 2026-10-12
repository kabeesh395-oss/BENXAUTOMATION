"""Procedural asset generator for BENX 2D Mascot rig layers.

Generates high-resolution, anti-aliased character parts:
- Head base, visor plate, antennae, earcups
- Dynamic LED visor eyes (happy, surprised, confused, serious, excited, sad, blink)
- Dialogue viseme mouth shapes (rest, a, o, e, wide)
- Torso / chassis (front, three_quarter_left, three_quarter_right) with BX emblem
- Arm pose layers (idle, gesture, pointing_right, pointing_up, thinking_chin, shrug, cheer)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFilter

log = logging.getLogger(__name__)

# Signature BENX Color Palette
COLOR_OBSIDIAN = (11, 19, 43, 255)
COLOR_NAVY_ARMOR = (28, 37, 65, 255)
COLOR_CYBER_TEAL = (0, 242, 254, 255)
COLOR_ELECTRIC_BLUE = (79, 172, 254, 255)
COLOR_PLASMA_WHITE = (255, 255, 255, 255)
COLOR_CORAL_NEON = (255, 65, 108, 255)
COLOR_VISOR_GLASS = (15, 23, 42, 240)


class MascotAssetBuilder:
    """Builds and caches all required BENX mascot rig layer components."""

    def __init__(self, output_dir: Path = Path("assets/mascot")) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self, force: bool = False) -> dict[str, Path]:
        """Generate all layer PNGs and save character spec."""
        paths: dict[str, Path] = {}

        # 1. Head & Visor
        paths["head_base"] = self._build_head_base(force)
        paths["visor_plate"] = self._build_visor_plate(force)

        # 2. Eye expressions
        for expr in ["happy", "surprised", "confused", "serious", "excited", "sad", "blink"]:
            paths[f"eyes_{expr}"] = self._build_eyes(expr, force)

        # 3. Visemes
        for vis in ["rest", "a", "o", "e", "wide"]:
            paths[f"mouth_{vis}"] = self._build_mouth(vis, force)

        # 4. Torsos
        paths["torso_front"] = self._build_torso("front", force)
        paths["torso_three_quarter_left"] = self._build_torso("three_quarter_left", force)
        paths["torso_three_quarter_right"] = self._build_torso("three_quarter_right", force)

        # 5. Arms & Poses
        for pose in ["idle", "gesture", "pointing_right", "pointing_up", "thinking_chin", "shrug", "cheer"]:
            paths[f"arms_{pose}"] = self._build_arms(pose, force)

        # 6. Save Manifest JSON
        manifest_file = self.output_dir / "rig_manifest.json"
        manifest_data = {
            "character": "BENX",
            "version": "2.0.0",
            "license": "original_creator_owned",
            "total_layers": len(paths),
            "layers": {k: str(v.name) for k, v in paths.items()},
        }
        manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        log.info("Generated %d BENX mascot rig layers in %s", len(paths), self.output_dir)
        return paths

    def _build_head_base(self, force: bool) -> Path:
        out = self.output_dir / "head_base.png"
        if out.is_file() and not force:
            return out

        img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Antennae stalks
        draw.line([(240, 180), (200, 70)], fill=COLOR_OBSIDIAN, width=14)
        draw.line([(360, 180), (400, 70)], fill=COLOR_OBSIDIAN, width=14)
        # Antenna tips (glowing orbs)
        draw.ellipse([(185, 55), (215, 85)], fill=COLOR_CYBER_TEAL)
        draw.ellipse([(385, 55), (415, 85)], fill=COLOR_CYBER_TEAL)
        draw.ellipse([(193, 63), (207, 77)], fill=COLOR_PLASMA_WHITE)
        draw.ellipse([(393, 63), (407, 77)], fill=COLOR_PLASMA_WHITE)

        # Earcups (audio sensors)
        draw.ellipse([(90, 240), (160, 360)], fill=COLOR_NAVY_ARMOR)
        draw.ellipse([(440, 240), (510, 360)], fill=COLOR_NAVY_ARMOR)
        draw.ellipse([(105, 260), (145, 340)], fill=COLOR_ELECTRIC_BLUE)
        draw.ellipse([(455, 260), (495, 340)], fill=COLOR_ELECTRIC_BLUE)

        # Main Helmet Shell (curved rounded rectangle)
        draw.rounded_rectangle([(130, 140), (470, 480)], radius=150, fill=COLOR_OBSIDIAN, outline=COLOR_NAVY_ARMOR, width=8)

        # Subtle specular top rim
        draw.arc([(180, 145), (420, 220)], start=190, end=350, fill=COLOR_ELECTRIC_BLUE, width=4)

        img.save(out, "PNG")
        return out

    def _build_visor_plate(self, force: bool) -> Path:
        out = self.output_dir / "visor_plate.png"
        if out.is_file() and not force:
            return out

        img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Panoramic curved glass visor faceplate
        draw.rounded_rectangle([(165, 210), (435, 430)], radius=90, fill=COLOR_VISOR_GLASS, outline=COLOR_ELECTRIC_BLUE, width=5)

        # Visor glass sheen (subtle gloss arc)
        draw.arc([(180, 220), (420, 280)], start=200, end=340, fill=(255, 255, 255, 70), width=6)

        img.save(out, "PNG")
        return out

    def _build_eyes(self, expression: str, force: bool) -> Path:
        out = self.output_dir / f"eyes_{expression}.png"
        if out.is_file() and not force:
            return out

        img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        left_center = (245, 290)
        right_center = (355, 290)

        if expression == "happy":
            # Upward curving joyful crescent eyes
            draw.arc([(220, 270), (270, 315)], start=180, end=360, fill=COLOR_CYBER_TEAL, width=8)
            draw.arc([(330, 270), (380, 315)], start=180, end=360, fill=COLOR_CYBER_TEAL, width=8)
        elif expression == "surprised":
            # Wide open luminous circular eyes
            draw.ellipse([(225, 270), (265, 310)], outline=COLOR_CYBER_TEAL, width=6)
            draw.ellipse([(335, 270), (375, 310)], outline=COLOR_CYBER_TEAL, width=6)
            draw.ellipse([(240, 285), (250, 295)], fill=COLOR_PLASMA_WHITE)
            draw.ellipse([(350, 285), (360, 295)], fill=COLOR_PLASMA_WHITE)
        elif expression == "confused":
            # Asymmetrical: left eye arched high, right eye squinted/tilted
            draw.arc([(220, 255), (270, 295)], start=180, end=360, fill=COLOR_CYBER_TEAL, width=7)
            draw.line([(335, 305), (375, 300)], fill=COLOR_CYBER_TEAL, width=6)
        elif expression == "serious":
            # Narrowed angular focused visor slits
            draw.line([(220, 290), (270, 296)], fill=COLOR_CYBER_TEAL, width=7)
            draw.line([(330, 296), (380, 290)], fill=COLOR_CYBER_TEAL, width=7)
            draw.ellipse([(242, 293), (248, 298)], fill=COLOR_PLASMA_WHITE)
            draw.ellipse([(352, 293), (358, 298)], fill=COLOR_PLASMA_WHITE)
        elif expression == "excited":
            # Star/diamond sparkles
            for cx, cy in [left_center, right_center]:
                draw.polygon([(cx, cy - 20), (cx + 10, cy), (cx, cy + 20), (cx - 10, cy)], fill=COLOR_CYBER_TEAL)
                draw.polygon([(cx, cy - 10), (cx + 5, cy), (cx, cy + 10), (cx - 5, cy)], fill=COLOR_PLASMA_WHITE)
        elif expression == "sad":
            # Downward drooping crescent eyes
            draw.arc([(220, 275), (270, 320)], start=0, end=180, fill=COLOR_CYBER_TEAL, width=7)
            draw.arc([(330, 275), (380, 320)], start=0, end=180, fill=COLOR_CYBER_TEAL, width=7)
        elif expression == "blink":
            # Closed blink: horizontal laser-thin glowing lines
            draw.line([(225, 292), (265, 292)], fill=COLOR_CYBER_TEAL, width=5)
            draw.line([(335, 292), (375, 292)], fill=COLOR_CYBER_TEAL, width=5)
            draw.line([(235, 292), (255, 292)], fill=COLOR_PLASMA_WHITE, width=2)
            draw.line([(345, 292), (365, 292)], fill=COLOR_PLASMA_WHITE, width=2)
        else:
            # Default normal expressive oval eyes
            draw.ellipse([(225, 270), (265, 310)], fill=COLOR_CYBER_TEAL)
            draw.ellipse([(335, 270), (375, 310)], fill=COLOR_CYBER_TEAL)
            draw.ellipse([(240, 282), (252, 294)], fill=COLOR_PLASMA_WHITE)
            draw.ellipse([(350, 282), (362, 294)], fill=COLOR_PLASMA_WHITE)

        img.save(out, "PNG")
        return out

    def _build_mouth(self, viseme: str, force: bool) -> Path:
        out = self.output_dir / f"mouth_{viseme}.png"
        if out.is_file() and not force:
            return out

        img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx, cy = 300, 375

        if viseme == "rest":
            # Soft relaxed horizontal digital curve
            draw.line([(275, cy), (325, cy)], fill=COLOR_CYBER_TEAL, width=5)
            draw.line([(285, cy), (315, cy)], fill=COLOR_PLASMA_WHITE, width=2)
        elif viseme == "a":
            # Open oval vowel mouth
            draw.ellipse([(cx - 24, cy - 14), (cx + 24, cy + 18)], fill=COLOR_CYBER_TEAL, outline=COLOR_ELECTRIC_BLUE, width=3)
            draw.ellipse([(cx - 15, cy - 8), (cx + 15, cy + 12)], fill=(10, 15, 30, 255))
            draw.line([(cx - 12, cy - 4), (cx + 12, cy - 4)], fill=COLOR_PLASMA_WHITE, width=3)  # teeth bar
        elif viseme == "o":
            # Round circular aperture mouth
            draw.ellipse([(cx - 16, cy - 16), (cx + 16, cy + 16)], fill=COLOR_CYBER_TEAL, outline=COLOR_ELECTRIC_BLUE, width=3)
            draw.ellipse([(cx - 10, cy - 10), (cx + 10, cy + 10)], fill=(10, 15, 30, 255))
        elif viseme == "e":
            # Wide smile/teeth grin
            draw.rounded_rectangle([(cx - 30, cy - 8), (cx + 30, cy + 10)], radius=6, fill=COLOR_CYBER_TEAL)
            draw.line([(cx - 25, cy + 1), (cx + 25, cy + 1)], fill=COLOR_PLASMA_WHITE, width=4)
        elif viseme == "wide":
            # Energetic stadium/pill mouth (shouting / big laugh)
            draw.rounded_rectangle([(cx - 38, cy - 16), (cx + 38, cy + 22)], radius=14, fill=COLOR_CYBER_TEAL)
            draw.rounded_rectangle([(cx - 28, cy - 8), (cx + 28, cy + 14)], radius=10, fill=(10, 15, 30, 255))
            draw.line([(cx - 20, cy - 2), (cx + 20, cy - 2)], fill=COLOR_PLASMA_WHITE, width=4)
        else:
            # Fallback line
            draw.line([(275, cy), (325, cy)], fill=COLOR_CYBER_TEAL, width=4)

        img.save(out, "PNG")
        return out

    def _build_torso(self, view: str, force: bool) -> Path:
        out = self.output_dir / f"torso_{view}.png"
        if out.is_file() and not force:
            return out

        img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Neck collar connector
        draw.rectangle([(260, 440), (340, 480)], fill=COLOR_NAVY_ARMOR, outline=COLOR_ELECTRIC_BLUE, width=3)

        if view == "front":
            # Main chest armor
            points = [(180, 480), (420, 480), (380, 600), (220, 600)]
            draw.polygon(points, fill=COLOR_OBSIDIAN, outline=COLOR_NAVY_ARMOR)

            # Shoulder plates
            draw.polygon([(140, 480), (190, 470), (180, 530), (130, 530)], fill=COLOR_NAVY_ARMOR)
            draw.polygon([(460, 480), (410, 470), (420, 530), (470, 530)], fill=COLOR_NAVY_ARMOR)

            # Circuit glow lines
            draw.line([(220, 510), (260, 510)], fill=COLOR_ELECTRIC_BLUE, width=4)
            draw.line([(340, 510), (380, 510)], fill=COLOR_ELECTRIC_BLUE, width=4)

            # Central Hexagonal "BX" Chest Emblem
            hex_pts = [(300, 510), (325, 525), (325, 555), (300, 570), (275, 555), (275, 525)]
            draw.polygon(hex_pts, fill=COLOR_OBSIDIAN, outline=COLOR_CYBER_TEAL)
            # BX text representation
            draw.text((287, 528), "BX", fill=COLOR_PLASMA_WHITE)
        elif view == "three_quarter_left":
            # Torso angled slightly rightward
            points = [(200, 480), (430, 480), (390, 600), (240, 600)]
            draw.polygon(points, fill=COLOR_OBSIDIAN, outline=COLOR_NAVY_ARMOR)
            # Chest Emblem shifted right
            hex_pts = [(330, 515), (350, 527), (350, 552), (330, 565), (310, 552), (310, 527)]
            draw.polygon(hex_pts, fill=COLOR_OBSIDIAN, outline=COLOR_CYBER_TEAL)
            draw.text((319, 531), "BX", fill=COLOR_PLASMA_WHITE)
        else:  # three_quarter_right
            points = [(170, 480), (400, 480), (360, 600), (210, 600)]
            draw.polygon(points, fill=COLOR_OBSIDIAN, outline=COLOR_NAVY_ARMOR)
            # Chest Emblem shifted left
            hex_pts = [(270, 515), (290, 527), (290, 552), (270, 565), (250, 552), (250, 527)]
            draw.polygon(hex_pts, fill=COLOR_OBSIDIAN, outline=COLOR_CYBER_TEAL)
            draw.text((259, 531), "BX", fill=COLOR_PLASMA_WHITE)

        img.save(out, "PNG")
        return out

    def _build_arms(self, pose: str, force: bool) -> Path:
        out = self.output_dir / f"arms_{pose}.png"
        if out.is_file() and not force:
            return out

        img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if pose == "idle":
            # Relaxed arms hanging naturally by sides
            draw.line([(150, 490), (130, 590)], fill=COLOR_NAVY_ARMOR, width=22)
            draw.line([(450, 490), (470, 590)], fill=COLOR_NAVY_ARMOR, width=22)
            # Hands
            draw.ellipse([(115, 575), (145, 605)], fill=COLOR_CYBER_TEAL)
            draw.ellipse([(455, 575), (485, 605)], fill=COLOR_CYBER_TEAL)
        elif pose == "gesture":
            # Left arm down, Right arm extended in open palm welcoming gesture
            draw.line([(150, 490), (130, 590)], fill=COLOR_NAVY_ARMOR, width=22)
            draw.ellipse([(115, 575), (145, 605)], fill=COLOR_CYBER_TEAL)
            # Right arm bent forward
            draw.line([(440, 490), (490, 530), (530, 510)], fill=COLOR_NAVY_ARMOR, width=20)
            draw.ellipse([(515, 495), (545, 525)], fill=COLOR_CYBER_TEAL)
        elif pose == "pointing_right":
            # Right arm pointing sharply to the right
            draw.line([(150, 490), (130, 590)], fill=COLOR_NAVY_ARMOR, width=22)
            draw.ellipse([(115, 575), (145, 605)], fill=COLOR_CYBER_TEAL)
            # Right arm horizontal
            draw.line([(440, 490), (510, 490), (560, 480)], fill=COLOR_NAVY_ARMOR, width=20)
            draw.polygon([(555, 470), (585, 480), (555, 490)], fill=COLOR_CYBER_TEAL)  # pointing index finger
        elif pose == "pointing_up":
            # Right arm pointing up toward insight / title
            draw.line([(150, 490), (130, 590)], fill=COLOR_NAVY_ARMOR, width=22)
            draw.ellipse([(115, 575), (145, 605)], fill=COLOR_CYBER_TEAL)
            # Right arm reaching up
            draw.line([(440, 490), (490, 450), (495, 380)], fill=COLOR_NAVY_ARMOR, width=20)
            draw.polygon([(485, 385), (495, 355), (505, 385)], fill=COLOR_CYBER_TEAL)
        elif pose == "thinking_chin":
            # Left arm folded, Right arm bent tapping chin
            draw.line([(150, 490), (190, 540), (260, 540)], fill=COLOR_NAVY_ARMOR, width=20)
            # Right arm up to visor chin
            draw.line([(440, 490), (410, 480), (360, 440)], fill=COLOR_NAVY_ARMOR, width=20)
            draw.ellipse([(345, 425), (375, 455)], fill=COLOR_CYBER_TEAL)
        elif pose == "shrug":
            # Both elbows bent out, hands open
            draw.line([(150, 480), (100, 520), (90, 470)], fill=COLOR_NAVY_ARMOR, width=20)
            draw.ellipse([(75, 455), (105, 485)], fill=COLOR_CYBER_TEAL)
            draw.line([(450, 480), (500, 520), (510, 470)], fill=COLOR_NAVY_ARMOR, width=20)
            draw.ellipse([(495, 455), (525, 485)], fill=COLOR_CYBER_TEAL)
        elif pose == "cheer":
            # Both arms held high triumphantly
            draw.line([(150, 480), (100, 430), (80, 360)], fill=COLOR_NAVY_ARMOR, width=20)
            draw.ellipse([(65, 345), (95, 375)], fill=COLOR_CYBER_TEAL)
            draw.line([(450, 480), (500, 430), (520, 360)], fill=COLOR_NAVY_ARMOR, width=20)
            draw.ellipse([(505, 345), (535, 375)], fill=COLOR_CYBER_TEAL)
        else:
            # Default to idle
            draw.line([(150, 490), (130, 590)], fill=COLOR_NAVY_ARMOR, width=22)
            draw.line([(450, 490), (470, 590)], fill=COLOR_NAVY_ARMOR, width=22)
            draw.ellipse([(115, 575), (145, 605)], fill=COLOR_CYBER_TEAL)
            draw.ellipse([(455, 575), (485, 605)], fill=COLOR_CYBER_TEAL)

        img.save(out, "PNG")
        return out
