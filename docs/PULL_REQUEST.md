# Pull Request: Improve mascot animation safe zones and subtitle rendering

**Target Branch:** `main`  
**Source Branch:** `feature/audit-bugfixes-v2-prep`  
**GitHub Actions Verified Run:** [#38421804975](https://github.com/kabeesh395-oss/BENXAUTOMATION/actions/runs/38421804975) (Python 3.11 & 3.12: **SUCCESS** 🟢)  
**One-Click PR Link:** [Create PR on GitHub](https://github.com/kabeesh395-oss/BENXAUTOMATION/compare/main...feature/audit-bugfixes-v2-prep?expand=1&title=Improve%20mascot%20animation%20safe%20zones%20and%20subtitle%20rendering)

---

## 1. Summary of Changes

### A. 2D Mascot Animation & Visual Framing
- **Vertical Re-framing for 9:16 Shorts:** Shifted character base Y from `0.32` to `0.22` of canvas height (`benxautomation/animation/mascot_engine.py`). Character sits in the middle-stage without colliding with lower-third subtitle banners.
- **Horizontal Framing for 16:9 Long-Form:** Set character base Y to `0.12` of canvas height with 1.2x scale, perfectly framing landscape presentations.
- **Upper Cyber HUD Pill:** Replaced the lower-third action text box (previously at Y=78% in tiny monospace font) with an Upper HUD cyber pill (`by1 = int(height * 0.10)` in 9:16, `0.05` in 16:9). Utilizes TrueType Arial Bold typography (`[ QUANTUM LEAP ]`, `[ PARALLEL QUBITS ]`) with rounded borders and cyan neon accents.

### B. Dynamic Subtitle Chunking & Safe Margin Enforcement
- **Phrase Chunking (`_chunk_dialogue_cues`):** Replaced monolithic 15-word dialogue blocks with concise 4-6 word dynamic cues (`benxautomation/animation/story_pipeline.py`). Captions now render in synchronized 1-2 line phrases instead of occluding 35% of the frame in a 4-line text wall.
- **Native ASS Subtitle Generation:** Integrated Advanced SubStation Alpha (`.ass`) generation with exact resolution definitions (`PlayResX: 1080, PlayResY: 1920` for Shorts; `PlayResX: 1920, PlayResY: 1080` for Long-Form).
- **Mobile Safe Margin (`MarginV=330`):** Aligns subtitles strictly inside the YouTube mobile safe zone (Y ~ 1520-1560px), safely above mobile UI overlays (channel handle, audio title, description, like/share icons) and below the mascot torso.

### C. Cloud Resilience & Offline Script Fallback
- **API Rate-Limit / Quota Interception:** Added graceful fallback in `benxautomation/pipeline.py` when primary remote providers encounter HTTP 429 quota exhaustion or network failures, routing directly to the offline fallback provider to guarantee that cloud automation jobs never crash or drop video generation.
- **Workflow Topic Fallback:** Configured deliberate fallback-to-topic execution in `.github/workflows/podcast_shorts_automation.yml` (`--fallback-to-topic`) and `.github/workflows/longform_automation.yml` (`--provider fallback`).

### D. CI Workflow Modernization
- **Feature Branch Testing:** Updated `.github/workflows/ci.yml` push triggers to include `feature/**`, ensuring automated validation before merging.

---

## 2. Commit Lineage & CI Verification

```text
* b693c3a (HEAD -> feature/audit-bugfixes-v2-prep, origin/feature/audit-bugfixes-v2-prep) ci: trigger CI workflow on feature branch pushes
* 704da73 feat(animation): fix mascot safe-zone positioning, HUD pills, and ASS subtitles
* ec2fbcd fix(workflows): repair CI requests mutation, eliminate silent skips, and add comprehensive audit & QA documentation
* 4a8ff0c fix(ci): align acceptance test duration assertion with container framing tolerance
* 74aa32b fix(ci): size synthetic speech audio under target frame boundary to prevent padding overflow
```

* **Parent Relationship Verified:** `704da73` is the direct ancestor of `b693c3a` (`git merge-base --is-ancestor 704da73 b693c3a` returned 0).
* **Remote CI Run Verified:** [GitHub Actions Run 38421804975](https://github.com/kabeesh395-oss/BENXAUTOMATION/actions/runs/38421804975)
  - `test (3.11)` on Ubuntu: **SUCCESS**
  - `test (3.12)` on Ubuntu: **SUCCESS**
  - Ruff Linter: **SUCCESS**
  - Pytest Suite: **SUCCESS**

---

## 3. Local Test & Render Evidence

| Check | Expected | Actual Result | Status |
| :--- | :--- | :--- | :--- |
| **Ruff Check** | 0 lint errors | `All checks passed!` | **PASS** |
| **Pytest Suite** | 267 tests | `267 passed in 157.88s` | **PASS** |
| **Regression Tests** | Cue chunking & ASS margins | `test_story_pipeline_subtitle_phrase_chunking_and_ass_styling` passed | **PASS** |
| **Shorts 9:16 Render** | 1080x1920, 24fps | `ai_quantum_leap.mp4` (25.0s, 6,060,915 bytes) | **PASS** |
| **Shorts Decode** | FFmpeg full decode | `0 errors, returncode 0` | **PASS** |
| **Long-Form 16:9 Render** | 1920x1080, 24fps | `benx_quantum_longform.mp4` (12.17s, 2,990,122 bytes) | **PASS** |
| **Long-Form Decode** | FFmpeg full decode | `0 errors, returncode 0` | **PASS** |
| **Secrets Scan** | 0 leaked credentials | `0 secret leaks detected` | **PASS** |

---

## 4. Visual QA Evidence

- **Before/After Comparison:** `output/mascot_sample/before_after_comparison.png`
- **Shorts Opening (01s):** `output/qa_visual_inspection/shorts_opening_01s.png`
- **Shorts Middle (12s):** `output/qa_visual_inspection/shorts_middle_12s.png`
- **Shorts Ending (23s):** `output/qa_visual_inspection/shorts_ending_23s.png`
- **Long-Form Opening (02s):** `output/qa_visual_inspection/longform_opening_02s.png`
- **Long-Form Middle (06s):** `output/qa_visual_inspection/longform_middle_06s.png`
- **Long-Form Ending (10s):** `output/qa_visual_inspection/longform_ending_10s.png`

---

## 5. Known Limitations & Next Steps

1. **Procedural Rig Assets:** Current character rig utilizes 2D SVG/PNG composite layers (eyes, visor, visemes, torso, arms). Complex bone rigging / inverse kinematics is slated for V2.
2. **YouTube Production Credentials:** Scheduled cron workflows are set to `--mode upload_private` and require GitHub repository secrets (`PODCAST_SCHEDULED_SOURCE_URL`, `YOUTUBE_CLIENT_SECRET_JSON`, `YOUTUBE_TOKENS_JSON`) for unattended channel uploads.
