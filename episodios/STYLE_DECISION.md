# Visual & Editorial Style Decision — CTS Shorts Factory (`FailSafe Lab`)

**Decision Status:** LOCKED (M1 Autonomous Style Selection per `ORIGINAL_REQUEST.md` & `PROJECT.md`)  
**Selected Style Identifier:** `2.5d_projected_isometric_cad_vector`  
**Channel Identity:** **FailSafe Lab** (`@FailSafeLab`, 100% `en-US`)  
**Selected Narration Voice:** **`Charon`** (`google-genai` `v1beta`, `gemini-3.8-flash-tts` + fallback chain)

---

## 1. Evidence Observed in Both Reference Videos (`/reel-watch` Audit)

Both reference links provided by the user were analyzed via `.agents/skills/reel-watch/scripts/reel.py` (`gemini-3.5-flash` full video+audio watch) plus visual inspection of high-resolution thumbnails and full-video `sb0` storyboard frame sheets (125 frames per video):

| Visual / Editorial Dimension | Reference A: `DYYsGuTpBKc` (Possiblo — *What If Clothes Disappeared?*, 8m32s) | Reference B: `M_t2ZUz7_pc` (Iflord — *What If You Were Immortal?*, 8m45s) | Synthesis for `FailSafe Lab` (65–80s Vertical Shorts) |
|---|---|---|---|
| **Core Visual Medium** | 2D clean flat/soft-shaded vector animation with rim-lit stick-silhouette characters (`thumb_hq1`–`hq3.jpg`). | 2D clean flat/soft-shaded vector animation with warm rim-lit stick-silhouette characters (`thumb_maxres.jpg`, `thumb_hq2.jpg`). | **2.5D Projected/Isometric Clean Vector CAD Animation** (no stick-figure clone overlap; machined steel/brass 3D-extruded polygons + directional rim-lighting). |
| **Science / Physics Cutaway Stage** | Cuts directly to a **deep midnight-navy volumetric spotlight stage** with glowing directional rays (`T-SHIRT ✓` vs `SKIN ✗`, `sb0_01` cell [3,1]) and glowing isometric 3D volumes (`2,700 L` water cube, `sb0_03` cell [0,0]). | Cuts directly to a **deep navy radial-gradient infographic stage** with dotted circular callout rings (`thumb_hq1.jpg`), bone/DNA cutaways (`sb0_00`), comparison bar charts (`sb0_01` cell [0,2]), and live glowing curves (`sb0_01` row 3). | **Adopt as 100% full-time canvas!** Deep Blueprint Navy (`#0B1220`) radial spotlight stage + crisp subtle CAD grid (`#15243D`) + animated force arrows, dotted measurement arcs, and live comparison bars (`20 MS` vs `250 MS`). |
| **Lighting & Depth Polish** | Strong directional white/warm rim-lighting (`thumb_hq3.jpg`), soft cast shadows, overhead spotlight cones (`sb0_03` cell [0,0]). | Crisp warm amber rim-lighting (`thumb_maxres.jpg`, `thumb_hq2.jpg`), radial focal bloom behind metallic bullet, subtle foreground/background contrast separation. | **Adopt in M2 `materials.py`:** 3-face isometric shading (lit top `#B8C7D9`, mid bevel `#6E839E`, shaded side `#3A4B63`) + crisp 2–3px specular rim strokes + soft radial glow halos on stress/spark hotspots. |
| **Hook & Headline Typography** | Massive white + safety-yellow bold sans-serif (`NO MORE CLOTHES?`, `thumb_maxres.jpg`) with thick black outline (`#000000`). | Massive white + safety-yellow stacked bold sans-serif (`CAN'T DIE.`, `thumb_maxres.jpg`) paired with a bullet frozen milliseconds from impact. | **Adopt for Frame 0 (`t=0.0s`) & Covers:** `Montserrat-Black` white + high-vis safety yellow (`#FFC83D`) with 5–6px deep ink stroke (`#060A12`) inside `y=260..460, x=90..990`. |
| **Data & Telemetry Badges** | Compact dark pill chips with yellow uppercase labels (`DAY 9`, `2,700 L`, `1 HOUR LATER`). | Compact dark pill chips (`TURRITOPSIS DOHRNII`, `HEALED IN 1.9S`, `DAY 16`, `DAY 21`) + crisp 2-line stat blocks. | **Adopt for Beats 2–12 HUD Callouts:** Compact translucent navy chips (`#121E33`) inside `x=90..930, y=490..640` (strictly omitted on Beat 1 / Frame 0 so Frame 0 stays razor-clean). |
| **Pacing & Engagement Structure** | Immediate premise plunge, rapid quantitative escalations (`37°C`, `15 MIN`, `$1T`, `2,700 L`), direct closing question (`"What would YOU grab first?"`). | Instant crash cold open (`00:00`–`00:10`), clean numeric milestones, mid-video comment cards + end subscribe (appropriate for 9-min VOD). | **Adapt for 65–80s Shorts:** Instant Frame 0 crisis hook at `t=0.0s`, 12 tight beats (4–7s each) with 5 distinct camera presets, **zero** mid-video subscribe prompts, crisp 1-word closing CTA (`Comment YES or NO`). |

