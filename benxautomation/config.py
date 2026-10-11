"""Configuration model with Pydantic validation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from benxautomation.errors import ConfigurationError


# ── Sub-models ──────────────────────────────────────────────────────

class ShortsConfig(BaseModel):
    """Rendering parameters for YouTube Shorts (9:16 portrait)."""
    width: int = 1080
    height: int = 1920
    duration_seconds: int = Field(default=30, gt=0, le=60)
    fps: int = Field(default=30, gt=0)


class LongformConfig(BaseModel):
    """Rendering parameters for long-form videos (16:9 landscape)."""
    width: int = 1920
    height: int = 1080
    duration_seconds: int = Field(default=120, gt=0)
    fps: int = Field(default=30, gt=0)


class RenderingConfig(BaseModel):
    """FFmpeg and rendering settings."""
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    shorts: ShortsConfig = ShortsConfig()
    longform: LongformConfig = LongformConfig()


class PublishingConfig(BaseModel):
    """YouTube publishing settings."""
    enabled: bool = False
    youtube_client_secret_path: Optional[str] = None
    enforce_private: bool = False  # Set to True only when strictly enforcing private-only testing
    default_privacy: str = "public"  # "public", "private", "unlisted"
    auto_upload_private: bool = False  # Automatically upload verified videos
    upload_ledger_path: Optional[str] = None



class AssetsConfig(BaseModel):
    """Asset directories and manifest path."""
    input_dir: str = "assets/"
    output_dir: str = "output/"
    license_manifest: Optional[str] = None


class ScriptConfig(BaseModel):
    """Configuration for AI and fallback script generation."""
    provider: str = "auto"  # "auto", "gemini", "openai", "fallback"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    base_url_env: str = "OPENAI_BASE_URL"
    gemini_model: str = "gemini-3.5-flash"
    gemini_api_key_env: str = "GEMINI_API_KEY"
    temperature: float = 0.4
    timeout_seconds: int = 30
    default_target_audience: str = "general audience"
    default_tone: str = "engaging and informative"



class AudioMixingConfig(BaseModel):
    """Configuration for audio mixing and background music."""
    music_enabled: bool = True
    music_volume: float = 0.15
    default_bgm_path: Optional[str] = None


# ── Root config ─────────────────────────────────────────────────────

class AppConfig(BaseModel):
    """Top-level application configuration."""
    project_name: str = "BENXAUTOMATION"
    default_language: str = "en"
    rendering: RenderingConfig = RenderingConfig()
    publishing: PublishingConfig = PublishingConfig()
    assets: AssetsConfig = AssetsConfig()
    script: ScriptConfig = ScriptConfig()
    audio: AudioMixingConfig = AudioMixingConfig()

    @field_validator("default_language")
    @classmethod
    def _validate_language_code(cls, v: str) -> str:
        if not v or len(v) < 2:
            raise ValueError("default_language must be a valid BCP-47 code (e.g. 'en')")
        return v.lower()


def load_config(path: Path | str) -> AppConfig:
    """Load and validate a YAML config file.

    Raises ``ConfigurationError`` if the file is missing or invalid.
    """
    path = Path(path)
    if not path.is_file():
        raise ConfigurationError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            raw = {}
        return AppConfig(**raw)
    except Exception as exc:
        raise ConfigurationError(f"Invalid config: {exc}") from exc
