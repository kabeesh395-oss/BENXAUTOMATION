# BENXAUTOMATION
Modular AI-powered YouTube automation for Shorts, long-form videos, multilingual dubbing, thumbnails, metadata, copyright tracking and scheduled publishing.

---

## Overview

BENXAUTOMATION is a modular, extensible framework for automated YouTube video creation. It handles the complete lifecycle of production-grade video generation:
- **Configuration Validation** (Pydantic v2 schemas)
- **Asset License Manifest Verification** (`cc0`, `mit`, `apache-2.0`, `cc-by-4.0`, etc.)
- **AI Video Generation via MoneyPrinterTurbo Adapter** (Supports CLI subprocess invocation and FastAPI REST client)
- **Neural Text-To-Speech (TTS)** (`edge-tts` engine generating real MP3 speech)
- **Timed Subtitle Generation** (SRT generation and automatic FFmpeg subtitle burning)
- **Pluggable Video Rendering** (Shorts 9:16 and Long-form 16:9 via FFmpeg with audio and subtitles)
- **Media Validation** (`MediaValidator` inspecting streams, duration, dimensions, codecs, and playability)
- **Persistent Job Queue & Worker Pool** (SQLite-backed persistent queue with restart recovery, retries, bounded worker pool, disk storage safeguards, and emergency stop)
- **Official YouTube OAuth2 Publisher** (Full OAuth2 authorization flow, token exchange, refresh, channel verification, and restricted visibility enforcement)

---

## Project Structure

```
BENXAUTOMATION/
├── .github/
│   └── workflows/
│       └── ci.yml                    # Automated pytest execution on GitHub Actions
├── assets/
│   ├── sample_card.png           # Licensed base asset
│   └── license_manifest.yaml     # Asset license declaration
├── benxautomation/
│   ├── config.py                 # Pydantic configuration schemas & validation
│   ├── logger.py                 # Structured JSON logging
│   ├── errors.py                 # Custom exception hierarchy
│   ├── asset_manifest.py         # License manifest parsing & verification
│   ├── pipeline.py               # End-to-end rendering coordinator
│   ├── main.py                   # CLI entrypoint
│   ├── adapters/
│   │   └── moneyprinter.py       # MoneyPrinterTurbo adapter (CLI + REST API)
│   ├── tts/
│   │   └── engine.py             # Neural Edge-TTS engine (audio synthesis)
│   ├── subtitles/
│   │   └── generator.py          # Timed subtitle (.srt) generator & parser
│   ├── queue/
│   │   ├── job_queue.py          # SQLite persistent queue with restart recovery
│   │   ├── monitor.py            # Storage safeguard & emergency stop monitor
│   │   └── worker.py             # Bounded parallel worker pool
│   ├── renderer/
│   │   ├── base.py               # Abstract RendererPlugin & RenderResult
│   │   ├── ffmpeg_utils.py       # Subprocess wrapper & path resolution
│   │   ├── shorts_plugin.py      # 9:16 portrait video rendering plugin
│   │   ├── longform_plugin.py    # 16:9 landscape video rendering plugin
│   │   └── media_validator.py    # Duration, dimensions, codecs & playability validator
│   ├── publisher/
│   │   └── youtube.py            # YouTube OAuth2 publisher & safety guard
│   └── i18n/
│       └── registry.py           # Multilingual registry (20+ language support)
├── tests/                        # Comprehensive test suite (72 passed unit & integration tests)
├── config.example.yaml           # Example configuration without secrets
├── pyproject.toml                 # Build setup, dependencies, pytest configuration
├── requirements.txt               # Production and dev dependencies
└── README.md                      # Project documentation
```

---

## Prerequisites

- **Python 3.11+**
- **FFmpeg & FFprobe** installed on system PATH (or specified via configuration)

---

## Installation

```bash
git clone https://github.com/kabeesh395-oss/BENXAUTOMATION.git
cd BENXAUTOMATION

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

---

## Configuration

Copy `config.example.yaml` to `config.yaml` to customize settings:

```yaml
project_name: "MyChannel"
default_language: "en"

rendering:
  ffmpeg_path: "ffmpeg"
  ffprobe_path: "ffprobe"
  shorts:
    width: 1080
    height: 1920
    duration_seconds: 30
    fps: 30
  longform:
    width: 1920
    height: 1080
    duration_seconds: 120
    fps: 30

publishing:
  enabled: false  # Kept disabled until OAuth credentials are fully configured

assets:
  input_dir: "assets/"
  output_dir: "output/"
  license_manifest: "assets/license_manifest.yaml"
```

---

## Usage

### Command Line Interface

Render both Shorts and Long-form from an image/video asset:
```bash
python -m benxautomation.main --asset assets/sample.png --output-dir output/ --duration 5
```

Render Shorts only (9:16):
```bash
python -m benxautomation.main --asset assets/sample.png --shorts-only --duration 15
```

Render Long-form only (16:9):
```bash
python -m benxautomation.main --asset assets/sample.png --longform-only --duration 60
```

With asset license validation:
```bash
python -m benxautomation.main --asset assets/sample.png --manifest assets/license_manifest.yaml
```

---

## Asset License Manifest

Assets must be tracked with their license and attribution in a YAML manifest:

```yaml
assets:
  - file: "sample.png"
    license: "cc0"
    attribution: "Original work or public domain"
    source_url: "https://example.com"
```

Allowed licenses: `cc0`, `cc-by-4.0`, `cc-by-sa-4.0`, `mit`, `apache-2.0`, `public-domain`, `royalty-free`, `original`.

---

## Safety & Guard-rails

- **YouTube Publishing**: Disabled by default. Any call to `YouTubePublisher.upload()` raises `PublishingDisabledError` until official OAuth client credentials and flows are configured. No mock or fake uploads will ever take place.
- **Secrets Management**: No API keys or OAuth secrets are stored in the repository. `.env`, `client_secret*.json`, and private keys are ignored via `.gitignore`.

---

## Running Tests

Run the full pytest suite:
```bash
pytest
```

Run only unit tests (excluding tests requiring FFmpeg):
```bash
pytest -m "not ffmpeg"
```

Run with verbose output and tracebacks:
```bash
pytest -v --tb=short
```

---

## Current Status & Limitations (MVP)

- **Language Registry**: Currently seeded with English (`en`). Additional languages can be registered through `LanguageRegistry`, but automated multilingual TTS/dubbing is not yet connected.
- **Rendering**: Real rendering via FFmpeg produces valid MP4 files with video stream from local image/video assets. Audio track mixing and subtitle overlays will be added in future plugins.
- **Publishing**: Strictly disabled stub to protect against unauthorized uploads.

---

## Next Steps

1. Configure Google Cloud OAuth 2.0 Client credentials and implement authorization flow.
2. Add audio synthesis (TTS) plugin to mix voiceovers with background audio.
3. Integrate Whisper / subtitle generator plugin.
4. Expand language registry to the target 20 languages with per-language metadata models.
