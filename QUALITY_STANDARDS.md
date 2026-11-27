# FailSafe Lab — Minimum Quality Standard (`CTS` Project)

This document defines the **mandatory minimum quality floor** for every current (`ep01`–`ep10`) and future (`ep11+`) episode in `rradkch-svg/CTS`. Every rule below is enforced by both **automated tests** ([`tests/test_visual_standards.py`](tests/test_visual_standards.py)), the **QA validator** ([`src/cts_factory/qa/validator.py`](src/cts_factory/qa/validator.py)), and the **production skill** ([`.agents/skills/shorts-factory/SKILL.md`](.agents/skills/shorts-factory/SKILL.md)).

---

## 1. Platform Safe Zones (1080×1920, 9:16)

1. **Right-Side UI Dead Zone (`x > 855`):**
   - TikTok, Instagram Reels, and YouTube Shorts overlay Like/Comment/Share buttons on the right margin.
   - **ALL** interactive pills (`draw_cta_buttons`), comparison bar cards (`draw_comparison_bars`), circular gauges (`draw_pressure_gauge`), HUD callouts (`draw_hud_callout`), and in-scene 2D labels MUST stay strictly inside **`x <= 855`** (hard pixel ceiling `x < 870`).
   - **NEVER** hand-roll raw `YES` / `NO` rectangles in episode files — always call [`draw_cta_buttons(...)`](src/cts_factory/engine/primitives.py).
2. **Lower Caption Safe Zone (`y <= 1418`, `x <= 875`):**
   - Captions MUST use generous word spacing (`>= 0.34 * font_size`), max font size `56`, bold ink stroke, and zero opaque backing boxes.
   - Position captions so they never collide with platform bottom metadata or cut across BOLT's face/torso.
3. **Cover 1:1 Center Crop (`y = 420..1500`):**
   - Every episode cover (`cover.png` + `cover.jpg`, `1080x1920`) MUST keep its series badge (`y = 432..484`), 2-line headline (`y = 498..636`), and bottom pill (`y = 1424..1484`) strictly inside the **1:1 center square (`y = 420..1500`)** so zero text is ever clipped in Instagram/TikTok/YouTube profile grids.
   - Every episode's `render_cover_hero` MUST support dedicated cover framing (`is_cover=True`) so the 3D subject sits cleanly between the top headline and bottom pill (zero text colliding with 3D objects or BOLT's helmet), backed by dark vignette scrims (`_apply_cover_scrims`).
4. **Frame 0 Hook Headline Safe Zone (`x = 215..865`, `y = 310..485`):**
   - When platforms use Frame 0 as a profile grid thumbnail (e.g., Buffer Free `thumbnailOffset: 0`), Instagram overlays its top-right Reels play icon (`[▶]`) at `x ≈ 880..1040`.
   - [`draw_top_hook`](src/cts_factory/engine/primitives.py) MUST hard-clamp the Frame 0 headline symmetrically around `cx = 540` with **`x <= 865`** (hard pixel ceiling `x <= 870`) and **`y >= 305`** so no word is ever clipped by the Reels `[▶]` badge.

---

## 2. BOLT (`UNIT-01`) Character & Narrative Standards

1. **Zero Vehicle / Cockpit Leg Clipping:**
   - Whenever BOLT sits inside a vehicle, cockpit, coaster car, capsule hatch, or submarine, **MUST pass `show_legs=False`** to [`add_crash_test_dummy(...)`](src/cts_factory/engine/dummy.py) so legs NEVER poke through floors or hulls.
2. **Grounded Contact & Unobstructed Face:**
   - Standing BOLT MUST have boots resting flush on real solid geometry (floor, cab deck, steel catwalk, observation deck) — never floating in mid-air.
   - `brace_impact` hands MUST stay wide of the curved glass visor (`abs(x) >= 0.45`) so BOLT's expressive LED eyes are never hidden.
   - Keep BOLT positioned clear of 2D comparison cards, gauges, and 3D arrows (no amputated arms behind cards, no arrows impaling his head).
3. **No Character Cloning & Interactive Beats:**
   - **NEVER** render two BOLTs in the same frame.
   - Include interactive narrator-to-BOLT moments (waving, physical comedy/reactions directly tied to the mechanism, e.g., sliding down the dam spillway when the floodgates open, waving from an open capsule hatch, cruising in his Yellow Car or Yellow Sub).

---

## 3. 3D Mechanical, Material & Physics Fidelity

1. **Authentic Materials (No Rivets on Concrete):**
   - Use `texture="concrete"` or `"matte"` for concrete, asphalt, rock, and resin; `texture="painted_metal"` for vehicle hulls; `texture="brushed_steel"` / `"machined_brass"` / `"carbon_weave"` strictly for metal/carbon parts.
