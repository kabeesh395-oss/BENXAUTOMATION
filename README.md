# BENXAUTOMATION V2

> Production-Grade AI Code Review, YouTube Podcast-to-Shorts Repurposing, and Original BENX 2D Mascot Animation Engine.

[![CI — Tests](https://github.com/kabeesh395-oss/BENXAUTOMATION/actions/workflows/ci.yml/badge.svg)](https://github.com/kabeesh395-oss/BENXAUTOMATION/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## What is BENXAUTOMATION V2?

BENXAUTOMATION V2 is an open-source, modular automation suite engineered for high-retention video production and automated GitHub workflows:

1. **BENX Original 2D Mascot Animation Engine**:
   - Original, copyright-free character rig (`assets/mascot/`): helmet visor, dynamic LED eyes (6 expressions + blinks), lip-sync visemes (REST, A, O, E, WIDE), 7 arm gestures, and front/three-quarter body views.
   - Genuine 2D frame-by-frame motion: harmonic breathing cycles, automatic natural eye blinks, speech viseme sync, camera pan/dolly dynamics, and particle drift.
   - Supports both vertical 9:16 Shorts (`1080x1920`) and horizontal 16:9 (`1920x1080`) videos.
   - Built-in mathematical `MotionValidator` ensuring high inter-frame pixel deltas (averages > 2.0% delta across scenes, rejecting static slideshows).
2. **Story-to-Animation Pipeline**:
   - Converts story text or structured scripts into multi-scene 2D animated videos with synchronized neural voice narration (`edge-tts`), burned subtitles (`.srt`/`.vtt`), thumbnails, and metadata receipts.
   - Offline deterministic story catalog (`LocalStoryScriptCatalog`) ensuring zero crashes when external AI providers are offline.
3. **Podcast & Livestream-to-Shorts Engine**:
   - Repurposes local recordings and licensed YouTube streams into vertical 1080x1920 Shorts.
   - Timed transcription, highlight detection, face-tracking/crop, burned captions, and per-clip metadata.
4. **CodeRabbit AI Integration**:
   - Configured with official Schema v2 (`.coderabbit.yaml`) for automated GitHub Pull Request reviews.
   - Specialized review prompts for Python reliability, FFmpeg safety, secret scanning, and test coverage with noisy style nitpicks suppressed.
5. **Quality & Maintainability Tooling**:
   - Fast Python linting via **Ruff** (`ruff check .`).
   - GitHub Actions CI matrix for Python 3.11 and 3.12 with 257 unit & integration tests passing.
   - Human-in-the-loop review gating before merging or publishing.

---

## Architecture Overview

```
BENXAUTOMATION/
├── .coderabbit.yaml               # CodeRabbit AI PR review configuration (Schema v2)
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Automated Ruff linting & pytest matrix (3.11 & 3.12)
│       ├── podcast_shorts_automation.yml # Scheduled Shorts repurposing
│       └── longform_automation.yml       # Scheduled long-form automation
├── assets/
│   ├── mascot/                    # Reusable BENX 2D Mascot rig layers (24 PNG layers)
│   │   ├── character_spec.json    # Character design specifications & color palette
│   │   ├── rig_manifest.json      # Layer manifest with license verification
│   │   ├── head_base.png, visor_plate.png
│   │   ├── eyes_*.png (happy, surprised, confused, serious, excited, sad, blink)
│   │   ├── mouth_*.png (rest, a, o, e, wide)
│   │   ├── torso_*.png (front, three_quarter_left, three_quarter_right)
│   │   └── arms_*.png (idle, gesture, pointing_up, pointing_right, thinking_chin, shrug, cheer)
│   └── license_manifest.yaml      # Commercial rights manifest for graphic assets
├── benxautomation/
│   ├── animation/                 # Mascot 2D engine & story animation pipeline
│   │   ├── mascot_assets.py       # Procedural anti-aliased character asset builder
│   │   ├── mascot_engine.py       # Multi-scene frame compositing & FFmpeg video encoder
│   │   ├── story_pipeline.py      # End-to-end story-to-animation workflow coordinator
│   │   └── motion_validator.py    # Mathematical inter-frame pixel delta validator
│   ├── podcast/                   # Podcast/livestream ingestion, transcription, & highlights
│   ├── repurpose/                 # Vertical reframing, face-tracking, and subtitle burning
│   ├── publisher/
│   │   └── youtube.py             # YouTube OAuth2 manager with strict PRIVATE upload gates
│   └── tts/
│       └── engine.py              # Neural Edge-TTS voiceover synthesizer
├── docs/
│   ├── BENX_MASCOT_DESIGN_SPEC.md # Full mascot character design specification
│   ├── CODERABBIT_SETUP.md        # CodeRabbit installation & PR review workflow guide
│   └── SWEEP_AI_EVALUATION.md     # Deprecation assessment of Sweep AI & alternatives
├── scripts/
│   └── render_mascot_sample.py    # Standalone script to render official mascot sample video
├── tests/                         # Test suite (257 passing tests)
│   └── test_mascot_animation.py   # Comprehensive mascot engine unit & integration tests
├── pyproject.toml                 # Package configuration, Ruff settings, & pytest config
└── requirements.txt               # Pinned dependencies
```

---

## Quickstart (Windows & Cross-Platform)

### 1. Prerequisites
- **Python 3.11 or 3.12**
- **FFmpeg & FFprobe** installed and accessible on your `PATH`.
  ```powershell
  # Check FFmpeg installation
  ffmpeg -version
  ffprobe -version
  ```

### 2. Setup Virtual Environment
```powershell
Set-Location "E:\New folder\BENXAUTOMATION"

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install package and development tools
pip install -r requirements.txt
pip install -e ".[dev]"
```

### 3. Generate Mascot Rig Layers
```powershell
python -c "from benxautomation.animation.mascot_assets import MascotAssetBuilder; MascotAssetBuilder().generate_all()"
```

### 4. Render Sample Mascot Animation Video
Render an official 9:16 vertical animated Short with speech, subtitles, and real character motion:
```powershell
python scripts/render_mascot_sample.py
```
Output files will be generated in `output/mascot_sample/ai_quantum_leap_shorts/`:
- `ai_quantum_leap.mp4` (Full 1080x1920 video with moving character and burned captions)
- `ai_quantum_leap_thumbnail.jpg` (High-res thumbnail)
- `ai_quantum_leap_subtitles.srt` / `.vtt` (Synchronized subtitles)
- `sample_validation_report.json` (FFprobe & MotionValidator metrics)

---

## Story-to-Animation Python API

```python
from pathlib import Path
from benxautomation.animation.story_pipeline import (
    StoryAnimationPipeline,
    LocalStoryScriptCatalog,
    StoryScript,
    MascotScene,
)

# 1. Initialize Pipeline
pipeline = StoryAnimationPipeline(output_dir=Path("output/my_stories"))

# 2. Define or Load a Story
story = StoryScript(
    story_id="cyber_insight",
    title="Understanding Encryption",
    topic="Cybersecurity",
    format="shorts",  # or "longform" (16:9)
    scenes=[
        MascotScene(
            scene_id="s1",
            duration_seconds=3.5,
            dialogue="Modern encryption shields your data using mathematical keys.",
            pose="gesture",
            expression="happy",
            view="front",
            camera_motion="DOLLY_IN_CLOSEUP",
            action_text="SECURE DATA",
        ),
        MascotScene(
            scene_id="s2",
            duration_seconds=3.0,
            dialogue="Never share private keys, and stay curious with BENX!",
            pose="pointing_up",
            expression="excited",
            view="three_quarter_left",
            camera_motion="STATIC_MEDIUM",
            action_text="STAY SAFE",
        ),
    ],
)

# 3. Produce and Validate Animation
result = pipeline.produce_story_animation(story, fps=24)
print(f"Rendered: {result.video_path}")
print(f"Motion score: {result.motion_score}% (Verified: {result.motion_verified})")
```

---

## AI Code Review & Workflow

### CodeRabbit AI
CodeRabbit is integrated via [`.coderabbit.yaml`](.coderabbit.yaml) complying with schema v2.
- **Rules**: Enforces strict Python exception handling, FFmpeg path sanitization, secret leakage prevention, and test additions on regressions.
- **Noise Suppression**: Stylistic formatting debates are muted; reviewers focus on genuine bugs.
- **Setup Guide**: See [`docs/CODERABBIT_SETUP.md`](docs/CODERABBIT_SETUP.md).

### Sweep AI Status & Decision
As documented in [`docs/SWEEP_AI_EVALUATION.md`](docs/SWEEP_AI_EVALUATION.md), Sweep AI's cloud service and GitHub App have been officially discontinued by its creators.
- **Decision**: No abandoned or unmaintained dependencies were installed.
- **Workflow Recommendation**: AI coding assistance is kept developer-driven (e.g., Aider, Claude Code, Cursor) with human-in-the-loop review. Autonomous bots are never granted direct write/merge permissions to `main`.

---

## Testing & Quality Assurance

Run the complete test suite (257 passing tests):
```powershell
pytest -q
```

Run only mascot animation tests:
```powershell
pytest tests/test_mascot_animation.py -v
```

Run Ruff lint check:
```powershell
ruff check .
```

---

## Security & Publishing Controls

- **Zero Secret Leaks**: No tokens, OAuth credentials, or API keys are committed. Configuration uses environment variables or GitHub Secrets.
- **Private-Only Uploads**: The pipeline defaults to `privacy_status: "private"`. Videos are never published publicly without explicit manual review.
- **Duplicate Protection**: SQLite upload ledger prevents re-uploading identical videos or wasting daily API quota.

---

## License

Original code and character designs are licensed under the **MIT License**. All mascot character assets are creator-owned by BENXAUTOMATION.
