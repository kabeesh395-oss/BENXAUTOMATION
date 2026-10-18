"""Original Procedural Funny Stickman Animation Engine for BENXAUTOMATION.

Features:
- Dual-character procedural rigging:
  * BEN: Energetic prankster with signature cyan/blue cap and expressive face.
  * MAX: Serious analytical straight man with nerd glasses and bow tie.
- Skeletal kinematics with continuous motion cycles (walk, run, jump, slip, crash, celebrate).
- Expressive facial rigs: happy, shocked, smirk, dizzy spirals (@_@), deadpan, wink.
- Slapstick comedy physics: squash & stretch, velocity anticipation, impact starbursts, smoke puffs.
- High-efficiency rawvideo FFmpeg pipeline rendering at 24fps (1080x1920 9:16 Shorts and 1920x1080 16:9).
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

log = logging.getLogger(__name__)

# Core Palette
COLOR_BEN_CAP = (0, 242, 254, 255)       # Cyber Teal
COLOR_BEN_ACCENT = (79, 172, 254, 255)    # Electric Blue
COLOR_MAX_GLASSES = (255, 180, 0, 255)    # Amber Gold
COLOR_MAX_TIE = (255, 65, 108, 255)       # Coral Red
COLOR_LINE_DARK = (15, 23, 42, 255)       # Deep Obsidian
COLOR_LINE_WHITE = (248, 250, 252, 255)   # Off-white for dark backgrounds
COLOR_SKIN = (255, 255, 255, 255)
COLOR_BANANA = (255, 225, 53, 255)
COLOR_STAR = (255, 215, 0, 255)


@dataclass
class LimbAngles:
    """Joint angles in degrees."""
    left_shoulder: float = 20.0
    left_elbow: float = 30.0
    right_shoulder: float = -20.0
    right_elbow: float = -30.0
    left_hip: float = 15.0
    left_knee: float = 10.0
    right_hip: float = -15.0
    right_knee: float = -10.0
    spine_tilt: float = 0.0
    head_tilt: float = 0.0


@dataclass
class StickmanPose:
    """Full body skeletal pose definition."""
    x: float = 0.0              # X offset from anchor
    y: float = 0.0              # Y offset from anchor
    scale: float = 1.0          # Character scale
    squash_x: float = 1.0       # Horizontal squash/stretch
    squash_y: float = 1.0       # Vertical squash/stretch
    rotation: float = 0.0       # Whole-body rotation in degrees
    limbs: LimbAngles = field(default_factory=LimbAngles)
    expression: str = "happy"    # happy, shocked, smirk, dizzy, deadpan, wink, angry
    mouth: str = "rest"         # rest, open, wide, o, grin
    flip_x: bool = False        # Face left vs right
    prop: Optional[str] = None  # banana, bomb, sign, gadget, none


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_in_out(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def ease_out_bounce(t: float) -> float:
    if t < (1 / 2.75):
        return 7.5625 * t * t
    elif t < (2 / 2.75):
        t -= (1.5 / 2.75)
        return 7.5625 * t * t + 0.75
    elif t < (2.5 / 2.75):
        t -= (2.25 / 2.75)
        return 7.5625 * t * t + 0.9375
    else:
        t -= (2.625 / 2.75)
        return 7.5625 * t * t + 0.984375


class StickmanRig:
    """Renders a procedural 2D stickman character with custom styling and expressions."""

    def __init__(self, character: str = "BEN") -> None:
        self.character = character.upper()
        self.stroke_width = 10
        self.head_radius = 55
        self.torso_length = 130
        self.upper_arm_length = 65
        self.forearm_length = 60
        self.thigh_length = 75
        self.shin_length = 70

    def interpolate_pose(self, pose_a: StickmanPose, pose_b: StickmanPose, t: float) -> StickmanPose:
        """Smoothly interpolate between two poses with ease-in-out."""
        te = ease_in_out(max(0.0, min(1.0, t)))
        la = pose_a.limbs
        lb = pose_b.limbs

        limbs = LimbAngles(
            left_shoulder=lerp(la.left_shoulder, lb.left_shoulder, te),
            left_elbow=lerp(la.left_elbow, lb.left_elbow, te),
            right_shoulder=lerp(la.right_shoulder, lb.right_shoulder, te),
            right_elbow=lerp(la.right_elbow, lb.right_elbow, te),
            left_hip=lerp(la.left_hip, lb.left_hip, te),
            left_knee=lerp(la.left_knee, lb.left_knee, te),
            right_hip=lerp(la.right_hip, lb.right_hip, te),
            right_knee=lerp(la.right_knee, lb.right_knee, te),
            spine_tilt=lerp(la.spine_tilt, lb.spine_tilt, te),
            head_tilt=lerp(la.head_tilt, lb.head_tilt, te),
        )

        return StickmanPose(
            x=lerp(pose_a.x, pose_b.x, te),
            y=lerp(pose_a.y, pose_b.y, te),
            scale=lerp(pose_a.scale, pose_b.scale, te),
            squash_x=lerp(pose_a.squash_x, pose_b.squash_x, te),
            squash_y=lerp(pose_a.squash_y, pose_b.squash_y, te),
            rotation=lerp(pose_a.rotation, pose_b.rotation, te),
            limbs=limbs,
            expression=pose_b.expression if t >= 0.5 else pose_a.expression,
            mouth=pose_b.mouth if t >= 0.5 else pose_a.mouth,
            flip_x=pose_b.flip_x if t >= 0.5 else pose_a.flip_x,
            prop=pose_b.prop if t >= 0.5 else pose_a.prop,
        )

    def get_walk_cycle_pose(self, phase: float, speed_mult: float = 1.0) -> StickmanPose:
        """Deterministic walk cycle with continuous leg movement and arm counter-swing."""
        p = (phase * speed_mult) % (2.0 * math.pi)
        bob = abs(math.sin(p)) * 14.0
        spine = math.sin(p) * 4.0

        # Sine wave leg swings (anti-phase)
        l_hip = math.sin(p) * 36.0
        r_hip = -math.sin(p) * 36.0
        # Knee bends more when leg moves backward
        l_knee = max(0.0, math.sin(p - 0.5)) * 42.0
        r_knee = max(0.0, math.sin(p + math.pi - 0.5)) * 42.0

        # Arm counter-swing
        l_sh = -math.sin(p) * 30.0
        r_sh = math.sin(p) * 30.0
        l_el = 25.0 + math.sin(p) * 15.0
        r_el = 25.0 - math.sin(p) * 15.0

        limbs = LimbAngles(
            left_shoulder=l_sh,
            left_elbow=l_el,
            right_shoulder=r_sh,
            right_elbow=r_el,
            left_hip=l_hip,
            left_knee=l_knee,
            right_hip=r_hip,
            right_knee=r_knee,
            spine_tilt=spine,
            head_tilt=spine * 0.5,
        )
        return StickmanPose(
            x=0.0,
            y=-bob,
            limbs=limbs,
            expression="happy",
            mouth="rest",
        )

    def get_run_cycle_pose(self, phase: float) -> StickmanPose:
        """Fast energetic run cycle with high knee lifts, forward lean, and arm pump."""
        p = (phase * 2.5) % (2.0 * math.pi)
        bob = abs(math.sin(p)) * 22.0
        forward_lean = 18.0

        l_hip = math.sin(p) * 55.0
        r_hip = -math.sin(p) * 55.0
        l_knee = max(5.0, math.sin(p - 0.4)) * 68.0
        r_knee = max(5.0, math.sin(p + math.pi - 0.4)) * 68.0

        l_sh = -math.sin(p) * 60.0
        r_sh = math.sin(p) * 60.0
        l_el = 50.0 + math.sin(p) * 35.0
        r_el = 50.0 - math.sin(p) * 35.0

        limbs = LimbAngles(
            left_shoulder=l_sh,
            left_elbow=l_el,
            right_shoulder=r_sh,
            right_elbow=r_el,
            left_hip=l_hip,
            left_knee=l_knee,
            right_hip=r_hip,
            right_knee=r_knee,
            spine_tilt=forward_lean,
            head_tilt=forward_lean * 0.4,
        )
        return StickmanPose(
            x=0.0,
            y=-bob,
            squash_x=1.05,
            squash_y=0.95,
            limbs=limbs,
            expression="smirk",
            mouth="wide",
        )

    def get_slip_fall_pose(self, progress: float) -> StickmanPose:
        """Comedy slapstick slip-and-fall physics (0.0=anticipate, 0.4=horizontal air hang, 1.0=ground splat)."""
        t = max(0.0, min(1.0, progress))

        if t < 0.25:
            # Stage 1: Foot slips forward, torso violently pitches back
            sub = t / 0.25
            limbs = LimbAngles(
                left_shoulder=-80.0 * sub,
                left_elbow=-40.0 * sub,
                right_shoulder=70.0 * sub,
                right_elbow=40.0 * sub,
                left_hip=-75.0 * sub,
                left_knee=15.0 * sub,
                right_hip=-60.0 * sub,
                right_knee=25.0 * sub,
                spine_tilt=-35.0 * sub,
                head_tilt=-20.0 * sub,
            )
            return StickmanPose(
                x=40.0 * sub,
                y=-15.0 * sub,
                rotation=-25.0 * sub,
                limbs=limbs,
                expression="shocked",
                mouth="o",
            )
        elif t < 0.65:
            # Stage 2: Airborne horizontal hang (cartoon gravity pause)
            sub = (t - 0.25) / 0.4
            rot = -25.0 - 55.0 * sub  # Flips backwards horizontally
            limbs = LimbAngles(
                left_shoulder=-110.0,
                left_elbow=-60.0,
                right_shoulder=-95.0,
                right_elbow=-50.0,
                left_hip=-70.0,
                left_knee=45.0,
                right_hip=-85.0,
                right_knee=30.0,
                spine_tilt=-10.0,
                head_tilt=-15.0,
            )
            return StickmanPose(
                x=40.0 + 30.0 * sub,
                y=-15.0 - math.sin(sub * math.pi) * 60.0,  # Arc in air
                rotation=rot,
                limbs=limbs,
                expression="shocked",
                mouth="wide",
            )
        else:
            # Stage 3: Ground splat with cartoon squash
            sub = (t - 0.65) / 0.35
            squash = 1.0 + (1.0 - sub) * 0.4
            stretch = 1.0 - (1.0 - sub) * 0.35
            limbs = LimbAngles(
                left_shoulder=-140.0,
                left_elbow=-20.0,
                right_shoulder=140.0,
                right_elbow=20.0,
                left_hip=-90.0,
                left_knee=10.0,
                right_hip=90.0,
                right_knee=10.0,
                spine_tilt=0.0,
                head_tilt=0.0,
            )
            return StickmanPose(
                x=70.0,
                y=120.0,
                rotation=-90.0,
                squash_x=squash,
                squash_y=stretch,
                limbs=limbs,
                expression="dizzy",
                mouth="open",
            )

    def draw_character(
        self,
        canvas: Image.Image,
        anchor_x: float,
        anchor_y: float,
        pose: StickmanPose,
        line_color: Tuple[int, int, int, int] = COLOR_LINE_DARK,
    ) -> None:
        """Render the complete stickman rig at the target anchor position."""
        draw = ImageDraw.Draw(canvas)

        # Apply squash & stretch and overall position
        x0 = anchor_x + pose.x
        y0 = anchor_y + pose.y
        scale = pose.scale
        sw = int(self.stroke_width * scale)

        # Base skeletal coordinates relative to hip (0,0)
        hip_x, hip_y = x0, y0

        # Spine & Neck
        spine_rad = math.radians(pose.limbs.spine_tilt + pose.rotation)
        neck_x = hip_x + math.sin(spine_rad) * (self.torso_length * scale * pose.squash_y)
        neck_y = hip_y - math.cos(spine_rad) * (self.torso_length * scale * pose.squash_y)

        # Draw Torso line
        draw.line([(hip_x, hip_y), (neck_x, neck_y)], fill=line_color, width=sw + 2)

        # Head position
        head_rad = math.radians(pose.limbs.head_tilt + pose.rotation)
        hr = int(self.head_radius * scale)
        head_cx = neck_x + math.sin(head_rad) * (hr * 1.3)
        head_cy = neck_y - math.cos(head_rad) * (hr * 1.3)

        # Legs (Hips to Knees to Feet)
        self._draw_leg(
            draw, hip_x, hip_y, pose.limbs.left_hip, pose.limbs.left_knee,
            pose.rotation, scale, sw, line_color, is_left=True,
        )
        self._draw_leg(
            draw, hip_x, hip_y, pose.limbs.right_hip, pose.limbs.right_knee,
            pose.rotation, scale, sw, line_color, is_left=False,
        )

        # Arms (Neck to Shoulders to Elbows to Hands)
        hand_l = self._draw_arm(
            draw, neck_x, neck_y, pose.limbs.left_shoulder, pose.limbs.left_elbow,
            pose.rotation, scale, sw, line_color, is_left=True,
        )
        hand_r = self._draw_arm(
            draw, neck_x, neck_y, pose.limbs.right_shoulder, pose.limbs.right_elbow,
            pose.rotation, scale, sw, line_color, is_left=False,
        )

        # Head Circle & Face
        self._draw_head(draw, head_cx, head_cy, hr, pose, line_color)

        # Character Accessories (BEN Cap / MAX Glasses & Tie)
        if self.character == "BEN":
            self._draw_ben_cap(draw, head_cx, head_cy, hr, pose)
        else:
            self._draw_max_accessories(draw, head_cx, head_cy, hr, neck_x, neck_y, pose)

        # Optional Prop held in right hand or ground
        if pose.prop:
            self._draw_prop(draw, hand_r[0], hand_r[1], pose.prop, scale)

        # Dizzy stars if dizzy
        if pose.expression == "dizzy":
            self._draw_dizzy_stars(draw, head_cx, head_cy - hr * 1.4, hr)

    def _draw_leg(
        self,
        draw: ImageDraw.ImageDraw,
        hx: float,
        hy: float,
        hip_deg: float,
        knee_deg: float,
        body_rot: float,
        scale: float,
        sw: int,
        line_color: Tuple[int, int, int, int],
        is_left: bool,
    ) -> Tuple[float, float]:
        thigh_len = self.thigh_length * scale
        shin_len = self.shin_length * scale

        hip_rad = math.radians(hip_deg + body_rot)
        knee_x = hx + math.sin(hip_rad) * thigh_len
        knee_y = hy + math.cos(hip_rad) * thigh_len

        shin_rad = math.radians(hip_deg + knee_deg + body_rot)
        foot_x = knee_x + math.sin(shin_rad) * shin_len
        foot_y = knee_y + math.cos(shin_rad) * shin_len

        # Thigh & Shin
        draw.line([(hx, hy), (knee_x, knee_y)], fill=line_color, width=sw)
        draw.line([(knee_x, knee_y), (foot_x, foot_y)], fill=line_color, width=sw)

        # Foot shoe tip
        foot_dir = 1.0 if is_left else 1.2
        foot_tip_x = foot_x + (18 * scale * foot_dir)
        draw.line([(foot_x, foot_y), (foot_tip_x, foot_y + 2)], fill=line_color, width=sw)
        return (foot_x, foot_y)

    def _draw_arm(
        self,
        draw: ImageDraw.ImageDraw,
        nx: float,
        ny: float,
        sh_deg: float,
        el_deg: float,
        body_rot: float,
        scale: float,
        sw: int,
        line_color: Tuple[int, int, int, int],
        is_left: bool,
    ) -> Tuple[float, float]:
        uarm_len = self.upper_arm_length * scale
        farm_len = self.forearm_length * scale

        sh_rad = math.radians(sh_deg + body_rot + (180.0 if not is_left else 0.0))
        el_x = nx + math.sin(sh_rad) * uarm_len
        el_y = ny + math.cos(sh_rad) * uarm_len

        el_rad = math.radians(sh_deg + el_deg + body_rot + (180.0 if not is_left else 0.0))
        hand_x = el_x + math.sin(el_rad) * farm_len
        hand_y = el_y + math.cos(el_rad) * farm_len

        draw.line([(nx, ny), (el_x, el_y)], fill=line_color, width=sw)
        draw.line([(el_x, el_y), (hand_x, hand_y)], fill=line_color, width=sw)

        # Hand circle
        hr = int(8 * scale)
        draw.ellipse([(hand_x - hr, hand_y - hr), (hand_x + hr, hand_y + hr)], fill=line_color)
        return (hand_x, hand_y)

    def _draw_head(
        self,
        draw: ImageDraw.ImageDraw,
        cx: float,
        cy: float,
        radius: int,
        pose: StickmanPose,
        line_color: Tuple[int, int, int, int],
    ) -> None:
        sw = int(self.stroke_width * pose.scale)
        # Head background fill (solid white/light skin for high contrast on dark)
        draw.ellipse(
            [(cx - radius, cy - radius), (cx + radius, cy + radius)],
            fill=COLOR_SKIN,
            outline=line_color,
            width=sw,
        )

        # Facial expressions
        eye_y = cy - int(radius * 0.15)
        eye_spacing = int(radius * 0.35)
        lx = cx - eye_spacing
        rx = cx + eye_spacing

        if pose.expression == "happy":
            # Happy curved arc eyes (^_^)
            draw.arc([(lx - 12, eye_y - 12), (lx + 12, eye_y + 12)], start=190, end=350, fill=COLOR_LINE_DARK, width=4)
            draw.arc([(rx - 12, eye_y - 12), (rx + 12, eye_y + 12)], start=190, end=350, fill=COLOR_LINE_DARK, width=4)
        elif pose.expression == "shocked":
            # Big wide round cartoon eyes (O_O)
            draw.ellipse([(lx - 14, eye_y - 18), (lx + 14, eye_y + 18)], fill=COLOR_SKIN, outline=COLOR_LINE_DARK, width=4)
            draw.ellipse([(rx - 14, eye_y - 18), (rx + 14, eye_y + 18)], fill=COLOR_SKIN, outline=COLOR_LINE_DARK, width=4)
            # Tiny pupils centered
            draw.ellipse([(lx - 4, eye_y - 4), (lx + 4, eye_y + 4)], fill=COLOR_LINE_DARK)
            draw.ellipse([(rx - 4, eye_y - 4), (rx + 4, eye_y + 4)], fill=COLOR_LINE_DARK)
        elif pose.expression == "dizzy":
            # Spiral knocked-out eyes (@_@)
            self._draw_spiral(draw, lx, eye_y, 14, COLOR_LINE_DARK)
            self._draw_spiral(draw, rx, eye_y, 14, COLOR_LINE_DARK)
        elif pose.expression == "smirk":
            # Confident mischievous eyes (one curved, one raised)
            draw.arc([(lx - 12, eye_y - 12), (lx + 12, eye_y + 12)], start=190, end=350, fill=COLOR_LINE_DARK, width=4)
            draw.ellipse([(rx - 10, eye_y - 10), (rx + 10, eye_y + 10)], fill=COLOR_LINE_DARK)
            # Cocked eyebrow
            draw.line([(rx - 12, eye_y - 18), (rx + 14, eye_y - 24)], fill=COLOR_LINE_DARK, width=4)
        elif pose.expression == "rage":
            # Furrowed angry diagonal rage eyebrows with sharp eyes
            draw.line([(lx - 16, eye_y - 12), (lx + 10, eye_y + 4)], fill=COLOR_LINE_DARK, width=6)
            draw.line([(rx + 16, eye_y - 12), (rx - 10, eye_y + 4)], fill=COLOR_LINE_DARK, width=6)
            draw.ellipse([(lx - 6, eye_y + 2), (lx + 6, eye_y + 14)], fill=COLOR_LINE_DARK)
            draw.ellipse([(rx - 6, eye_y + 2), (rx + 6, eye_y + 14)], fill=COLOR_LINE_DARK)
            # Red throbbing anger vein '#' on forehead
            draw.line([(cx + int(radius * 0.4), cy - int(radius * 0.7)), (cx + int(radius * 0.7), cy - int(radius * 0.7))], fill=(239, 68, 68, 255), width=3)
            draw.line([(cx + int(radius * 0.4), cy - int(radius * 0.5)), (cx + int(radius * 0.7), cy - int(radius * 0.5))], fill=(239, 68, 68, 255), width=3)
            draw.line([(cx + int(radius * 0.5), cy - int(radius * 0.8)), (cx + int(radius * 0.5), cy - int(radius * 0.4))], fill=(239, 68, 68, 255), width=3)
            draw.line([(cx + int(radius * 0.6), cy - int(radius * 0.8)), (cx + int(radius * 0.6), cy - int(radius * 0.4))], fill=(239, 68, 68, 255), width=3)
        elif pose.expression == "panic":
            # Wide vibrating eyes with big cartoon blue sweat drop
            draw.ellipse([(lx - 12, eye_y - 14), (lx + 12, eye_y + 14)], fill=COLOR_SKIN, outline=COLOR_LINE_DARK, width=4)
            draw.ellipse([(rx - 12, eye_y - 14), (rx + 12, eye_y + 14)], fill=COLOR_SKIN, outline=COLOR_LINE_DARK, width=4)
            draw.ellipse([(lx - 3, eye_y - 3), (lx + 3, eye_y + 3)], fill=COLOR_LINE_DARK)
            draw.ellipse([(rx - 3, eye_y - 3), (rx + 3, eye_y + 3)], fill=COLOR_LINE_DARK)
            # Big cartoon teardrop sweat drop running down temple
            sw_x, sw_y = cx + int(radius * 0.8), cy - int(radius * 0.2)
            draw.polygon([(sw_x, sw_y - 14), (sw_x - 8, sw_y + 6), (sw_x + 8, sw_y + 6)], fill=(56, 189, 248, 255))
            draw.ellipse([(sw_x - 8, sw_y), (sw_x + 8, sw_y + 12)], fill=(56, 189, 248, 255))
        elif pose.expression == "sleepy":
            # Half-closed curved droopy lines (-.-)
            draw.line([(lx - 14, eye_y + 2), (lx + 14, eye_y - 2)], fill=COLOR_LINE_DARK, width=4)
            draw.line([(rx - 14, eye_y - 2), (rx + 14, eye_y + 2)], fill=COLOR_LINE_DARK, width=4)
            # Floating comic Zzz
            draw.text((cx + int(radius * 0.8), cy - int(radius * 1.1)), "Zzz", fill=(99, 102, 241, 255))
        elif pose.expression == "deadpan":
            # Flat unimpressed horizontal line eyes (-_-)
            draw.line([(lx - 14, eye_y), (lx + 14, eye_y)], fill=COLOR_LINE_DARK, width=5)
            draw.line([(rx - 14, eye_y), (rx + 14, eye_y)], fill=COLOR_LINE_DARK, width=5)
        else:
            # Standard friendly dot eyes
            draw.ellipse([(lx - 6, eye_y - 6), (lx + 6, eye_y + 6)], fill=COLOR_LINE_DARK)
            draw.ellipse([(rx - 6, eye_y - 6), (rx + 6, eye_y + 6)], fill=COLOR_LINE_DARK)

        # Mouth rendering
        mouth_y = cy + int(radius * 0.35)
        if pose.mouth == "grit":
            # Clenched teeth grid rectangle [|||||]
            mw, mh = 36, 16
            draw.rectangle([(cx - mw // 2, mouth_y - mh // 2), (cx + mw // 2, mouth_y + mh // 2)], fill=COLOR_SKIN, outline=COLOR_LINE_DARK, width=4)
            draw.line([(cx - mw // 2, mouth_y), (cx + mw // 2, mouth_y)], fill=COLOR_LINE_DARK, width=2)
            for x_div in range(int(cx - mw // 2 + 7), int(cx + mw // 2), 7):
                draw.line([(x_div, mouth_y - mh // 2), (x_div, mouth_y + mh // 2)], fill=COLOR_LINE_DARK, width=2)
        elif pose.mouth == "scream":
            # Giant cartoon gaping scream oval
            draw.ellipse([(cx - 18, mouth_y - 12), (cx + 18, mouth_y + 28)], fill=COLOR_LINE_DARK)
            draw.chord([(cx - 12, mouth_y + 8), (cx + 12, mouth_y + 26)], start=0, end=180, fill=COLOR_MAX_TIE)
        elif pose.mouth == "wide":
            # Big open D-shape smile :D
            draw.chord([(cx - 24, mouth_y - 10), (cx + 24, mouth_y + 26)], start=0, end=180, fill=COLOR_LINE_DARK)
            # Tongue
            draw.chord([(cx - 14, mouth_y + 8), (cx + 14, mouth_y + 24)], start=0, end=180, fill=COLOR_MAX_TIE)
        elif pose.mouth == "open":
            # Talking / shocked oval mouth :O
            draw.ellipse([(cx - 12, mouth_y - 8), (cx + 12, mouth_y + 16)], fill=COLOR_LINE_DARK)
        elif pose.mouth == "o":
            draw.ellipse([(cx - 10, mouth_y - 10), (cx + 10, mouth_y + 10)], outline=COLOR_LINE_DARK, width=4)
        elif pose.mouth == "grin":
            draw.arc([(cx - 22, mouth_y - 12), (cx + 22, mouth_y + 16)], start=20, end=160, fill=COLOR_LINE_DARK, width=5)
        else:
            # Friendly resting smile
            draw.arc([(cx - 16, mouth_y - 8), (cx + 16, mouth_y + 12)], start=20, end=160, fill=COLOR_LINE_DARK, width=4)

    def _draw_ben_cap(
        self,
        draw: ImageDraw.ImageDraw,
        cx: float,
        cy: float,
        radius: int,
        pose: StickmanPose,
    ) -> None:
        """BEN's signature backwards neon cyan cap."""
        cap_y = cy - int(radius * 0.55)
        # Cap dome on top of head
        draw.chord(
            [(cx - radius - 2, cap_y - int(radius * 0.55)), (cx + radius + 2, cap_y + int(radius * 0.45))],
            start=180,
            end=360,
            fill=COLOR_BEN_CAP,
            outline=COLOR_LINE_DARK,
            width=3,
        )
        # Backwards cap visor bill sticking out to the left
        bill_pts = [
            (cx - radius - 1, cap_y + 2),
            (cx - radius - 30, cap_y - 12),
            (cx - radius - 22, cap_y - 2),
            (cx - radius + 5, cap_y + 6),
        ]
        draw.polygon(bill_pts, fill=COLOR_BEN_ACCENT, outline=COLOR_LINE_DARK)

    def _draw_max_accessories(
        self,
        draw: ImageDraw.ImageDraw,
        cx: float,
        cy: float,
        radius: int,
        neck_x: float,
        neck_y: float,
        pose: StickmanPose,
    ) -> None:
        """MAX's signature rectangular gold glasses and red bow tie."""
        eye_y = cy - int(radius * 0.15)
        eye_spacing = int(radius * 0.35)
        gw, gh = 28, 20

        # Glasses Left Frame & Right Frame
        draw.rectangle([(cx - eye_spacing - gw // 2, eye_y - gh // 2), (cx - eye_spacing + gw // 2, eye_y + gh // 2)], outline=COLOR_MAX_GLASSES, width=4)
        draw.rectangle([(cx + eye_spacing - gw // 2, eye_y - gh // 2), (cx + eye_spacing + gw // 2, eye_y + gh // 2)], outline=COLOR_MAX_GLASSES, width=4)
        # Bridge
        draw.line([(cx - eye_spacing + gw // 2, eye_y), (cx + eye_spacing - gw // 2, eye_y)], fill=COLOR_MAX_GLASSES, width=4)

        # Red Bow Tie at neck
        bt_pts = [
            (neck_x - 18, neck_y - 10),
            (neck_x, neck_y),
            (neck_x - 18, neck_y + 10),
        ]
        draw.polygon(bt_pts, fill=COLOR_MAX_TIE)
        bt_pts_r = [
            (neck_x + 18, neck_y - 10),
            (neck_x, neck_y),
            (neck_x + 18, neck_y + 10),
        ]
        draw.polygon(bt_pts_r, fill=COLOR_MAX_TIE)
        draw.ellipse([(neck_x - 5, neck_y - 5), (neck_x + 5, neck_y + 5)], fill=COLOR_LINE_DARK)

    def _draw_spiral(self, draw: ImageDraw.ImageDraw, x: float, y: float, max_r: float, color: Tuple[int, int, int, int]) -> None:
        pts = []
        for a in np.linspace(0, 4 * math.pi, 30):
            r = (a / (4 * math.pi)) * max_r
            px = x + math.cos(a) * r
            py = y + math.sin(a) * r
            pts.append((px, py))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=color, width=3)

    def _draw_dizzy_stars(self, draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float) -> None:
        # Ring of yellow cartoon stars circling head
        for i in range(4):
            angle = (i * math.pi / 2.0)
            sx = cx + math.cos(angle) * (radius * 0.9)
            sy = cy + math.sin(angle) * (radius * 0.4)
            draw.ellipse([(sx - 6, sy - 6), (sx + 6, sy + 6)], fill=COLOR_STAR)

    def _draw_prop(self, draw: ImageDraw.ImageDraw, x: float, y: float, prop: str, scale: float) -> None:
        if prop == "banana":
            # Banana peel with yellow curves
            draw.arc([(x - 25, y - 20), (x + 25, y + 20)], start=30, end=160, fill=COLOR_BANANA, width=10)
            draw.polygon([(x - 20, y + 10), (x - 30, y + 22), (x - 12, y + 15)], fill=COLOR_BANANA)
            draw.polygon([(x + 20, y + 10), (x + 30, y + 22), (x + 12, y + 15)], fill=COLOR_BANANA)
        elif prop == "gadget":
            # Futuristic glowing high-tech gizmo
            draw.rectangle([(x - 20, y - 16), (x + 20, y + 16)], fill=(30, 41, 59, 255), outline=COLOR_BEN_CAP, width=3)
            draw.ellipse([(x - 8, y - 8), (x + 8, y + 8)], fill=COLOR_BEN_CAP)
            draw.line([(x, y - 16), (x, y - 30)], fill=COLOR_BEN_CAP, width=3)
            draw.ellipse([(x - 4, y - 34), (x + 4, y - 26)], fill=COLOR_MAX_TIE)
        elif prop == "coffee_mug":
            # White ceramic mug with steam curls
            draw.rectangle([(x - 14, y - 16), (x + 14, y + 16)], fill=(255, 255, 255, 255), outline=COLOR_LINE_DARK, width=3)
            draw.arc([(x + 10, y - 10), (x + 24, y + 10)], start=270, end=90, fill=COLOR_LINE_DARK, width=3)
            # Rising comic steam curls
            draw.arc([(x - 8, y - 32), (x, y - 18)], start=180, end=360, fill=(148, 163, 184, 255), width=2)
            draw.arc([(x + 2, y - 36), (x + 10, y - 20)], start=180, end=360, fill=(148, 163, 184, 255), width=2)
        elif prop == "alarm_clock":
            # Retro red alarm clock with twin bells
            draw.ellipse([(x - 18, y - 18), (x + 18, y + 18)], fill=(239, 68, 68, 255), outline=COLOR_LINE_DARK, width=3)
            draw.ellipse([(x - 14, y - 26), (x - 6, y - 18)], fill=(203, 213, 225, 255), outline=COLOR_LINE_DARK, width=2)
            draw.ellipse([(x + 6, y - 26), (x + 14, y - 18)], fill=(203, 213, 225, 255), outline=COLOR_LINE_DARK, width=2)
            # Clock hands pointing at 6 AM
            draw.line([(x, y), (x, y - 10)], fill=COLOR_LINE_DARK, width=2)
            draw.line([(x, y), (x + 6, y)], fill=COLOR_LINE_DARK, width=2)
            # Ringing vibration waves
            draw.arc([(x - 28, y - 24), (x - 20, y + 4)], start=120, end=240, fill=COLOR_LINE_DARK, width=2)
            draw.arc([(x + 20, y - 24), (x + 28, y + 4)], start=300, end=60, fill=COLOR_LINE_DARK, width=2)
        elif prop == "dumbbell":
            # Heavy black cartoon barbell
            draw.line([(x - 26, y), (x + 26, y)], fill=COLOR_LINE_DARK, width=5)
            draw.rectangle([(x - 30, y - 16), (x - 22, y + 16)], fill=(30, 41, 59, 255), outline=COLOR_LINE_DARK, width=2)
            draw.rectangle([(x + 22, y - 16), (x + 30, y + 16)], fill=(30, 41, 59, 255), outline=COLOR_LINE_DARK, width=2)
        elif prop == "phone":
            # Sleek smartphone with glowing message
            draw.rectangle([(x - 10, y - 20), (x + 10, y + 20)], fill=(30, 41, 59, 255), outline=COLOR_LINE_DARK, width=2)
            draw.rectangle([(x - 8, y - 16), (x + 8, y + 14)], fill=(56, 189, 248, 255))
        elif prop == "frying_pan":
            # Black cast-iron pan with long handle
            draw.ellipse([(x - 18, y - 10), (x + 18, y + 10)], fill=(30, 41, 59, 255), outline=COLOR_LINE_DARK, width=3)
            draw.line([(x + 16, y), (x + 38, y - 12)], fill=COLOR_LINE_DARK, width=6)


@dataclass
class ComedyScene:
    """Scene definition for the Funny Stickman Story Engine."""
    scene_id: str
    duration_seconds: float
    title: str
    narration: str
    ben_action: str             # walk, run, slip, air_hang, splat, shrug, dance, idle, rage, panic, sleepy, celebrate
    max_action: str             # watch, shock, facepalm, pointing, panic, idle, laugh
    sfx_cue: Optional[str] = None  # whoosh, boing, splat, explosion, record_scratch
    punchline_sub: str = ""
    backdrop_theme: str = "studio_dark"
    camera_pan_x: float = 0.0
    ben_prop: Optional[str] = None
    max_prop: Optional[str] = None


class StickmanAnimationEngine:
    """Renders full animated Stickman comedy scenes to high-quality MP4 using FFmpeg."""

    def __init__(
        self,
        width: int = 1080,
        height: int = 1920,
        fps: int = 24,
        ffmpeg_path: str = "ffmpeg",
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.ffmpeg_path = ffmpeg_path
        self.ben_rig = StickmanRig("BEN")
        self.max_rig = StickmanRig("MAX")

    def render_backdrop(self, time_sec: float, theme: str) -> Image.Image:
        """Render modern dynamic colorful backdrop suited to story location."""
        bg = Image.new("RGBA", (self.width, self.height), (255, 255, 255, 255))
        draw = ImageDraw.Draw(bg)
        floor_y = int(self.height * 0.72)

        theme_lower = (theme or "bedroom").lower()

        if "bedroom" in theme_lower:
            # 1. Bedroom: Cozy pastel lavender walls with warm wood floor
            draw.rectangle([(0, 0), (self.width, floor_y)], fill=(238, 230, 248, 255))
            draw.rectangle([(0, floor_y), (self.width, self.height)], fill=(214, 180, 142, 255))
            draw.line([(0, floor_y), (self.width, floor_y)], fill=(120, 90, 60, 255), width=5)
            # Wood planks
            for px in range(0, self.width, 140):
                draw.line([(px, floor_y), (px, self.height)], fill=(180, 145, 110, 180), width=2)

            # Morning window with sunbeam
            wx, wy, ww, wh = 100, int(self.height * 0.18), 240, 320
            draw.rectangle([(wx, wy), (wx + ww, wy + wh)], fill=(186, 230, 253, 255), outline=COLOR_LINE_DARK, width=6)
            draw.line([(wx + ww // 2, wy), (wx + ww // 2, wy + wh)], fill=COLOR_LINE_DARK, width=4)
            draw.line([(wx, wy + wh // 2), (wx + ww, wy + wh // 2)], fill=COLOR_LINE_DARK, width=4)
            # Gentle sunlight beam
            sun_poly = [(wx, wy + wh), (wx + ww, wy + wh), (wx + ww + 380, floor_y), (wx + 100, floor_y)]
            draw.polygon(sun_poly, fill=(254, 240, 138, 55))

            # Bed silhouette on left
            bx, by = 60, floor_y - 120
            draw.rectangle([(bx, by), (bx + 260, floor_y)], fill=(196, 181, 253, 255), outline=COLOR_LINE_DARK, width=4)
            draw.rectangle([(bx + 20, by - 35), (bx + 110, by)], fill=(255, 255, 255, 255), outline=COLOR_LINE_DARK, width=3)

            # Floating dust motes in sunbeam
            for i in range(16):
                dx = (wx + 80 + i * 27 + int(time_sec * 15)) % (self.width // 2)
                dy = (wy + 40 + i * 33 + int(math.sin(time_sec + i) * 20)) % floor_y
                draw.ellipse([(dx, dy), (dx + 3, dy + 3)], fill=(255, 255, 255, 180))

        elif "office" in theme_lower:
            # 2. Office: Cool pastel slate blue walls with modern office carpet
            draw.rectangle([(0, 0), (self.width, floor_y)], fill=(226, 232, 240, 255))
            draw.rectangle([(0, floor_y), (self.width, self.height)], fill=(148, 163, 184, 255))
            draw.line([(0, floor_y), (self.width, floor_y)], fill=(71, 85, 105, 255), width=5)

            # Office window with blinds
            wx, wy, ww, wh = int(self.width * 0.55), int(self.height * 0.15), 340, 360
            draw.rectangle([(wx, wy), (wx + ww, wy + wh)], fill=(199, 210, 254, 255), outline=COLOR_LINE_DARK, width=5)
            for by_line in range(wy + 25, wy + wh, 25):
                draw.line([(wx, by_line), (wx + ww, by_line)], fill=(148, 163, 184, 180), width=2)

            # Ticking wall clock on left
            ck_x, ck_y, cr = 180, int(self.height * 0.22), 55
            draw.ellipse([(ck_x - cr, ck_y - cr), (ck_x + cr, ck_y + cr)], fill=(255, 255, 255, 255), outline=COLOR_LINE_DARK, width=4)
            # Clock hands rotating slowly with time
            h_ang = (time_sec * 2.0) % (2.0 * math.pi)
            draw.line([(ck_x, ck_y), (ck_x + math.sin(h_ang) * 32, ck_y - math.cos(h_ang) * 32)], fill=COLOR_LINE_DARK, width=3)
            draw.line([(ck_x, ck_y), (ck_x + 20, ck_y)], fill=COLOR_LINE_DARK, width=4)

            # Potted plant silhouette
            px = 120
            draw.polygon([(px - 25, floor_y), (px + 25, floor_y), (px + 35, floor_y - 65), (px - 35, floor_y - 65)], fill=(180, 83, 9, 255), outline=COLOR_LINE_DARK)
            for leaf_a in [-0.8, -0.4, 0.0, 0.4, 0.8]:
                lx = px + math.sin(leaf_a) * 70
                ly = (floor_y - 65) - math.cos(leaf_a) * 60
                draw.line([(px, floor_y - 65), (lx, ly)], fill=(22, 163, 74, 255), width=8)

        elif "kitchen" in theme_lower:
            # 3. Kitchen: Warm peach / apricot walls with checkered tile floor
            draw.rectangle([(0, 0), (self.width, floor_y)], fill=(254, 237, 222, 255))
            draw.rectangle([(0, floor_y), (self.width, self.height)], fill=(241, 245, 249, 255))
            # Checkerboard tiles
            tile_w = 90
            for tx in range(0, self.width, tile_w):
                for ty in range(floor_y, self.height, tile_w):
                    if ((tx // tile_w) + (ty // tile_w)) % 2 == 0:
                        draw.rectangle([(tx, ty), (tx + tile_w, ty + tile_w)], fill=(203, 213, 225, 140))
            draw.line([(0, floor_y), (self.width, floor_y)], fill=(148, 163, 184, 255), width=5)

            # Kitchen counter on right
            cx, cy = int(self.width * 0.65), floor_y - 130
            draw.rectangle([(cx, cy), (self.width, floor_y)], fill=(254, 215, 170, 255), outline=COLOR_LINE_DARK, width=4)
            # Toaster / appliance on counter
            draw.rectangle([(cx + 40, cy - 50), (cx + 120, cy)], fill=(226, 232, 240, 255), outline=COLOR_LINE_DARK, width=3)
            # Animated comic steam
            for s in range(3):
                sy = (cy - 70 - int(time_sec * 35 + s * 25)) % 100
                draw.arc([(cx + 60 + s * 15, cy - 70 - sy), (cx + 80 + s * 15, cy - 50 - sy)], start=180, end=360, fill=(156, 163, 175, 200), width=2)

        elif "street" in theme_lower:
            # 4. Street: Pastel sky blue with pavement sidewalk & lamppost
            draw.rectangle([(0, 0), (self.width, floor_y)], fill=(186, 230, 253, 255))
            draw.rectangle([(0, floor_y), (self.width, self.height)], fill=(203, 213, 225, 255))
            draw.line([(0, floor_y), (self.width, floor_y)], fill=(100, 116, 139, 255), width=6)
            # Sidewalk slabs
            for sx in range(0, self.width, 180):
                draw.line([(sx, floor_y), (sx, self.height)], fill=(148, 163, 184, 180), width=2)

            # Fluffy comic clouds drifting across sky
            for c_idx in range(4):
                cloud_x = (c_idx * 310 + int(time_sec * 35)) % (self.width + 200) - 100
                cloud_y = int(self.height * 0.12) + (c_idx % 2) * 90
                draw.ellipse([(cloud_x, cloud_y), (cloud_x + 120, cloud_y + 60)], fill=(255, 255, 255, 230))
                draw.ellipse([(cloud_x + 40, cloud_y - 25), (cloud_x + 160, cloud_y + 45)], fill=(255, 255, 255, 230))
                draw.ellipse([(cloud_x + 100, cloud_y), (cloud_x + 210, cloud_y + 60)], fill=(255, 255, 255, 230))

            # Distant city building silhouettes
            for b_idx, bx in enumerate(range(0, self.width, 150)):
                bh = 80 + (b_idx % 3) * 60
                draw.rectangle([(bx, floor_y - bh), (bx + 110, floor_y)], fill=(148, 163, 184, 140))

            # Lamppost silhouette on right
            lx = int(self.width * 0.85)
            draw.line([(lx, floor_y), (lx, floor_y - 320)], fill=COLOR_LINE_DARK, width=6)
            draw.arc([(lx - 40, floor_y - 340), (lx + 40, floor_y - 300)], start=180, end=360, fill=(254, 240, 138, 255), outline=COLOR_LINE_DARK, width=3)

        elif "park" in theme_lower:
            # 5. Park: Soft sunny mint meadow & cartoon tree
            draw.rectangle([(0, 0), (self.width, floor_y)], fill=(207, 250, 254, 255))
            draw.rectangle([(0, floor_y), (self.width, self.height)], fill=(134, 239, 172, 255))
            draw.line([(0, floor_y), (self.width, floor_y)], fill=(34, 197, 94, 255), width=6)

            # Cartoon tree on right
            tx = int(self.width * 0.85)
            draw.rectangle([(tx - 25, floor_y - 320), (tx + 25, floor_y)], fill=(120, 90, 60, 255), outline=COLOR_LINE_DARK, width=4)
            # Foliage puffs
            draw.ellipse([(tx - 130, floor_y - 500), (tx + 130, floor_y - 280)], fill=(74, 222, 128, 255), outline=COLOR_LINE_DARK, width=4)
            draw.ellipse([(tx - 90, floor_y - 560), (tx + 90, floor_y - 380)], fill=(134, 239, 172, 255), outline=COLOR_LINE_DARK, width=4)

            # Falling comic leaves
            for l_idx in range(8):
                leaf_x = (l_idx * 140 + int(time_sec * 45)) % self.width
                leaf_y = (floor_y - 350 + int(time_sec * 30 * (l_idx + 1))) % (floor_y - 40)
                draw.ellipse([(leaf_x, leaf_y), (leaf_x + 14, leaf_y + 8)], fill=(234, 179, 8, 255))

        elif "gym" in theme_lower:
            # 6. Gym: Energetic warm amber with dark rubber gym floor
            draw.rectangle([(0, 0), (self.width, floor_y)], fill=(254, 243, 199, 255))
            draw.rectangle([(0, floor_y), (self.width, self.height)], fill=(71, 85, 105, 255))
            draw.line([(0, floor_y), (self.width, floor_y)], fill=(30, 41, 59, 255), width=6)
            # Motivational banner on wall
            draw.rectangle([(int(self.width * 0.25), int(self.height * 0.15)), (int(self.width * 0.75), int(self.height * 0.24))], fill=(239, 68, 68, 255), outline=COLOR_LINE_DARK, width=4)
            # Weight rack silhouette on left
            rx = 80
            draw.line([(rx, floor_y), (rx, floor_y - 240)], fill=COLOR_LINE_DARK, width=8)
            draw.line([(rx + 80, floor_y), (rx + 80, floor_y - 240)], fill=COLOR_LINE_DARK, width=8)
            for bar_y in range(floor_y - 200, floor_y - 40, 50):
                draw.line([(rx - 15, bar_y), (rx + 95, bar_y)], fill=COLOR_LINE_DARK, width=6)

        elif "classroom" in theme_lower:
            # 7. Classroom: Soft mint walls & giant chalkboard
            draw.rectangle([(0, 0), (self.width, floor_y)], fill=(209, 250, 229, 255))
            draw.rectangle([(0, floor_y), (self.width, self.height)], fill=(245, 208, 169, 255))
            draw.line([(0, floor_y), (self.width, floor_y)], fill=(180, 140, 90, 255), width=5)
            # Giant Chalkboard
            cb_x, cb_y, cb_w, cb_h = int(self.width * 0.15), int(self.height * 0.14), int(self.width * 0.7), 340
            draw.rectangle([(cb_x, cb_y), (cb_x + cb_w, cb_y + cb_h)], fill=(15, 81, 50, 255), outline=(120, 80, 40, 255), width=12)
            # Funny chalk formula doodle
            draw.line([(cb_x + 50, cb_y + 120), (cb_x + 130, cb_y + 120)], fill=(255, 255, 255, 220), width=3)
            draw.text((cb_x + 60, cb_y + 80), "E = mc² ? NO!", fill=(255, 255, 255, 240))
            draw.text((cb_x + 60, cb_y + 150), "SLEEP = 100%", fill=(254, 240, 138, 255))

        elif "comedy_burst" in theme_lower:
            # 8. Slapstick Punchline Sunburst
            cx, cy = self.width // 2, floor_y - 100
            num_rays = 16
            for r_idx in range(num_rays):
                ang1 = (r_idx * 2 * math.pi / num_rays) + (time_sec * 0.5)
                ang2 = ((r_idx + 0.5) * 2 * math.pi / num_rays) + (time_sec * 0.5)
                ray_r = self.height
                p1 = (cx, cy)
                p2 = (cx + math.cos(ang1) * ray_r, cy + math.sin(ang1) * ray_r)
                p3 = (cx + math.cos(ang2) * ray_r, cy + math.sin(ang2) * ray_r)
                col = (254, 240, 138, 255) if (r_idx % 2 == 0) else (254, 205, 211, 255)
                draw.polygon([p1, p2, p3], fill=col)

        else:
            # 9. Default dynamic cyber / studio stage
            draw.rectangle([(0, 0), (self.width, floor_y)], fill=(15, 23, 42, 255))
            draw.rectangle([(0, floor_y), (self.width, self.height)], fill=(30, 41, 59, 255))
            draw.line([(0, floor_y), (self.width, floor_y)], fill=(51, 65, 85, 255), width=6)
            cx = self.width // 2
            spot_cx = cx + int(math.sin(time_sec * 1.8) * (self.width * 0.22))
            for r in range(int(self.width * 0.65), 0, -45):
                alpha = int(45 * (1.0 - r / (self.width * 0.65)))
                draw.ellipse([(spot_cx - r, -80), (spot_cx + r, int(self.height * 0.82))], fill=(0, 242, 254, alpha))

        return bg

    def render_scene_frame(
        self,
        scene: ComedyScene,
        scene_time: float,
        global_time: float,
    ) -> Image.Image:
        """Render a single comedy frame featuring BEN and MAX."""
        frame = self.render_backdrop(global_time, scene.backdrop_theme)
        floor_y = float(self.height * 0.72)

        progress = max(0.0, min(1.0, scene_time / max(0.1, scene.duration_seconds)))

        # Determine BEN pose based on action
        ben_anchor_x = self.width * 0.35 + scene.camera_pan_x
        ben_anchor_y = floor_y - 60

        if scene.ben_action == "run":
            # Running across screen
            run_x = lerp(-120, self.width * 0.55, progress)
            ben_pose = self.ben_rig.get_run_cycle_pose(global_time * 5.0)
            ben_pose.x = run_x - ben_anchor_x
            ben_pose.prop = scene.ben_prop or "gadget"
        elif scene.ben_action == "walk":
            walk_x = lerp(-100, self.width * 0.20, progress)
            ben_pose = self.ben_rig.get_walk_cycle_pose(global_time * 4.0)
            ben_pose.x = walk_x - (ben_anchor_x - self.width * 0.35)
            ben_pose.prop = scene.ben_prop
        elif scene.ben_action == "slip":
            # Slapstick banana slip
            ben_pose = self.ben_rig.get_slip_fall_pose(progress)
            ben_pose.prop = scene.ben_prop or "banana"
        elif scene.ben_action == "splat":
            ben_pose = self.ben_rig.get_slip_fall_pose(1.0)
            ben_pose.expression = "dizzy"
            ben_pose.prop = scene.ben_prop
        elif scene.ben_action == "dance":
            p = global_time * 6.0
            limbs = LimbAngles(
                left_shoulder=-120.0 + math.sin(p) * 30.0,
                left_elbow=40.0,
                right_shoulder=-120.0 - math.sin(p) * 30.0,
                right_elbow=-40.0,
                left_hip=math.sin(p) * 20.0,
                right_hip=-math.sin(p) * 20.0,
                spine_tilt=math.sin(p) * 10.0,
            )
            ben_pose = StickmanPose(
                y=-abs(math.sin(p)) * 25.0,
                limbs=limbs,
                expression="happy",
                mouth="wide",
                prop=scene.ben_prop,
            )
        elif scene.ben_action == "shrug":
            limbs = LimbAngles(
                left_shoulder=85.0,
                left_elbow=60.0,
                right_shoulder=-85.0,
                right_elbow=-60.0,
                left_hip=10.0,
                right_hip=-10.0,
                head_tilt=15.0,
            )
            ben_pose = StickmanPose(limbs=limbs, expression="smirk", mouth="grin", prop=scene.ben_prop)
        elif scene.ben_action == "rage":
            p = global_time * 14.0
            shake = math.sin(p) * 8.0
            limbs = LimbAngles(
                left_shoulder=-105.0,
                left_elbow=-60.0,
                right_shoulder=-105.0,
                right_elbow=60.0,
                spine_tilt=shake,
                head_tilt=-shake,
            )
            ben_pose = StickmanPose(x=shake, limbs=limbs, expression="rage", mouth="grit", prop=scene.ben_prop)
        elif scene.ben_action == "panic":
            p = global_time * 9.0
            limbs = LimbAngles(
                left_shoulder=-125.0 + math.sin(p) * 35.0,
                left_elbow=-40.0,
                right_shoulder=-125.0 - math.sin(p) * 35.0,
                right_elbow=40.0,
                left_hip=math.sin(p) * 20.0,
                right_hip=-math.sin(p) * 20.0,
            )
            ben_pose = StickmanPose(limbs=limbs, expression="panic", mouth="scream", prop=scene.ben_prop)
        elif scene.ben_action == "sleepy":
            bob = math.sin(global_time * 1.5) * 5.0
            limbs = LimbAngles(
                left_shoulder=20.0,
                left_elbow=20.0,
                right_shoulder=-20.0,
                right_elbow=-20.0,
                spine_tilt=10.0,
                head_tilt=18.0,
            )
            ben_pose = StickmanPose(y=bob, limbs=limbs, expression="sleepy", mouth="rest", prop=scene.ben_prop)
        elif scene.ben_action == "celebrate":
            p = global_time * 5.0
            limbs = LimbAngles(
                left_shoulder=-140.0,
                left_elbow=20.0,
                right_shoulder=-140.0,
                right_elbow=-20.0,
                spine_tilt=math.sin(p) * 6.0,
            )
            ben_pose = StickmanPose(y=-abs(math.sin(p)) * 20.0, limbs=limbs, expression="happy", mouth="wide", prop=scene.ben_prop)
        else:
            # Idle gentle bounce
            bob = math.sin(global_time * 3.0) * 8.0
            ben_pose = StickmanPose(y=bob, expression="happy", mouth="rest", prop=scene.ben_prop)

        # Determine MAX pose
        max_anchor_x = self.width * 0.72 + scene.camera_pan_x
        max_anchor_y = floor_y - 60

        if scene.max_action == "shock":
            limbs = LimbAngles(
                left_shoulder=-100.0,
                left_elbow=-40.0,
                right_shoulder=-100.0,
                right_elbow=40.0,
                spine_tilt=-10.0,
                head_tilt=-15.0,
            )
            max_pose = StickmanPose(limbs=limbs, expression="shocked", mouth="o", prop=scene.max_prop)
        elif scene.max_action == "facepalm":
            # Hand over forehead, shaking head
            limbs = LimbAngles(
                left_shoulder=-135.0,
                left_elbow=-90.0,
                right_shoulder=20.0,
                right_elbow=30.0,
                spine_tilt=8.0,
                head_tilt=12.0,
            )
            max_pose = StickmanPose(limbs=limbs, expression="deadpan", mouth="rest", prop=scene.max_prop)
        elif scene.max_action == "panic":
            p = global_time * 8.0
            limbs = LimbAngles(
                left_shoulder=-120.0 + math.sin(p) * 40.0,
                left_elbow=-40.0,
                right_shoulder=-120.0 - math.sin(p) * 40.0,
                right_elbow=40.0,
                left_hip=math.sin(p) * 25.0,
                right_hip=-math.sin(p) * 25.0,
            )
            max_pose = StickmanPose(limbs=limbs, expression="shocked", mouth="wide", prop=scene.max_prop)
        elif scene.max_action == "laugh":
            p = global_time * 7.0
            limbs = LimbAngles(
                left_shoulder=40.0,
                left_elbow=60.0,
                right_shoulder=-40.0,
                right_elbow=-60.0,
                spine_tilt=-8.0 + math.sin(p) * 6.0,
                head_tilt=math.sin(p) * 8.0,
            )
            max_pose = StickmanPose(limbs=limbs, expression="happy", mouth="wide", prop=scene.max_prop)
        else:
            # Watching Ben with hands on hips
            limbs = LimbAngles(
                left_shoulder=45.0,
                left_elbow=70.0,
                right_shoulder=-45.0,
                right_elbow=-70.0,
            )
            max_pose = StickmanPose(limbs=limbs, expression="deadpan", mouth="rest", prop=scene.max_prop)

        # Render both characters
        self.ben_rig.draw_character(frame, ben_anchor_x, ben_anchor_y, ben_pose)
        self.max_rig.draw_character(frame, max_anchor_x, max_anchor_y, max_pose)

        # Draw comedy punchline / SFX visual burst if triggered
        if scene.sfx_cue and (0.2 < progress < 0.7):
            self._draw_comic_burst(frame, ben_anchor_x + ben_pose.x, ben_anchor_y + ben_pose.y - 80, scene.sfx_cue.upper())

        return frame

    def _draw_comic_burst(self, frame: Image.Image, x: float, y: float, text: str) -> None:
        """Draw dynamic comic action bubble (e.g. SPLAT!, BOING!, WHOOSH!)."""
        draw = ImageDraw.Draw(frame)
        # Comic starburst polygon
        points = []
        num_points = 12
        r_outer = 90
        r_inner = 55
        for i in range(num_points * 2):
            angle = i * math.pi / num_points
            r = r_outer if (i % 2 == 0) else r_inner
            px = x + math.cos(angle) * r
            py = y + math.sin(angle) * r
            points.append((px, py))

        draw.polygon(points, fill=COLOR_MAX_TIE, outline=COLOR_LINE_DARK)
        # Centered bold text
        try:
            font = ImageFont.truetype("arial.ttf", 26)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((x - tw // 2, y - th // 2), text, fill=(255, 255, 255, 255), font=font)

    def render_to_mp4(
        self,
        scenes: List[ComedyScene],
        output_mp4: Path,
        audio_path: Optional[Path] = None,
    ) -> Path:
        """Render all scenes into an MP4 video using FFmpeg piped rawvideo stdin."""
        output_mp4 = Path(output_mp4)
        output_mp4.parent.mkdir(parents=True, exist_ok=True)

        total_duration = sum(s.duration_seconds for s in scenes)
        total_frames = int(total_duration * self.fps)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{self.width}x{self.height}",
            "-pix_fmt", "rgba",
            "-r", str(self.fps),
            "-i", "-",
        ]

        if audio_path and Path(audio_path).is_file():
            cmd.extend(["-i", str(audio_path), "-c:a", "aac", "-b:a", "192k", "-shortest"])

        cmd.extend([
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "18",
            str(output_mp4),
        ])

        log.info("Launching FFmpeg stickman renderer: %d frames (%.1fs)", total_frames, total_duration)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        global_time = 0.0
        frame_interval = 1.0 / self.fps

        for scene in scenes:
            scene_frames = int(scene.duration_seconds * self.fps)
            for f in range(scene_frames):
                scene_time = f * frame_interval
                img = self.render_scene_frame(scene, scene_time, global_time)
                proc.stdin.write(img.tobytes())
                global_time += frame_interval

        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="replace")
        proc.wait()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg stickman render failed (code {proc.returncode}):\n{stderr[-1000:]}")

        log.info("Successfully rendered stickman video to %s", output_mp4)
        return output_mp4
