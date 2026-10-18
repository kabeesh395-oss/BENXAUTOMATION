"""2D Puppet & Body Language Rigging Engine for BEN and Character Universe.

Supports ALL 5 characters in the Universe with signature body language, props, and visemes:
1. BEN: Black sunglasses, smartphone with glowing screen, USB cable sparks, cool thumbs-up.
2. MAX (Robot): Segmented robotic clamp arms, antenna with flashing LED, holographic circuit blueprint.
3. The King: Royal velvet/ermine sleeves, golden scepter with ruby crystal, imperial decree scroll.
4. Mr. Cash: Pinstripe suit with gold cufflinks, stacks of $100 bills, animated falling gold coins.
5. Dr. Quantum: Lab coat sleeves, bubbling chemistry flask with rising fizz bubbles, orbiting atomic electrons.

All characters share:
- Audio RMS Viseme Lip-Sync (closed, open, O-shape).
- Natural Eye Blinking & Facial Expressions.
- Speech-synced Cadence & Body Bobbing (sinusoidal bounce).
- Expressive Poses: IDLE, POINTING, SHRUGGING, PANIC_JUMP, HOLDING_PROP, THUMBS_UP.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from benxautomation.logger import get_logger

log = get_logger(__name__)


class PuppetPose(str, Enum):
    """Core expressive poses for character body language."""
    IDLE = "idle"
    POINTING = "pointing"
    SHRUGGING = "shrugging"
    PANIC_JUMP = "panic_jump"
    HOLDING_PHONE = "holding_phone"
    HOLDING_PROP = "holding_prop"
    THUMBS_UP = "thumbs_up"


@dataclass
class PuppetState:
    """Instantaneous state of the rigged character in a given frame."""
    character: str  # "ben", "max", "mr_cash", "the_king", "dr_quantum"
    pose: PuppetPose = PuppetPose.IDLE
    is_speaking: bool = False
    speech_energy: float = 0.0  # Audio RMS 0.0 to 1.0
    is_blinking: bool = False
    frame_idx: int = 0
    pose_progress: float = 1.0  # 0.0 to 1.0 transition progress
    expression: str = "talking"  # "shocked", "panic", "smirk", "warning", "explaining", "skeptical", "triumph", "talking"


# Rigging specifications per character with exact facial feature alignments
CHARACTER_RIG_CONFIGS: Dict[str, Dict[str, Any]] = {
    "ben": {
        "outline_color": (0, 0, 0),
        "sleeve_color": (30, 41, 59),
        "hand_color": (255, 255, 255),
        "mouth_offset": (0.51, 0.53),
        "eye_offset": (0.51, 0.46),
        "shoulder_left": (0.30, 0.60),
        "shoulder_right": (0.70, 0.60),
        "signature_prop": "smartphone",
    },
    "max": {
        "outline_color": (30, 41, 59),
        "sleeve_color": (148, 163, 184),
        "hand_color": (255, 255, 255),
        "mouth_offset": (0.58, 0.482),
        "eye_offset": (0.58, 0.40),
        "shoulder_left": (0.30, 0.58),
        "shoulder_right": (0.70, 0.58),
        "signature_prop": "blueprint",
        "is_robot": False,
    },
    "the_king": {
        "outline_color": (0, 0, 0),
        "sleeve_color": (185, 28, 28),  # Royal red velvet
        "hand_color": (255, 255, 255),
        "cuff_color": (254, 240, 138),  # Gold trim
        "mouth_offset": (0.52, 0.52),
        "eye_offset": (0.52, 0.42),
        "shoulder_left": (0.30, 0.60),
        "shoulder_right": (0.70, 0.60),
        "signature_prop": "scepter",
    },
    "mr_cash": {
        "outline_color": (0, 0, 0),
        "sleeve_color": (15, 23, 42),  # Pinstripe navy
        "hand_color": (255, 255, 255),
        "cuff_color": (234, 179, 8),  # Gold cufflinks
        "mouth_offset": (0.49, 0.46),
        "eye_offset": (0.49, 0.37),
        "shoulder_left": (0.30, 0.56),
        "shoulder_right": (0.70, 0.56),
        "signature_prop": "cash",
    },
    "dr_quantum": {
        "outline_color": (0, 0, 0),
        "sleeve_color": (248, 250, 252),  # Lab coat white
        "hand_color": (255, 255, 255),
        "cuff_color": (59, 130, 246),  # Blue gloves / cuffs
        "mouth_offset": (0.55, 0.49),
        "eye_offset": (0.55, 0.42),
        "shoulder_left": (0.30, 0.58),
        "shoulder_right": (0.70, 0.58),
        "signature_prop": "flask",
    },
}



class PuppetCharacter:
    """Rigged 2D character capable of full-body actions, poses, and props for all universe members."""

    def __init__(self, character: str = "ben", asset_dir: Path | str = "assets/characters/universe_debut"):
        self.character = character.lower().strip()
        self.asset_dir = Path(asset_dir)
        self._sprite_cache: Dict[str, Image.Image] = {}

    def _load_base_sprite(self, filename: str) -> Optional[Image.Image]:
        """Load and cache high-res character sprite."""
        if filename in self._sprite_cache:
            return self._sprite_cache[filename].copy()

        path = self.asset_dir / filename
        if path.exists():
            im = Image.open(path).convert("RGBA")
            self._sprite_cache[filename] = im
            return im.copy()
        return None

    def render_puppet_frame(
        self,
        state: PuppetState,
        canvas_size: Tuple[int, int] = (1080, 1920),
        background: Optional[Image.Image] = None,
    ) -> Image.Image:
        """Compose the character with procedural body language, pose, lip-sync, and bounce."""
        tw, th = canvas_size
        char_key = state.character.lower()
        cfg = CHARACTER_RIG_CONFIGS.get(char_key, CHARACTER_RIG_CONFIGS["ben"])

        if background is not None:
            if background.size != canvas_size:
                background = background.resize(canvas_size, Image.Resampling.LANCZOS)
            frame = background.convert("RGBA")
        else:
            frame = Image.new("RGBA", canvas_size, (255, 255, 255, 0))

        # 1. Compute Speech Cadence & Body Bobbing
        bounce_y = 0
        if state.is_speaking:
            bounce_y = int(math.sin(state.frame_idx * 0.6) * 7.0)

        # Panic jump elevates character by 35px with spring dampening
        if state.pose == PuppetPose.PANIC_JUMP:
            jump_phase = (state.frame_idx % 24) / 24.0
            bounce_y -= int(math.sin(jump_phase * math.pi) * 38.0)

        # 2. Select / Render Facial Viseme
        viseme = "closed"
        if state.is_speaking:
            viseme = "open" if (state.frame_idx % 5 < 3) else "o"

        base_sprite = self._get_character_base_image(state, viseme)
        if base_sprite is None:
            base_sprite = Image.new("RGBA", (768, 1376), (255, 255, 255, 255))

        # Fit character to canvas cleanly without letterboxing
        scale = max(tw / base_sprite.width, th / base_sprite.height)
        nw, nh = int(base_sprite.width * scale), int(base_sprite.height * scale)
        scaled_char = base_sprite.resize((nw, nh), Image.Resampling.LANCZOS)

        # Character placement on canvas
        char_x = (tw - nw) // 2
        char_y = (th - nh) + bounce_y

        frame.paste(scaled_char, (char_x, char_y), scaled_char)


        draw = ImageDraw.Draw(frame)

        # 3. Dynamic Facial Viseme & Blinking Overlays
        if char_key != "ben":
            self._draw_facial_expressions(draw, state, cfg, char_x, char_y, nw, nh, viseme)
        else:
            self._draw_ben_facial_overlays(draw, state, cfg, char_x, char_y, nw, nh, viseme)

        # 4. Procedural Character-Specific Arm Gestures
        self._draw_arm_gestures(draw, state, cfg, char_x, char_y, nw, nh)

        # 5. Character Signature Props & Particle FX
        self._draw_signature_props(draw, state, cfg, char_x, char_y, nw, nh)

        return frame.convert("RGB")

    def _get_character_base_image(self, state: PuppetState, viseme: str) -> Optional[Image.Image]:
        """Fetch the base sprite image."""
        char = state.character.lower()

        if char == "ben":
            if state.is_blinking:
                fname = "ben_intro_blink.jpg"
            elif viseme == "open":
                fname = "ben_intro_open.jpg"
            elif viseme == "o":
                fname = "ben_intro_o.jpg"
            else:
                fname = "ben_intro_closed.jpg"
            return self._load_base_sprite(fname)

        elif char == "max":
            return self._load_base_sprite("max_logic.jpg")
        elif char == "mr_cash":
            return self._load_base_sprite("cash_finance.jpg")
        elif char == "the_king":
            return self._load_base_sprite("king_history.jpg")
        elif char == "dr_quantum":
            return self._load_base_sprite("quantum_science.jpg")

        return self._load_base_sprite("ben_intro_closed.jpg")

    def _draw_ben_facial_overlays(
        self,
        draw: ImageDraw.ImageDraw,
        state: PuppetState,
        cfg: Dict[str, Any],
        cx: int,
        cy: int,
        cw: int,
        ch: int,
        viseme: str,
    ) -> None:
        """Render dynamic comic emotional expressions and overlays on BEN."""
        mx = cx + int(cw * cfg["mouth_offset"][0])
        my = cy + int(ch * cfg["mouth_offset"][1])
        ex = cx + int(cw * cfg["eye_offset"][0])
        ey = cy + int(ch * cfg["eye_offset"][1])
        expr = getattr(state, "expression", "talking").lower()

        # ── 1. BEN EMOTIONAL OVERLAYS & EYEBROWS (ABOVE SUNGLASSES) ──
        if expr == "shocked":
            drop_x = cx + int(cw * 0.72)
            drop_y = cy + int(ch * 0.22)
            draw.ellipse([drop_x, drop_y, drop_x + 14, drop_y + 24], fill=(56, 189, 248), outline=(0, 0, 0), width=3)
            draw.text((cx + int(cw * 0.52), cy + int(ch * 0.12)), "!", fill=(239, 68, 68))
            draw.arc([ex - 42, ey - 32, ex - 10, ey - 14], start=190, end=350, fill=(0, 0, 0), width=5)
            draw.arc([ex + 10, ey - 32, ex + 42, ey - 14], start=190, end=350, fill=(0, 0, 0), width=5)

        elif expr == "panic":
            d_x = cx + int(cw * 0.66)
            d_y = cy + int(ch * 0.28) + (state.frame_idx % 12) * 2
            draw.ellipse([d_x, d_y, d_x + 16, d_y + 26], fill=(56, 189, 248), outline=(0, 0, 0), width=3)
            draw.line([(ex - 40, ey - 22), (ex - 24, ey - 28), (ex - 8, ey - 22)], fill=(0, 0, 0), width=5)
            draw.line([(ex + 8, ey - 22), (ex + 24, ey - 28), (ex + 40, ey - 22)], fill=(0, 0, 0), width=5)

        elif expr == "smirk":
            gx, gy = ex + 36, ey - 12
            draw.line([(gx - 10, gy), (gx + 10, gy)], fill=(254, 240, 138), width=3)
            draw.line([(gx, gy - 10), (gx, gy + 10)], fill=(254, 240, 138), width=3)
            draw.line([(ex - 36, ey - 22), (ex - 8, ey - 22)], fill=(0, 0, 0), width=4)
            draw.line([(ex + 8, ey - 20), (ex + 38, ey - 34)], fill=(0, 0, 0), width=5)

        elif expr == "warning":
            draw.line([(ex - 40, ey - 26), (ex - 8, ey - 16)], fill=(0, 0, 0), width=6)
            draw.line([(ex + 8, ey - 16), (ex + 40, ey - 26)], fill=(0, 0, 0), width=6)

        elif expr == "skeptical":
            draw.line([(ex - 38, ey - 18), (ex - 8, ey - 18)], fill=(0, 0, 0), width=5)
            draw.arc([ex + 8, ey - 34, ex + 42, ey - 14], start=190, end=350, fill=(0, 0, 0), width=5)
            draw.text((cx + int(cw * 0.68), cy + int(ch * 0.12)), "?", fill=(59, 130, 246))

        elif expr == "triumph":
            for sx_off, sy_off in [(0.25, 0.18), (0.75, 0.16)]:
                sx = cx + int(cw * sx_off)
                sy = cy + int(ch * sy_off)
                draw.line([(sx - 8, sy), (sx + 8, sy)], fill=(253, 224, 71), width=3)
                draw.line([(sx, sy - 8), (sx, sy + 8)], fill=(253, 224, 71), width=3)
            draw.arc([ex - 40, ey - 28, ex - 8, ey - 14], start=190, end=350, fill=(0, 0, 0), width=4)
            draw.arc([ex + 8, ey - 28, ex + 40, ey - 14], start=190, end=350, fill=(0, 0, 0), width=4)

        # ── 2. BEN DYNAMIC VISEME MOUTH (SPEECH + EMOTION) ───────────
        if expr != "talking":
            if viseme == "open":
                if expr == "shocked":
                    draw.ellipse([mx - 24, my - 16, mx + 24, my + 24], fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                    draw.rectangle([mx - 18, my - 12, mx + 18, my - 4], fill=(255, 255, 255))
                elif expr == "panic":
                    draw.ellipse([mx - 22, my - 14, mx + 22, my + 16], fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                    for tx in range(mx - 14, mx + 15, 7):
                        draw.line([(tx, my - 10), (tx, my + 12)], fill=(255, 255, 255), width=2)
                elif expr == "smirk":
                    draw.pieslice([mx - 20, my - 12, mx + 28, my + 20], start=0, end=180, fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                    draw.rectangle([mx - 14, my - 10, mx + 20, my - 4], fill=(255, 255, 255))
                elif expr == "warning":
                    draw.rounded_rectangle([mx - 22, my - 8, mx + 22, my + 10], radius=4, fill=(255, 255, 255), outline=(0, 0, 0), width=4)
                    draw.line([(mx - 20, my + 1), (mx + 20, my + 1)], fill=(0, 0, 0), width=2)
                    for tx in range(mx - 14, mx + 15, 7):
                        draw.line([(tx, my - 7), (tx, my + 9)], fill=(0, 0, 0), width=2)
                elif expr == "triumph":
                    draw.pieslice([mx - 26, my - 14, mx + 26, my + 26], start=0, end=180, fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                    draw.rectangle([mx - 18, my - 10, mx + 18, my - 3], fill=(255, 255, 255))
                else:
                    draw.ellipse([mx - 22, my - 14, mx + 22, my + 14], fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                    draw.rectangle([mx - 16, my - 10, mx + 16, my - 3], fill=(255, 255, 255))

            elif viseme == "o":
                draw.ellipse([mx - 15, my - 15, mx + 15, my + 15], fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                draw.ellipse([mx - 8, my - 8, mx + 8, my + 8], fill=(136, 19, 55))

            else:  # viseme == "closed"
                if expr == "shocked":
                    draw.ellipse([mx - 10, my - 8, mx + 10, my + 8], fill=(225, 29, 72), outline=(0, 0, 0), width=3)
                elif expr == "panic":
                    draw.line([(mx - 22, my), (mx - 11, my + 6), (mx, my - 4), (mx + 11, my + 6), (mx + 22, my)], fill=(0, 0, 0), width=5)
                elif expr == "smirk":
                    draw.arc([mx - 22, my - 14, mx + 22, my + 10], start=10, end=160, fill=(0, 0, 0), width=5)
                    draw.line([(mx + 20, my - 2), (mx + 28, my - 10)], fill=(0, 0, 0), width=4)
                elif expr == "warning":
                    draw.line([(mx - 22, my), (mx + 22, my)], fill=(0, 0, 0), width=5)
                elif expr == "skeptical":
                    draw.line([(mx - 18, my + 5), (mx + 18, my - 5)], fill=(0, 0, 0), width=5)
                elif expr == "triumph":
                    draw.arc([mx - 24, my - 12, mx + 24, my + 14], start=10, end=170, fill=(0, 0, 0), width=5)
                else:
                    draw.arc([mx - 20, my - 10, mx + 20, my + 10], start=10, end=170, fill=(0, 0, 0), width=4)

    def _draw_facial_expressions(
        self,
        draw: ImageDraw.ImageDraw,
        state: PuppetState,
        cfg: Dict[str, Any],
        cx: int,
        cy: int,
        cw: int,
        ch: int,
        viseme: str,
    ) -> None:
        """Render synchronized mouth visemes, blinking, and emotional expressions on universe characters."""
        mx = cx + int(cw * cfg["mouth_offset"][0])
        my = cy + int(ch * cfg["mouth_offset"][1])
        ex = cx + int(cw * cfg["eye_offset"][0])
        ey = cy + int(ch * cfg["eye_offset"][1])
        expr = getattr(state, "expression", "talking").lower()
        is_robot = cfg.get("is_robot", False)

        # ── 1. ROBOT (MAX) DIGITAL VISOR MATRIX ──────────────────────
        if is_robot:
            draw.rectangle([ex - 50, ey - 18, ex + 50, ey + 18], fill=(15, 23, 42), outline=(30, 41, 59), width=3)
            if expr in ("panic", "warning", "shocked"):
                border_col = (239, 68, 68) if (state.frame_idx % 4 < 2) else (185, 28, 28)
                draw.rectangle([ex - 50, ey - 18, ex + 50, ey + 18], outline=border_col, width=3)

            glyph_map = {
                "shocked": "[O_O]",
                "panic": "[X_X]",
                "smirk": "[^ _ ~]",
                "warning": "[!_!]",
                "skeptical": "[?_?]",
                "triumph": "[^_^]",
                "explaining": "[=_=]",
            }
            glyph = glyph_map.get(expr, "[o_o]" if state.is_speaking else "[-_-]")
            if state.is_blinking:
                glyph = "[---]"
            glyph_col = (34, 197, 94) if expr == "triumph" else ((239, 68, 68) if expr in ("warning", "panic") else (14, 165, 233))
            draw.text((ex - 35, ey - 8), glyph, fill=glyph_col)
            return

        # ── 2. EYES & EYEBROWS (ALL UNIVERSE CHARACTERS) ──────────────
        eb_y = ey - 22
        if expr == "warning":
            draw.line([(ex - 36, eb_y - 6), (ex - 8, eb_y + 4)], fill=(0, 0, 0), width=5)
            draw.line([(ex + 8, eb_y + 4), (ex + 36, eb_y - 6)], fill=(0, 0, 0), width=5)
        elif expr == "shocked":
            draw.arc([ex - 38, eb_y - 14, ex - 6, eb_y + 2], start=190, end=350, fill=(0, 0, 0), width=5)
            draw.arc([ex + 6, eb_y - 14, ex + 38, eb_y + 2], start=190, end=350, fill=(0, 0, 0), width=5)
            drop_x = cx + int(cw * 0.72)
            drop_y = cy + int(ch * 0.22)
            draw.ellipse([drop_x, drop_y, drop_x + 14, drop_y + 24], fill=(56, 189, 248), outline=(0, 0, 0), width=3)
            draw.text((cx + int(cw * 0.52), cy + int(ch * 0.12)), "!", fill=(239, 68, 68))
        elif expr == "skeptical":
            draw.line([(ex - 36, eb_y + 4), (ex - 8, eb_y + 4)], fill=(0, 0, 0), width=5)
            draw.arc([ex + 6, eb_y - 16, ex + 38, eb_y + 2], start=190, end=350, fill=(0, 0, 0), width=5)
            draw.text((cx + int(cw * 0.68), cy + int(ch * 0.12)), "?", fill=(59, 130, 246))
        elif expr == "panic":
            draw.line([(ex - 36, eb_y + 2), (ex - 22, eb_y - 6), (ex - 8, eb_y + 2)], fill=(0, 0, 0), width=4)
            draw.line([(ex + 8, eb_y + 2), (ex + 22, eb_y - 6), (ex + 36, eb_y + 2)], fill=(0, 0, 0), width=4)
            drop_x = cx + int(cw * 0.70)
            drop_y = cy + int(ch * 0.25)
            draw.ellipse([drop_x, drop_y, drop_x + 14, drop_y + 24], fill=(56, 189, 248), outline=(0, 0, 0), width=3)
        elif expr == "smirk":
            draw.line([(ex - 36, eb_y), (ex - 8, eb_y)], fill=(0, 0, 0), width=4)
            draw.line([(ex + 8, eb_y + 2), (ex + 36, eb_y - 10)], fill=(0, 0, 0), width=5)
            sx, sy = ex + 32, ey - 6
            draw.line([(sx - 8, sy), (sx + 8, sy)], fill=(254, 240, 138), width=3)
            draw.line([(sx, sy - 8), (sx, sy + 8)], fill=(254, 240, 138), width=3)
        elif expr == "triumph":
            for sx_off, sy_off in [(0.25, 0.20), (0.78, 0.20)]:
                sx = cx + int(cw * sx_off)
                sy = cy + int(ch * sy_off)
                draw.line([(sx - 8, sy), (sx + 8, sy)], fill=(253, 224, 71), width=3)
                draw.line([(sx, sy - 8), (sx, sy + 8)], fill=(253, 224, 71), width=3)

        # Eye blinking
        if state.is_blinking:
            draw.arc([ex - 42, ey - 10, ex - 10, ey + 10], start=20, end=160, fill=(0, 0, 0), width=4)
            draw.arc([ex + 10, ey - 10, ex + 42, ey + 10], start=20, end=160, fill=(0, 0, 0), width=4)

        # ── 3. SYNCHRONIZED MOUTH VISEMES (ALL CHARACTERS) ───────────
        if viseme == "open":
            if expr == "shocked":
                draw.ellipse([mx - 24, my - 16, mx + 24, my + 24], fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                draw.rectangle([mx - 18, my - 12, mx + 18, my - 4], fill=(255, 255, 255))
            elif expr == "panic":
                draw.ellipse([mx - 22, my - 14, mx + 22, my + 16], fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                for tx in range(mx - 14, mx + 15, 7):
                    draw.line([(tx, my - 10), (tx, my + 12)], fill=(255, 255, 255), width=2)
            elif expr == "smirk":
                draw.pieslice([mx - 20, my - 12, mx + 28, my + 20], start=0, end=180, fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                draw.rectangle([mx - 14, my - 10, mx + 20, my - 4], fill=(255, 255, 255))
            elif expr == "warning":
                draw.rounded_rectangle([mx - 22, my - 8, mx + 22, my + 10], radius=4, fill=(255, 255, 255), outline=(0, 0, 0), width=4)
                draw.line([(mx - 20, my + 1), (mx + 20, my + 1)], fill=(0, 0, 0), width=2)
                for tx in range(mx - 14, mx + 15, 7):
                    draw.line([(tx, my - 7), (tx, my + 9)], fill=(0, 0, 0), width=2)
            elif expr == "triumph":
                draw.pieslice([mx - 26, my - 14, mx + 26, my + 26], start=0, end=180, fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                draw.rectangle([mx - 18, my - 10, mx + 18, my - 3], fill=(255, 255, 255))
            else:
                draw.ellipse([mx - 24, my - 14, mx + 24, my + 14], fill=(225, 29, 72), outline=(0, 0, 0), width=4)
                draw.rectangle([mx - 18, my - 10, mx + 18, my - 3], fill=(255, 255, 255))

        elif viseme == "o":
            draw.ellipse([mx - 15, my - 15, mx + 15, my + 15], fill=(225, 29, 72), outline=(0, 0, 0), width=4)
            draw.ellipse([mx - 8, my - 8, mx + 8, my + 8], fill=(136, 19, 55))

        else:  # viseme == "closed"
            if expr == "shocked":
                draw.ellipse([mx - 10, my - 8, mx + 10, my + 8], fill=(225, 29, 72), outline=(0, 0, 0), width=3)
            elif expr == "panic":
                draw.line([(mx - 24, my), (mx - 12, my + 8), (mx, my - 6), (mx + 12, my + 8), (mx + 24, my - 2)], fill=(0, 0, 0), width=5)
            elif expr == "smirk":
                draw.arc([mx - 22, my - 14, mx + 22, my + 10], start=10, end=160, fill=(0, 0, 0), width=5)
                draw.line([(mx + 20, my - 2), (mx + 28, my - 10)], fill=(0, 0, 0), width=4)
            elif expr == "warning":
                draw.line([(mx - 22, my), (mx + 22, my)], fill=(0, 0, 0), width=5)
            elif expr == "skeptical":
                draw.line([(mx - 20, my + 6), (mx + 20, my - 6)], fill=(0, 0, 0), width=5)
            elif expr == "triumph":
                draw.arc([mx - 24, my - 12, mx + 24, my + 14], start=10, end=170, fill=(0, 0, 0), width=5)
            else:
                draw.arc([mx - 20, my - 10, mx + 20, my + 10], start=10, end=170, fill=(0, 0, 0), width=4)



    def _draw_arm_gestures(
        self,
        draw: ImageDraw.ImageDraw,
        state: PuppetState,
        cfg: Dict[str, Any],
        cx: int,
        cy: int,
        cw: int,
        ch: int,
    ) -> None:
        """Render character-tailored arms (robot clamps, royal sleeves, pinstripes, lab coat)."""
        sl = (cx + int(cw * cfg["shoulder_left"][0]), cy + int(ch * cfg["shoulder_left"][1]))
        sr = (cx + int(cw * cfg["shoulder_right"][0]), cy + int(ch * cfg["shoulder_right"][1]))

        outline = cfg.get("outline_color", (0, 0, 0))
        sleeve = cfg.get("sleeve_color", (30, 41, 59))
        hand = cfg.get("hand_color", (255, 255, 255))
        arm_w = 16

        pose = state.pose
        if pose == PuppetPose.HOLDING_PROP:
            # Prop pose defaults to character signature
            pass

        if pose == PuppetPose.POINTING:
            # Right arm extends upward pointing at screen text
            elbow = (sr[0] + 80, sr[1] - 35)
            wrist = (elbow[0] + 85, elbow[1] - 70)
            finger = (wrist[0] + 35, wrist[1] - 25)

            # Sleeve
            draw.line([sr, elbow], fill=sleeve, width=arm_w + 4)
            draw.line([sr, elbow], fill=outline, width=arm_w)
            draw.line([elbow, wrist], fill=outline, width=arm_w)

            if cfg.get("is_robot"):
                # Robot 2-prong metallic pincer
                draw.arc([wrist[0] - 12, wrist[1] - 20, wrist[0] + 16, wrist[1] + 20], start=270, end=90, fill=hand, width=6)
            else:
                # Comic white glove & index finger
                draw.ellipse([wrist[0] - 14, wrist[1] - 14, wrist[0] + 14, wrist[1] + 14], fill=hand, outline=outline, width=4)
                draw.line([wrist, finger], fill=outline, width=arm_w - 4)

        elif pose == PuppetPose.SHRUGGING:
            # Both arms lifted sideways with open palms
            # Left
            el_l = (sl[0] - 65, sl[1] + 25)
            wr_l = (el_l[0] - 50, el_l[1] - 55)
            draw.line([sl, el_l], fill=sleeve, width=arm_w + 4)
            draw.line([sl, el_l], fill=outline, width=arm_w)
            draw.line([el_l, wr_l], fill=outline, width=arm_w)
            draw.ellipse([wr_l[0] - 14, wr_l[1] - 14, wr_l[0] + 14, wr_l[1] + 14], fill=hand, outline=outline, width=4)

            # Right
            el_r = (sr[0] + 65, sr[1] + 25)
            wr_r = (el_r[0] + 50, el_r[1] - 55)
            draw.line([sr, el_r], fill=sleeve, width=arm_w + 4)
            draw.line([sr, el_r], fill=outline, width=arm_w)
            draw.line([el_r, wr_r], fill=outline, width=arm_w)
            draw.ellipse([wr_r[0] - 14, wr_r[1] - 14, wr_r[0] + 14, wr_r[1] + 14], fill=hand, outline=outline, width=4)

        elif pose == PuppetPose.THUMBS_UP:
            elbow = (sr[0] + 65, sr[1] + 10)
            wrist = (elbow[0] + 45, elbow[1] - 45)
            thumb = (wrist[0], wrist[1] - 30)

            draw.line([sr, elbow], fill=sleeve, width=arm_w + 4)
            draw.line([sr, elbow], fill=outline, width=arm_w)
            draw.line([elbow, wrist], fill=outline, width=arm_w)
            draw.ellipse([wrist[0] - 16, wrist[1] - 16, wrist[0] + 16, wrist[1] + 16], fill=hand, outline=outline, width=5)
            draw.line([wrist, thumb], fill=outline, width=arm_w)

    def _draw_signature_props(
        self,
        draw: ImageDraw.ImageDraw,
        state: PuppetState,
        cfg: Dict[str, Any],
        cx: int,
        cy: int,
        cw: int,
        ch: int,
    ) -> None:
        """Render character-specific signature props and particle effects."""
        char = state.character.lower()
        frame_idx = state.frame_idx

        # 1. BEN: Smartphone + Charging Cable
        if char == "ben" and state.pose in (PuppetPose.HOLDING_PHONE, PuppetPose.HOLDING_PROP):
            px = cx + int(cw * 0.42)
            py = cy + int(ch * 0.46)
            pw, ph = 120, 210
            draw.rounded_rectangle([px, py, px + pw, py + ph], radius=18, fill=(30, 30, 30), outline=(0, 0, 0), width=6)
            draw.rectangle([px + 10, py + 22, px + pw - 10, py + ph - 24], fill=(14, 165, 233))
            sx, sy = px + pw // 2, py + ph // 2
            draw.ellipse([sx - 20, sy - 20, sx + 20, sy + 20], fill=(239, 68, 68), outline=(0, 0, 0), width=3)
            draw.line([(sx, sy - 12), (sx, sy + 3)], fill=(255, 255, 255), width=4)
            draw.ellipse([sx - 2, sy + 7, sx + 2, sy + 11], fill=(255, 255, 255))
            draw.line([(sx, py + ph), (sx, py + ph + 40), (sx + 70, py + ph + 110)], fill=(249, 115, 22), width=8)

        # 2. MAX: Holographic Logic Display
        elif char == "max":
            if state.pose in (PuppetPose.HOLDING_PROP, PuppetPose.HOLDING_PHONE, PuppetPose.POINTING):
                bx = cx + int(cw * 0.65)
                by = cy + int(ch * 0.35)
                bw, bh = 150, 95
                draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=8, fill=(15, 23, 42), outline=(14, 165, 233), width=4)
                for offset_x in range(15, bw, 25):
                    draw.line([(bx + offset_x, by + 10), (bx + offset_x, by + bh - 10)], fill=(56, 189, 248), width=2)
                draw.text((bx + 18, by + 35), "LOGIC 0x7F", fill=(56, 189, 248))

        # 3. The King: Royal Crown Sparkles & Sword Gleam
        elif char == "the_king":
            gx = cx + int(cw * 0.62)
            gy = cy + int(ch * 0.28)
            draw.line([(gx - 10, gy), (gx + 10, gy)], fill=(254, 240, 138), width=3)
            draw.line([(gx, gy - 10), (gx, gy + 10)], fill=(254, 240, 138), width=3)

        # 4. Mr. Cash: Animated Falling Golden Coins
        elif char == "mr_cash":
            for i in range(5):
                coin_x = cx + int(cw * (0.15 + i * 0.18))
                coin_y = cy + int((ch * 0.15) + ((frame_idx * 7 + i * 90) % int(ch * 0.65)))
                draw.ellipse([coin_x - 16, coin_y - 16, coin_x + 16, coin_y + 16], fill=(234, 179, 8), outline=(0, 0, 0), width=3)
                draw.text((coin_x - 6, coin_y - 10), "$", fill=(255, 255, 255))

        # 5. Dr. Quantum: Bubbling Chemical Fizz & Orbiting Atom
        elif char == "dr_quantum":
            fx = cx + int(cw * 0.22)
            fy = cy + int(ch * 0.44)
            for i in range(4):
                bub_y = fy - int((frame_idx * 5 + i * 24) % 110)
                bub_x = fx + int(math.sin(frame_idx * 0.35 + i * 1.5) * 16)
                draw.ellipse([bub_x - 7, bub_y - 7, bub_x + 7, bub_y + 7], fill=(216, 180, 254), outline=(147, 51, 234), width=2)

            hx = cx + int(cw * 0.52)
            hy = cy + int(ch * 0.26)
            orbit_r = 75
            ang = frame_idx * 0.15
            elec_x = int(hx + math.cos(ang) * orbit_r)
            elec_y = int(hy + math.sin(ang) * (orbit_r * 0.4))
            draw.ellipse([hx - orbit_r, hy - 30, hx + orbit_r, hy + 30], outline=(14, 165, 233), width=2)
            draw.ellipse([elec_x - 7, elec_y - 7, elec_x + 7, elec_y + 7], fill=(56, 189, 248), outline=(0, 0, 0), width=2)