2. **Real 3D Mechanical Parts (No Primitive Substitutes):**
   - **Springs:** Always use [`Scene3D.add_coil_spring(...)`](src/cts_factory/engine/renderer3d.py) for helical springs (never stacked coins/cylinders).
   - **Gears & Differentials:** Use real toothed bevel/spur gears with radial teeth orientation and physical shafts/cross-pins (never smooth spheres).
   - **Cutaways:** Open 180°/210° cutaway shells so internal parts and BOLT are 100% unobstructed (never closed 360° opaque cylinders blocking the interior).
   - **Parachutes & Fluids:** Use concave open-skirt canopies for parachutes; continuous translucent sheets + spray/foam for water/fluid flow (never rigid hexagonal sticks).
3. **Mathematical & Physical Accuracy:**
   - **Curved-Path Vehicles:** With `rot_matrix(0, yaw, 0)` mapping local `+X` to `(cos(yaw), 0, -sin(yaw))`, a vehicle following `(R*sin(a), y, z0 + R*cos(a))` MUST use **`yaw = +a`** (and road tiles `rot=(0, +a, 0)`) so the vehicle turns strictly tangent to the curve.
   - **Smooth Oscillation:** Never flip sign discontinuously (`1.0 if sin >= 0 else -1.0`); always use continuous trigonometric motion.
   - **Exact Counts & Proportions:** Spoken part counts MUST match 3D counts (`24 bolts` = `24` bolts in 3D). Comparison bar fractions MUST be mathematically exact (`0%` = empty track, `100%` vs `200%` = `0.50` vs `1.00`).
   - **Zero Rendering Artifacts:** Zero Z-fighting (never overlap coaxial cylinders at nearly identical radii), zero black floor grids in open sky/ocean scenes, zero bloom bleeding through opaque walls, zero detached floating parts during collapse/implosion.

---

## 4. Semantic HUD, Gauges & Typography

1. **Semantic Badge Coloring ([`resolve_callout_accent`](src/cts_factory/engine/renderer.py)):**
   - Safe / passed / solution / CTA badges MUST render in **emerald** (or cyan for neutral telemetry) — NEVER red danger borders.
   - Failure / overload / warning / climax badges render in **danger crimson**.
2. **Legible Self-Contained Gauges:**
   - All dial text MUST auto-fit strictly inside the dial circle, with the needle drawn behind a dark readout backing plate.
   - Live gauge numbers MUST match the beat's HUD callout value (no contradictory numbers on screen).
   - Use `invert_scale=True` when high percentage means safety/protection (e.g., `98% PUSHED`, `99% CAUGHT`, `ZERO POWER` lock).
3. **Typography & Units:**
   - Always use real typographic symbols (`°F`, `°`) instead of `DEG F` / `DEG` in all new scripts and on-screen telemetry.
   - Avoid splitting numbers from their units across lines in top hooks (e.g., keep `40 FT` together).
4. **Cross-Platform Ending CTA (YouTube Shorts + TikTok + Instagram Reels — `ep11+`):**
   - Never say `"Subscribe"` mid-video or at the end (sounds recycled on TikTok/Instagram).
   - In the final ~2 seconds (Beat 12, seamlessly attached to the ending question with BOLT waving), close with the canonical cross-platform line:
     > **`"Follow FailSafe Lab before the next machine breaks — and comment YES or NO."`**

---

## 5. Mandatory Automated & Visual QA Gate

Before any episode is considered final or merged:

1. **Automated Standards & Unit Suite (100% pass):**
   ```bash
   PYTHONPATH=src:. uv run --offline --with pytest --with pillow --with numpy --with google-genai --with faster-whisper --with rapidocr --with onnxruntime --with imageio-ffmpeg pytest -q
   ```
2. **Pre-Render Visual Preview:** Render key beats + `cover.png` and visually inspect them before committing CPU time to a full MP4 render.
3. **Final Render + Technical QA + `/reel-watch` (0 violations):**
   - Dedicated sequential `render --episode <slug> --final`
   - `qa --episode <slug> --with-reel-watch` (`1080x1920`, `30 fps`, `65–80s`, `-14.5 ± 1.2 LUFS`, `TP <= -1.0 dBTP`, `0` silence gaps, `0` violations)
   - Visually inspect extracted frames and `cover.png` to confirm zero overlaps, clipping, or narrative disconnects.
4. **Secret & Git Hygiene:** Never stage, print, or commit `.env`, `reels/`, `cache/`, or API keys.
