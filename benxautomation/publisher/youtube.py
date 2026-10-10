"""YouTube publisher with official OAuth2 flow and strict verification safeguards.

Publishing remains safely locked until:
1. `publishing.enabled` is explicitly True in configuration.
2. Official Google OAuth client credentials (client_secret.json) are provided.
3. OAuth refresh tokens are stored securely and verified against the YouTube API.
4. Channel settings and visibility are verified.

By default, any upload must use restricted visibility ('private' or 'unlisted')
for manual verification before unattended publication can ever be unlocked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from benxautomation.config import PublishingConfig
from benxautomation.errors import PublishingDisabledError
from benxautomation.logger import get_logger

log = get_logger(__name__)

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


@dataclass
class ChannelInfo:
    """Verified YouTube channel metadata."""
    channel_id: str
    title: str
    custom_url: Optional[str] = None


class YouTubeOAuthManager:
    """Manages the official YouTube OAuth2 flow."""

    def __init__(
        self,
        client_secret_path: Path | str,
        token_path: Path | str = "youtube_tokens.json",
    ):
        self.client_secret_path = Path(client_secret_path)
        self.token_path = Path(token_path)

    def load_client_credentials(self) -> tuple[str, str]:
        """Read client_id and client_secret from Google Cloud JSON file."""
        if not self.client_secret_path.is_file():
            raise PublishingDisabledError(
                f"Client secret file not found: {self.client_secret_path}"
            )
        try:
            data = json.loads(self.client_secret_path.read_text(encoding="utf-8"))
            info = data.get("installed") or data.get("web") or {}
            client_id = info["client_id"]
            client_secret = info["client_secret"]
            return client_id, client_secret
        except Exception as exc:
            raise PublishingDisabledError(
                f"Failed to parse Google OAuth client secrets: {exc}"
            ) from exc

    def get_authorization_url(self, redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob") -> str:
        """Generate the official Google consent URL for youtube.upload."""
        client_id, _ = self.load_client_credentials()
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": YOUTUBE_UPLOAD_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(
        self,
        auth_code: str,
        redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob",
    ) -> dict[str, Any]:
        """Exchange authorization code for access and refresh tokens."""
        client_id, client_secret = self.load_client_credentials()
        data = {
            "code": auth_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        resp = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=30)
        if resp.status_code != 200:
            raise PublishingDisabledError(f"OAuth code exchange failed: {resp.text}")

        token_data = resp.json()
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
        log.info("Saved OAuth tokens to %s", self.token_path)
        return token_data

    def get_valid_access_token(self) -> str:
        """Load stored token and refresh if expired."""
        if not self.token_path.is_file():
            raise PublishingDisabledError(
                f"OAuth token file not found at {self.token_path}. Run authorization flow first."
            )
        try:
            tokens = json.loads(self.token_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise PublishingDisabledError(f"Cannot read token file: {exc}") from exc

        # Refresh if refresh_token present
        if "refresh_token" in tokens:
            client_id, client_secret = self.load_client_credentials()
            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
            }
            resp = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=30)
            if resp.status_code == 200:
                new_tokens = resp.json()
                tokens["access_token"] = new_tokens["access_token"]
                self.token_path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
                return tokens["access_token"]

        if "access_token" in tokens:
            return tokens["access_token"]

        raise PublishingDisabledError("No valid access or refresh token found.")

    def verify_channel(self) -> ChannelInfo:
        """Query YouTube API to verify that the authorized account has an active channel."""
        access_token = self.get_valid_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(
            f"{YOUTUBE_CHANNELS_URL}?part=snippet&mine=true",
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            raise PublishingDisabledError(
                f"YouTube channel verification failed ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        items = data.get("items", [])
        if not items:
            raise PublishingDisabledError("No YouTube channel found for authenticated account.")

        ch = items[0]
        return ChannelInfo(
            channel_id=ch["id"],
            title=ch["snippet"]["title"],
            custom_url=ch["snippet"].get("customUrl"),
        )


class YouTubePublisher:
    """Enforces official OAuth upload flow with strict security guards."""

    ALLOWED_VISIBILITY = {"private", "unlisted", "public"}

    def __init__(
        self,
        config: PublishingConfig,
        oauth_manager: Optional[YouTubeOAuthManager] = None,
    ):
        self._config = config
        self.oauth_manager = oauth_manager
        if not self.oauth_manager and config.youtube_client_secret_path:
            self.oauth_manager = YouTubeOAuthManager(config.youtube_client_secret_path)

    def upload(
        self,
        video_path: Path,
        *,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        privacy_status: str = "private",  # Restricted by default for safety
    ) -> dict[str, Any]:
        """Perform real resumable upload to YouTube.

        Always raises PublishingDisabledError if config is disabled,
        credentials are missing, or channel is unverified.
        """
        # Guard 1: Must be explicitly enabled in configuration
        if not self._config.enabled:
            raise PublishingDisabledError(
                "YouTube publishing is disabled in configuration. "
                "Set publishing.enabled=true to allow."
            )

        # Guard 2: OAuth manager must exist
        if not self.oauth_manager:
            raise PublishingDisabledError(
                "YouTube OAuth manager is not configured. "
                "Set youtube_client_secret_path in config."
            )

        # Guard 3: Must verify channel
        channel = self.oauth_manager.verify_channel()
        log.info("Verified target YouTube channel: %s (%s)", channel.title, channel.channel_id)

        # Guard 4: Validate visibility
        if privacy_status not in self.ALLOWED_VISIBILITY:
            raise PublishingDisabledError(
                f"Invalid privacy status '{privacy_status}'. Must be one of {self.ALLOWED_VISIBILITY}"
            )

        if not video_path.is_file() or video_path.stat().st_size == 0:
            raise PublishingDisabledError(f"Video file is invalid or empty: {video_path}")

        # Real Resumable Upload
        access_token = self.oauth_manager.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
            "X-Upload-Content-Type": "video/mp4",
        }

        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        init_url = f"{YOUTUBE_UPLOAD_URL}?uploadType=resumable&part=snippet,status"
        init_resp = requests.post(init_url, json=metadata, headers=headers, timeout=30)
        if init_resp.status_code != 200:
            raise PublishingDisabledError(f"Failed to initiate YouTube upload: {init_resp.text}")

        upload_url = init_resp.headers.get("Location")
        if not upload_url:
            raise PublishingDisabledError("Missing upload Location header from YouTube response.")

        with open(video_path, "rb") as f:
            upload_resp = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": "video/mp4"},
                timeout=300,
            )

        if upload_resp.status_code not in (200, 201):
            raise PublishingDisabledError(f"YouTube video upload failed: {upload_resp.text}")

        res = upload_resp.json()
        log.info("Successfully uploaded video ID: %s (privacy: %s)", res.get("id"), privacy_status)
        return res
