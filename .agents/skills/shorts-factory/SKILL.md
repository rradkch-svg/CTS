---
name: shorts-factory
description: End-to-end production, packaging, and QA pipeline for original 3D/2.5D animated Shorts/Reels/TikToks (65–80s, 9:16, 30fps) designed for high retention and monetization. Use whenever planning, scripting, rendering, auditing, or packaging a short-form animated video in this repository.
---

# Shorts Factory — Production & Minimum Quality Playbook

This skill encodes the battle-tested rules and **mandatory minimum quality floor** (see also [`QUALITY_STANDARDS.md`](../../../QUALITY_STANDARDS.md)) for producing original, high-retention 3D/2.5D animated short-form videos (`9:16`, `1080x1920`, `30 fps`) for **YouTube Shorts**, **TikTok (>61s Creator Rewards eligible)**, and **Instagram Reels**.

---

## 1. Pre-Production Rules (Before Generating Anything)

1. **Uniqueness Test (YouTube "Inauthentic Content" defense):**
   - Always use this channel's distinct character rig (**BOLT / `UNIT-01`**), palette, voice (`brand.json`), and original scripts. Never recycle identical art/voice across different channels.
2. **Autonomous Episodes for Daily Consistency:**
   - Every episode must stand on its own (no waiting on viewer comments before producing the next video).
3. **Target Duration:**
   - **`65–80 seconds`** (hard floor `>= 62s` for TikTok Creator Rewards eligibility while staying punchy on Shorts & Reels).
4. **Frame 0 (`0.0s`) = Feed Cover (Most Important Retention Lever):**
   - Never open on an empty wide shot or slow fade-in.
   - Open at `t = 0.0s` on peak-tension 3D action + short high-contrast two-tone hook text across the top (`x = 215..865`, `y = 310..485`, clearing the Instagram Reels grid `[▶]` badge), immediately paired with a sharp spoken hook.
5. **Interactive BOLT Beats & Zero Mid-Video Subscribe Prompts:**
   - Never ask viewers to "like and subscribe" mid-video.
   - Include playful narrator-to-BOLT interaction beats (e.g., waving, comedic reactions tied directly to the mechanism such as sliding down a flooded dam spillway or cruising in his vehicle).
6. **Cross-Platform Ending Follow + 1-Word Comment CTA (`ep11+`):**
   - Never say `"Subscribe"` (breaks native feel on TikTok & Instagram).
   - Close seamlessly in the final ~2 seconds (Beat 12, while BOLT waves) with our canonical cross-platform line + 1-word prompt:
     > `"Follow FailSafe Lab before the next machine breaks — and comment YES or NO."`

---

## 2. Minimum Visual, 3D & UI Quality Standards (Mandatory Floor)

Every episode MUST satisfy all rules below (enforced automatically by `tests/test_visual_standards.py` and `qa/validator.py`):

### Safe Zones (`1080x1920`, 9:16)
- **Right UI Dead Zone (`x <= 855`):** ALL CTA buttons (`draw_cta_buttons`), comparison bars (`draw_comparison_bars`), gauges (`draw_pressure_gauge`), HUD callouts (`draw_hud_callout`), and in-scene 2D labels MUST stay strictly inside **`x <= 855`** (clearing TikTok/Reels/Shorts right-edge icons). Never hand-roll custom `YES`/`NO` buttons.
- **Lower Captions (`y <= 1418`, `x <= 875`):** Synced to word-level `faster-whisper` timestamps, 2–4 words per block, bold outlined white + yellow accent, generous word spacing (`>= 0.34 * font_size`), zero opaque backing boxes.
- **Cover 1:1 Center Crop (`y = 420..1500`):** Top series badge (`y=432..484`), 2-line headline (`y=498..636`), and bottom pill (`y=1424..1484`) MUST fit strictly inside the 1:1 square crop with dark vignette scrims (`_apply_cover_scrims`) and dedicated `is_cover=True` camera framing so ZERO text collides with 3D objects or BOLT's helmet.

### BOLT (`UNIT-01`) Standards
- **Seated Vehicle Rule:** Always pass `show_legs=False` to `add_crash_test_dummy(...)` when BOLT sits inside a car, submarine, mini-jet, coaster car, or capsule hatch — zero legs poking through floors/hulls.
- **Grounded & Unobstructed:** Standing BOLT MUST have boots flush on real geometry (floor, cab deck, steel catwalk, observation deck), never floating in empty air; `brace_impact` hands stay clear of visor eyes; never clone two BOLTs in one frame.

