# BENX Mascot 2D Animation — Quality Assurance & Rendering Specification

**Date:** 2026-10-13  
**Audience:** 2D Animation Engineers, Video Editors, and QA Leads  
**Repository:** [kabeesh395-oss/BENXAUTOMATION](https://github.com/kabeesh395-oss/BENXAUTOMATION)

---

## 1. Quality Standards & Character Integrity

The BENX Mascot 2D storytelling pipeline delivers dynamic animated explainers featuring **BENX Bot**, an original cyber scout character.

### Core Character Constraints
1. **Silhouette & Recognizability:** High-contrast obsidian graphite helmet (`#0B132B`) with cyber-teal visor display (`#00F2FE`) and central glowing "BX" chest emblem.
2. **Visual Consistency:** Character proportions, color palettes, and layer hierarchies remain identical across all scenes.
3. **Continuous Motion:** Slideshows or sequences of static stills with changing backgrounds are strictly prohibited. The engine guarantees harmonic breathing cycles, automatic eye blinks, synchronized viseme lip movement, and camera drift.
4. **Mobile Readability:** Character silhouette and subtitle typography remain sharp and readable on vertical 9:16 smartphone displays (`1080 x 1920`).

---

## 2. Technical Rendering Specifications

| Parameter | 9:16 Vertical (Shorts) | 16:9 Landscape (Long-Form) | Tolerances |
| :--- | :--- | :--- | :--- |
| **Resolution** | `1080 x 1920` | `1920 x 1080` | Exact pixel dimensions required |
| **Pixel Format** | `yuv420p` | `yuv420p` | Required for maximum device compatibility |
| **Frame Rate** | 24 FPS (or 30 FPS) | 24 FPS (or 30 FPS) | Constant frame rate (`-r 24`) |
| **Video Codec** | H.264 (`libx264`, preset `fast`, crf `20`) | H.264 (`libx264`, preset `fast`, crf `20`) | Must decode cleanly with FFmpeg |
| **Audio Codec** | AAC (`192 kbps`, 48 kHz stereo) | AAC (`192 kbps`, 48 kHz stereo) | Synchronized with narration |
| **Faststart** | `-movflags +faststart` | `-movflags +faststart` | Web streamable |

---

## 3. Character Rig & Animation Hierarchy

The character rig ([`benxautomation/animation/mascot_engine.py`](file:///e:/New%20folder/BENXAUTOMATION/benxautomation/animation/mascot_engine.py)) assembles six composited RGBA layers:

```
[Layer 6: Arms & Hands]   --> Pose: gesture / pointing_up / cheer / thinking_chin
          ▲
[Layer 5: Mouth Viseme]   --> Lip Sync: rest / a / o / e / wide
          ▲
[Layer 4: Eyes Display]   --> Mood: happy / surprised / excited / blink (3.2s cycle)
          ▲
[Layer 3: Visor Plate]    --> Panoramic glass visor with cyber neon bloom
          ▲
[Layer 2: Head Base]      --> Obsidian graphite helmet with cyber antenna nodes
          ▲
[Layer 1: Torso Chassis]  --> Navy cyber-plate body with glowing "BX" emblem
```

### Micro-Motion Dynamics:
- **Harmonic Breathing:** Harmonic oscillation `y_offset = sin(2 * pi * t * 0.8) * 4px`.
- **Visor Luminescence:** Periodic pulsing `0.95x - 1.05x` luminance oscillation.
- **Lip Synchronization:** Dialogue audio energy and phoneme timing dynamically map speech to mouth viseme shapes (`a`, `o`, `e`, `wide`, `rest`).
- **Eye Blinking:** 120ms automatic horizontal blink frame every 3.2 seconds.
- **Camera Transitions:** Dolly-in closeup, static medium, pan left-to-right, and orbit drift.

---

## 4. Automated Motion QA & Verification Metrics

To mathematically ensure animation quality without relying on subjective human observation, the pipeline runs [MotionValidator](file:///e:/New%20folder/BENXAUTOMATION/benxautomation/animation/motion_validator.py):

### 4.1 Motion Delta Algorithm
1. Uniformly sample frames at `1.0s` intervals across the rendered video.
2. Convert frames to grayscale 8-bit luminance matrices: $L_i, L_{i+1}$.
3. Calculate mean absolute pixel delta:
   $$\Delta_{i, i+1} = \frac{1}{W \times H} \sum_{x, y} |L_i(x, y) - L_{i+1}(x, y)|$$
4. Compute total Motion Score:
   $$\text{Motion Score} (\%) = \frac{\Delta}{255} \times 100$$
5. Count Significant Movement Events ($\Delta > 1.0\%$).

### 4.2 Quality Gate Thresholds
- **Motion Score:** Must be $\ge 1.0\%$.
- **Significant Movement Events:** Must be $\ge 3$ events.
- **Decode Verification:** Complete decode check via `ffmpeg -v error -i ... -f null -` must produce zero errors.
- **Audio Alignment:** Video duration must match narration duration within $0.1\text{s}$ container framing tolerance.

---

## 5. Verified Sample Render Inspection Evidence

A production test animation was rendered using [`scripts/render_mascot_sample.py`](file:///e:/New%20folder/BENXAUTOMATION/scripts/render_mascot_sample.py):

### Technical Output Inspection
- **Artifact Path:** [`output/mascot_sample/ai_quantum_leap_shorts/ai_quantum_leap.mp4`](file:///e:/New%20folder/BENXAUTOMATION/output/mascot_sample/ai_quantum_leap_shorts/ai_quantum_leap.mp4)
- **File Size:** `6,554,744 bytes` (~6.55 MB)
- **Duration:** `25.00 seconds`
- **Dimensions:** `1080 x 1920` (exact 9:16 vertical)
- **Video Stream:** H.264, 24 FPS, yuv420p
- **Audio Stream:** AAC stereo, 48 kHz
- **Motion Score:** **`2.62%`** (PASS — threshold >= 1.0%)
- **Significant Movement Events:** **`17`** (PASS — threshold >= 3)
- **Associated Artifacts:**
  - Thumbnail: `output/mascot_sample/ai_quantum_leap_shorts/ai_quantum_leap_thumbnail.jpg`
  - Subtitles (SRT): `output/mascot_sample/ai_quantum_leap_shorts/ai_quantum_leap_subtitles.srt`
  - Subtitles (VTT): `output/mascot_sample/ai_quantum_leap_shorts/ai_quantum_leap_subtitles.vtt`
  - Validation Report: `output/mascot_sample/sample_validation_report.json`

---

## 6. Limitations & Architectural Evolution to V2

| Feature | Current V1 Engine | Planned V2 Architecture |
| :--- | :--- | :--- |
| **Compositing Engine** | Python PIL Sprite Rig + FFmpeg filter graph | Rive runtime / Godot 4 headless export |
| **Limb Articulation** | Pre-rendered multi-segment pose sprites | Real-time 2D inverse kinematics (IK) bones |
| **Lip Sync Accuracy** | Audio envelope & phrase-based viseme map | Phoneme-level alignment via Rhubarb Lip Sync |
| **Rendering Compute** | 100% CPU-only (runs smoothly on free GitHub Actions runners) | Optional GPU hardware acceleration (NVENC) |
