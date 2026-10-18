"""Prototype renderer matching the exact OverSimplified / TheOdd1sOut cartoon character style requested by the user.

Features:
- Solid white cartoon bean/marshmallow head with bold black ink outline.
- Expressive comic face with angular angry eyebrows, beady black eyes, sharp pointed nose, determined mouth.
- Golden 5-spiked royal crown with cel-shading.
- Crimson/burgundy royal cape with dramatic high popped collar and gold brooches.
- Segmented dark charcoal armor and white cartoon gloved hand gripping sword with blue crystal pommel.
- Cinematic volumetric lighting: diagonal god rays, painterly atmospheric night clouds, subtle star sparkles.
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_PATH = Path(r"C:\Users\Admin\.gemini\antigravity-ide\brain\a98a7b4a-96a1-4c47-807f-0171a6094767\king_cartoon_style_prototype.png")

W, H = 1080, 1920
img = Image.new("RGBA", (W, H), (0, 0, 0, 255))

# 1. Base Night Sky Gradient
sky = Image.new("RGBA", (W, H), (20, 30, 48, 255))
sky_draw = ImageDraw.Draw(sky)
for y in range(H):
    t = y / H
    r = int(25 * (1 - t) + 40 * t)
    g = int(35 * (1 - t) + 55 * t)
    b = int(55 * (1 - t) + 75 * t)
    sky_draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

# 2. Volumetric God Rays (Moonlight Beams streaming from top-left)
rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
rays_draw = ImageDraw.Draw(rays)
# Light source at top-left (-100, -100)
lx, ly = -100, -100
for angle_deg in [18, 24, 30, 36, 42, 48, 54, 60, 68]:
    rad = math.radians(angle_deg)
    width_angle = math.radians(2.8)
    length = 2600
    p1 = (lx, ly)
    p2 = (lx + math.cos(rad - width_angle) * length, ly + math.sin(rad - width_angle) * length)
    p3 = (lx + math.cos(rad + width_angle) * length, ly + math.sin(rad + width_angle) * length)
    alpha = 38 if (angle_deg in (30, 42, 54)) else 22
    rays_draw.polygon([p1, p2, p3], fill=(210, 235, 255, alpha))

rays = rays.filter(ImageFilter.GaussianBlur(18))
sky.alpha_composite(rays)

# 3. Painterly Atmospheric Clouds (Soft layered dark navy/slate clouds)
clouds = Image.new("RGBA", (W, H), (0, 0, 0, 0))
c_draw = ImageDraw.Draw(clouds)

cloud_clusters = [
    # Background layer (darker)
    [(100, 300, 280, 140), (250, 260, 320, 160), (450, 310, 300, 150), (-80, 280, 260, 140)],
    [(600, 450, 360, 170), (820, 420, 340, 160), (400, 480, 300, 150)],
    # Foreground cloud layer
    [(0, 750, 420, 220), (300, 720, 480, 240), (680, 740, 450, 230), (950, 710, 380, 200)],
]

# Draw background cloud puffs
for bx, by, bw, bh in cloud_clusters[0] + cloud_clusters[1]:
    c_draw.ellipse([(bx, by), (bx + bw, by + bh)], fill=(45, 60, 80, 180))

# Draw foreground cloud puffs with lighter rim
for fx, fy, fw, fh in cloud_clusters[2]:
    c_draw.ellipse([(fx, fy), (fx + fw, fy + fh)], fill=(60, 78, 102, 220))
    # Soft rim highlight on top of cloud
    c_draw.arc([(fx + 10, fy + 5), (fx + fw - 10, fy + fh - 5)], start=190, end=350, fill=(130, 160, 195, 120), width=6)

clouds = clouds.filter(ImageFilter.GaussianBlur(8))
sky.alpha_composite(clouds)

# 4. Subtle Star Particles
star_draw = ImageDraw.Draw(sky)
star_coords = [(180, 120), (320, 80), (550, 140), (750, 95), (920, 160), (60, 220), (850, 280), (420, 200)]
for sx, sy in star_coords:
    star_draw.ellipse([(sx - 2, sy - 2), (sx + 2, sy + 2)], fill=(255, 255, 255, 200))
    star_draw.ellipse([(sx - 4, sy - 4), (sx + 4, sy + 4)], fill=(255, 255, 255, 70))

# Composite sky onto canvas
img.alpha_composite(sky)

# 5. Character Rendering: "THE KING" (Exact OverSimplified / TheOdd1sOut Style)
char_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(char_layer)

# Character center anchor
cx = int(W * 0.50)
cy = int(H * 0.62)
scale = 1.65

LINE_COLOR = (18, 22, 30, 255)
LINE_W = 10
SKIN_COLOR = (255, 255, 255, 255)
CROWN_GOLD = (245, 205, 42, 255)
CROWN_SHADOW = (212, 170, 28, 255)
CAPE_BURGUNDY = (142, 28, 62, 255)
CAPE_COLLAR = (112, 18, 48, 255)
CAPE_SHADOW = (88, 12, 38, 255)
ARMOR_DARK = (48, 54, 66, 255)
ARMOR_HIGHLIGHT = (70, 78, 95, 255)
BUTTON_GOLD = (255, 215, 60, 255)
GEM_BLUE = (140, 215, 250, 255)

# --- A. Back Cape (Behind torso and shoulders) ---
cape_back_poly = [
    (cx - int(240 * scale), cy - int(40 * scale)),
    (cx - int(380 * scale), cy + int(450 * scale)),
    (cx + int(380 * scale), cy + int(450 * scale)),
    (cx + int(240 * scale), cy - int(40 * scale)),
]
d.polygon(cape_back_poly, fill=CAPE_SHADOW)

# --- B. Armor Breastplate (Torso) ---
torso_poly = [
    (cx - int(120 * scale), cy + int(10 * scale)),
    (cx + int(120 * scale), cy + int(10 * scale)),
    (cx + int(140 * scale), cy + int(320 * scale)),
    (cx - int(140 * scale), cy + int(320 * scale)),
]
d.polygon(torso_poly, fill=ARMOR_DARK, outline=LINE_COLOR, width=LINE_W)

# Armor center crease highlight
d.line([(cx, cy + int(20 * scale)), (cx, cy + int(300 * scale))], fill=ARMOR_HIGHLIGHT, width=6)
# Segmented chest plate curves
d.arc([(cx - int(100 * scale), cy + int(40 * scale)), (cx + int(100 * scale), cy + int(160 * scale))], start=20, end=160, fill=LINE_COLOR, width=LINE_W)

# --- C. Right Arm (Segmented armor holding sword) ---
# Shoulder pauldron
r_sh_poly = [
    (cx + int(110 * scale), cy + int(30 * scale)),
    (cx + int(220 * scale), cy + int(90 * scale)),
    (cx + int(180 * scale), cy + int(170 * scale)),
    (cx + int(90 * scale), cy + int(120 * scale)),
]
d.polygon(r_sh_poly, fill=ARMOR_DARK, outline=LINE_COLOR, width=LINE_W)

# Forearm armor
r_fa_poly = [
    (cx + int(170 * scale), cy + int(140 * scale)),
    (cx + int(270 * scale), cy + int(180 * scale)),
    (cx + int(250 * scale), cy + int(240 * scale)),
    (cx + int(150 * scale), cy + int(200 * scale)),
]
d.polygon(r_fa_poly, fill=ARMOR_DARK, outline=LINE_COLOR, width=LINE_W)
# Arm armor segment rings
d.line([(cx + int(180 * scale), cy + int(165 * scale)), (cx + int(165 * scale), cy + int(215 * scale))], fill=LINE_COLOR, width=LINE_W)
d.line([(cx + int(225 * scale), cy + int(185 * scale)), (cx + int(210 * scale), cy + int(235 * scale))], fill=LINE_COLOR, width=LINE_W)

# --- D. Front Royal Cape & Popped Collar ---
# High popped collar behind head
collar_left = [
    (cx - int(120 * scale), cy + int(30 * scale)),
    (cx - int(180 * scale), cy - int(90 * scale)),
    (cx - int(110 * scale), cy - int(30 * scale)),
    (cx - int(60 * scale), cy + int(20 * scale)),
]
d.polygon(collar_left, fill=CAPE_COLLAR, outline=LINE_COLOR, width=LINE_W)

collar_right = [
    (cx + int(60 * scale), cy + int(20 * scale)),
    (cx + int(110 * scale), cy - int(30 * scale)),
    (cx + int(180 * scale), cy - int(90 * scale)),
    (cx + int(120 * scale), cy + int(30 * scale)),
]
d.polygon(collar_right, fill=CAPE_COLLAR, outline=LINE_COLOR, width=LINE_W)

# Front draping cape wings over shoulders
cape_left_drape = [
    (cx - int(60 * scale), cy + int(20 * scale)),
    (cx - int(180 * scale), cy - int(80 * scale)),
    (cx - int(240 * scale), cy + int(80 * scale)),
    (cx - int(280 * scale), cy + int(420 * scale)),
    (cx - int(130 * scale), cy + int(380 * scale)),
    (cx - int(90 * scale), cy + int(120 * scale)),
]
d.polygon(cape_left_drape, fill=CAPE_BURGUNDY, outline=LINE_COLOR, width=LINE_W)

cape_right_drape = [
    (cx + int(60 * scale), cy + int(20 * scale)),
    (cx + int(180 * scale), cy - int(80 * scale)),
    (cx + int(240 * scale), cy + int(80 * scale)),
    (cx + int(270 * scale), cy + int(320 * scale)),
    (cx + int(170 * scale), cy + int(240 * scale)),
    (cx + int(100 * scale), cy + int(100 * scale)),
]
d.polygon(cape_right_drape, fill=CAPE_BURGUNDY, outline=LINE_COLOR, width=LINE_W)

# Cape golden spherical buttons
btn_r = int(18 * scale)
d.ellipse([(cx - int(65 * scale) - btn_r, cy + int(45 * scale) - btn_r), (cx - int(65 * scale) + btn_r, cy + int(45 * scale) + btn_r)], fill=BUTTON_GOLD, outline=LINE_COLOR, width=6)
d.ellipse([(cx + int(65 * scale) - btn_r, cy + int(45 * scale) - btn_r), (cx + int(65 * scale) + btn_r, cy + int(45 * scale) + btn_r)], fill=BUTTON_GOLD, outline=LINE_COLOR, width=6)
# Button shine highlights
d.ellipse([(cx - int(70 * scale), cy + int(38 * scale)), (cx - int(64 * scale), cy + int(44 * scale))], fill=(255, 255, 255, 255))
d.ellipse([(cx + int(60 * scale), cy + int(38 * scale)), (cx + int(66 * scale), cy + int(44 * scale))], fill=(255, 255, 255, 255))

# --- E. Cartoon White Head ---
hx = cx
hy = cy - int(70 * scale)
hr_w = int(105 * scale)
hr_h = int(115 * scale)

# Head shadow on neck
d.ellipse([(hx - hr_w - 4, hy - hr_h + int(18 * scale)), (hx + hr_w + 4, hy + hr_h + int(18 * scale))], fill=(225, 230, 240, 255))
# Pure white head
d.ellipse([(hx - hr_w, hy - hr_h), (hx + hr_w, hy + hr_h)], fill=SKIN_COLOR, outline=LINE_COLOR, width=LINE_W)

# --- F. Face Details: Angry / Determined Expression ---
eye_y = hy - int(10 * scale)
eye_spacing = int(35 * scale)
lx = hx - eye_spacing
rx = hx + eye_spacing

# Angular angry eyebrows (\ /)
eb_w = int(32 * scale)
eb_h = int(18 * scale)
# Left eyebrow slanting down-right
d.polygon([(lx - eb_w, eye_y - eb_h - int(8 * scale)), (lx + int(8 * scale), eye_y - int(2 * scale)), (lx + int(4 * scale), eye_y + int(6 * scale)), (lx - eb_w - int(4 * scale), eye_y)], fill=LINE_COLOR)
# Right eyebrow slanting down-left
d.polygon([(rx + eb_w, eye_y - eb_h - int(8 * scale)), (rx - int(8 * scale), eye_y - int(2 * scale)), (rx - int(4 * scale), eye_y + int(6 * scale)), (rx + eb_w + int(4 * scale), eye_y)], fill=LINE_COLOR)

# Beady black cartoon eyes tucked under eyebrows
eye_r = int(13 * scale)
d.ellipse([(lx - eye_r + int(6 * scale), eye_y + int(4 * scale)), (lx + eye_r + int(6 * scale), eye_y + int(24 * scale))], fill=LINE_COLOR)
d.ellipse([(rx - eye_r - int(6 * scale), eye_y + int(4 * scale)), (rx + eye_r - int(6 * scale), eye_y + int(24 * scale))], fill=LINE_COLOR)

# Stylized pointed nose (pointing slightly to the right)
nose_pts = [
    (hx - int(4 * scale), eye_y + int(24 * scale)),
    (hx + int(20 * scale), eye_y + int(46 * scale)),
    (hx - int(6 * scale), eye_y + int(46 * scale)),
]
d.line([(hx - int(4 * scale), eye_y + int(24 * scale)), (hx + int(20 * scale), eye_y + int(46 * scale))], fill=LINE_COLOR, width=LINE_W - 2)
d.line([(hx + int(20 * scale), eye_y + int(46 * scale)), (hx - int(8 * scale), eye_y + int(46 * scale))], fill=LINE_COLOR, width=LINE_W - 2)

# Determined frowned mouth line
mouth_pts = [
    (hx - int(24 * scale), eye_y + int(68 * scale)),
    (hx, eye_y + int(64 * scale)),
    (hx + int(28 * scale), eye_y + int(76 * scale)),
]
for i in range(len(mouth_pts) - 1):
    d.line([mouth_pts[i], mouth_pts[i + 1]], fill=LINE_COLOR, width=LINE_W - 2)

# --- G. Golden Spiked Royal Crown ---
crown_base_y = hy - int(92 * scale)
crown_w = int(112 * scale)
crown_h = int(105 * scale)

# Crown base polygon with 5 spikes: left, mid-left, center (tallest), mid-right, right
crown_pts = [
    (hx - crown_w, crown_base_y),                                         # Left base
    (hx - crown_w - int(12 * scale), crown_base_y - int(60 * scale)),     # Spike 1
    (hx - int(55 * scale), crown_base_y - int(25 * scale)),               # Valley 1
    (hx - int(35 * scale), crown_base_y - int(88 * scale)),               # Spike 2
    (hx, crown_base_y - int(35 * scale)),                                 # Valley 2
    (hx, crown_base_y - crown_h),                                         # Center Spike (Tallest)
    (hx, crown_base_y - int(35 * scale)),                                 # Valley 2
    (hx + int(35 * scale), crown_base_y - int(88 * scale)),               # Spike 4
    (hx + int(55 * scale), crown_base_y - int(25 * scale)),               # Valley 3
    (hx + crown_w + int(12 * scale), crown_base_y - int(60 * scale)),     # Spike 5
    (hx + crown_w, crown_base_y),                                         # Right base
]

# Cel-shaded Crown Base Band
d.polygon(crown_pts, fill=CROWN_GOLD, outline=LINE_COLOR, width=LINE_W)
# Crown bottom shading band
d.polygon([(hx - crown_w, crown_base_y), (hx + crown_w, crown_base_y), (hx + crown_w - int(8 * scale), crown_base_y - int(18 * scale)), (hx - crown_w + int(8 * scale), crown_base_y - int(18 * scale))], fill=CROWN_SHADOW)
# Crown base curve line
d.arc([(hx - crown_w, crown_base_y - int(12 * scale)), (hx + crown_w, crown_base_y + int(12 * scale))], start=0, end=180, fill=LINE_COLOR, width=LINE_W)

# --- H. Sword and White Gloved Hand ---
# Sword blade & hilt
sx = cx + int(270 * scale)
sy = cy + int(180 * scale)

# Pommel (Blue glowing gem circle)
pommel_r = int(20 * scale)
d.ellipse([(sx - pommel_r, sy - int(65 * scale) - pommel_r), (sx + pommel_r, sy - int(65 * scale) + pommel_r)], fill=GEM_BLUE, outline=LINE_COLOR, width=7)
# Pommel highlight
d.ellipse([(sx - int(8 * scale), sy - int(72 * scale)), (sx - int(2 * scale), sy - int(66 * scale))], fill=(255, 255, 255, 255))

# Sword handle grip
d.line([(sx, sy - int(65 * scale)), (sx, sy + int(20 * scale))], fill=(210, 220, 230, 255), width=int(18 * scale))
d.line([(sx, sy - int(65 * scale)), (sx, sy + int(20 * scale))], fill=LINE_COLOR, width=LINE_W)

# Crossguard
d.rectangle([(sx - int(38 * scale), sy + int(20 * scale)), (sx + int(38 * scale), sy + int(34 * scale))], fill=ARMOR_DARK, outline=LINE_COLOR, width=LINE_W)

# White cartoon 4-fingered gloved hand wrapped around sword handle
gx = sx
gy = sy - int(15 * scale)
# Glove body
d.ellipse([(gx - int(28 * scale), gy - int(22 * scale)), (gx + int(28 * scale), gy + int(22 * scale))], fill=SKIN_COLOR, outline=LINE_COLOR, width=LINE_W)
# 3 Finger segments gripping
for fi in range(3):
    f_y = gy - int(16 * scale) + fi * int(14 * scale)
    d.arc([(gx - int(26 * scale), f_y - int(8 * scale)), (gx + int(14 * scale), f_y + int(8 * scale))], start=120, end=320, fill=LINE_COLOR, width=6)

# Composite character over sky
img.alpha_composite(char_layer)

# Save result
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
img.save(str(OUT_PATH), "PNG")
print(f"Generated prototype: {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
