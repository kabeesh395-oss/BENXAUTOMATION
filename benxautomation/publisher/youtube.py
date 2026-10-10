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
from benxautomation.errors import DuplicateUploadError, PublishingDisabledError
from benxautomation.logger import get_logger
from benxautomation.publisher.ledger import (
    DEFAULT_LEDGER_FILE,
    UploadLedger,
    UploadRecord,
)

log = get_logger(__name__)

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
DEFAULT_YOUTUBE_SCOPES = [
    YOUTUBE_UPLOAD_SCOPE,
    YOUTUBE_READONLY_SCOPE,
]
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


def check_scopes_sufficient(
    granted_scopes: set[str],
    required_scopes: list[str],
) -> tuple[bool, list[str]]:
    """Verify if granted scopes fulfill the required scopes.

    Returns (is_sufficient, missing_scopes).
    Broad administrative scopes (e.g. 'https://www.googleapis.com/auth/youtube' or
    'https://www.googleapis.com/auth/youtube.force-ssl') satisfy all narrower scopes.
    """
    full_scopes = {
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    }
    if full_scopes.intersection(granted_scopes):
        return True, []

    missing = [req for req in required_scopes if req not in granted_scopes]
    return len(missing) == 0, missing


class YouTubeOAuthManager:
    """Manages the official YouTube OAuth2 flow."""

    def __init__(
        self,
        client_secret_path: Path | str,
        token_path: Path | str = DEFAULT_TOKEN_FILE,
        scopes: Optional[list[str]] = None,
    ):
        self.client_secret_path = Path(client_secret_path)
        self.token_path = Path(token_path)
        self.scopes = list(scopes) if scopes is not None else list(DEFAULT_YOUTUBE_SCOPES)

    def _safe_backup_insufficient_token(self, reason: str) -> Path:
        """Back up an invalid or insufficient token file safely without printing its contents."""
        bak_path = self.token_path.with_name(self.token_path.name + ".bak")
        try:
            if self.token_path.exists():
                self.token_path.replace(bak_path)
                _restrict_file_permissions(bak_path)
                log.warning(
                    "Backed up insufficient token file '%s' -> '%s' (%s)",
                    self.token_path.name,
                    bak_path.name,
                    reason,
                )
                return bak_path
        except Exception as exc:
            log.warning("Could not rename token file to backup %s: %s", bak_path, exc)
            try:
                self.token_path.unlink(missing_ok=True)
            except Exception:
                pass
        return bak_path

    def handle_scope_error_if_any(self, resp: requests.Response, operation: str = "YouTube API") -> None:
        """Check if HTTP response indicates insufficient OAuth scope and invalidate token safely."""
        if resp.status_code == 403 and (
            "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in resp.text
            or "insufficientpermissions" in resp.text.lower()
            or "insufficient scope" in resp.text.lower()
        ):
            bak_path = self._safe_backup_insufficient_token(f"403 scope error on {operation}")
            reauth_cmd = (
                f'python -m benxautomation.publisher.youtube authorize --client-secret "{self.client_secret_path}"'
            )
            raise PublishingDisabledError(
                f"{operation} failed with 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT. "
                f"The token does not grant the required scopes. "
                f"The insufficient token has been safely backed up to '{bak_path.name}'. "
                f"Please reauthorize by running:\n  {reauth_cmd}"
            )

    @classmethod
    def resolve_client_secret_file(cls, path: Path | str) -> Path:
        """Resolve client secret file, supporting direct file path or directory containing client_secret_*.json."""
        target = Path(path)
        if target.is_file():
            return target
        if target.is_dir():
            candidates = [
                f for f in target.iterdir()
                if f.is_file() and f.suffix.lower() == ".json" and ("client_secret" in f.name.lower() or "credentials" in f.name.lower())
            ]
            if len(candidates) == 1:
                log.info("Resolved client secret JSON inside directory %s -> %s", target, candidates[0].name)
                return candidates[0]
            elif len(candidates) > 1:
                candidate_names = [c.name for c in candidates]
                raise PublishingDisabledError(
                    f"Directory '{target}' contains multiple candidate credential files: {candidate_names}. "
                    f"Please specify the exact file path."
                )
            else:
                raise PublishingDisabledError(
                    f"Path '{target}' is a directory but contains no client_secret*.json files. "
                    f"Please download the OAuth 2.0 Desktop app JSON from Google Cloud Console."
                )
        raise PublishingDisabledError(
            f"Client secret file not found: {target}. "
            f"Please download the OAuth 2.0 Desktop app JSON from Google Cloud Console."
        )

    def load_client_credentials(self) -> tuple[str, str]:
        """Read and validate client_id and client_secret from Google Cloud Desktop OAuth JSON."""
        resolved_path = self.resolve_client_secret_file(self.client_secret_path)
        try:
            content = resolved_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PublishingDisabledError(
                f"Failed to parse Google OAuth client secrets (invalid JSON in {resolved_path.name}): {exc}"
            ) from exc
        except Exception as exc:
            raise PublishingDisabledError(
                f"Failed to read Google OAuth client secrets from {resolved_path}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise PublishingDisabledError(
                "Invalid Google OAuth client secrets format: Top-level JSON must be an object."
            )

        if "installed" in data:
            info = data["installed"]
        elif "web" in data:
            raise PublishingDisabledError(
                f"Invalid Google OAuth client type: Found 'web' client credentials in {resolved_path.name}. "
                f"BENXAUTOMATION requires a 'Desktop app' OAuth Client ID. "
                f"Please create an OAuth 2.0 Client ID of type 'Desktop app' in Google Cloud Console."
            )
        else:
            raise PublishingDisabledError(
                f"Invalid Google OAuth credentials JSON: Missing 'installed' key in {resolved_path.name}. "
                f"Please download Desktop app OAuth client credentials from Google Cloud Console."
            )

        client_id = info.get("client_id")
        client_secret = info.get("client_secret")

        if not client_id or not isinstance(client_id, str) or not client_id.strip():
            raise PublishingDisabledError(
                f"Invalid Google OAuth credentials: 'client_id' is missing or empty in {resolved_path.name}."
            )

        if not client_secret or not isinstance(client_secret, str) or not client_secret.strip():
            raise PublishingDisabledError(
                f"Invalid Google OAuth credentials: 'client_secret' is missing or empty in {resolved_path.name}."
            )

        return client_id.strip(), client_secret.strip()

    def get_authorization_url(
        self,
        redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob",
        scopes: Optional[list[str]] = None,
    ) -> str:
        """Generate the official Google consent URL requesting required YouTube scopes."""
        client_id, _ = self.load_client_credentials()
        target_scopes = scopes if scopes is not None else self.scopes
        scope_str = " ".join(target_scopes)
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope_str,
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
        scopes: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Run loopback redirect server, open browser for consent, and store tokens."""
        redirect_uri = f"http://127.0.0.1:{port}/oauth2callback"
        auth_url = self.get_authorization_url(redirect_uri=redirect_uri, scopes=scopes)

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

    def get_valid_access_token(self, required_scopes: Optional[list[str]] = None) -> str:
        """Load stored token, verify scopes, and refresh if expired."""
        if not self.token_path.is_file():
            raise PublishingDisabledError(
                f"OAuth token file not found at {self.token_path}. Run authorization flow first."
            )
        try:
            tokens = json.loads(self.token_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise PublishingDisabledError(f"Cannot read token file: {exc}") from exc

        req_scopes = required_scopes if required_scopes is not None else self.scopes

        # 1. Proactively check granted scopes if recorded in stored token
        if "scope" in tokens and isinstance(tokens["scope"], str):
            granted = set(tokens["scope"].split())
            sufficient, missing = check_scopes_sufficient(granted, req_scopes)
            if not sufficient:
                bak_path = self._safe_backup_insufficient_token(f"missing scopes: {missing}")
                reauth_cmd = (
                    f'python -m benxautomation.publisher.youtube authorize --client-secret "{self.client_secret_path}"'
                )
                missing_str = ", ".join(missing)
                raise PublishingDisabledError(
                    f"Stored YouTube OAuth token at '{self.token_path.name}' has insufficient scopes "
                    f"(missing: {missing_str}). "
                    f"The insufficient token has been safely backed up to '{bak_path.name}'. "
                    f"Please reauthorize with required scopes by running:\n  {reauth_cmd}"
                )

        # 2. Refresh if refresh_token present
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
                if "scope" in new_tokens:
                    tokens["scope"] = new_tokens["scope"]

                # Validate scope on refreshed response if available
                if "scope" in tokens and isinstance(tokens["scope"], str):
                    granted = set(tokens["scope"].split())
                    sufficient, missing = check_scopes_sufficient(granted, req_scopes)
                    if not sufficient:
                        bak_path = self._safe_backup_insufficient_token(f"missing scopes after refresh: {missing}")
                        reauth_cmd = (
                            f'python -m benxautomation.publisher.youtube authorize --client-secret "{self.client_secret_path}"'
                        )
                        missing_str = ", ".join(missing)
                        raise PublishingDisabledError(
                            f"Refreshed YouTube OAuth token has insufficient scopes (missing: {missing_str}). "
                            f"The insufficient token has been safely backed up to '{bak_path.name}'. "
                            f"Please reauthorize with required scopes by running:\n  {reauth_cmd}"
                        )

                self.token_path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
                _restrict_file_permissions(self.token_path)
                return tokens["access_token"]
            elif resp.status_code == 400 and ("invalid_grant" in resp.text or "revoked" in resp.text.lower()):
                bak_path = self._safe_backup_insufficient_token("refresh token invalid_grant")
                reauth_cmd = (
                    f'python -m benxautomation.publisher.youtube authorize --client-secret "{self.client_secret_path}"'
                )
                raise PublishingDisabledError(
                    f"OAuth refresh token is invalid or revoked. "
                    f"The token was backed up to '{bak_path.name}'. "
                    f"Please reauthorize by running:\n  {reauth_cmd}"
                )

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
            self.handle_scope_error_if_any(resp, "YouTube channel verification")
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
    """Enforces official OAuth upload flow with strict security guards and persistent upload ledger."""

    ALLOWED_VISIBILITY = {"private", "unlisted", "public"}

    def __init__(
        self,
        config: PublishingConfig,
        oauth_manager: Optional[YouTubeOAuthManager] = None,
        ledger: Optional[UploadLedger] = None,
    ):
        self._config = config
        self.oauth_manager = oauth_manager
        if not self.oauth_manager and config.youtube_client_secret_path:
            self.oauth_manager = YouTubeOAuthManager(config.youtube_client_secret_path)

        if ledger is not None:
            self.ledger = ledger
        elif config.upload_ledger_path:
            self.ledger = UploadLedger(config.upload_ledger_path)
        else:
            self.ledger = UploadLedger(DEFAULT_LEDGER_FILE)

    def _probe_resumable_session(
        self,
        session_uri: str,
        file_size: int,
        access_token: str,
    ) -> dict[str, Any]:
        """Query Google Resumable Upload session status using Content-Range: bytes */file_size."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Range": f"bytes */{file_size}",
        }
        try:
            resp = requests.put(session_uri, headers=headers, timeout=30)
            if resp.status_code in (200, 201):
                # Upload was already completely received and created on YouTube
                data = resp.json()
                return {"status": "COMPLETED", "video_id": data.get("id"), "raw": data}
            elif resp.status_code == 308:
                # Resume incomplete; extract bytes received so far
                range_header = resp.headers.get("Range")
                if range_header and range_header.startswith("bytes=0-"):
                    last_byte = int(range_header.split("-")[1])
                    return {"status": "RESUMABLE", "bytes_received": last_byte + 1}
                return {"status": "RESUMABLE", "bytes_received": 0}
            else:
                return {"status": "EXPIRED", "reason": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as exc:
            return {"status": "ERROR", "reason": str(exc)}

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
            if self.oauth_manager:
                self.oauth_manager.handle_scope_error_if_any(resp, f"YouTube video verification ({video_id})")
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
        allow_duplicate: bool = False,
        raise_on_duplicate: bool = False,
    ) -> dict[str, Any]:
        """Perform resumable upload with duplicate ledger checks and crash recovery."""
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

        # Guard 3: Validate visibility
        if privacy_status not in self.ALLOWED_VISIBILITY:
            raise PublishingDisabledError(
                f"Invalid privacy status '{privacy_status}'. Must be one of {self.ALLOWED_VISIBILITY}"
            )

        # Guard 4: Enforce private-only during acceptance testing
        if self._config.enforce_private and privacy_status != "private":
            raise PublishingDisabledError(
                f"Publishing with visibility '{privacy_status}' is blocked by safety guard. "
                f"Acceptance testing strictly enforces private-only uploads (enforce_private=True). "
                f"Public or unlisted publishing is prohibited."
            )

        # Guard 5: Validate video file existence and non-zero size
        if not video_path.is_file() or video_path.stat().st_size == 0:
            raise PublishingDisabledError(f"Video file is invalid or empty: {video_path}")

        file_size = video_path.stat().st_size
        content_hash = self.ledger.compute_file_hash(video_path)

        # Guard 6: Duplicate-upload prevention using persistent upload ledger
        completed_record = self.ledger.get_completed_upload(content_hash)
        if completed_record and completed_record.video_id and not allow_duplicate:
            log.info(
                "Duplicate upload prevented for %s (hash=%s). Already published to YouTube as Video ID: %s",
                video_path.name,
                content_hash[:12],
                completed_record.video_id,
            )
            if raise_on_duplicate:
                raise DuplicateUploadError(
                    f"Duplicate upload prevented: Video file '{video_path.name}' (SHA256={content_hash[:12]}...) "
                    f"was already uploaded with Video ID: '{completed_record.video_id}'."
                )
            return {
                "id": completed_record.video_id,
                "video_id": completed_record.video_id,
                "title": completed_record.title,
                "privacy_status": completed_record.privacy_status,
                "already_uploaded": True,
                "url": f"https://youtu.be/{completed_record.video_id}",
            }


        # Guard 7: Verify target channel
        channel = self.oauth_manager.verify_channel()
        log.info("Verified target YouTube channel: %s (%s)", channel.title, channel.channel_id)

        access_token = self.oauth_manager.get_valid_access_token()

        # Step 8: Resumable session recovery check
        upload_url: Optional[str] = None
        record_id: Optional[int] = None
        start_byte: int = 0
        resumed: bool = False

        active_record = self.ledger.get_active_session(content_hash)
        if active_record and active_record.session_uri:
            log.info("Found interrupted upload session for %s. Probing session status...", video_path.name)
            probe = self._probe_resumable_session(active_record.session_uri, file_size, access_token)
            if probe["status"] == "COMPLETED":
                vid_id = probe["video_id"]
                log.info("Interrupted upload was already completed on YouTube! Video ID: %s", vid_id)
                self.ledger.record_complete(active_record.id, vid_id, privacy_status=privacy_status)
                return {
                    "id": vid_id,
                    "video_id": vid_id,
                    "title": title,
                    "privacy_status": privacy_status,
                    "resumed": True,
                    "already_uploaded": True,
                    "url": f"https://youtu.be/{vid_id}",
                }
            elif probe["status"] == "RESUMABLE":
                upload_url = active_record.session_uri
                record_id = active_record.id
                start_byte = probe["bytes_received"]
                resumed = True
                log.info("Resuming interrupted upload from byte %d / %d", start_byte, file_size)
            else:
                log.warning(
                    "Interrupted session expired or invalid (%s). Discarding session and initiating fresh upload.",
                    probe.get("reason"),
                )
                self.ledger.record_failure(active_record.id, f"Session expired/invalid: {probe.get('reason')}")

        # Step 9: Initiate new resumable session if not resuming
        if not upload_url:
            init_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(file_size),
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
            init_resp = requests.post(init_url, json=metadata, headers=init_headers, timeout=30)
            if init_resp.status_code != 200:
                if self.oauth_manager:
                    self.oauth_manager.handle_scope_error_if_any(init_resp, "YouTube upload initiation")
                raise PublishingDisabledError(f"Failed to initiate YouTube upload: {init_resp.text}")

            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                raise PublishingDisabledError("Missing upload Location header from YouTube response.")

            rec = self.ledger.record_start(
                content_hash=content_hash,
                file_path=video_path,
                file_size=file_size,
                title=title,
                privacy_status=privacy_status,
                session_uri=upload_url,
                channel_id=channel.channel_id,
            )
            record_id = rec.id

        # Step 10: Stream video data (full file or remaining resumed bytes)
        upload_headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes {start_byte}-{file_size - 1}/{file_size}",
        }

        try:
            with open(video_path, "rb") as f:
                if start_byte > 0:
                    f.seek(start_byte)
                upload_resp = requests.put(
                    upload_url,
                    data=f,
                    headers=upload_headers,
                    timeout=300,
                )
        except Exception as exc:
            log.error(
                "Upload transfer interrupted: %s (record_id=%s, video=%s)",
                exc,
                record_id,
                video_path.name,
                extra={
                    "video_path": str(video_path),
                    "content_hash": content_hash,
                    "stage": "binary_transfer",
                    "start_byte": start_byte,
                },
            )
            if record_id is not None:
                self.ledger.record_failure(record_id, f"Transfer interrupted: {exc}")
            raise PublishingDisabledError(f"Resumable upload stream interrupted: {exc}") from exc

        if upload_resp.status_code not in (200, 201):
            if self.oauth_manager:
                self.oauth_manager.handle_scope_error_if_any(upload_resp, "YouTube video binary upload")
            if record_id is not None:
                self.ledger.record_failure(record_id, f"Upload rejected ({upload_resp.status_code}): {upload_resp.text}")
            raise PublishingDisabledError(f"YouTube video upload failed ({upload_resp.status_code}): {upload_resp.text}")

        res = upload_resp.json()
        video_id = res.get("id")
        if not video_id:
            if record_id is not None:
                self.ledger.record_failure(record_id, "Missing video ID in response")
            raise PublishingDisabledError(f"Upload completed but no video ID was returned: {res}")

        if record_id is not None:
            self.ledger.record_complete(record_id, video_id=video_id, privacy_status=privacy_status)

        log.info(
            "Successfully uploaded video ID: %s (privacy: %s, resumed=%s)",
            video_id,
            privacy_status,
            resumed,
        )
        res["video_id"] = video_id
        res["privacy_status"] = privacy_status
        res["resumed"] = resumed
        return res

    def upload_private_acceptance_test(
        self,
        video_path: Path,
        title: str = "BENXAUTOMATION Acceptance Test [PRIVATE]",
        description: str = "Automated acceptance test video uploaded privately by BENXAUTOMATION.",
        allow_duplicate: bool = False,
    ) -> dict[str, Any]:
        """Upload a single video strictly as private and verify its existence on YouTube."""
        log.info("Starting one-video private acceptance test upload for %s", video_path)
        upload_res = self.upload(
            video_path=video_path,
            title=title,
            description=description,
            privacy_status="private",
            allow_duplicate=allow_duplicate,
        )
        video_id = upload_res.get("id") or upload_res.get("video_id")
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
    auth_p.add_argument(
        "--scopes",
        nargs="+",
        default=DEFAULT_YOUTUBE_SCOPES,
        help="OAuth scopes to request (default: youtube.upload and youtube.readonly)",
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
    up_p.add_argument(
        "--allow-duplicate",
        action="store_true",
        default=False,
        help="Allow upload even if already recorded in ledger",
    )
    up_p.add_argument(
        "--ledger-file",
        type=Path,
        default=None,
        help="Path to upload ledger SQLite db",
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

    # ledger-list
    list_p = subparsers.add_parser("ledger-list", help="List upload records from persistent ledger")
    list_p.add_argument(
        "--ledger-file",
        type=Path,
        default=DEFAULT_LEDGER_FILE,
        help="Path to ledger SQLite db",
    )

    # record-verified
    rec_p = subparsers.add_parser("record-verified", help="Register a verified upload in the ledger")
    rec_p.add_argument("--video-id", required=True, help="YouTube video ID (e.g. nmdEewLCffw)")
    rec_p.add_argument("--title", required=True, help="Video title")
    rec_p.add_argument("--video", "-v", type=Path, default=None, help="Path to video file")
    rec_p.add_argument("--content-hash", default=None, help="SHA-256 hash if video file not given")
    rec_p.add_argument("--channel-id", default="BENX_07", help="YouTube channel title or ID")
    rec_p.add_argument("--privacy", default="private", help="Privacy status (default: private)")
    rec_p.add_argument(
        "--ledger-file",
        type=Path,
        default=DEFAULT_LEDGER_FILE,
        help="Path to ledger SQLite db",
    )

    return parser


def main() -> None:
    parser = _build_cli()
    args = parser.parse_args()

    try:
        if args.command == "ledger-list":
            ledger = UploadLedger(args.ledger_file)
            records = ledger.list_records()
            print(f"\n[UPLOAD LEDGER] ({len(records)} entries in {ledger.db_path})")
            if not records:
                print("  (No uploads recorded yet)")
            for r in records:
                print(f"  - [{r.status}] ID={r.id} | VideoID={r.video_id} | Title='{r.title}' | Hash={r.content_hash[:10]}... | Privacy={r.privacy_status}")
            return

        if args.command == "record-verified":
            ledger = UploadLedger(args.ledger_file)
            file_hash = args.content_hash
            file_size = 0
            file_path_str = ""
            if args.video and args.video.is_file():
                file_hash = ledger.compute_file_hash(args.video)
                file_size = args.video.stat().st_size
                file_path_str = str(args.video)
            elif not file_hash:
                file_hash = f"manual_{args.video_id}"

            rec = ledger.record_completed_upload(
                content_hash=file_hash,
                video_id=args.video_id,
                title=args.title,
                privacy_status=args.privacy,
                file_path=file_path_str,
                file_size=file_size,
                channel_id=args.channel_id,
            )
            print(f"\n[LEDGER RECORDED] Registered verified video ID={rec.video_id} for channel {rec.channel_id}")
            return

        mgr = YouTubeOAuthManager(
            client_secret_path=args.client_secret,
            token_path=args.token_file,
        )

        if args.command == "authorize":
            print(f"Starting OAuth loopback flow on port {args.port}...")
            mgr.scopes = args.scopes
            mgr.run_local_server_flow(port=args.port, scopes=args.scopes)
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
            ledger = UploadLedger(args.ledger_file) if args.ledger_file else None
            pub = YouTubePublisher(cfg, oauth_manager=mgr, ledger=ledger)
            print(f"Uploading private acceptance test video: {args.video}...")
            res = pub.upload_private_acceptance_test(
                video_path=args.video,
                title=args.title,
                allow_duplicate=args.allow_duplicate,
            )
            print("\n[UPLOAD VERIFIED]")
            print(f"Video ID:        {res['video_id']}")
            print(f"Title:           {res['title']}")
            print(f"Privacy Status:  {res['privacy_status']}")
            print(f"Upload Status:   {res.get('upload_status', 'uploaded')}")
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
