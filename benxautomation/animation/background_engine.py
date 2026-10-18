"""Dynamic 2D Vector Cartoon Background Engine.

Generates high-resolution, stylized 2D cartoon/comic backgrounds matching the
OverSimplified, Kurzgesagt, and TheOdd1sOut visual aesthetic.
Supports both YouTube Shorts (9:16 portrait) and Long-form (16:9 landscape) videos.
Themes include:
- bank_vault: Steel vault door, digital security grid, stacks of gold coins
- tech_blueprint: Deep navy technical grid, glowing cyan circuit traces, logic gates
- cyber_matrix: Dark charcoal matrix with streaming green data code and shield padlock
- quantum_lab: High-tech physics lab, blackboard equations, glowing particle chamber
- wall_street: Financial trading floor, candlestick charts, ticker tape
- command_center: Cyber war room, world map silhouette, radar sweep
- airport_station: Modern transit terminal, departure schedule board, charging kiosk
- throne_room: Medieval stone castle arches, crimson royal velvet banners, gold chandeliers
- retro_mainframe: 1970s tape drives with spinning white reels, blinking console lamps
- ben_studio: Creator studio, hexagonal acoustic foam panels, vibrant neon rim glow
- street_day / street_night: Urban skyline with cartoon skyscrapers and street lamps
- lab: Chemistry workspace with glassware and scientific shelving
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from benxautomation.logger import get_logger

log = get_logger(__name__)


class BackgroundEngine:
    """Renders authentic 2D cartoon background environments for video scenes."""

    def __init__(self, cache_dir: Path | str = "assets/backgrounds"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Image.Image] = {}

    def render_background(
        self,
        theme: str,
        canvas_size: Tuple[int, int] = (1080, 1920),
        frame_idx: int = 0,
    ) -> Image.Image:
        """Render a full-resolution 2D vector-style background frame for a scene."""
        w, h = canvas_size
        clean_theme = theme.lower().strip().replace(" ", "_").replace("-", "_")

        render_map = {
            "bank_vault": self._render_bank_vault,
            "tech_blueprint": self._render_tech_blueprint,
            "cyber_matrix": self._render_cyber_matrix,
            "quantum_lab": self._render_quantum_lab,
            "wall_street": self._render_wall_street,
            "command_center": self._render_command_center,
            "airport_station": self._render_airport_station,
            "throne_room": self._render_throne_room,
            "retro_mainframe": self._render_retro_mainframe,
            "ben_studio": self._render_ben_studio,
            "street_day": self._render_street_day,
            "street_night": self._render_street_night,
            "lab": self._render_quantum_lab,
        }

        render_func = render_map.get(clean_theme, self._render_ben_studio)
        return render_func(w, h, frame_idx)

    # ── 1. Bank Vault ────────────────────────────────────────────────
    def _render_bank_vault(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (15, 23, 42))  # Deep slate
        draw = ImageDraw.Draw(img)

        # Steel wall plates with rivet dots
        for x in range(0, w, 160):
            draw.line([(x, 0), (x, h)], fill=(30, 41, 59), width=2)
            for y in range(80, h, 160):
                draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(71, 85, 105))

        # Massive circular vault door in background
        cx, cy = w // 2, int(h * 0.42)
        r_outer = min(w, h) // 3
        draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=(51, 65, 85), outline=(0, 0, 0), width=8)
        draw.ellipse([cx - r_outer + 30, cy - r_outer + 30, cx + r_outer - 30, cy + r_outer - 30], fill=(30, 41, 59), outline=(100, 116, 139), width=5)

        # Rotating vault locking spokes
        angle_base = (frame_idx * 0.02)
        for i in range(8):
            ang = angle_base + i * (math.pi / 4)
            x2 = cx + int(math.cos(ang) * (r_outer - 40))
            y2 = cy + int(math.sin(ang) * (r_outer - 40))
            draw.line([(cx, cy), (x2, y2)], fill=(203, 213, 225), width=8)

        # Central steel hub
        draw.ellipse([cx - 45, cy - 45, cx + 45, cy + 45], fill=(226, 232, 240), outline=(0, 0, 0), width=6)

        # Gold bullion stacks at bottom corners
        floor_y = int(h * 0.78)
        draw.rectangle([0, floor_y, w, h], fill=(15, 23, 42), outline=(0, 0, 0), width=4)
        for row in range(3):
            by = floor_y + 20 + row * 35
            for col in range(4):
                bx = 40 + col * 70 + (row * 30)
                draw.rounded_rectangle([bx, by, bx + 60, by + 28], radius=4, fill=(234, 179, 8), outline=(0, 0, 0), width=3)

        return img

    # ── 2. Tech Blueprint ────────────────────────────────────────────
    def _render_tech_blueprint(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (10, 25, 47))  # Classic cyan-navy blueprint
        draw = ImageDraw.Draw(img)

        # Technical grid lines
        grid_size = 60
        for x in range(0, w, grid_size):
            draw.line([(x, 0), (x, h)], fill=(17, 45, 78), width=1)
        for y in range(0, h, grid_size):
            draw.line([(0, y), (w, y)], fill=(17, 45, 78), width=1)

        # Microchip circuit traces
        trace_color = (0, 240, 255)
        cx, cy = w // 2, int(h * 0.38)
        chip_w, chip_h = int(w * 0.45), int(w * 0.45)
        x0, y0 = cx - chip_w // 2, cy - chip_h // 2
        draw.rectangle([x0, y0, x0 + chip_w, y0 + chip_h], fill=(13, 37, 63), outline=trace_color, width=4)

        # Chip pins and branching circuit lines
        for i in range(5):
            py = y0 + 30 + i * (chip_h - 60) // 4
            # Left pins
            draw.line([(x0, py), (x0 - 50, py)], fill=trace_color, width=3)
            draw.line([(x0 - 50, py), (x0 - 90, py + (i - 2) * 25)], fill=trace_color, width=3)
            # Right pins
            draw.line([(x0 + chip_w, py), (x0 + chip_w + 50, py)], fill=trace_color, width=3)
            draw.line([(x0 + chip_w + 50, py), (x0 + chip_w + 90, py - (i - 2) * 25)], fill=trace_color, width=3)

        # Glowing CPU label
        label = "LOGIC_CORE // 0x7F"
        draw.text((cx - 85, cy - 10), label, fill=(0, 240, 255))
        return img

    # ── 3. Cyber Matrix ──────────────────────────────────────────────
    def _render_cyber_matrix(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (5, 5, 10))  # Near-black
        draw = ImageDraw.Draw(img)

        # Descending emerald code streams
        chars = ["0", "1", "<>", "[]", "{}", "FF", "404", "ROOT", "AI"]
        col_w = 40
        num_cols = w // col_w
        for c in range(num_cols):
            x = c * col_w + 10
            speed = 12 + (c % 5) * 4
            offset_y = (frame_idx * speed + c * 73) % h
            for r in range(12):
                y = (offset_y + r * 30) % h
                alpha = int(255 * (1.0 - r / 12.0))
                ch = chars[(c + r + frame_idx // 3) % len(chars)]
                color = (34, alpha, 94) if r > 0 else (187, 247, 208)
                draw.text((x, y), ch, fill=color)

        # Central Cybersecurity Shield Wireframe
        cx, cy = w // 2, int(h * 0.40)
        sw, sh = int(w * 0.35), int(w * 0.42)
        shield_pts = [
            (cx - sw // 2, cy - sh // 2),
            (cx + sw // 2, cy - sh // 2),
            (cx + sw // 2, cy + sh // 6),
            (cx, cy + sh // 2),
            (cx - sw // 2, cy + sh // 6),
        ]
        draw.polygon(shield_pts, fill=(16, 185, 129, 30), outline=(52, 211, 153), width=4)
        return img

    # ── 4. Quantum Physics Lab ───────────────────────────────────────
    def _render_quantum_lab(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (24, 24, 38))  # Dark violet lab
        draw = ImageDraw.Draw(img)

        # Blackboard with quantum equations at top
        bw, bh = int(w * 0.85), int(h * 0.28)
        bx0 = (w - bw) // 2
        by0 = 60
        draw.rectangle([bx0, by0, bx0 + bw, by0 + bh], fill=(15, 23, 42), outline=(148, 163, 184), width=6)
        draw.text((bx0 + 30, by0 + 25), "E = mc^2   |   Ψ(x,t) = Ae^(i(kx - ωt))", fill=(255, 255, 255))
        draw.text((bx0 + 30, by0 + 65), "Δx * Δp >= ħ / 2   [QUANTUM ENTANGLEMENT]", fill=(147, 197, 253))
        draw.text((bx0 + 30, by0 + 105), "ENTANGLED SPIN: |ψ⟩ = (|00⟩ + |11⟩) / √2", fill=(253, 224, 71))

        # Orbiting Atomic Rings in Center
        cx, cy = w // 2, int(h * 0.45)
        draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(236, 72, 153), outline=(255, 255, 255), width=3)
        for i, rad in enumerate([110, 160, 210]):
            ang_tilt = i * (math.pi / 3) + (frame_idx * 0.03)
            # Elliptical ring
            rx, ry = rad, int(rad * 0.45)
            # Draw ring approximation
            draw.arc([cx - rx, cy - ry, cx + rx, cy + ry], start=0, end=360, fill=(168, 85, 247), width=3)
            # Orbiting electron
            el_ang = (frame_idx * 0.08 * (i + 1))
            el_x = cx + int(math.cos(el_ang) * rx)
            el_y = cy + int(math.sin(el_ang) * ry)
            draw.ellipse([el_x - 7, el_y - 7, el_x + 7, el_y + 7], fill=(56, 189, 248), outline=(255, 255, 255), width=2)

        return img

    # ── 5. Wall Street ───────────────────────────────────────────────
    def _render_wall_street(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (11, 15, 25))  # Bloomberg terminal dark
        draw = ImageDraw.Draw(img)

        # Candlestick stock chart
        chart_y = int(h * 0.35)
        num_candles = 16
        candle_w = int(w * 0.8) // num_candles
        chart_x0 = (w - (num_candles * candle_w)) // 2

        # Draw grid
        for gy in range(chart_y - 120, chart_y + 160, 40):
            draw.line([(chart_x0, gy), (chart_x0 + num_candles * candle_w, gy)], fill=(30, 41, 59), width=1)

        # Seeded candlesticks
        for i in range(num_candles):
            cx = chart_x0 + i * candle_w + candle_w // 2
            is_green = (math.sin(i * 1.3 + frame_idx * 0.04) > 0)
            color = (34, 197, 94) if is_green else (239, 68, 68)
            high = chart_y - int(math.sin(i * 0.7) * 70 + 40)
            low = high + int(abs(math.cos(i * 1.1)) * 60 + 30)
            # Wick
            draw.line([(cx, high), (cx, low)], fill=color, width=2)
            # Body
            b_top = high + 10
            b_bot = low - 10
            draw.rectangle([cx - 8, b_top, cx + 8, b_bot], fill=color, outline=(0, 0, 0), width=1)

        # Scrolling stock ticker banner at top
        banner_h = 55
        draw.rectangle([0, 40, w, 40 + banner_h], fill=(0, 0, 0), outline=(234, 179, 8), width=3)
        tickers = " ▲ NASDAQ +3.4%   ▼ TECH -1.8%   ▲ BITCOIN $98,400   ▲ AI_CORP +12.5%   ▼ OIL -0.6%"
        scroll_x = (frame_idx * -3) % (w + 400) - 100
        draw.text((scroll_x, 56), tickers, fill=(255, 255, 255))
        return img

    # ── 6. Command Center ────────────────────────────────────────────
    def _render_command_center(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (10, 15, 30))
        draw = ImageDraw.Draw(img)

        # Stylized Global Radar Circle
        cx, cy = w // 2, int(h * 0.38)
        radar_r = min(w, h) // 3
        draw.ellipse([cx - radar_r, cy - radar_r, cx + radar_r, cy + radar_r], fill=(15, 23, 42), outline=(59, 130, 246), width=4)
        draw.ellipse([cx - radar_r // 2, cy - radar_r // 2, cx + radar_r // 2, cy + radar_r // 2], fill=None, outline=(30, 58, 138), width=2)
        draw.line([(cx - radar_r, cy), (cx + radar_r, cy)], fill=(30, 58, 138), width=2)
        draw.line([(cx, cy - radar_r), (cx, cy + radar_r)], fill=(30, 58, 138), width=2)

        # Sweeping radar needle
        ang = frame_idx * 0.06
        sweep_x = cx + int(math.cos(ang) * (radar_r - 10))
        sweep_y = cy + int(math.sin(ang) * (radar_r - 10))
        draw.line([(cx, cy), (sweep_x, sweep_y)], fill=(96, 165, 250), width=4)

        # Blinking threat alert points
        for i in range(4):
            pt_ang = i * 1.5 + 0.4
            px = cx + int(math.cos(pt_ang) * (radar_r * 0.65))
            py = cy + int(math.sin(pt_ang) * (radar_r * 0.65))
            blink = (frame_idx + i * 5) % 12 < 6
            color = (239, 68, 68) if blink else (127, 29, 29)
            draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=color, outline=(255, 255, 255), width=2)

        return img

    # ── 7. Airport Station ───────────────────────────────────────────
    def _render_airport_station(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (241, 245, 249))  # Bright modern terminal
        draw = ImageDraw.Draw(img)

        # Terminal arched ceiling beams
        for x in range(0, w + 100, 180):
            draw.line([(x, 0), (x - 80, int(h * 0.4))], fill=(203, 213, 225), width=6)

        # Split-flap departure schedule board
        board_w, board_h = int(w * 0.88), int(h * 0.24)
        bx0 = (w - board_w) // 2
        by0 = 70
        draw.rectangle([bx0, by0, bx0 + board_w, by0 + board_h], fill=(15, 23, 42), outline=(0, 0, 0), width=6)
        draw.text((bx0 + 25, by0 + 20), "DEPARTURES // FLIGHT STATUS", fill=(234, 179, 8))
        draw.text((bx0 + 25, by0 + 55), "FL 204  LONDON     ON TIME   GATE B12", fill=(255, 255, 255))
        draw.text((bx0 + 25, by0 + 85), "FL 891  TOKYO      BOARDING  GATE A04", fill=(52, 211, 153))
        draw.text((bx0 + 25, by0 + 115), "FL 410  NEW YORK   DELAYED   GATE C22", fill=(239, 68, 68))

        # Public USB charging station kiosk silhouette on right
        kx0 = int(w * 0.76)
        ky0 = int(h * 0.38)
        draw.rounded_rectangle([kx0, ky0, kx0 + 100, ky0 + 350], radius=12, fill=(30, 41, 59), outline=(0, 0, 0), width=5)
        draw.rectangle([kx0 + 15, ky0 + 25, kx0 + 85, ky0 + 90], fill=(59, 130, 246), outline=(0, 0, 0), width=3)
        draw.text((kx0 + 25, ky0 + 45), "USB", fill=(255, 255, 255))
        # USB Ports
        for i in range(3):
            draw.rectangle([kx0 + 35, ky0 + 120 + i * 40, kx0 + 65, ky0 + 135 + i * 40], fill=(0, 0, 0))

        return img

    # ── 8. Throne Room ───────────────────────────────────────────────
    def _render_throne_room(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (40, 20, 25))  # Royal castle stone
        draw = ImageDraw.Draw(img)

        # Stone castle wall masonry
        for y in range(0, h, 80):
            shift = 50 if (y // 80) % 2 == 1 else 0
            for x in range(-50, w + 100, 100):
                draw.rectangle([x + shift, y, x + shift + 96, y + 76], outline=(60, 35, 40), width=2)

        # Royal Red Velvet Banners on sides
        banner_w = int(w * 0.18)
        draw.polygon([(0, 0), (banner_w, 0), (banner_w, int(h * 0.65)), (banner_w // 2, int(h * 0.60)), (0, int(h * 0.65))], fill=(185, 28, 28), outline=(234, 179, 8), width=5)
        rx0 = w - banner_w
        draw.polygon([(rx0, 0), (w, 0), (w, int(h * 0.65)), (rx0 + banner_w // 2, int(h * 0.60)), (rx0, int(h * 0.65))], fill=(185, 28, 28), outline=(234, 179, 8), width=5)

        # Grand Stone Arch in Center
        cx, cy = w // 2, int(h * 0.38)
        arch_r = min(w, h) // 3
        draw.arc([cx - arch_r, cy - arch_r, cx + arch_r, cy + arch_r], start=180, end=360, fill=(234, 179, 8), width=8)

        # Golden Fleur-de-lis Crest in Center
        draw.ellipse([cx - 40, cy - arch_r - 20, cx + 40, cy - arch_r + 60], fill=(234, 179, 8), outline=(0, 0, 0), width=4)
        return img

    # ── 9. Retro Mainframe ───────────────────────────────────────────
    def _render_retro_mainframe(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (30, 35, 45))  # Vintage 1970s server beige/slate
        draw = ImageDraw.Draw(img)

        # Dual spinning magnetic tape drive cabinet in center
        cx = w // 2
        cy = int(h * 0.35)
        cw = int(w * 0.75)
        ch = int(h * 0.32)
        draw.rounded_rectangle([cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2], radius=16, fill=(15, 23, 42), outline=(0, 0, 0), width=6)

        # Left and Right tape reels
        reel_r = ch // 3
        for idx, rx in enumerate([cx - cw // 4, cx + cw // 4]):
            draw.ellipse([rx - reel_r, cy - reel_r, rx + reel_r, cy + reel_r], fill=(241, 245, 249), outline=(0, 0, 0), width=5)
            # Spinning reel cutouts
            ang = (frame_idx * 0.12 * (1 if idx == 0 else -1))
            for sp in range(3):
                sang = ang + sp * (2 * math.pi / 3)
                sx = rx + int(math.cos(sang) * (reel_r * 0.6))
                sy = cy + int(math.sin(sang) * (reel_r * 0.6))
                draw.ellipse([sx - 12, sy - 12, sx + 12, sy + 12], fill=(15, 23, 42))

        # Blinking 1970s mainframe bulb grid
        for row in range(3):
            for col in range(12):
                bx = cx - cw // 2 + 40 + col * (cw - 80) // 12
                by = cy + ch // 2 + 30 + row * 26
                on = ((frame_idx + row * 7 + col * 3) % 4) == 0
                color = (239, 68, 68) if on else (75, 85, 99)
                draw.ellipse([bx - 6, by - 6, bx + 6, by + 6], fill=color)

        return img

    # ── 10. BEN Creator Studio (Default) ─────────────────────────────
    def _render_ben_studio(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (18, 18, 28))  # Dark sleek creator studio
        draw = ImageDraw.Draw(img)

        # Hexagonal acoustic foam panels in background
        hex_size = 55
        for row in range(0, int(h * 0.6), 85):
            shift = hex_size if (row // 85) % 2 == 1 else 0
            for col in range(0, w + 100, 110):
                hx = col + shift
                hy = row + 60
                draw.regular_polygon((hx, hy, hex_size), n_sides=6, fill=(30, 30, 46), outline=(45, 45, 68))

        # Subtle neon purple/cyan backlight aura in center
        cx, cy = w // 2, int(h * 0.42)
        glow_r = min(w, h) // 3
        draw.ellipse([cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r], fill=(49, 46, 129, 60))

        # Studio microphone arm silhouette in background corner
        draw.line([(w - 80, 0), (w - 140, 160)], fill=(75, 85, 99), width=8)
        draw.ellipse([w - 165, 150, w - 115, 210], fill=(100, 116, 139), outline=(0, 0, 0), width=4)
        return img

    # ── 11. Street Day ───────────────────────────────────────────────
    def _render_street_day(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (186, 230, 253))  # Cartoon sunny blue sky
        draw = ImageDraw.Draw(img)

        # Cartoon Skyscrapers silhouette
        skyline_y = int(h * 0.35)
        for i, (b_x, b_w, b_h, col) in enumerate([
            (20, 140, 320, (148, 163, 184)),
            (180, 160, 420, (100, 116, 139)),
            (360, 200, 280, (148, 163, 184)),
            (580, 150, 460, (71, 85, 105)),
            (750, 180, 360, (100, 116, 139)),
            (950, 120, 300, (148, 163, 184)),
        ]):
            if b_x < w:
                draw.rectangle([b_x, skyline_y - b_h + 300, b_x + b_w, skyline_y + 300], fill=col, outline=(0, 0, 0), width=4)
                # Windows
                for wy in range(skyline_y - b_h + 330, skyline_y + 250, 40):
                    for wx in range(b_x + 15, b_x + b_w - 15, 30):
                        draw.rectangle([wx, wy, wx + 16, wy + 22], fill=(254, 240, 138))

        return img

    # ── 12. Street Night ─────────────────────────────────────────────
    def _render_street_night(self, w: int, h: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (w, h), (15, 23, 42))  # Dark city night
        draw = ImageDraw.Draw(img)

        # Crescent moon
        draw.ellipse([80, 80, 160, 160], fill=(254, 240, 138))
        draw.ellipse([110, 70, 180, 160], fill=(15, 23, 42))

        # Dark buildings with glowing yellow windows
        skyline_y = int(h * 0.40)
        for i in range(0, w, 120):
            bh = 220 + (i % 5) * 60
            draw.rectangle([i, skyline_y - bh + 250, i + 110, skyline_y + 250], fill=(30, 41, 59), outline=(0, 0, 0), width=4)
            for wy in range(skyline_y - bh + 270, skyline_y + 230, 45):
                draw.rectangle([i + 20, wy, i + 45, wy + 25], fill=(253, 224, 71) if ((i + wy) % 3 == 0) else (51, 65, 85))

        return img
