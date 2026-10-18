"""Upload the Juice Jacking Viral Short to YouTube as PUBLIC.

Direct user command: 'UPLOADE PANI RU PULIC LA ELLA PERFECT'
"""

import json
import mimetypes
from pathlib import Path
import requests

from benxautomation.config import PublishingConfig
from benxautomation.logger import get_logger
from benxautomation.publisher.youtube import YouTubePublisher, YouTubeOAuthManager

log = get_logger("upload_juice_jacking_public")

YOUTUBE_THUMBNAILS_SET_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"


def set_custom_thumbnail(oauth_manager: YouTubeOAuthManager, video_id: str, thumb_path: Path) -> bool:
    """Attempt to upload a custom thumbnail; fail gracefully if channel lacks custom thumb permission."""
    if not thumb_path.exists():
        log.warning("Thumbnail path %s does not exist; skipping thumbnail upload.", thumb_path)
        return False

    try:
        access_token = oauth_manager.get_valid_access_token()
        content_type = mimetypes.guess_type(str(thumb_path))[0] or "image/jpeg"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": content_type,
        }
        url = f"{YOUTUBE_THUMBNAILS_SET_URL}?videoId={video_id}&uploadType=media"
        with open(thumb_path, "rb") as f:
            resp = requests.post(url, headers=headers, data=f, timeout=30)

        if resp.status_code in (200, 201):
            log.info("Custom thumbnail successfully uploaded for video %s!", video_id)
            return True
        else:
            log.warning(
                "Custom thumbnail upload skipped (HTTP %d: %s). YouTube will use auto-generated Shorts frame.",
                resp.status_code,
                resp.text[:200],
            )
            return False
    except Exception as exc:
        log.warning("Thumbnail upload attempt encountered error: %s. Continuing.", exc)
        return False


def main() -> None:
    metadata_path = Path("output/autonomous_runs/juice_jacking_airport_hack_shorts/juice_jacking_airport_hack_metadata.json")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    video_path = Path(meta["video_path"])
    thumb_path = Path(meta.get("thumbnail_path", "output/autonomous_runs/juice_jacking_airport_hack_shorts/juice_jacking_airport_hack_thumb.jpg"))
    title = meta["title"]
    description = meta["description"]
    tags = meta.get("tags", [])
    privacy_status = "public"

    log.info("=== UPLOADING JUICE JACKING VIRAL SHORT TO YOUTUBE (PUBLIC) ===")
    log.info("Video: %s (%0.2f MB)", video_path, video_path.stat().st_size / (1024 * 1024))
    log.info("Title: %s", title)
    log.info("Privacy: %s", privacy_status)

    cfg = PublishingConfig(
        enabled=True,
        enforce_private=False,
        youtube_client_secret_path="client_secret.json",
        default_privacy="public",
    )
    publisher = YouTubePublisher(cfg)

    # Verify channel
    channel = publisher.oauth_manager.verify_channel()
    log.info("Target Channel: %s (%s)", channel.title, channel.channel_id)

    # Execute upload
    result = publisher.upload(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status,
        allow_duplicate=False,
    )

    video_id = result.get("video_id") or result.get("id")
    if not video_id:
        raise RuntimeError(f"Upload failed: No video_id returned: {result}")

    youtube_url = f"https://youtube.com/shorts/{video_id}"
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    log.info("Video successfully uploaded! ID: %s | Shorts URL: %s", video_id, youtube_url)

    # Try setting custom thumbnail
    thumb_uploaded = set_custom_thumbnail(publisher.oauth_manager, video_id, thumb_path)

    # Verify video details from YouTube Data API
    verified = publisher.verify_video(video_id)
    log.info("Verification confirmed: Title='%s', Privacy='%s', UploadStatus='%s'",
             verified.get("title"), verified.get("privacy_status"), verified.get("upload_status"))

    # Update metadata file
    meta["privacy_status"] = verified.get("privacy_status", privacy_status)
    meta["youtube_video_id"] = video_id
    meta["youtube_url"] = youtube_url
    meta["youtube_watch_url"] = watch_url
    meta["custom_thumbnail_set"] = thumb_uploaded
    meta["channel_id"] = channel.channel_id
    meta["channel_title"] = channel.title
    meta["published"] = True

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    safe_title = title.encode("ascii", "replace").decode("ascii")
    print("\n" + "=" * 60)
    print(">> SUCCESS! JUICE JACKING VIRAL SHORT IS LIVE ON YOUTUBE!")
    print(f"Title:       {safe_title}")
    print(f"Channel:     {channel.title} ({channel.channel_id})")
    print(f"Visibility:  {meta['privacy_status'].upper()}")
    print(f"Video ID:    {video_id}")
    print(f"Shorts Link: {youtube_url}")
    print(f"Watch Link:  {watch_url}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
