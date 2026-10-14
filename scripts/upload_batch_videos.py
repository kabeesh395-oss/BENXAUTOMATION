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

    from benxautomation.animation.script_generator import AnimationScriptGenerator

    topic_map = {t["id"]: t for t in AnimationScriptGenerator.TOPIC_DEFINITIONS}

    videos = []
    # 5 High-Retention Animated Shorts
    for i in range(1, 6):
        sid = f"anim_short_{i:02d}"
        tdef = topic_map.get(sid, {})
        vtitle = f"{tdef.get('title', 'Cyber Breakthrough')} | BENX #Shorts"
        vdesc = f"{tdef.get('hook', '')}\n\nFollow BENX for daily breakthroughs in future tech, quantum computing, and AI systems!\n\n#Shorts #Technology #Innovation #BENX"
        videos.append({
            "path": Path(f"output/animated_shorts/{sid}/{sid}.mp4"),
            "title": vtitle,
            "desc": vdesc,
            "is_short": True,
        })

    # 2 Longform Documentaries
    videos.append({
        "path": Path("output/final_acceptance_run/video_longform.mp4"),
        "title": "Surprising Facts About Ocean & Science | BENX Deep Dive",
        "desc": "Deep science exploration and ocean mysteries documentary. Uploaded privately for review.\n\n#Science #Ocean #Documentary #BENX",
        "tags": ["science", "ocean", "documentary", "benx"],
        "is_short": False,
    })
    videos.append({
        "path": Path("output/deep_ocean_acceptance/deep_sea_abyss_longform.mp4"),
        "title": "Mysteries of the Deep Sea Abyss | BENX Deep Dive",
        "desc": "Exploring the unknown abyss of the ocean. Uploaded privately for review.\n\n#Science #Ocean #Documentary #BENX",
        "tags": ["science", "ocean", "deepsea", "documentary", "benx"],
        "is_short": False,
    })

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
