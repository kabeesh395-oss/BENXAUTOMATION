"""Official Channel Debut Short: BEN introduces the channel!

Title: Welcome to My Channel! | Meet BEN & The Gang
Starring: BEN (The Tech & Comedy Host)
Format: 1080x1920 (9:16 Shorts), 24fps
Audio: Edge-TTS Neural Voice (en-US-ChristopherNeural)
Subtitles: Mobile Safe-Zone Burned ASS Subtitles (MarginV=330)
"""

from pathlib import Path
from benxautomation.animation.stickman_engine import ComedyScene
from benxautomation.animation.stickman_story import StickmanStoryPipeline, StickmanStoryScript

OUTPUT_DIR = Path("output/channel_launch")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 4-Scene Epic Channel Kickoff Storyboard
scenes = [
    ComedyScene(
        scene_id="sc1_welcome_hook",
        duration_seconds=7.0,
        title="Welcome to My Channel!",
        narration="Yo! Welcome to my channel! I am Ben! If you love crazy tech hacks, hilarious stories, and pure cartoon madness, you just found your new home on YouTube!",
        ben_action="celebrate",
        max_action="watch",
        sfx_cue=None,
        punchline_sub="YO! Welcome to My Channel! I'm BEN!",
        backdrop_theme="kitchen",
        ben_prop="coffee_mug",
    ),
    ComedyScene(
        scene_id="sc2_the_universe",
        duration_seconds=7.5,
        title="Meet The Whole Gang",
        narration="Every single day, we break down ancient history with The King, money secrets with Mr. Cash, fitness fails with Tank, and science paradoxes with Dr. Quantum!",
        ben_action="walk",
        max_action="watch",
        sfx_cue="whoosh",
        punchline_sub="Tech, History, Finance & Science!",
        backdrop_theme="office",
        ben_prop="phone",
    ),
    ComedyScene(
        scene_id="sc3_the_promise",
        duration_seconds=7.5,
        title="No Boring Content",
        narration="No boring lectures, no fake advice! Just high-speed animated comedy that actually makes you smarter before your brain melts!",
        ben_action="run",
        max_action="panic",
        sfx_cue="boing",
        punchline_sub="Pure Animated Comedy That Makes You Smarter!",
        backdrop_theme="kitchen",
        ben_prop="gadget",
    ),
    ComedyScene(
        scene_id="sc4_subscribe_outro",
        duration_seconds=7.5,
        title="Hit Subscribe Right Now!",
        narration="So smash that subscribe button right now before your Wi-Fi dies! Drop a comment, join the crew, and let's go!",
        ben_action="shrug",
        max_action="laugh",
        sfx_cue="splat",
        punchline_sub="Smash SUBSCRIBE & Join the Crew! Let's Go!",
        backdrop_theme="comedy_burst",
    ),
]

script = StickmanStoryScript(
    story_id="ben_official_channel_intro",
    title="WELCOME TO MY CHANNEL! 🔥 Meet BEN & The Gang | Official Channel Intro",
    topic="Official YouTube Channel Introduction by BEN",
    scenes=scenes,
    format="shorts",
    voice="en-US-ChristopherNeural",
    tags=["shorts", "animation", "channelintro", "benx", "cartoons", "comedy", "tech", "funny"],
    description=(
        "WELCOME TO MY CHANNEL! 🔥 I'm BEN, and every single day we drop high-speed, hilarious cartoon Shorts "
        "covering tech hacks, crazy history, money secrets, and mind-blowing science!\n\n"
        "Smash SUBSCRIBE and join the squad right now! 🚀\n\n"
        "#shorts #animation #cartoons #comedy #channelintro #benx"
    ),
)

pipeline = StickmanStoryPipeline()
result = pipeline.run_pipeline(script, output_dir=OUTPUT_DIR, burn_subtitles=True)

print("\n" + "=" * 60)
print("OFFICIAL CHANNEL INTRO SHORT PRODUCED SUCCESSFULLY!")
print("=" * 60)
print(f"Video File:      {result.video_path}")
print(f"Duration:        {result.duration_seconds:.2f}s")
print(f"FPS:             {result.fps}")
print(f"Motion Score:    {result.motion_score:.4f} (Valid: {result.quality_passed})")
print(f"Thumbnail:       {result.thumbnail_path}")
print(f"Subtitles:       {result.ass_path}")
print(f"Metadata:        {result.metadata_path}")
print("=" * 60 + "\n")
