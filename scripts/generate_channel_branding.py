"""Generate complete YouTube Channel Branding Package for BENX_07.

Creates:
1. 2560x1440 Channel Banner (featuring BEN and Character Universe).
2. 800x800 High-Res Channel Avatar / Profile Picture.
3. Channel About Bio & Keywords (optimized for YouTube search indexing).
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path("output/channel_branding")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = Path("assets/characters/universe_debut")


def create_channel_banner():
    """Create 2560x1440 YouTube Banner compliant with safe area (1546x423)."""
    banner = Image.new("RGB", (2560, 1440), (250, 250, 250))
    draw = ImageDraw.Draw(banner)

    # Safe zone center: y = 508 to 931 (height 423)
    safe_y0 = 508
    safe_y1 = 931

    # Draw modern geometric tech / comic background
    draw.rectangle([0, safe_y0 - 20, 2560, safe_y1 + 20], fill=(245, 245, 245))
    draw.line([(0, safe_y0 - 20), (2560, safe_y0 - 20)], fill=(0, 0, 0), width=6)
    draw.line([(0, safe_y1 + 20), (2560, safe_y1 + 20)], fill=(0, 0, 0), width=6)

    # Load and place characters in safe zone
    # Left: The King & Dr. Quantum
    # Center: BEN
    # Right: MAX & Mr. Cash
    char_size = 380

    def load_char(fname):
        p = ASSETS_DIR / fname
        if p.exists():
            im = Image.open(p).convert("RGB")
            # circular or clean crop
            im = im.resize((char_size, char_size), Image.Resampling.LANCZOS)
            return im
        return None

    ben_img = load_char("ben_intro_open.jpg")
    king_img = load_char("king_history.jpg")
    cash_img = load_char("cash_finance.jpg")
    max_img = load_char("max_logic.jpg")
    quant_img = load_char("quantum_science.jpg")

    cy = safe_y0 + (safe_y1 - safe_y0 - char_size) // 2

    # Paste characters across safe zone
    if king_img:
        banner.paste(king_img, (320, cy))
        draw.rectangle([320, cy, 320 + char_size, cy + char_size], outline=(0, 0, 0), width=5)
    if quant_img:
        banner.paste(quant_img, (720, cy))
        draw.rectangle([720, cy, 720 + char_size, cy + char_size], outline=(0, 0, 0), width=5)
    if ben_img:
        # Center hero
        banner.paste(ben_img, (1090, cy))
        draw.rectangle([1090, cy, 1090 + char_size, cy + char_size], outline=(239, 68, 68), width=8)
    if max_img:
        banner.paste(max_img, (1490, cy))
        draw.rectangle([1490, cy, 1490 + char_size, cy + char_size], outline=(0, 0, 0), width=5)
    if cash_img:
        banner.paste(cash_img, (1890, cy))
        draw.rectangle([1890, cy, 1890 + char_size, cy + char_size], outline=(0, 0, 0), width=5)

    # Channel Title Banner in safe zone
    font = None
    try:
        font = ImageFont.truetype("arialbd.ttf", 64)
    except Exception:
        pass

    title_text = "BENX | DAILY 2D ANIMATED SHORTS & TECH DEEP DIVES"
    bbox = draw.textbbox((0, 0), title_text, font=font)
    tw = bbox[2] - bbox[0]
    tx = (2560 - tw) // 2
    ty = safe_y0 - 90

    # Draw title plate
    draw.rectangle([tx - 30, ty - 10, tx + tw + 30, ty + 80], fill=(239, 68, 68), outline=(0, 0, 0), width=6)
    draw.text((tx, ty), title_text, fill=(255, 255, 255), font=font)

    banner_path = OUTPUT_DIR / "youtube_channel_banner.jpg"
    banner.save(banner_path, quality=95)
    print("Channel Banner generated:", banner_path)
    return banner_path


def create_channel_avatar():
    """Create 800x800 square Avatar of BEN with iconic sunglasses and bold outline."""
    avatar_path = OUTPUT_DIR / "youtube_channel_avatar.jpg"
    ben_p = ASSETS_DIR / "ben_intro_closed.jpg"
    if ben_p.exists():
        im = Image.open(ben_p).convert("RGB")
        im = im.resize((800, 800), Image.Resampling.LANCZOS)
    else:
        im = Image.new("RGB", (800, 800), (255, 255, 255))

    draw = ImageDraw.Draw(im)
    draw.rectangle([0, 0, 800, 800], outline=(239, 68, 68), width=16)

    # Accent badge at bottom
    font = None
    try:
        font = ImageFont.truetype("arialbd.ttf", 52)
    except Exception:
        pass
    badge_text = "BENX"
    bbox = draw.textbbox((0, 0), badge_text, font=font)
    bw = bbox[2] - bbox[0]
    bx = (800 - bw) // 2
    draw.rectangle([bx - 24, 700, bx + bw + 24, 780], fill=(0, 0, 0), outline=(255, 255, 255), width=4)
    draw.text((bx, 712), badge_text, fill=(255, 255, 255), font=font)

    im.save(avatar_path, quality=95)
    print("Channel Avatar generated:", avatar_path)
    return avatar_path


def create_channel_seo_metadata():
    """Generate optimized Channel About Description & Search Keywords."""
    about_text = """Welcome to BENX! 🔥 The home of high-speed 2D animated comedy Shorts and mind-blowing tech documentaries!

Every single day, join BEN and the Character Universe:
🕶️ BEN: Everyday tech hacks, smartphone survival guides, and hilarious dilemmas.
🤖 MAX: Logic breakdowns, cyber heists, and computer code disasters.
💰 Mr. Cash: Billion-dollar corporate wars, financial secrets, and wealth loops.
👑 The King: Bizarre ancient empires, eccentric rulers, and forgotten laws.
🔬 Dr. Quantum: Mind-bending physics, space mysteries, and quantum science.

✨ Authentic 2D OverSimplified hand-drawn comic animation — 0% generic AI nonsense.
🚀 Smash SUBSCRIBE and join the squad to get smarter every single day!

Business & Inquiries: Contact through channel details.
#animation #cartoons #comedy #tech #shorts #oversimplified #theodd1sout #benx"""

    about_path = OUTPUT_DIR / "channel_about_description.txt"
    about_path.write_text(about_text, encoding="utf-8")

    keywords = [
        "BENX",
        "animated shorts",
        "cartoon animation",
        "oversimplified",
        "theodd1sout",
        "tech hacks",
        "cybersecurity",
        "juice jacking",
        "coding disaster",
        "finance secrets",
        "weird history",
        "science explained",
        "2d cartoon",
        "comedy animation",
        "daily shorts",
    ]
    keywords_path = OUTPUT_DIR / "channel_keywords.txt"
    keywords_path.write_text(", ".join(keywords), encoding="utf-8")

    print("Channel SEO About & Keywords generated in:", OUTPUT_DIR)


if __name__ == "__main__":
    create_channel_banner()
    create_channel_avatar()
    create_channel_seo_metadata()