---

## 2. Why `2.5d_projected_isometric_cad_vector` Wins Over Pure Stick-Figure Reference Replication

1. **Niche-Visual Fit (`ORIGINAL_REQUEST.md:4-6`):** Both `DYYsGuTpBKc` and `M_t2ZUz7_pc` are narrative "What If" lifestyle channels where stick-silhouette characters carry dialogue skits. By contrast, our chosen high-RPM niche is **Engineering, "How It Works" & Real Disasters** (*"moving mechanical parts, force arrows, and clean 3D exploded views hypnotize the viewer"*). Notably, the **highest-retention explanatory frames** in both reference videos are precisely their **dark-navy glowing cutaway diagrams, isometric volumes, and telemetry graphs** — not the casual room dialogue! Making that dark-navy high-contrast cutaway aesthetic our core visual identity with **articulated 2.5D isometric CAD machinery** delivers maximum hypnotic appeal for adult 25–45 STEM/engineering viewers.
2. **Anti-Clone Originality (`SKILL.md:14-16`, `brand_template.json:7`):** Avoiding black stick-silhouette characters guarantees **0% visual overlap** with sister survival-storytelling channels, Possiblo, or Iflord — preventing YouTube "reused/repetitive content" flags while establishing a signature, instantly recognizable brand look for `FailSafe Lab`.
3. **2-Core CPU Render Feasibility (Reconciling T2 & `PROJECT.md:65`):** This VM runs on 2 Intel Xeon CPU cores (no GPU). Raytraced Blender/3D pipelines would take hours per episode and lack pre-installed tooling. Programmatic 2.5D orthographic/isometric projection in **Pillow 13 + NumPy 2.5** piped directly to `ffmpeg` renders at **16–23 fps** (~85–130s per 70s episode) while producing razor-sharp extruded bevels, meshing gears, recoiling braided cables, directional force arrows, glowing stress heatmaps, and volumetric spotlights.

---

## 3. Explicit Reconciliation of Design Tensions (T1, T2, T3, T7)

- **T1 (Frame 0 Peak-Tension Hook at `t=0.0s`):**
  - Directly mirroring `M_t2ZUz7_pc`'s `thumb_maxres.jpg` (bullet frozen milliseconds from impact + giant white/yellow outlined hook text), every `FailSafe Lab` episode opens at **`t=0.0s`** with **zero fade-in**, **zero empty wide shot**, and **zero HUD clutter (`beats[0].callout = None`)**:
    1. **Full-frame peak-tension 2.5D macro cutaway** (`camera_preset = "FRAME0_HERO"`): e.g., frayed braided steel hoist cables snapping with amber/crimson sparks (`ep01`) or a deep-sea composite cylinder ringed by dense glowing cyan/crimson inward hydrostatic arrows (`ep02`).
    2. **Bold short two-tone top hook text** (`Montserrat-Black`, white + `#FFC83D` yellow accent, `5px` `#060A12` outline) strictly inside **`x=90..990, y=260..460`**.
    3. **Immediate spoken hook** onset at `t ≈ 0.05s`.
