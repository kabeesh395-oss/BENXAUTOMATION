"""Multi-Scene Storyboard Generator for Funny Stickman (BEN & MAX) Shorts.

Features:
- Converts a ComedyIdea into a timestamped, 4-scene StickmanStoryScript (~30s total).
- Dynamic, colorful story-aware backgrounds across scenes (bedroom, kitchen, office, street, gym, comedy_burst).
- Rich physical slapstick animation instructions:
  * Opening hook (< 3s retention trigger).
  * Escalating comedic stakes.
  * Slapstick climax with SFX cues (whoosh, boing, splat, record_scratch).
  * Sarcastic punchline outro with radiating comedy sunburst.
- Precise caption safe-zone subtitles and metadata generation.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from benxautomation.animation.stickman_engine import ComedyScene
from benxautomation.animation.stickman_ideas import ComedyIdea
from benxautomation.animation.stickman_story import StickmanStoryScript

log = logging.getLogger(__name__)


class StickmanStoryboardGenerator:
    """Transforms ComedyIdeas into fully timed 4-scene Stickman animation scripts."""

    def __init__(self, default_voice: str = "en-US-ChristopherNeural") -> None:
        self.default_voice = default_voice

    def generate_storyboard(self, idea: ComedyIdea) -> StickmanStoryScript:
        """Create a complete multi-scene animated script from a comedy idea."""
        if idea.idea_id == "snooze_math_trap":
            scenes = self._build_snooze_math_scenes()
        elif idea.idea_id == "gym_first_day_fail":
            scenes = self._build_gym_fail_scenes()
        elif idea.idea_id == "coffee_overdose_matrix":
            scenes = self._build_coffee_overdose_scenes()
        elif idea.idea_id == "chef_scrambled_egg":
            scenes = self._build_chef_egg_scenes()
        elif idea.idea_id == "wifi_router_kick":
            scenes = self._build_wifi_router_scenes()
        else:
            scenes = self._build_generic_scenes(idea)

        # Assemble hashtags and YouTube metadata
        tags = [
            "shorts",
            "funny",
            "animation",
            "stickman",
            "comedy",
            "cartoon",
            "relatable",
            "humor",
            "benx",
        ]

        description = (
            f"{idea.title}\n\n"
            f"{idea.premise}\n"
            f"{idea.twist}\n\n"
            f"#shorts #funny #animation #stickman #comedy #cartoons"
        )

        script = StickmanStoryScript(
            story_id=idea.idea_id,
            title=f"{idea.title} | Funny Stickman Comedy",
            topic=idea.premise,
            scenes=scenes,
            format="shorts",
            voice=self.default_voice,
            tags=tags,
            description=description,
        )

        valid, errors = script.validate()
        if not valid:
            raise ValueError(f"Generated storyboard is invalid: {', '.join(errors)}")

        return script

    def _build_snooze_math_scenes(self) -> List[ComedyScene]:
        """Scene storyboard for: When Your 5 AM Alarm Has a Math Puzzle."""
        return [
            ComedyScene(
                scene_id="sc1_snooze_hook",
                duration_seconds=7.0,
                title="The Math Alarm Hack",
                narration="Behold my ultimate anti-sleep strategy! I set an alarm that requires solving calculus to turn off! Tomorrow at 5:00 AM, I am unstoppable!",
                ben_action="celebrate",
                max_action="facepalm",
                sfx_cue=None,
                punchline_sub="5 AM Calculus Alarm: Unstoppable!",
                backdrop_theme="bedroom",
                ben_prop="alarm_clock",
            ),
            ComedyScene(
                scene_id="sc2_snooze_5am",
                duration_seconds=7.5,
                title="5:00 AM Ringing",
                narration="RIIIIING! Integral of 2x from zero to five?! My half-unconscious brain solves it in three seconds without even opening an eyelid! SNOOZE!",
                ben_action="sleepy",
                max_action="shock",
                sfx_cue="boing",
                punchline_sub="Integral of 2x = 25... SNOOZE!",
                backdrop_theme="bedroom",
                ben_prop="alarm_clock",
            ),
            ComedyScene(
                scene_id="sc3_snooze_wakeup",
                duration_seconds=7.5,
                title="Waking Up at 2 PM",
                narration="Wait... why is the sun blinding my eyes? What time is it?! Max, why does my clock say 2:15 PM?!",
                ben_action="panic",
                max_action="watch",
                sfx_cue="whoosh",
                punchline_sub="Wait... why is it 2:15 PM?!",
                backdrop_theme="bedroom",
                ben_prop="alarm_clock",
            ),
            ComedyScene(
                scene_id="sc4_snooze_punchline",
                duration_seconds=7.5,
                title="The Math Genius Twist",
                narration="You solved seven differential equations in your sleep just to stay in bed. You are a lazy genius. Subscribe if you snooze like Ben!",
                ben_action="shrug",
                max_action="laugh",
                sfx_cue="splat",
                punchline_sub="Lazy genius math skills! Subscribe!",
                backdrop_theme="comedy_burst",
            ),
        ]

    def _build_gym_fail_scenes(self) -> List[ComedyScene]:
        """Scene storyboard for: Day 1 at the Gym vs The Lightest Dumbbell."""
        return [
            ComedyScene(
                scene_id="sc1_gym_hook",
                duration_seconds=7.0,
                title="Gym Day One Confidence",
                narration="New year, new Ben! Look at this neon headband! I am hitting the heavy weights immediately! Step aside, amateurs!",
                ben_action="walk",
                max_action="watch",
                sfx_cue=None,
                punchline_sub="Day 1 at the Gym: Step aside, amateurs!",
                backdrop_theme="gym",
                ben_prop="phone",
            ),
            ComedyScene(
                scene_id="sc2_gym_lift",
                duration_seconds=7.5,
                title="The Two Kilo Challenge",
                narration="Behold this titanium iron dumbbell! Preparing for maximum explosive power! Three, two, one, UP!",
                ben_action="rage",
                max_action="facepalm",
                sfx_cue="whoosh",
                punchline_sub="Maximum explosive power! UP!",
                backdrop_theme="gym",
                ben_prop="dumbbell",
            ),
            ComedyScene(
                scene_id="sc3_gym_pinned",
                duration_seconds=7.5,
                title="Pinned Under the Weight",
                narration="MEDIC! Max, help! My biceps have filed for bankruptcy! This two kilogram weight has gravitational pull!",
                ben_action="splat",
                max_action="shock",
                sfx_cue="splat",
                punchline_sub="Help! Pinned by a 2kg dumbbell!",
                backdrop_theme="gym",
                ben_prop="dumbbell",
            ),
            ComedyScene(
                scene_id="sc4_gym_outro",
                duration_seconds=7.5,
                title="Pinky Finger Reality Check",
                narration="I can lift this with my pinky finger, Ben. Maybe start with breathing exercises tomorrow. Subscribe if gym day one humbled you too!",
                ben_action="dizzy",
                max_action="laugh",
                sfx_cue="boing",
                punchline_sub="Lifted with one pinky! Subscribe!",
                backdrop_theme="comedy_burst",
            ),
        ]

    def _build_coffee_overdose_scenes(self) -> List[ComedyScene]:
        """Scene storyboard for: What Happens When You Drink 4 Espressos at Once."""
        return [
            ComedyScene(
                scene_id="sc1_coffee_hook",
                duration_seconds=7.0,
                title="The Espresso Potion",
                narration="Just one tiny email left to finish! But I am feeling sluggish, so I poured four shots of dark roast into one mega mug!",
                ben_action="idle",
                max_action="watch",
                sfx_cue=None,
                punchline_sub="4 Shots of Espresso into One Mug!",
                backdrop_theme="kitchen",
                ben_prop="coffee_mug",
            ),
            ComedyScene(
                scene_id="sc2_coffee_matrix",
                duration_seconds=7.5,
                title="Time Warps",
                narration="Wait... why is the kitchen clock moving in reverse?! I can hear my Wi-Fi router thinking! I am vibrating in four dimensions!",
                ben_action="run",
                max_action="panic",
                sfx_cue="whoosh",
                punchline_sub="I can hear Wi-Fi signals in 4D!",
                backdrop_theme="office",
                ben_prop="coffee_mug",
            ),
            ComedyScene(
                scene_id="sc3_coffee_send",
                duration_seconds=7.5,
                title="Typing at Mach 5",
                narration="Email drafted! My fingers typed two thousand words per second! Smashing Send right now with supersonic precision!",
                ben_action="dance",
                max_action="shock",
                sfx_cue="boing",
                punchline_sub="Typing at 2,000 words per second!",
                backdrop_theme="office",
                ben_prop="phone",
            ),
            ComedyScene(
                scene_id="sc4_coffee_outro",
                duration_seconds=7.5,
                title="The Matrix Reality Check",
                narration="You just sent fifty lines of the letter 'A' to your boss. Sleep it off, Einstein. Subscribe for more coffee adventures!",
                ben_action="shrug",
                max_action="facepalm",
                sfx_cue="splat",
                punchline_sub="Sent 'AAAAAAAAA' to the boss! Subscribe!",
                backdrop_theme="comedy_burst",
            ),
        ]

    def _build_chef_egg_scenes(self) -> List[ComedyScene]:
        """Scene storyboard for: Cooking Like a Michelin Chef Goes Wrong."""
        return [
            ComedyScene(
                scene_id="sc1_chef_hook",
                duration_seconds=7.0,
                title="Michelin Chef Ambition",
                narration="Watch and learn, Max! Today, Chef Ben is executing the legendary aerodynamic five-foot pancake flip!",
                ben_action="celebrate",
                max_action="watch",
                sfx_cue=None,
                punchline_sub="The 5-Foot Aerodynamic Pan Flip!",
                backdrop_theme="kitchen",
                ben_prop="frying_pan",
            ),
            ComedyScene(
                scene_id="sc2_chef_launch",
                duration_seconds=7.5,
                title="The Launch",
                narration="Behold the wrist flick of a culinary master! Up into the stratosphere goes the golden batter!",
                ben_action="rage",
                max_action="shock",
                sfx_cue="whoosh",
                punchline_sub="Up into the stratosphere it goes!",
                backdrop_theme="kitchen",
                ben_prop="frying_pan",
            ),
            ComedyScene(
                scene_id="sc3_chef_fan",
                duration_seconds=7.5,
                title="Ceiling Fan Catastrophe",
                narration="Wait! The ceiling fan is on high speed! No, no, no! It's like a yellow food grenade in the kitchen!",
                ben_action="panic",
                max_action="panic",
                sfx_cue="splat",
                punchline_sub="Ceiling fan food grenade!",
                backdrop_theme="kitchen",
                ben_prop="frying_pan",
            ),
            ComedyScene(
                scene_id="sc4_chef_outro",
                duration_seconds=7.5,
                title="Egg on Face",
                narration="An eggshell landed directly on my nose. Stick to eating cereal, Gordon Ramsay. Subscribe if cooking is hard for you too!",
                ben_action="shrug",
                max_action="facepalm",
                sfx_cue="boing",
                punchline_sub="Eggshell on nose! Subscribe!",
                backdrop_theme="comedy_burst",
            ),
        ]

    def _build_wifi_router_scenes(self) -> List[ComedyScene]:
        """Scene storyboard for: The 1% Battery and Router Reboot Panic."""
        return [
            ComedyScene(
                scene_id="sc1_wifi_hook",
                duration_seconds=7.0,
                title="1% Battery Panic",
                narration="Final boss is at one percent health! But wait... phone battery is at one percent, and the Wi-Fi just died!",
                ben_action="panic",
                max_action="shock",
                sfx_cue=None,
                punchline_sub="1% Boss Health vs 1% Phone Battery!",
                backdrop_theme="bedroom",
                ben_prop="phone",
            ),
            ComedyScene(
                scene_id="sc2_wifi_sprint",
                duration_seconds=7.5,
                title="Hallway Sprint",
                narration="Sprinting to the living room! Dodging furniture, leaping over dirty laundry, heading straight for the router!",
                ben_action="run",
                max_action="watch",
                sfx_cue="whoosh",
                punchline_sub="Olympic sprint to reboot the router!",
                backdrop_theme="street",
                ben_prop="phone",
            ),
            ComedyScene(
                scene_id="sc3_wifi_blow",
                duration_seconds=7.5,
                title="The Router Blow",
                narration="Blowing into the Ethernet cable like an old video game cartridge! Power cord re-inserted! Come on, green light!",
                ben_action="rage",
                max_action="facepalm",
                sfx_cue="boing",
                punchline_sub="Blowing into Ethernet cables!",
                backdrop_theme="office",
                ben_prop="gadget",
            ),
            ComedyScene(
                scene_id="sc4_wifi_outro",
                duration_seconds=7.5,
                title="System Update Trap",
                narration="Great news, Wi-Fi is back. Bad news: Windows is installing update one of four thousand. Subscribe if you know the pain!",
                ben_action="splat",
                max_action="laugh",
                sfx_cue="splat",
                punchline_sub="Windows Update 1 of 4,000! Subscribe!",
                backdrop_theme="comedy_burst",
            ),
        ]

    def _build_generic_scenes(self, idea: ComedyIdea) -> List[ComedyScene]:
        """Procedural 4-scene generator for dynamic ideas."""
        locs = idea.locations if len(idea.locations) >= 4 else ["bedroom", "kitchen", "street", "comedy_burst"]
        prop1 = idea.props[0] if idea.props else "phone"
        prop2 = idea.props[1] if len(idea.props) > 1 else prop1

        return [
            ComedyScene(
                scene_id=f"{idea.idea_id}_sc1",
                duration_seconds=7.0,
                title="The Hook",
                narration=f"Listen up! Today I am tackling this once and for all: {idea.premise}",
                ben_action="celebrate",
                max_action="watch",
                sfx_cue=None,
                punchline_sub=idea.title[:45],
                backdrop_theme=locs[0],
                ben_prop=prop1,
            ),
            ComedyScene(
                scene_id=f"{idea.idea_id}_sc2",
                duration_seconds=7.5,
                title="The Escalation",
                narration=f"Watch this masterclass execution! Nothing could possibly go wrong now! {idea.conflict}",
                ben_action="run",
                max_action="panic",
                sfx_cue="whoosh",
                punchline_sub="Nothing could possibly go wrong!",
                backdrop_theme=locs[1],
                ben_prop=prop2,
            ),
            ComedyScene(
                scene_id=f"{idea.idea_id}_sc3",
                duration_seconds=7.5,
                title="The Slapstick Climax",
                narration="Wait, wait, wait! Whoooaa! Physics has betrayed me once again!",
                ben_action="slip",
                max_action="shock",
                sfx_cue="splat",
                punchline_sub="WHOOOAA! Physics betrayed me!",
                backdrop_theme=locs[2],
                ben_prop=prop1,
            ),
            ComedyScene(
                scene_id=f"{idea.idea_id}_sc4",
                duration_seconds=7.5,
                title="The Punchline",
                narration=f"{idea.twist} Subscribe for more daily stickman comedy!",
                ben_action="shrug",
                max_action="laugh",
                sfx_cue="boing",
                punchline_sub="Subscribe for daily stickman comedy!",
                backdrop_theme=locs[3] if "comedy_burst" in locs[3] else "comedy_burst",
            ),
        ]
