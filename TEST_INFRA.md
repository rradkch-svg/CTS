# CTS Shorts Factory — E2E Testing Infrastructure (`TEST_INFRA.md`)

**Project:** CTS Shorts Factory (`en-US` Engineering, "How It Works" & Real Disasters)  
**Repository:** `/home/antigravity/rradkch-svg/CTS`  
**Track:** Independent Requirement-Driven Opaque-Box E2E Testing Track (`e2e_orch_1`)  
**Specification Sources:**
- `/home/antigravity/rradkch-svg/CTS/.agents/teamwork/ORIGINAL_REQUEST.md`
- `/home/antigravity/rradkch-svg/CTS/PROJECT.md` (21-Feature Inventory, Interface Contracts #1–#6, Design Tensions T1–T8)
- `/home/antigravity/rradkch-svg/CTS/.agents/skills/shorts-factory/SKILL.md`
- `/home/antigravity/rradkch-svg/CTS/.agents/skills/reel-watch/SKILL.md`
- `/home/antigravity/rradkch-svg/CTS/brand_template.json` & `.gitignore`

---

## 1. Test Philosophy

1. **Strict Opaque-Box Verification (Zero Internal Imports):**
   - `tests/e2e/` MUST NEVER import any application module from `src/` or `cts_factory` (zero `import cts_factory` / `from cts_factory ...`).
   - All assertions observe strictly external deliverables and black-box interfaces: JSON/Markdown manifests, PNG images, WAV/NPY audio artifacts, MP4 video streams (`ffprobe`, `ffmpeg ebur128`, PCM 0.5s RMS, frame extraction via Pillow/NumPy), `/reel-watch` audit folders (`reels/`), git state (`git ls-files`, `git check-ignore`, `git log`), and CLI subprocess invocations (`python -m cts_factory.cli ...`).
2. **100% Deterministic, Offline, Zero-API-Spend Execution:**
   - Canonical runner command (zero external test frameworks such as `pytest`, zero network access):
     ```bash
     uv run --offline --with pillow --with numpy python -m unittest discover -s tests/e2e -v
     ```
   - In-process Python dependencies are strictly limited to Python 3.12 stdlib (`unittest`, `json`, `re`, `wave`, `subprocess`, `pathlib`, `fractions`, `difflib`, `hashlib`, `tempfile`) plus `PIL` (`Pillow`) and `numpy`. System tools invoked via `subprocess` are `ffprobe`, `ffmpeg`, `git`, `bash`, and `uv run --offline`.
   - Subprocess CLI calls strip `GEMINI_API_KEY` and `GOOGLE_API_KEY` by default (`strip_api_keys=True`) so E2E tests **never** spend Gemini API quota.
3. **Dynamic Discovery (Zero Hardcoded Episode Slugs or Timestamps):**
   - Episodes `ep01_*` and `ep02_*` are discovered dynamically from `episodios/` and cross-checked against `episodios/themes_backlog.json`.
   - `/reel-watch` folders under `reels/` are matched by inspecting `manifest.json` (`sources`, `meta.webpage_url`, `fetched_via`, `engine`) and `breakdown.md` / `local.md` (skipping empty/incomplete orphan directories such as `reels/20261123-060431_youtube_342c/`).
   - Missing deliverables fail cleanly with descriptive `AssertionError` messages at test runtime — never crashing test discovery/collection.
4. **Dual-Target Self-Validation (`CTS_E2E_PROJECT_ROOT`):**
   - By default, `tests/e2e/helpers/discovery.py` resolves the repository root `/home/antigravity/rradkch-svg/CTS`.
   - When `CTS_E2E_PROJECT_ROOT` is set to a temporary synthetic workspace built by `tests/e2e/helpers/fixtures.py`, the exact same E2E suite can be verified for:
     - **True Positives:** Spec-compliant synthetic deliverables pass cleanly.
     - **True Negatives (Mutation Resistance):** 18 targeted single-defect mutations (short duration, wrong fps/resolution/pix_fmt, loudness violation, `-60 dB` silence vacuum, static slideshow, black Frame 0, PT-BR leakage, invalid YT titles, mid-video subscribe CTA, caption overflow, cover safe-zone clipping, oversize banner, secret leak, missing reference breakdown) are reliably caught.
5. **Tolerance & Schema Flexibility Discipline:**
   - Accept documented schema aliases between `brand_template.json` and `PROJECT.md` Contract #1 (`audio_lufs`/`loudness_target_lufs`, `audio_lra_max`/`max_lra_lu`, `audio_sample_rate`/`audio_sample_rate_hz`, `narration.models`/`narration.model`).
   - Honor T1 (Frame 0 subject flexibility for Engineering niche), T2 (autonomous visual style choice), T3 (stylized educational disaster analysis), T6 (preserved `marca/`/`episodios/` folder names and starter `README.md`/`brand_template.json` excluded from `en-US` leakage scans), and T7 (unified safe zones).

---

## 2. 21-Feature Inventory Mapped to Tiers 1–3

Every feature from `PROJECT.md § Feature Inventory` is mapped to Tier 1 (Happy Path, `>=5` tests/feature), Tier 2 (Boundary/Corner/Negative/Leakage, `>=5` tests/feature), and Tier 3 (Cross-Feature Pairwise Interactions):

| # | Feature | Observable External Artifacts / Probes | Tier 1 (`>=5` tests) | Tier 2 (`>=5` tests) | Tier 3 Seams |
|---|---|---|---|---|---|
| F01 | Reference Video Breakdown (`/reel-watch`) | `reels/*/` (`DYYsGuTpBKc`, `M_t2ZUz7_pc`), `manifest.json`, `frames/`, `breakdown.md`, `local.md`/`gemini.md`, `reels/INDEX.md`, `reel.py --help` | Both YT ref runs discovered, valid `manifest.json` + `breakdown.md` + frames, engine output present, `INDEX.md` formatted entries, visual/pacing analysis present | Nonexistent input exits non-zero, `--help` flags valid, all `INDEX.md` paths resolve, frames non-corrupt & non-blank, zero secrets in `reels/` docs | `T3-01` (F01↔F02), `T3-27` (F01↔F20↔F21) |
| F02 | Autonomous Style Selection | `brand.json::visual_style`, `retention_rules.frame_0_hook`, `brand_template.json` | Concrete `visual_style.type`, rationale `>=120` chars, cites both YT refs, T1 Frame 0 formula locked, `>=5` distinct hex palette colors | Zero `TBD`/`TODO`/`DEFINIR` placeholders, WCAG contrast (`text_primary >=7:1`, accents `>=4.5:1`), palette distinct from template, no photorealistic deepfake claim, `brand_template.json` intact | `T3-01` (F01↔F02), `T3-02` (F02↔F04↔F05) |
| F03 | Strict `en-US` Localization | `brand.json`, `themes_backlog.json`, `THEMES_CATALOG.md`, `script.json`, `captions.json`, `publish_meta.json`, `/reel-watch` `local.md`, filenames | `language == "en-US"` + ASCII handle, themes/catalog 0 PT leakage, both `script.json` 0 PT leakage, `captions.json` + `local.md` English, ASCII English filenames inside `episodios/` & `marca/` | Zero template PT placeholders (`DEFINIR_NOME_DO_CANAL`, `Rota Crítica`), zero unambiguous UK spellings (`colour`/`centre`/`aluminium`), zero mojibake (`\ufffd`, `Ã§`), zero PT CTAs (`Comente`/`Inscreva-se`), starter files preserved | `T3-24` (F03↔F20) |
| F04 | Brand Manifest (`brand.json`) | `brand.json`, CLI error behavior on invalid brand | All top-level keys present, `video_spec` exact invariants, `narration` `v1beta` + `gemini-3.8-flash-tts`, `visual_style` hex + fonts + T7 safe zones, `publishing` & `retention_rules` flags | Zero secret keys in `brand.json`, niche updated to Engineering/Disasters, `@handle` & `HH:MM` schedule regex, CLI fails fast on corrupt `brand.json`, `narration.models` fallback chain deduplicated | `T3-02`, `T3-03`, `T3-16`, `T3-28` |
| F05 | YouTube Channel Banner | `marca/youtube_banner.png`, `marca/youtube_banner_preview.png`, `marca/brand_sheet.png`, CLI `build-banner` | Exact `2560x1440` PNG `<6 MB`, preview & brand sheet valid non-blank PNGs, mobile safe zone `(507,508,2053,931)` high contrast/edge detail, desktop/TV background filled & non-white/non-alpha, brand sheet displays palette swatches | Mobile safe-zone edge clearance (no bright text strokes abutting `x=507`/`2053` or `y=508`/`931` border), banner distinct from preview (no guide overlay pixels on prod banner), `build-banner` idempotence/exit `0`, zero alpha holes (`min(alpha)==255`), TV outer strips match dark palette | `T3-02`, `T3-03`, `T3-16` |
| F06 | 6 Original Engineering / Disasters Themes | `episodios/themes_backlog.json`, `episodios/THEMES_CATALOG.md` | Exact `6` themes, exact `2` selected with rationale, unique slugs + `en-US` titles/hooks/mechanisms/CTAs, `THEMES_CATALOG.md` complete (`>=1000` bytes), all standalone autonomous | Pairwise title Jaccard `<0.50` & unique slugs, zero graphic gore/demonetization words (T3), engineering/physics/disaster domain keywords, JSON↔MD exact parity, 6-theme compilation math (`390–480s`) | `T3-04`, `T3-05`, `T3-28` |
| F07 | Full Production of Top 2 Episodes | `episodios/ep01_*/*`, `episodios/ep02_*/*`, CLI `--help` | Exactly 2 `ep01_*`/`ep02_*` folders, full 11-artifact bundle in each, both MP4s `>=2 MB` & zero-error `ffmpeg -v error` decode, distinct SHA-256 across all artifacts, CLI exposes all 7 subcommands | Zero `.tmp`/`.part`/`ep03_*` leftovers, nonexistent `--episode` exits non-zero cleanly, `ffprobe` clean container/streams, `narration_envelope.npy` finite 1D non-empty array, no raw frame dumps bloating dirs | `T3-04`, `T3-06`, `T3-20` |
| F08 | Video Master Specs | `ffprobe` + `ffmpeg` decode on both `.mp4` files | Exact `1080x1920` (9:16), `h264` + `yuv420p`, constant `30 fps` (`avg_frame_rate` within `±0.05`), duration `65.0–80.0s` (hard floor `>=62.0s`), 1 AAC stereo 48 kHz audio stream | Zero VFR drift (`|nb_frames - dur*30| <= 3`), audio/video duration parity (`<=0.25s`), square pixels SAR `1:1` & rotation `0`, healthy audio (`160–224 kbps`) & video (`0.2–15 Mbps`) bitrates, zero decode errors | `T3-10`, `T3-11`, `T3-16`, `T3-21`, `T3-28` |
| F09 | Frame 0 (`t=0.0s`) Feed Cover Hook | Frame `n=0,15` extracted via `ffmpeg`, `narration_timeline.json`, `narration_clean.wav` | Immediate full visibility (`mean_luma>=20`, `std>=25`), high-contrast top hook in `(90,260,990,460)`, top hook clears extreme top (`y<200`) & side edges, rich center hero detail (`y=480..1360`), immediate voice onset (`beat0.start_s<=0.15s`, speech energy `>-35 dBFS` within `0.45s`) | Zero fade-in ramp (`luma(f0)/luma(f15) >= 0.75`), hook luminance spread `p95-p05 >= 100`, hook clear of lower caption band & no subscribe text in `hook_text`, Frame 0 visually distinct from last frame, hook visually persists at `t=0.5s` | `T3-12`, `T3-17` |
| F10 | Real Articulated Animation & 3–5 Camera Angles | `script.json` presets, `ffmpeg` 1 fps & high-fps intra-beat frame samples | `3–5` distinct `camera_preset` values per episode, `>=85%` active motion in scene viewport (`y=460..1360`, excluding captions), zero frozen `>=3s` stretches, `>=3` visual camera cuts / distinct angle clusters, differential 4×4 spatial tile motion (anti-Ken-Burns / anti-slideshow) | No single `camera_preset` `>60%` of episode duration, zero black (`<5`) or white (`>250`) glitch frames, caption+hook masked scene still animated across all 5 acts, beat camera-cut timestamps produce visual delta, final 2s remain animated | `T3-13`, `T3-14` |
| F11 | Linux Font Safety | `assets/fonts/*.ttf`, `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`, `brand.json`, static scan of `src/`, `.gitignore`, `setup_vm.sh` | Bundled Montserrat + DejaVu exist & load in `PIL.ImageFont.truetype`, `brand.json` points to Montserrat + DejaVu Linux paths, zero Windows font paths in `brand.json`/`src/`, high-contrast crisp typography in rendered PNGs, `assets/fonts/*.ttf` gitignored & untracked | Fallback font works cleanly when primary missing (Pillow glyph test + CLI behavior), engineering symbols (`°%×—–$#'"`) render cleanly in Montserrat & DejaVu, zero unguarded `ImageFont.load_default()` in `src/`, zero `/home/` or `/Users/` paths in `brand.json`, `bash -n setup_vm.sh` exits `0` | `T3-03`, `T3-25` |
| F12 | Visual Continuity Checklist | Sampled MP4 frames, `/reel-watch` frames & `local.md`, `qa_report.json` | Caption strokes stay in `(110,1380,930,1520)` band, zero bright text strokes clipped at extreme margins (`x<35`, `x>1045`, `y<120`, `y>1640`), callout beats keep callout clear of lower caption band, consistent dark palette border luminance (`<=110`), `qa_report.json` records visual/continuity pass | Right-side platform UI clearance (`x>950, y=1380..1520`), bottom platform chrome clearance (`y>1600`), no bright flash frames across episode, cross-episode background median RGB cohesion (`dist <= 45` to `brand.json::background_dark`), `/reel-watch` frames visually non-duplicate & well-distributed | `T3-15` |
| F13 | Retention Structure & 1-Word Ending CTA | `script.json`, `narration_timeline.json`, `publish_meta.json` | All 5 acts (`hook`, `mechanism`, `escalation`, `climax`, `cta`) present, zero mid-video subscribe/like prompts, story-tied 1-word/1-number ending CTA, fast storyteller cadence (`2.0–4.0 words/sec`), `>=8` beats & mean beat duration `<=10s` | Even final CTA free of subscribe begging, `hook` beat punchy (`<=6.5s`, `<=25` words), tight pauses (`0.0 <= pause_after_s <= 0.6`), CTA token echoed in `pinned_comment`, strictly monotonic act progression | `T3-06`, `T3-07`, `T3-12`, `T3-18`, `T3-19`, `T3-22` |
| F14 | Gemini 3.8 Flash TTS Narration | `cache/tts/*.wav`, `narration_clean.wav`, `narration_timeline.json`, static scan of `src/cts_factory/audio/tts.py`, CLI `build-audio` | `cache/tts/` has `>=len(beats)` SHA-256 hex WAVs, all WAVs valid RIFF 48 kHz mono 16-bit PCM `>0.3s`, `narration_timeline.json` matches all `script.json` beats monotonically, static scan confirms `v1beta` + `gemini-3.8-flash-tts` + env-only key, offline cache re-run invariance (when cached) | Missing-key uncached negative CLI test exits non-zero cleanly, zero silent/clipped beat WAVs (`peak>0.05`, clip ratio `<0.5%`), non-overlapping beat timestamps, `narration_clean.wav` matches `total_duration_s ±0.25s`, zero secret keys in timeline/cache filenames | `T3-06`, `T3-07`, `T3-08`, `T3-09`, `T3-10`, `T3-12`, `T3-13`, `T3-26` |
| F15 | Soft Silence Trimming & Continuous Ambient Bed | `audio_master.wav`, `narration_clean.wav`, MP4 decoded PCM, `ffmpeg silencedetect` | `audio_master.wav` 48 kHz stereo PCM, zero `0.5s` RMS windows `<= -60 dBFS` in `audio_master.wav`, zero `0.5s` RMS windows `<= -60 dBFS` in MP4 audio, inter-beat narration pauses (`<-45 dBFS`) remain energized (`>=-55 dBFS`) in master, beat WAV tails smoothly faded (`|last_sample|<0.2`) | Full-span (including edges) zero 0.5s digital-zero blocks, stereo L/R balance `<=3.0 dB`, sidechain ducking / speech dominance (`speech RMS >= pause RMS + 4 dB`), zero DC offset (`|mean|<0.01`) & finite samples, `ffmpeg silencedetect=noise=-60dB:d=0.5` reports `0` silence intervals | `T3-08`, `T3-10`, `T3-21` |
| F16 | Broadcast Loudness Mastering | `ffmpeg -vn -af ebur128=peak=true`, `ffprobe`, `qa_report.json` | `audio_master.wav` `I` in `[-15.3, -13.7] LUFS`, `audio_master.wav` `TP <= -1.0 dBTP`, `audio_master.wav` `0.5 <= LRA <= 4.0 LU`, final `.mp4` `I` in `[-15.5, -13.5] LUFS` & `LRA <= 4.3 LU` & `TP <= -0.8 dBTP`, MP4 audio stream `aac` `48000 Hz` `stereo` `160–224 kbps` | WAV↔MP4 loudness parity (`|I_mp4 - I_wav| <= 0.5 LU`), cross-episode loudness parity (`|I_ep01 - I_ep02| <= 1.0 LU`), zero digital clipping (`peak < 0.99`), `audio_master.wav` peak strictly `< 0.0 dBTP`, `qa_report.json` LUFS/TP/LRA agrees with independent `ebur128` (`±0.4`) | `T3-11`, `T3-21`, `T3-28` |
| F17 | Whisper-Synced Word-Level Captions | `captions.json`, sampled MP4 frames (`y=1380..1520, x=110..930`) | Valid schema `blocks[].words[]` (`>=20` blocks), `1<=len(words)<=4` with `>=85%` in `[2,4]` & 1-word only on isolated trailing/CTA boundary, monotonic non-overlapping block & word timings covering episode, reconciled text similarity vs `script.json` `>=0.85`, high-contrast caption strokes visible in `(110,1380,930,1520)` on active frames | Non-uniform Whisper-derived word durations (`std >= 0.03s`, CV `>= 0.12`), no opaque solid rectangle box behind captions, both white text (`>220`) & brand accent highlight pixels present in caption band, right-side UI clearance (`x>955` clear of caption strokes), zero empty tokens or `<0.02s` zero-duration words | `T3-07`, `T3-09`, `T3-10`, `T3-14`, `T3-15`, `T3-22`, `T3-23`, `T3-25` |
| F18 | Episode Cover (`1080x1920`) & Grid Preview | `episodios/*/cover.png`, `episodios/*/cover_grid_preview.png` | Exact `1080x1920` PNG, valid `cover_grid_preview.png` (`>=600x600`, distinct from `cover.png`), strong foreground/headline contrast inside Reels safe zone `(90,330,990,1580)`, zero bright typography clipped in forbidden outer strips (`y<255`, `y>1665`), rich hero artwork (`std>=20`) aligned to brand palette | Tight Reels border check (`y<315`, `y>1595` free of clipped bright headline strokes), `ep01` & `ep02` covers visually distinct (`MAD>=15`) yet palette-cohesive (outer margin RGB dist `<=45`), zero alpha holes (`min(alpha)==255`), crisp thumbnail contrast (`p95-p05>=110` inside safe zone), file size `20 KB <= bytes < 6 MB` | `T3-16`, `T3-17`, `T3-18`, `T3-25` |
| F19 | Platform Metadata & Publishing Checklist | `publish_meta.json`, `script.json::publish_meta`, optional checklist files | All required fields present (`youtube_title`, `youtube_description`, `ig_tiktok_caption`, `hashtags`, `pinned_comment`, `related_video_slot`, `schedule_hour`, `ai_disclosure`), YT title `10–50` chars + `0` `#` + exact `1` UPPERCASE word, minimal YT description (`<=280` chars) + rich IG/TikTok caption & `>=3` hashtags, `pinned_comment`/`related_video_slot`/`schedule_hour`/`ai_disclosure==False` valid, 48h iteration loop fields present | No ellipsis truncation (`...`) or surrounding whitespace & distinct `ep01`/`ep02` titles, valid unique `en-US` hashtags (`^#?[A-Za-z][A-Za-z0-9_]{1,35}$`), `script.json::title == publish_meta::youtube_title`, `related_video_slot` non-placeholder, zero spam URL shorteners or graphic policy triggers | `T3-05`, `T3-18`, `T3-19`, `T3-20`, `T3-28` |
| F20 | Mandatory QA Gate | `qa_report.json`, `reels/` local audits (`local.md`, `manifest.json`, `frames/`), CLI `qa` | Both `qa_report.json` valid & passing, quantitative metrics recorded (res/fps/dur/LUFS/TP/LRA/RMS), CLI `qa --episode <slug>` exits `0` for both episodes, `/reel-watch --engine local` audit dirs exist for both episodes (`>=8` frames, `local.md`, `manifest.json`), `local.md` has non-empty Whisper transcript & OCR section | Negative CLI `qa` rejects short/wrong-res MP4 in temp workspace, negative CLI `qa` rejects silence-vacuum MP4, negative CLI `qa` rejects loudness-violation MP4, freshness (`qa_report.json` & audit match current MP4), `reel.py --engine local --max-frames 4 --llm off` succeeds in temp `REEL_HOME` | `T3-21`, `T3-22`, `T3-23`, `T3-24`, `T3-27` |
| F21 | Security & Git Hygiene | `git check-ignore`, `git ls-files`, `git diff --cached`, `git log`, repo file secret scan, CLI canary env test | `git check-ignore .env` exits `0` & `.env` untracked, zero `.agents/teamwork/` paths tracked/staged, zero `reels/` or `assets/fonts/*.ttf` tracked, zero secret regex patterns across repo text files, env `GEMINI_API_KEY` literal never appears outside `.env` | `git log -p -n 30` has zero leaked keys/`.env`/`.agents/teamwork/`, CLI canary secret (`GEMINI_API_KEY="DUMMY_SECRET_CANARY_..."`) never echoed to stdout/stderr/reports, static scan of `src/` finds zero `shell=True`/`os.system`, `.gitignore` retains all critical rules, zero stray `.env.bak`/credential JSONs tracked | `T3-26`, `T3-27` |

---

## 3. Test Architecture

```text
tests/e2e/
├── __init__.py
├── helpers/
│   ├── __init__.py          # Public re-exports
│   ├── discovery.py         # CTS_E2E_PROJECT_ROOT override, dynamic ep01/ep02, marca/, reels/ discovery
│   ├── media.py             # mtime-cached ffprobe, ebur128 (-vn), 0.5s PCM RMS, RGB frame decode, motion/cut analysis
│   ├── images.py            # Geometry, Rec.709 luminance/WCAG contrast, safe-zone & clipping checks (Frame 0, captions, cover, banner)
│   ├── text_checks.py       # Zero-FP en-US PT-leakage detector, YT title, CTA, secrets, git hygiene, caption & transcript checks
│   ├── cli_runner.py        # Offline uv subprocess invoker (PYTHONPATH=src, strip_api_keys=True)
│   └── fixtures.py          # Fast (<9s) compliant synthetic workspace builder + 18 targeted single-defect mutators
├── test_helpers_self.py     # Self-tests proving every helper passes on compliant synthetic fixtures & fails on all 18 mutations
├── tier1_features/          # Tier 1: Isolated happy-path feature coverage (>=105 tests, >=5 per feature F01–F21)
│   ├── __init__.py
│   ├── test_f01_f05_brand_and_refs.py
│   ├── test_f06_f10_episodes_and_video.py
│   ├── test_f11_f15_continuity_and_audio.py
│   └── test_f16_f21_mastering_qa_security.py
├── tier2_boundaries/        # Tier 2: Boundaries, corner cases, negative CLI & leakage (>=105 tests, >=5 per feature F01–F21)
│   ├── __init__.py
│   ├── test_b01_b05_brand_and_refs.py
│   ├── test_b06_b10_episodes_and_video.py
│   ├── test_b11_b15_continuity_and_audio.py
│   └── test_b16_b21_mastering_qa_security.py
├── tier3_interactions/      # Tier 3: Cross-feature pairwise interactions (>=25 tests; target 28)
│   ├── __init__.py
│   ├── test_t3_brand_themes_packaging.py
│   └── test_t3_audio_video_captions_qa.py
└── tier4_workloads/         # Tier 4: Real-world application scenarios (>=12 tests; target 14)
    ├── __init__.py
    └── test_t4_real_world_workloads.py
```

---

## 4. Tier 4 Real-World Application Scenarios (14 Scenarios)

1. **`T4-01` YouTube Shorts Desktop Studio Publish Readiness:** End-to-end validation of MP4, `<=50`-char 1-CAPS title, minimal desc, `3:4`-safe `1080x1920` cover, `related_video_slot`, fixed schedule, `ai_disclosure=False`, pinned comment, and `2560x1440 <6MB` banner.
2. **`T4-02` TikTok Creator Rewards (`>61s` Original Non-Slideshow) Readiness:** Duration `>=62.0s` (`65–80s`), articulated motion across `3–5` angles, continuous `-14.5 LUFS` audio with zero silence gaps, captions clearing TikTok right-rail (`x<=930`) & bottom chrome (`y<=1520`), TikTok caption + hashtags.
3. **`T4-03` Instagram Reels Profile Grid & Audio Compliance:** Cover hero/headline inside strict Reels grid (`y=330..1580`), `cover_grid_preview.png` generated, cohesive cross-episode cover palette, AAC 48 kHz stereo `-14.5 LUFS`, IG caption + hashtags.
4. **`T4-04` 10-Minute Long-Form Compilation Readiness & Lossless Concatenation:** Actual `ffmpeg -f concat -safe 0 -c copy` join of `ep01` + `ep02` in `mktemp -d`, verifying exit `0`, zero decode errors, exact summed duration, `<=1.0 LU` cross-seam loudness parity, and 6-theme compilation math.
5. **`T4-05` Fresh-Clone Reproducibility & Secret-Hygiene Audit:** `.env`, `reels/`, `assets/fonts/*.ttf`, `.agents/teamwork/` untracked; `bash -n setup_vm.sh`; valid `pyproject.toml`; zero Windows paths or secrets; `brand_template.json` preserved.
6. **`T4-06` Complete `/reel-watch` End-to-End Audit Traceability:** Full provenance chain `DYYsGuTpBKc`/`M_t2ZUz7_pc` → `brand.json` rationale → `ep01`/`ep02` local audits → `reels/INDEX.md` → transcript/OCR alignment with canonical scripts.
7. **`T4-07` Feed-Scroll First-Second Survival (`t=0.0..2.0s`):** Immediate full luminance at `t=0.0s`, top hook contrast in `y=260..460`, immediate voice onset `<0.45s`, active first-second motion, first caption block `<=0.6s`.
8. **`T4-08` Offline Zero-API-Spend Re-Verification:** With `GEMINI_API_KEY` stripped and `uv --offline`, verify `qa` CLI succeeds and TTS disk cache covers all beats without network calls.
9. **`T4-09` Brand Uniqueness & Anti-"Inauthentic Content" Monetization Defense:** Zero *Rota Crítica* / starter-template residue, distinct voice/palette, distinct episodes, educational non-graphic disaster framing (T3), `ai_disclosure=False`.
10. **`T4-10` 48-Hour Post-Publish Analytics & Iteration Loop Readiness:** `never_delete_stalled_shorts=True`, 48h review window, `75%+` stayed-to-watch target, ~100% AVD target, retention drop-off diagnosis aligned to `narration_timeline.json`.
11. **`T4-11` Multi-Device YouTube Channel Banner Cropping Simulation:** Crop `youtube_banner.png` into TV (`2560x1440`), Desktop (`0,508,2560,931`), and Mobile (`507,508,2053,931`) viewports verifying centered high-contrast brand identity in Mobile crop and cohesive fill across Desktop & TV.
12. **`T4-12` Sound-Off Mobile Viewer Comprehension:** Verify full narrative + final 1-word/1-number CTA are conveyed cleanly via `captions.json` + on-screen hook/callouts in 2–4 word bursts with zero UI clipping.
13. **`T4-13` Adversarial QA Gate Rejection Workflow:** Build a multi-defect synthetic episode in `mktemp -d` (wrong res, short duration, silence gap, loudness violation) and verify `cts_factory.cli qa` rejects it cleanly (non-zero exit) without mutating real deliverables.
14. **`T4-14` Daily Autonomous Production Cadence (6-Theme Independence):** Verify all 6 themes in `themes_backlog.json` & `THEMES_CATALOG.md` are standalone, order-independent, scheduled at fixed `HH:MM`, and 100% `en-US`.

---

## 5. Coverage Thresholds & Quality Gates

| Metric | Required Minimum | Target |
|---|---:|---:|
| Features Covered | 21 / 21 (`100%`) | 21 / 21 (`100%`) |
| Tier 1 Feature Coverage Tests | `>= 105` (`>= 5` per feature) | `105+` |
| Tier 2 Boundary & Corner Case Tests | `>= 105` (`>= 5` per feature) | `105+` |
| Tier 3 Cross-Feature Interaction Tests | `>= 25` | `28` |
| Tier 4 Real-World Workload Scenarios | `>= 12` | `14` |
| **Total E2E Tests (Tiers 1–4)** | **`>= 247`** | **`252+`** |
| Helper Synthetic Fixture Self-Tests | `>= 20` (all 18 mutators + clean pass) | `25+` |
| Internal `cts_factory` Imports in `tests/e2e/` | `0` | `0` |
| Dummy / Tautological Assertions (`assertTrue(True)`, unconditional skip) | `0` | `0` |
| Live Gemini API Calls | `0` | `0` |
| Hardcoded Secrets / API Keys | `0` | `0` |
