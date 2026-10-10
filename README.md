# BENXAUTOMATION
Modular AI-powered YouTube automation for Shorts, long-form videos, multilingual dubbing, thumbnails, metadata, copyright tracking and scheduled publishing.

---

## Overview

BENXAUTOMATION is a modular, extensible framework for automated YouTube video creation. It is designed to safely handle the lifecycle of video generation:
- Configuration validation (Pydantic v2)
- Asset verification and license tracking
- Pluggable video rendering (Shorts 9:16 and Long-form 16:9 via FFmpeg)
- Metadata & language registry (ready to expand to 20+ languages)
- Protected YouTube publishing interface (disabled until OAuth is configured)

---

## Project Structure

```
BENXAUTOMATION/
├── .github/
│   └── workflows/
│       └── ci.yml                    # Automated pytest execution on GitHub Actions
├── assets/
│   └── .gitkeep                      # Assets directory (images, audio, video)
├── benxautomation/
│   ├── __init__.py                   # Package version & metadata
│   ├── config.py                     # Pydantic configuration schemas & validation
│   ├── logger.py                     # Structured JSON logging
│   ├── errors.py                     # Exception hierarchy
│   ├── asset_manifest.py             # Asset license manifest parsing & checks
│   ├── pipeline.py                   # High-level pipeline coordinator
│   ├── main.py                       # CLI entrypoint
│   ├── renderer/
│   │   ├── __init__.py
│   │   ├── base.py                   # Abstract RendererPlugin & RenderResult
│   │   ├── ffmpeg_utils.py           # Subprocess wrapper & ffprobe inspection
│   │   ├── shorts_plugin.py          # 9:16 portrait video rendering plugin
│   │   └── longform_plugin.py        # 16:9 landscape video rendering plugin
│   ├── publisher/
│   │   ├── __init__.py
│   │   └── youtube.py                # YouTube publisher stub (OAuth guard-rail)
│   └── i18n/
│       ├── __init__.py
│       └── registry.py               # Multilingual registry (designed for 20+ languages)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures & FFmpeg detection
│   ├── test_config.py                # Config validation tests
│   ├── test_asset_manifest.py        # License manifest validation tests
│   ├── test_renderer_base.py         # Plugin interface contract tests
│   ├── test_ffmpeg_utils.py          # FFmpeg and probe tests
│   ├── test_shorts_plugin.py         # Shorts rendering tests
│   ├── test_longform_plugin.py       # Long-form rendering tests
│   ├── test_publisher.py             # YouTube publisher safety guard tests
│   ├── test_i18n.py                  # Language registry tests
│   ├── test_logger.py                # JSON logger tests
│   └── test_pipeline.py              # Pipeline integration tests
├── config.example.yaml               # Example configuration without secrets
├── pyproject.toml                     # Build setup, dependencies, pytest configuration
├── requirements.txt                   # Production and dev dependencies
└── README.md                          # Project documentation
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