### 3D Mechanical, Material & Physics Fidelity
- **Materials:** Use `texture="concrete"` / `"matte"` for concrete/asphalt/resin (never brushed steel with rivets); `texture="painted_metal"` for vehicle shells.
- **Real Mechanisms:** Use `Scene3D.add_coil_spring(...)` for springs (never stacked coins/cylinders); toothed bevel/spur gears with radial teeth and shafts/cross-pins (never smooth spheres); open 180°/210° cutaways (never closed opaque cylinders hiding the interior); concave open-skirt parachutes; continuous translucent water sheets + foam (never rigid hexagonal sticks).
- **Math & Physics Accuracy:**
  - Curved-path vehicles on `(R*sin(a), y, z0 + R*cos(a))` MUST use **`yaw = +a`** and road tiles `rot=(0, +a, 0)` so the vehicle turns strictly tangent to the curve.
  - Use continuous trig oscillation (never discontinuous `1.0 if sin >= 0 else -1.0` teleportation).
  - Part counts (`24 bolts` = `24` in 3D), comparison bar fractions (`0%` = empty track; `100%` of `200%` = `0.50`), and live gauge values MUST exactly match narration and badges.
  - Zero Z-fighting (no duplicate coaxial cylinders), zero black floor grids in sky/ocean scenes, zero bloom bleed through opaque walls, zero detached floating parts during collapse/implosion.

### Semantic HUD & Gauges
- **Badge Colors (`resolve_callout_accent`):** Safe/passed/solution/CTA badges MUST be **emerald** (never red); failure/overload/climax badges in **danger crimson**; neutral telemetry in **cyan**.
- **Gauges (`draw_pressure_gauge`):** All text auto-fits strictly inside the dial circle; needle renders behind a dark readout backing plate; use `invert_scale=True` when high % = good/safe; use proper `°F` / `°` symbols (never `DEG F`).

### Audio (`AAC 48 kHz stereo`, `192 kbps`, `-14.5 LUFS`)
- **TTS:** `gemini-3.8-flash-tts` (`v1beta`) with fallback chain & SHA-256 disk cache (`GEMINI_API_KEY` / `GEMINI_API_KEY_FALLBACK` from `.env` only — NEVER hardcode or commit keys).
- **Zero Silence Vacuums:** Continuous ambient bed + procedural SFX, `-52 dB` soft silence trim + tail padding, mastered via 2-pass `ffmpeg loudnorm` to **`-14.5 LUFS` (`True Peak <= -1.0 dBTP`, `LRA <= 4.0 LU`)**.

---

## 3. Mandatory QA Gate Before Approving Any Episode

Before marking any rendered episode final:

1. **Automated Standards & Test Suite:**
   ```bash
   PYTHONPATH=src:. uv run --offline --with pytest --with pillow --with numpy --with google-genai --with faster-whisper --with rapidocr --with onnxruntime --with imageio-ffmpeg pytest -q
   ```
2. **Pre-Render Visual Preview:** Render key beats + `cover.png` and visually inspect before running full sequential MP4 renders.
3. **Technical QA + Mandatory `/reel-watch` (0 violations):**
   ```bash
   PYTHONPATH=src uv run --offline --with pillow --with numpy --with google-genai --with faster-whisper --with rapidocr --with onnxruntime --with imageio-ffmpeg \
     python -m cts_factory.cli qa --episode <slug> --with-reel-watch
   ```
4. **Visual Frame & Cover Audit:** Inspect extracted frames, `cover.png`, and `cover_grid_preview.png` to verify zero spelling errors, zero clipping, zero safe-zone invasions, and crisp Frame 0 readability.

---

## 4. Packaging, Publishing & 48-Hour Iteration Loop

- **YouTube Channel Banner (`2560x1440`, `< 6 MB`):** Desktop strip `2560x423` (`y = 508..931`), all-device mobile safe zone `1546x423` (`x = 507..2053, y = 508..931`).
- **Title:** `<= 50 characters`, strong hook first, 1 word in **UPPERCASE**, zero `#hashtags` in title.
- **Schedule & First-Minute Pinned Comment:** Schedule uploads ahead of time at a fixed daily hour and pin a 1-tap comment prompt at publish time.
- **48-Hour Loop:** Never delete/re-upload stalled Shorts. Track *Stayed to watch (`>= 75%`)*, *Average view duration (`~100%`)*, and exact drop-off second to iterate on the next episode.
