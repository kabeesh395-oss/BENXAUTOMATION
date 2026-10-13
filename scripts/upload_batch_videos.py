"""Upload 5 Shorts and 2 Longform videos strictly as PRIVATE to YouTube."""

import sys
from pathlib import Path

from benxautomation.config import PublishingConfig
from benxautomation.publisher.ledger import UploadLedger
from benxautomation.publisher.youtube import YouTubeOAuthManager, YouTubePublisher


def main() -> None:
    client_secret = Path("client_secret.json")
    if not client_secret.is_file():
        print("Error: client_secret.json not found", file=sys.stderr)
        sys.exit(1)

    mgr = YouTubeOAuthManager(client_secret_path=client_secret)
    channel = mgr.verify_channel()
    print("\n==================================================")
    print(f" YouTube Upload Target: {channel.title} ({channel.channel_id})")
    print(" Mode: Strict PRIVATE review uploads")
    print("==================================================\n")

    cfg = PublishingConfig(enabled=True, enforce_private=True)
    ledger = UploadLedger("output/upload_ledger.sqlite")
    pub = YouTubePublisher(cfg, oauth_manager=mgr, ledger=ledger)

    videos = [
        # 5 Shorts
        {
            "path": Path("output/animated_shorts/anim_short_01/anim_short_01.mp4"),
            "title": "BENX Animated Stick Adventure #1 #Shorts",
            "desc": "BENX animated character story #1. Uploaded privately for review.",
            "is_short": True,
        },
        {
            "path": Path("output/animated_shorts/anim_short_02/anim_short_02.mp4"),
            "title": "BENX Animated Stick Adventure #2 #Shorts",
            "desc": "BENX animated character story #2. Uploaded privately for review.",
            "is_short": True,
        },
        {
            "path": Path("output/animated_shorts/anim_short_03/anim_short_03.mp4"),
            "title": "BENX Animated Stick Adventure #3 #Shorts",
            "desc": "BENX animated character story #3. Uploaded privately for review.",
            "is_short": True,
        },
        {
            "path": Path("output/animated_shorts/anim_short_04/anim_short_04.mp4"),
            "title": "BENX Animated Stick Adventure #4 #Shorts",
            "desc": "BENX animated character story #4. Uploaded privately for review.",
            "is_short": True,
        },
        {
            "path": Path("output/animated_shorts/anim_short_05/anim_short_05.mp4"),
            "title": "BENX Animated Stick Adventure #5 #Shorts",
            "desc": "BENX animated character story #5. Uploaded privately for review.",
            "is_short": True,
        },
        # 2 Longform
        {
            "path": Path("output/final_acceptance_run/video_longform.mp4"),
            "title": "Surprising Facts About Ocean & Science | BENX Automation",
            "desc": "Deep science exploration and ocean mysteries documentary. Uploaded privately for review.",
            "is_short": False,
        },
        {
            "path": Path("output/deep_ocean_acceptance/deep_sea_abyss_longform.mp4"),
            "title": "Mysteries of the Deep Sea Abyss | BENX Deep Dive",
            "desc": "Exploring the unknown abyss of the ocean. Uploaded privately for review.",
            "is_short": False,
        },
    ]

    results = []
    for idx, item in enumerate(videos, start=1):
        vpath = item["path"]
        if not vpath.is_file():
            print(f"[{idx}/7] SKIP - File not found: {vpath}")
            continue

        print(f"[{idx}/7] Uploading: {item['title']} ({vpath.name}, {vpath.stat().st_size / 1024 / 1024:.2f} MB)...")
        try:
            res = pub.upload_private_verified_with_quality_gate(
                video_path=vpath,
                title=item["title"],
                description=item["desc"],
                tags=["benx", "animation", "shorts" if item["is_short"] else "documentary"],
                is_short=item["is_short"],
                allow_duplicate=True,
            )
            print(f"      -> SUCCESS: Video ID: {res.get('video_id')} | Status: {res.get('status')}")
            results.append({"title": item["title"], "id": res.get("video_id"), "status": "SUCCESS"})
        except Exception as exc:
            print(f"      -> FAILED: {exc}")
            results.append({"title": item["title"], "error": str(exc), "status": "FAILED"})

    print("\n==================================================")
    print(" BATCH UPLOAD SUMMARY")
    print("==================================================")
    for r in results:
        vid = r.get("id", "N/A")
        print(f"- {r['title']}: {r['status']} (ID: {vid})")


if __name__ == "__main__":
    main()
