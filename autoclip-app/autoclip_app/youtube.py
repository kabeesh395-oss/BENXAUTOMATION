from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SECRETS_FILE = ROOT / "client_secrets.json"
TOKEN_FILE = DATA / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _save_credentials(credentials: Any) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")


def youtube_status() -> dict[str, Any]:
    if not SECRETS_FILE.exists():
        return {
            "connected": False,
            "configured": False,
            "message": "Add your Google OAuth Desktop client file as autoclip-app/client_secrets.json.",
        }
    if not TOKEN_FILE.exists():
        return {"connected": False, "configured": True, "message": "YouTube account not connected yet."}
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            _save_credentials(credentials)
        if credentials.valid:
            return {"connected": True, "configured": True, "message": "YouTube channel connected."}
        return {"connected": False, "configured": True, "message": "YouTube authorization expired. Reconnect."}
    except Exception as exc:
        return {"connected": False, "configured": True, "message": f"Could not read YouTube token: {exc}"}


def connect_youtube() -> dict[str, Any]:
    if not SECRETS_FILE.exists():
        raise RuntimeError(
            "Missing client_secrets.json. Create a Google Cloud OAuth Desktop app client, "
            "enable YouTube Data API v3, and place the downloaded JSON at autoclip-app/client_secrets.json."
        )
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), SCOPES)
    credentials = flow.run_local_server(
        host="127.0.0.1", port=0, open_browser=True, access_type="offline",
        prompt="consent",
    )
    _save_credentials(credentials)
    return youtube_status()


def upload_public_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str] | None = None,
    category_id: str = "22",
) -> dict[str, str]:
    status = youtube_status()
    if not status["connected"]:
        raise RuntimeError(status["message"])

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    safe_title = (title or video_path.stem).strip()[:100] or video_path.stem
    safe_description = (description or "Created with AutoClip AI.")[:5000]
    safe_tags = [str(tag).strip()[:30] for tag in (tags or []) if str(tag).strip()][:30]
    body = {
        "snippet": {
            "title": safe_title,
            "description": safe_description,
            "tags": safe_tags,
            "categoryId": category_id,
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(
        str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
    )
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = str(response["id"])
    return {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}", "privacy_status": "public"}
