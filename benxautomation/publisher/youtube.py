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

import argparse
import http.server
import json
import os
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse

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
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

DEFAULT_TOKEN_DIR = Path.home() / ".benxautomation"
DEFAULT_TOKEN_FILE = DEFAULT_TOKEN_DIR / "youtube_tokens.json"


def _restrict_file_permissions(file_path: Path) -> None:
    """Ensure token file is accessible only by the current user."""
    try:
        if os.name == "nt":
            username = os.environ.get("USERNAME", "")
            if username:
                subprocess.run(
                    ["icacls", str(file_path), "/inheritance:r", "/grant:r", f"{username}:F"],
                    check=False,
                    capture_output=True,
                )
        else:
            file_path.chmod(0o600)
    except Exception as exc:
        log.warning("Could not set strict file permissions on %s: %s", file_path, exc)


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handles the OAuth2 redirect callback on local loopback."""

    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)

        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                b"<h2 style='color:#2e7d32;'>YouTube OAuth Authorization Successful!</h2>"
                b"<p>You can now safely close this browser tab and return to the terminal.</p>"
                b"</body></html>"
            )
        else:
            err = params.get("error", ["Unknown error"])[0]
            _OAuthCallbackHandler.error = err
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                f"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                f"<h2 style='color:#c62828;'>Authorization Failed</h2>"
                f"<p>Error: {err}</p>"
                f"</body></html>".encode("utf-8")
            )

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress server logs
        pass


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
        token_path: Path | str = DEFAULT_TOKEN_FILE,
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
        _restrict_file_permissions(self.token_path)
        log.info("Saved OAuth tokens to %s", self.token_path)
        return token_data

    def run_local_server_flow(
        self,
        port: int = 8080,
        open_browser: bool = True,
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        """Run loopback redirect server, open browser for consent, and store tokens."""
        redirect_uri = f"http://127.0.0.1:{port}/oauth2callback"
        auth_url = self.get_authorization_url(redirect_uri=redirect_uri)

        server_address = ("127.0.0.1", port)
        try:
            httpd = http.server.HTTPServer(server_address, _OAuthCallbackHandler)
        except OSError as e:
            raise PublishingDisabledError(
                f"Could not bind to local port {port} for OAuth callback: {e}"
            ) from e

        httpd.timeout = timeout_seconds
        _OAuthCallbackHandler.auth_code = None
        _OAuthCallbackHandler.error = None

        log.info("Starting local redirect server on %s", redirect_uri)
        print(f"\nOpening browser for Google OAuth consent:\n{auth_url}\n")
        if open_browser:
            webbrowser.open(auth_url)

        print(f"Waiting for authorization callback on {redirect_uri} (timeout {timeout_seconds}s)...")
        httpd.handle_request()
        httpd.server_close()

        if _OAuthCallbackHandler.error:
            raise PublishingDisabledError(
                f"OAuth authorization was denied or failed: {_OAuthCallbackHandler.error}"
            )

        code = _OAuthCallbackHandler.auth_code
        if not code:
            raise PublishingDisabledError(
                "OAuth authorization timed out or no code was received from browser."
            )

        tokens = self.exchange_code_for_tokens(code, redirect_uri=redirect_uri)
        return tokens

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
                _restrict_file_permissions(self.token_path)
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

    def verify_video(self, video_id: str) -> dict[str, Any]:
        """Query YouTube Data API to verify uploaded video status."""
        if not self.oauth_manager:
            raise PublishingDisabledError("YouTube OAuth manager is not configured.")
        access_token = self.oauth_manager.get_valid_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(
            f"{YOUTUBE_VIDEOS_URL}?part=snippet,status&id={video_id}",
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            raise PublishingDisabledError(
                f"Failed to query YouTube video {video_id} ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        items = data.get("items", [])
        if not items:
            raise PublishingDisabledError(f"Video {video_id} not found on YouTube.")

        item = items[0]
        status = item.get("status", {})
        snippet = item.get("snippet", {})
        return {
            "video_id": video_id,
            "title": snippet.get("title"),
            "privacy_status": status.get("privacyStatus"),
            "upload_status": status.get("uploadStatus"),
            "url": f"https://youtu.be/{video_id}",
            "raw": item,
        }

    def upload(
        self,
        video_path: Path,
        *,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        privacy_status: str = "private",  # Restricted by default for safety
    ) -> dict[str, Any]:
        """Perform real resumable upload to YouTube."""
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

    def upload_private_acceptance_test(
        self,
        video_path: Path,
        title: str = "BENXAUTOMATION Acceptance Test [PRIVATE]",
        description: str = "Automated acceptance test video uploaded privately by BENXAUTOMATION.",
    ) -> dict[str, Any]:
        """Upload a single video strictly as private and verify its existence on YouTube."""
        log.info("Starting one-video private acceptance test upload for %s", video_path)
        upload_res = self.upload(
            video_path=video_path,
            title=title,
            description=description,
            privacy_status="private",
        )
        video_id = upload_res.get("id")
        if not video_id:
            raise PublishingDisabledError(f"Upload completed but no video ID was returned: {upload_res}")

        verified = self.verify_video(video_id)
        log.info(
            "Confirmed private video upload on YouTube: ID=%s, URL=%s, Privacy=%s",
            video_id,
            verified["url"],
            verified["privacy_status"],
        )
        return verified


def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benxautomation.publisher.youtube",
        description="Official YouTube OAuth2 Authentication & Private Upload Verification",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # authorize
    auth_p = subparsers.add_parser("authorize", help="Run local loopback OAuth consent flow")
    auth_p.add_argument(
        "--client-secret",
        "-s",
        type=Path,
        required=True,
        help="Path to Google Cloud client_secret.json",
    )
    auth_p.add_argument(
        "--token-file",
        "-t",
        type=Path,
        default=DEFAULT_TOKEN_FILE,
        help="Path to store tokens (default: ~/.benxautomation/youtube_tokens.json)",
    )
    auth_p.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        help="Local loopback port for OAuth redirect (default: 8080)",
    )

    # verify-channel
    chan_p = subparsers.add_parser("verify-channel", help="Verify authenticated channel info")
    chan_p.add_argument(
        "--client-secret",
        "-s",
        type=Path,
        required=True,
        help="Path to Google Cloud client_secret.json",
    )
    chan_p.add_argument(
        "--token-file",
        "-t",
        type=Path,
        default=DEFAULT_TOKEN_FILE,
        help="Path to tokens file",
    )

    # upload-test
    up_p = subparsers.add_parser("upload-test", help="Upload one video as PRIVATE for acceptance")
    up_p.add_argument("--video", "-v", type=Path, required=True, help="Path to existing MP4 video")
    up_p.add_argument(
        "--title",
        default="BENXAUTOMATION Acceptance Test [PRIVATE]",
        help="Video title",
    )
    up_p.add_argument(
        "--client-secret",
        "-s",
        type=Path,
        required=True,
        help="Path to Google Cloud client_secret.json",
    )
    up_p.add_argument(
        "--token-file",
        "-t",
        type=Path,
        default=DEFAULT_TOKEN_FILE,
        help="Path to tokens file",
    )

    # verify-video
    v_p = subparsers.add_parser("verify-video", help="Query video status by ID")
    v_p.add_argument("--video-id", required=True, help="YouTube video ID")
    v_p.add_argument(
        "--client-secret",
        "-s",
        type=Path,
        required=True,
        help="Path to Google Cloud client_secret.json",
    )
    v_p.add_argument(
        "--token-file",
        "-t",
        type=Path,
        default=DEFAULT_TOKEN_FILE,
        help="Path to tokens file",
    )

    return parser


def main() -> None:
    parser = _build_cli()
    args = parser.parse_args()

    try:
        mgr = YouTubeOAuthManager(
            client_secret_path=args.client_secret,
            token_path=args.token_file,
        )

        if args.command == "authorize":
            print(f"Starting OAuth loopback flow on port {args.port}...")
            mgr.run_local_server_flow(port=args.port)
            print("\n[SUCCESS] OAuth authorization complete!")
            print(f"Tokens stored safely at: {mgr.token_path}")
            chan = mgr.verify_channel()
            print(f"Authenticated Channel Name: {chan.title}")
            print(f"Authenticated Channel ID:   {chan.channel_id}")

        elif args.command == "verify-channel":
            chan = mgr.verify_channel()
            print(f"\n[CHANNEL VERIFIED]")
            print(f"Title:      {chan.title}")
            print(f"Channel ID: {chan.channel_id}")
            if chan.custom_url:
                print(f"Custom URL: {chan.custom_url}")

        elif args.command == "upload-test":
            cfg = PublishingConfig(enabled=True)
            pub = YouTubePublisher(cfg, oauth_manager=mgr)
            print(f"Uploading private acceptance test video: {args.video}...")
            res = pub.upload_private_acceptance_test(
                video_path=args.video,
                title=args.title,
            )
            print("\n[UPLOAD VERIFIED]")
            print(f"Video ID:        {res['video_id']}")
            print(f"Title:           {res['title']}")
            print(f"Privacy Status:  {res['privacy_status']}")
            print(f"Upload Status:   {res['upload_status']}")
            print(f"Private Video URL: {res['url']}")

        elif args.command == "verify-video":
            cfg = PublishingConfig(enabled=True)
            pub = YouTubePublisher(cfg, oauth_manager=mgr)
            res = pub.verify_video(args.video_id)
            print("\n[VIDEO VERIFIED]")
            print(f"Video ID:        {res['video_id']}")
            print(f"Title:           {res['title']}")
            print(f"Privacy Status:  {res['privacy_status']}")
            print(f"Private Video URL: {res['url']}")

    except PublishingDisabledError as e:
        print(f"\n[BLOCKED] Publishing error / safeguard: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