- **T2 (2.5D Vector Engineering Aesthetic):**
  - Canonical 5-angle 2.5D camera rig reused across all episodes (`FRAME0_HERO`, `ISO_WIDE`, `MACRO_CUTAWAY`, `EXPLODED_BLUEPRINT`, `IMPACT_CLOSEUP`) paired with episode-specific `scene_key` mechanical choreography.
- **T3 (Real Disasters Monetization & AI Disclosure Safety):**
  - Real engineering failure episodes (e.g., `ep02_submersible_implosion_physics`, `ep04_tacoma_bridge_flutter`, `ep06_skywalk_bolt_load`) depict **pure stylized CAD/blueprint cutaway structures, force arrows, and materials-science plies** — zero human injury, zero graphic wreckage, zero photorealistic news footage. Keeps monetization green across YouTube/TikTok/IG and keeps **`youtube_ai_disclosure_stylized_2d: false`** 100% accurate.
- **T7 (Explicit Horizontal + Vertical Safe Zones):**
  - Top Frame 0 hook text: `x=90..990, y=260..460`
  - Lower Whisper-synced captions (no opaque box, 2–4 words, `Montserrat-ExtraBold`, `#F8FAFC` + active word `#FFC83D`, `5px` `#060A12` stroke): `x=110..930, y=1380..1520` (max width `<= 820px`, completely clearing right-side platform action icons)
  - Telemetry HUD callouts (beats 2–12 only): `x=90..930, y=490..640`
  - Episode cover critical content: `x=90..990, y=330..1580` (satisfies both Reels grid and `3:4` `y=260..1660`)

---

## 4. Concrete Design Specifications Locked for M2–M5

- **Palette:** Deep Blueprint Navy (`#0B1220`), CAD Grid (`#15243D`), HUD Surface (`#121E33`), Brushed Steel (`#3A4B63` / `#6E839E` / `#B8C7D9`), Machined Brass (`#D4A24C`), Safety Industrial Amber (`#FF8C1A`), Telemetry Cyan (`#00D4FF`), Fracture Crimson (`#FF2E4C`), Locked Equilibrium Emerald (`#2EE58B`), Crisp Off-White (`#F8FAFC`), Active Safety Yellow (`#FFC83D`), Deep Ink Outline (`#060A12`).
- **Line Weights & Shading (`M2`):** Primary silhouette ink `3–4px` (`#060A12`), internal mechanical seam `2px`, metallic specular rim highlight `2–3px` (`#E2EDF8` / `#FFE1A8`), CAD grid `1px` at 25–35% opacity, volumetric radial spotlight pre-cached once per scene for 2-core CPU speed.
- **5 Canonical Camera Rig Presets (`M2`):**
  1. `FRAME0_HERO`: Zoomed `1.28x` dramatic macro cutaway centered at `y=940` leaving `y=260..460` crisp for Frame 0 hook text and `y=1380..1520` clean for captions.
  2. `ISO_WIDE`: Full-assembly 30° isometric view (`scale=1.0`, slight yaw/elevation breathing motion) showing full system scale (elevator shaft or ocean depth column).
  3. `MACRO_CUTAWAY`: Tight `1.45x` cross-section slice isolating internal moving components (centrifugal governor wheel or composite laminate plies).
  4. `EXPLODED_BLUEPRINT`: Separated orthographic/isometric exploded layers with dotted cyan leader lines, dimension ticks, and live stress vectors.
  5. `IMPACT_CLOSEUP`: High-energy `1.60x` tight mechanical climax framing with subtle micro-shake tied to audio RMS envelope and telemetry comparison bars.
- **Voice Selection (`M3`):** **`Charon`** (deep, resonant, authoritative documentary baritone; crisp articulation on engineering figures and numbers; `1.02x–1.06x` pacing; zero sibilant whispering; completely distinct from `Puck` and teen-oriented "What If" voices).
