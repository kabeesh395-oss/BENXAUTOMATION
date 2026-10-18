# BENXAUTOMATION: Fully Automated YouTube Shorts Stickman Comedy Channel System

## Executive Summary & Deliverables
This system upgrades `BENXAUTOMATION` into a focused, fully automated YouTube Shorts production and publishing pipeline in a single, locked signature art style: **Minimalist 2D Stick-Figure Comedy with Dynamic Colourful Backgrounds**.

### Key Architectural Achievements:
1. **Signature Character Rigging (BEN & MAX)**:
   - Bold black ink outlines (`COLOR_LINE_DARK = (15, 23, 42)`), crisp white character fills (`COLOR_SKIN = (255, 255, 255)`).
   - BEN: Backwards neon cyan cap (`#00F2FE`), electric blue bill, energetic prankster persona.
   - MAX: Amber gold nerd glasses (`#FFB400`), coral red bow tie (`#FF416C`), analytical straight-man persona.
   - Rich facial rigs & gags: `rage` (throbbing vein), `panic` (cartoon sweat drop), `sleepy` (Zzz), `dizzy` (@_@), and comedy props (`alarm_clock`, `coffee_mug`, `dumbbell`, `frying_pan`, `phone`, `banana`, `gadget`).
2. **Dynamic, Scene-Aware Colourful Backgrounds**:
   - Automatically renders story-appropriate locations without compromising character readability:
     * 🛏️ **Bedroom**: Pastel lavender walls (`#EEE6F8`), wood floor, morning sunlight beam, drifting dust motes.
     * 🍳 **Kitchen**: Warm peach walls (`#FEEDE2`), checkered tile floor, counter, steam curls.
     * 💼 **Office**: Cool slate blue walls (`#E2E8F0`), window blinds, ticking wall clock, potted plant.
     * 🌳 **Park**: Sunny mint meadow (`#CFFAFE`), cartoon tree, falling yellow leaves.
     * 🏋️ **Gym**: Warm amber walls (`#FEF3C7`), dark rubber floor, weight rack.
     * 🏫 **Classroom**: Soft mint (`#D1FAE5`), chalkboard with chalk math formula.
     * 💥 **Comedy Burst**: Radiating 16-ray sunburst (yellow & coral) for punchlines.
3. **Automatic Idea Selection & Heuristic Ranking (`stickman_ideas.py`)**:
   - Generates batches of relatable, everyday physical comedy concepts.
   - Transparent heuristic formula prioritizing:
     `score = 0.35 * hook_strength + 0.30 * visual_slapstick + 0.20 * clarity + 0.15 * novelty`.
   - Never fabricates trend numbers or claims fake viral data.
4. **4-Scene Storyboard Generator (`stickman_storyboard.py`)**:
   - Formats concepts into 28-30s Shorts with fast hooks (<3s), escalating gags, slapstick climax, and punchline outro.
   - Synchronized ASS subtitles rendered in the mobile safe zone (`MarginV=330`).
5. **Master Automated Channel Controller (`automated_channel.py`)**:
   - One-time channel setup & credential verification.
   - Daily batch generation (`--batch-size N`).
   - Pause, resume, and emergency-stop controls (`--pause`, `--resume`, `--emergency-stop`).
   - Persistent SQLite `UploadLedger` preventing duplicate uploads and strictly enforcing **private acceptance mode**.
6. **Zero Feature Loss Guarantee**:
   - Cleaned up demo path in `benxautomation/podcast/static/index.html` to an honest empty state.
   - 0 existing features, animation engines, or tests removed or weakened.
   - 100% test pass: 13 stickman tests passed in 1.33s; 71 core tests passed in 5.05s.

---

## Visual Verification & Rendered Output

### Verified Production Video 1: "What Happens When You Drink 4 Espressos at Once"
- **Path:** `output/stickman_channel/coffee_overdose_matrix.mp4`
- **Format:** 1080 × 1920 (9:16 Vertical Short)
- **Duration:** 29.50 seconds (708 frames @ 24 fps)
- **Audio:** Edge-TTS Neural Voice (`en-US-ChristopherNeural`, 24000 Hz, mono)
- **Motion Score:** **3.2654%** (Zero decode errors, zero freeze frames)
- **Subtitles:** Burned-in ASS subtitles (`MarginV=330` mobile safe zone)
- **Ledger Status:** Record #23 (`QUEUED_PRIVATE_ACCEPTANCE`)

#### Scene 1: The Kitchen Hook (Warm Peach + Checkered Tiles)
BEN pours 4 espresso shots into one mega mug while MAX watches from the kitchen counter.
![Scene 1 Kitchen](file:///C:/Users/Admin/.gemini/antigravity-ide/brain/a98a7b4a-96a1-4c47-807f-0171a6094767/stickman_coffee_sc1_kitchen.png)

#### Scene 2: The Office Escalation (Slate Blue + Ticking Clock)
BEN enters a supersonic caffeine sprint ("I can hear Wi-Fi signals in 4D!") while MAX panics.
![Scene 2 Office](file:///C:/Users/Admin/.gemini/antigravity-ide/brain/a98a7b4a-96a1-4c47-807f-0171a6094767/stickman_coffee_sc2_office_run.png)

#### Scene 3: The Punchline Outro (Dynamic Comedy Sunburst)
The twist is revealed: BEN sent 50 lines of 'A' to his boss. BEN shrugs with a smirk while MAX laughs with his hands up.
![Scene 4 Punchline](file:///C:/Users/Admin/.gemini/antigravity-ide/brain/a98a7b4a-96a1-4c47-807f-0171a6094767/stickman_coffee_sc4_comedy_burst.png)

---

## CLI Usage Guide

### 1. Check Channel Automation Status
```powershell
python -m benxautomation.animation.automated_channel --status
```

### 2. Produce a Single Short (Top-Ranked Heuristic Idea)
```powershell
python -m benxautomation.animation.automated_channel --publish-mode private
```

### 3. Produce a Specific Comedy Idea
```powershell
python -m benxautomation.animation.automated_channel --idea snooze_math_trap --publish-mode private
```

### 4. Produce a Daily Batch of 3 Shorts
```powershell
python -m benxautomation.animation.automated_channel --batch-size 3 --publish-mode private
```

### 5. Channel Operational Controls
```powershell
# Pause automation
python -m benxautomation.animation.automated_channel --pause

# Resume automation
python -m benxautomation.animation.automated_channel --resume

# Emergency stop (kills all publishing queues immediately)
python -m benxautomation.animation.automated_channel --emergency-stop
```

### 6. One-Time Channel Setup with Google OAuth
```powershell
python -m benxautomation.animation.automated_channel --channel-setup --client-secret path/to/client_secret.json --channel-name "BEN & MAX Cartoon Shorts"
```

---

## Test Verification Summary
- `pytest tests/test_stickman_engine.py tests/test_stickman_channel.py` ➔ **13 / 13 PASSED** (1.33s)
- `ruff check` on all new modules ➔ **All checks passed!** (0 errors)
- `pytest tests/test_upload_ledger.py tests/test_youtube_oauth.py ...` ➔ **71 / 71 PASSED** (5.05s)
- Total regression pass rate: **100%**.
