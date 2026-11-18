# BENXAUTOMATION Video Production Skill

This folder is a draft Agensi skill package. It guides an agent through an existing BENXAUTOMATION installation; it does not bundle the video engine.

## Package contents

- `SKILL.md`: agent instructions and required Agensi frontmatter.
- `references/feature-map.md`: supported workflow map and CLI entry points.
- `scripts/preflight.py`: standalone, standard-library environment check.

## Buyer prerequisites

- Existing BENXAUTOMATION checkout or installed package.
- Python 3.11 or 3.12.
- FFmpeg and FFprobe available on PATH.
- Local disk space for source media and rendered videos.

## Important limitation

Agensi delivers text files through its skill marketplace. The full BENXAUTOMATION repository includes Python application code, media assets, and external runtime dependencies, so this skill deliberately does not claim to distribute or install that application. See the project repository for the separate software and setup instructions.

## Build the ZIP

From the repository root:

```bash
python scripts/build_agensi_skill.py
```

The ZIP is written to `dist/benxautomation-video-production.zip`. It contains one top-level folder named `benxautomation-video-production`.
