# BENX Mascot Character Design Specification

## 1. Character Identity & Lore
- **Name:** BENX (also known as Benx Bot / Cyber Scout)
- **Role:** High-tech, charismatic digital host and storyteller for BENXAUTOMATION video productions.
- **Tone:** Curious, intelligent, energetic, friendly, and authoritative on technology, finance, and futuristic concepts.
- **Copyright & Ownership:** 100% original creator-owned design created specifically for BENXAUTOMATION. Zero copyrighted third-party IP or trademarks.

---

## 2. Silhouette & Anatomy
- **Head:**
  - Smooth rounded obsidian-graphite helmet (`#0B132B` / `#1C2541`) with bevelled cyber-chassis seams.
  - Dual cyber-teal antenna nodes (`#00F2FE`) on top for signal reception.
  - Cyber acoustic ear-sensor discs (`#4FACFE`) on the sides.
  - Panoramic curved glass visor faceplate displaying digital LED facial expressions.
- **Face & Visor Display:**
  - High-contrast LED visor array rendered in signature cyber-teal (`#00F2FE`) with soft outer neon bloom (`#4FACFE`).
  - Expressive digital eye glyphs with micro-glow.
  - Dynamic digital mouth viseme strip for synchronized dialogue.
- **Torso & Costume:**
  - Lightweight cyber-composite jacket / chassis in deep navy and charcoal.
  - Illuminated power circuitry running along the collarbone and sleeves.
  - Central hexagonal chest badge with glowing "BX" monogram emblem (`#00F2FE`).
- **Limbs:**
  - Articulated cybernetic arms with matte-white shoulder plates and cyan joints.
  - Friendly three-segment utility hands capable of clear human gestures (pointing, shrugging, chin-tapping, welcoming).

---

## 3. Color Palette
| Component | Color Name | Hex Code | RGB | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Base** | Obsidian Graphite | `#0B132B` | `(11, 19, 43)` | Helmet exterior, chassis base |
| **Secondary Armor** | Deep Cyber Navy | `#1C2541` | `(28, 37, 65)` | Chestplate, shoulders, arm plates |
| **Signature Glow** | Cyber Teal | `#00F2FE` | `(0, 242, 254)` | Eyes, visemes, antenna tips, chest badge |
| **Secondary Accent** | Electric Blue | `#4FACFE` | `(79, 172, 254)` | Seam glows, earcups, circuitry |
| **Core Highlight** | Plasma White | `#FFFFFF` | `(255, 255, 255)` | Specular highlights, eye pupils, visor gleam |
| **Alert / Emotion** | Coral Neon | `#FF416C` | `(255, 65, 108)` | Warning, surprise accents, high-priority points |
| **Background Dark** | Space Void | `#050811` | `(5, 8, 17)` | Stage backgrounds, contrast backdrop |

---

## 4. Facial Expressions
The visor display dynamically switches between clean, highly recognizable digital glyphs:
1. **HAPPY / CONFIDENT:** Upward curving warm crescent eyes, gentle upward mouth smile.
2. **SURPRISED:** Enlarged circular glowing rings with widened pupil rings, small open "O" mouth.
3. **CONFUSED:** Asymmetrical visor—left brow elevated high, right eye squinted/narrowed, wavy mouth.
4. **SERIOUS / WARNING:** Sharply angled visor slits with intense cyber glow, flat horizontal mouth.
5. **EXCITED:** Sparkling star/diamond cross illuminated eyes, wide energetic open smile.
6. **SAD / EMPATHETIC:** Soft downward-angled crescent eyes, downward curved mouth.
7. **BLINK:** Ultra-fast horizontal laser-thin line (120ms duration) occurring every 3–4 seconds.

---

## 5. Dialogue Visemes (Lip-Sync Shapes)
1. **REST:** Neutral glowing horizontal line with rounded caps.
2. **A (Ah / Uh):** Medium tall oval mouth with visible digital teeth contour.
3. **O (Oh / Oo):** Compact circular aperture shape.
4. **E (Ee / Eh):** Wide horizontal smile shape with teeth separator bar.
5. **WIDE (Shout / Emphasis):** Expanded stadium/pill mouth with high-intensity glow.

---

## 6. Poses & Body Gestures
1. **IDLE:** Hands relaxed near hips, gentle breathing cycle (subtle vertical bobbing `±4px`).
2. **GESTURE:** Right hand open forward in welcoming, conversational stance.
3. **POINTING_RIGHT:** Right index finger extended pointing toward graphics / charts on the right.
4. **POINTING_UP:** Right index finger pointing up toward a key idea or top title.
5. **THINKING_CHIN:** Right hand tucked under visor chin in an analytical, reflective pose.
6. **SHRUG:** Both hands raised outward with tilted head in an inquisitive or bewildered pose.
7. **CHEER / TRIUMPHANT:** Both arms raised high with fists or open palms celebrate success.

---

## 7. Camera & Scene Motion
- **Frame Rate:** 24 or 30 FPS.
- **Resolutions Supported:**
  - Vertical 9:16 Shorts: `1080 x 1920`
  - Horizontal 16:9 Long-form: `1920 x 1080`
- **Dynamic Micro-Motion:**
  - Breathing oscillation: harmonic sine curve `sin(2 * pi * t * 0.8) * 4px`.
  - Visor glow pulsing: subtle luminance oscillation `0.95 - 1.05x`.
  - Automatic eye blinking: every 3.2 seconds for 3-4 frames.
  - Camera motions: Static medium, Dolly-in closeup, Pan left-to-right, Dutch tilt, Orbit drift.
  - Background: Particle drift, grid scroll, or dynamic glow layers to ensure high inter-frame motion delta.
