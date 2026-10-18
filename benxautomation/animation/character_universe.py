"""Dynamic Character Universe for BENXAUTOMATION.

Provides an extensible roster of category-specific cartoon hosts adhering to the
signature OverSimplified / TheOdd1sOut 2D cartoon art style:
- Smooth white bald marshmallow/bean head.
- Bold black comic ink outlines.
- Expressive, exaggerated cartoon faces.
- Category-specific signature headwear, costumes, and props.
- Characteristic atmospheric, colorful cartoon backgrounds.

Supports pre-registered hero archetypes (Tech, History/Story, News, Finance, Fitness, Science, Gaming, Chef, Law)
plus on-demand dynamic character synthesis for ANY new topic category.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from benxautomation.logger import get_logger

log = get_logger(__name__)


@dataclass
class CharacterProfile:
    """Specification of a category-specific cartoon host."""
    character_id: str
    name: str
    category: str
    tagline: str
    voice: str                      # Edge-TTS voice identifier
    headwear: str
    outfit: str
    signature_prop: str
    environment_theme: str
    expression_default: str = "confident"
    description: str = ""

    def build_art_prompt(self, scene_action: str = "", emotion: str = "") -> str:
        """Generate consistent OverSimplified-style generation prompt for this character."""
        face_desc = emotion or self.expression_default
        action_desc = f", {scene_action}" if scene_action else ""
        return (
            f"2D cartoon animation YouTube Shorts frame in the exact viral OverSimplified and TheOdd1sOut art style: "
            f"A minimalist white cartoon character named {self.name} with a smooth white bald marshmallow head, "
            f"bold black comic ink outlines. Expressive {face_desc} face with bold black eyebrows and cartoon eyes. "
            f"Wearing {self.headwear} and {self.outfit}, holding {self.signature_prop} in a white cartoon gloved hand{action_desc}. "
            f"Standing in a vibrant colorful {self.environment_theme} background with atmospheric lighting. "
            f"Clean hand-drawn digital 2D cartoon aesthetic, vertical 9:16 aspect ratio."
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Pre-registered Signature Cast for High-Performing YouTube Niches
CORE_UNIVERSE_ROSTER: Dict[str, CharacterProfile] = {
    "tech": CharacterProfile(
        character_id="tech_ben",
        name="BEN",
        category="tech",
        tagline="The AI & Tech Prodigy",
        voice="en-US-ChristopherNeural",
        headwear="a backwards neon cyber-cyan baseball cap with an electric-blue visor",
        outfit="a sleek dark navy comic hoodie over white pants",
        signature_prop="a futuristic glowing smartphone or steaming coffee mug",
        environment_theme="modern high-tech apartment kitchen and cyber workstation with LED lights",
        expression_default="mischievous cocked-eyebrow smirk with pointy nose",
        description="Explains AI, coding, viral gadgets, and tech hacks with fast energetic humor.",
    ),
    "story": CharacterProfile(
        character_id="story_king",
        name="THE KING",
        category="story",
        tagline="The Ancient Storyteller",
        voice="en-US-GuyNeural",
        headwear="a golden royal 5-spiked crown with cel-shading",
        outfit="a dark crimson royal cape with a dramatic high popped flared collar, gold brooches, and dark knight armor breastplate",
        signature_prop="a medieval steel broadsword with a glowing blue crystal pommel",
        environment_theme="dramatic atmospheric night sky with painterly dark clouds and celestial volumetric god rays streaming down",
        expression_default="determined angry furrowed eyebrows and stoic grimace",
        description="Narrates epic history, legendary battles, mythology, and captivating life stories.",
    ),
    "news": CharacterProfile(
        character_id="news_scoop",
        name="SCOOP",
        category="news",
        tagline="The Breaking News Anchor",
        voice="en-US-AndrewNeural",
        headwear="a brown classic fedora hat with a white 'PRESS' badge in the band",
        outfit="a classic beige detective trench coat over a blue collared shirt and dark tie",
        signature_prop="a vintage metal broadcast microphone with a red 'LIVE' square box",
        environment_theme="modern broadcast news studio with digital world map screens and lower-third breaking news ticker",
        expression_default="wide energetic eyes and fast-talking expressive open mouth",
        description="Breaks down global news, trending internet mysteries, and viral fact-checks.",
    ),
    "finance": CharacterProfile(
        character_id="finance_cash",
        name="MR. CASH",
        category="finance",
        tagline="The Wealth & Market Mogul",
        voice="en-US-EricNeural",
        headwear="a round golden monocle over one eye with an arched eyebrow",
        outfit="a sharp luxury dark charcoal pinstripe three-piece suit with an emerald green tie and gold dollar-sign tie clip",
        signature_prop="a giant shiny golden coin with a dollar sign",
        environment_theme="sleek modern financial trading floor with glowing green stock market candlestick charts and upward trend arrows",
        expression_default="confident billionaire smirk with sharp intellect",
        description="Reveals stock market secrets, crypto trends, side hustles, and personal finance hacks.",
    ),
    "fitness": CharacterProfile(
        character_id="fitness_tank",
        name="TANK",
        category="fitness",
        tagline="The Iron Gym Coach",
        voice="en-US-ChristopherNeural",
        headwear="a bright red athletic sweatband around forehead",
        outfit="a grey athletic tank top with muscular cartoon arms and gym shorts",
        signature_prop="a heavy black iron dumbbell",
        environment_theme="vibrant modern gym background with barbell weight racks and glowing neon 'TRAIN HARD' workout signs",
        expression_default="pumped-up shouting face with wide determined smile and sweat drops",
        description="Coaches gym motivation, workout science, muscle myths, and healthy life hacks.",
    ),
    "science": CharacterProfile(
        character_id="science_quantum",
        name="DR. QUANTUM",
        category="science",
        tagline="The Space & Lab Genius",
        voice="en-US-BrianNeural",
        headwear="round green protective safety science goggles pushed up on forehead",
        outfit="a pristine white laboratory lab coat over a light blue shirt with a yellow bowtie and dark trousers",
        signature_prop="a glass conical flask with bubbling glowing purple chemical liquid",
        environment_theme="colorful high-tech laboratory with chalkboard physics equations and a telescope pointing at starry outer space",
        expression_default="excited curious genius face with wide sparkling eyes and open smile",
        description="Explores mind-blowing science paradoxes, universe secrets, and space discoveries.",
    ),
    "gaming": CharacterProfile(
        character_id="gaming_glitch",
        name="GLITCH",
        category="gaming",
        tagline="The Esports & Gaming Pro",
        voice="en-US-ChristopherNeural",
        headwear="a high-tech gaming headset with glowing RGB earcups and boom mic",
        outfit="an oversized purple and black gamer hoodie with neon circuit patterns",
        signature_prop="an ergonomic wireless gaming controller with glowing colored buttons",
        environment_theme="dark gaming room illuminated by glowing RGB light strips, dual monitors, and pixel art posters",
        expression_default="intense focused gaming stare with a triumphant victory smirk",
        description="Covers gaming lore, easter eggs, speedruns, and GTA / Minecraft / esports secrets.",
    ),
    "cooking": CharacterProfile(
        character_id="chef_pierre",
        name="CHEF PIERRE",
        category="cooking",
        tagline="The Master of Flavors",
        voice="en-US-GuyNeural",
        headwear="a tall pleated white cartoon chef toque hat",
        outfit="a double-breasted white chef jacket with red neckerchief and striped apron",
        signature_prop="a sizzling black frying pan with a golden flipping pancake or wooden spoon",
        environment_theme="bustling warm gourmet restaurant kitchen with hanging copper pots and fresh ingredients",
        expression_default="passionate expressive chef face with a playful wink and kiss-to-the-air pose",
        description="Shares insane cooking hacks, recipe secrets, street food mysteries, and culinary science.",
    ),
    "law": CharacterProfile(
        character_id="judge_justice",
        name="JUDGE JUSTICE",
        category="law",
        tagline="The Legal Arbiter",
        voice="en-US-GuyNeural",
        headwear="a classic colonial powdered judge wig",
        outfit="a dignified black judicial robe with a crisp white collar",
        signature_prop="a heavy solid oak wooden gavel held high ready to strike",
        environment_theme="grand mahogany courtroom with high pillars, leather law books, and Scales of Justice",
        expression_default="stern authoritative stare with furrowed eyebrows and imposing frown",
        description="Breaks down crazy laws, courtroom drama, legal loopholes, and true crime cases.",
    ),
}


class DynamicCharacterFactory:
    """Manages the cartoon universe roster and synthesizes custom archetypes on demand."""

    def __init__(self) -> None:
        self.roster: Dict[str, CharacterProfile] = dict(CORE_UNIVERSE_ROSTER)

    def get_character(self, category_or_id: str) -> Optional[CharacterProfile]:
        """Look up existing character by category or id."""
        key = category_or_id.lower().strip()
        if key in self.roster:
            return self.roster[key]
        for prof in self.roster.values():
            if prof.character_id == key or prof.name.lower() == key:
                return prof
        return None

    def classify_topic_and_get_character(self, topic: str) -> CharacterProfile:
        """Classify a topic string into the appropriate category host, or auto-synthesize one."""
        t_low = topic.lower()

        # Keyword mapping rules
        rules = [
            ("tech", [r"\b(ai|tech|code|coding|software|computer|phone|gadget|apple|google|robot|internet|app|cyber)\b"]),
            ("story", [r"\b(history|war|king|queen|ancient|empire|battle|myth|mythology|legend|medieval|conquest|roman|greek)\b"]),
            ("news", [r"\b(news|breaking|scandal|happened|today|currentevent|investigat|exposed|viral|drama|headline)\b"]),
            ("finance", [r"\b(money|finance|stock|invest|crypto|bitcoin|rich|billionaire|wealth|economy|market|cash|dollar|bank|earn)\b"]),
            ("fitness", [r"\b(gym|workout|fitness|muscle|exercise|diet|bodybuild|lift|protein|weight|cardio|trainer)\b"]),
            ("science", [r"\b(science|space|planet|physics|quantum|universe|nasa|blackhole|gravity|biology|chemistry|molecule|atom)\b"]),
            ("gaming", [r"\b(game|gaming|gta|minecraft|esports|playstation|xbox|nintendo|steam|speedrun|gamer|boss)\b"]),
            ("cooking", [r"\b(cook|food|recipe|chef|kitchen|eat|restaurant|bake|meal|dish|taste|flavor)\b"]),
            ("law", [r"\b(law|crime|court|judge|legal|lawyer|police|prison|jail|illegal|verdict|rule)\b"]),
        ]

        for cat, patterns in rules:
            for pat in patterns:
                if re.search(pat, t_low):
                    log.info("Classified topic '%s' to category '%s'", topic, cat)
                    return self.roster[cat]

        # If not directly matched, check if an archetype can be dynamically synthesized
        log.info("Topic '%s' did not match static category, synthesizing custom archetype.", topic)
        return self._synthesize_custom_character(topic)

    def _synthesize_custom_character(self, topic: str) -> CharacterProfile:
        """Synthesize a dynamic character adhering to the exact OverSimplified art formula."""
        # Clean slug
        slug = re.sub(r"[^a-z0-9]+", "_", topic.lower())[:16].strip("_") or "custom"
        char_id = f"custom_{slug}"

        # If already cached, reuse
        if char_id in self.roster:
            return self.roster[char_id]

        # Extract primary keyword
        words = [w for w in re.findall(r"[a-z]{3,}", topic.lower()) if w not in {"the", "and", "why", "how", "what", "with"}]
        topic_keyword = words[0].title() if words else "Universal"

        profile = CharacterProfile(
            character_id=char_id,
            name=f"CAPTAIN {topic_keyword.upper()}",
            category=slug,
            tagline=f"The {topic_keyword} Specialist",
            voice="en-US-ChristopherNeural",
            headwear="a stylish cartoon colored cap with a bold outline",
            outfit=f"a thematic cartoon jacket and shirt suited for {topic_keyword.lower()}",
            signature_prop=f"an iconic cartoon prop representing {topic_keyword.lower()}",
            environment_theme=f"colorful illustrated room with elements related to {topic_keyword.lower()}",
            expression_default="confident expressive face with bold black eyebrows and sharp eyes",
            description=f"Specialized host dynamically tailored for {topic}.",
        )

        self.roster[char_id] = profile
        return profile

    def list_all_characters(self) -> List[CharacterProfile]:
        """Return all available hosts in the universe."""
        return list(self.roster.values())
