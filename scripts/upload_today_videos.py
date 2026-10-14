"""Execute today's curated upload batch strictly as PRIVATE to YouTube."""

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
    print("\n" + "=" * 60)
    print(f" TARGET CHANNEL: {channel.title} ({channel.channel_id})")
    print(" EXECUTION MODE: Strict PRIVATE (Creator Review Only)")
    print("=" * 60 + "\n")

    cfg = PublishingConfig(enabled=True, enforce_private=True)
    ledger = UploadLedger("output/upload_ledger.sqlite")
    pub = YouTubePublisher(cfg, oauth_manager=mgr, ledger=ledger)

    todays_batch = [
        # Video 1 — Cyber Mascot 9:16 Short
        {
            "path": Path("output/mascot_sample/ai_quantum_leap_shorts/ai_quantum_leap.mp4"),
            "title": "Why Quantum Computing Changes Everything in 2026! | BENX #Shorts",
            "desc": (
                "What happens when computers think in parallel quantum states? "
                "Quantum qubits explore every possibility simultaneously.\n\n"
                "Subscribe to BENX for daily high-tech breakdowns, AI revolutions, and cyber engineering!\n\n"
                "#Shorts #QuantumComputing #TechBreakthrough #ArtificialIntelligence #BENX"
            ),
            "tags": ["quantum computing", "ai breakthrough", "tech news", "future tech", "benx", "shorts"],
            "is_short": True,
        },
        # Video 2 — Deep Science 9:16 Short
        {
            "path": Path("output/deep_sea_fixed_run/video_shorts.mp4"),
            "title": "The Deepest Ocean Mystery Science Can't Explain! | BENX #Shorts",
            "desc": (
                "At 36,000 feet beneath the Pacific Ocean, extreme pressure creates conditions more hostile than outer space. "
                "What is hiding in the Mariana Trench?\n\n"
                "Follow BENX for daily science & technology mysteries!\n\n"
                "#Shorts #OceanMystery #ScienceFacts #DeepSea #BENX"
            ),
            "tags": ["deep ocean", "mariana trench", "science mysteries", "extreme physics", "shorts", "benx"],
            "is_short": True,
        },
        # Video 3 — Humanoid Robotics 9:16 Short
        {
            "path": Path("output/original_content/ai_future_shorts_7315/ai_future_shorts_7315.mp4"),
            "title": "Tesla's Humanoid Robotics Breakthrough Terrified Engineers | BENX #Shorts",
            "desc": (
                "How neural network vision models are giving bipedal humanoid robots millisecond dexterity. "
                "Is AGI physical sooner than expected?\n\n"
                "Subscribe to BENX for daily engineering breakdowns!\n\n"
                "#Shorts #Robotics #HumanoidRobots #ArtificialIntelligence #BENX"
            ),
            "tags": ["humanoid robots", "tesla optimus", "robotics", "ai technology", "shorts", "benx"],
            "is_short": True,
        },
        # Video 4 — 16:9 Long-Form Deep Dive Documentary
        {
            "path": Path("output/mascot_longform/benx_quantum_longform_longform/benx_quantum_longform.mp4"),
            "title": "Quantum Supremacy: How Superconducting Circuits Calculate Exponentially | BENX Deep Dive",
            "desc": (
                "Welcome to the BENX Technology Lab. Classical computers process binary bits one at a time. "
                "Superconducting quantum circuits operate in multi-state superposition, solving calculations in minutes "
                "that would take classical supercomputers ten thousand years.\n\n"
                "In this technical breakdown, we explore quantum gates, qubit coherence, cryogenic dilution refrigerators, "
                "and the race toward fault-tolerant quantum supremacy.\n\n"
                "Chapters:\n"
                "00:00 - Quantum Superposition & Binary Limits\n"
                "02:15 - Superconducting Josephson Junctions\n"
                "05:40 - Cryogenic Cooling at Near Absolute Zero\n"
                "08:30 - The Quantum Decryption Threat\n\n"
                "#QuantumComputing #TechDocumentary #Superconductors #DeepTech #BENX"
            ),
            "tags": ["quantum supremacy", "superconducting circuits", "quantum physics", "tech documentary", "computer architecture", "benx"],
            "is_short": False,
        },
    ]

    results = []
    for idx, item in enumerate(todays_batch, start=1):
        vpath = item["path"]
        if not vpath.is_file():
            print(f"[{idx}/{len(todays_batch)}] SKIP — File missing: {vpath}")
            continue

        size_mb = vpath.stat().st_size / (1024 * 1024)
        print(f"[{idx}/{len(todays_batch)}] UPLOADING PRIVATE: {item['title']}")
        print(f"      File: {vpath.name} ({size_mb:.2f} MB)")
        try:
            res = pub.upload_private_verified_with_quality_gate(
                video_path=vpath,
                title=item["title"],
                description=item["desc"],
                tags=item["tags"],
                is_short=item["is_short"],
                allow_duplicate=True,
            )
            vid = res.get("video_id")
            vstatus = res.get("status")
            print(f"      -> SUCCESS! Video ID: {vid} | Status: {vstatus}")
            print(f"      -> YouTube Link: https://youtu.be/{vid}")
            results.append({"title": item["title"], "id": vid, "status": "SUCCESS"})
        except Exception as exc:
            print(f"      -> FAILED: {exc}")
            results.append({"title": item["title"], "error": str(exc), "status": "FAILED"})

    print("\n" + "=" * 60)
    print(" TODAY'S BATCH UPLOAD SUMMARY (STRICT PRIVATE)")
    print("=" * 60)
    for r in results:
        status_symbol = "[PASS]" if r["status"] == "SUCCESS" else "[FAIL]"
        print(f" {status_symbol} {r['title']}")
        if "id" in r:
            print(f"   YouTube Studio ID: {r['id']} (PRIVATE)")
        if "error" in r:
            print(f"   Error: {r['error']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
