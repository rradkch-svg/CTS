---
name: shorts-factory
description: End-to-end production, packaging, and QA pipeline for original 2D flat-vector animated Shorts/Reels/TikToks (65–80s, 9:16, 30fps) designed for high retention and monetization. Use whenever planning, scripting, rendering, auditing, or packaging a short-form animated video in this repository.
---

# Shorts Factory — Production & QA Playbook

This skill encodes the battle-tested rules for producing original, high-retention 2D animated short-form videos (`9:16`, `1080x1920`, `30 fps`) that work simultaneously on **YouTube Shorts**, **TikTok (>61s Creator Rewards eligible)**, and **Instagram Reels**, plus long-form **YouTube compilations (8–12 min)**.

---

## 1. Pre-Production Rules (Before Generating Anything)

1. **Uniqueness Test (YouTube "Inauthentic Content" defense):**
   - Ask: *"Could this video be uploaded to another generic channel without anyone noticing?"*
   - Always use this channel's distinct character rig, palette, voice (`brand.json`), and original scripts. Never recycle identical art/voice across different channels.
2. **Autonomous Episodes for Daily Consistency:**
   - Every episode must stand on its own (no waiting on viewer comments before producing the next video) so you can schedule consistently at a fixed daily/every-other-day hour.
3. **Target Duration:**
   - **`65–80 seconds`** (sweet spot: qualifies for TikTok's `>61s` monetization while staying punchy for Shorts & Reels; 6–8 episodes compile naturally into an 8–10 min horizontal/special YouTube video).
4. **Frame 0 (`0.0s`) = Feed Cover (Most Important Retention Lever):**
   - In the Shorts/Reels/TikTok feed, viewers do NOT see your thumbnail — the video starts playing immediately.
   - **Never** open on an empty wide shot or slow fade-in.
   - Open at `t = 0.0s` on a **large expressive reacting character face filling the frame** + **short high-contrast hook text across the top**, immediately paired with a sharp spoken hook.
5. **Zero Mid-Video Subscribe Prompts:**
   - Never ask viewers to "like and subscribe" in the middle of the story (it causes an instant retention cliff).
6. **1-Word Ending CTA:**
   - End with a low-friction **1-word / 1-number comment prompt** directly tied to the story (e.g., `"Comment 1 or 2"`, `"Comment YES or NO"`, `"Comment 10"`).

---

## 2. Production Standards (Animation, Audio, Captions)

### Animation (`1080x1920`, `30 fps`, `H.264 yuv420p`)
- **Real 2D articulated character animation** (head/brow/mouth/arm/prop motion, camera cuts across 3–5 distinct background angles, subtle particle/lighting ambience) — **never** static slides with Ken Burns zoom.
- **Render performance:** Render via Pillow + parallel/piped `ffmpeg` (`-pix_fmt yuv420p -c:v libx264 -crf 19`) rather than pure-Python slow per-frame numpy loops.
- **Linux font safety:** Always load bundled `.ttf` fonts from `assets/fonts/` (falling back to `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`). Never hardcode `C:\Windows\Fonts\...`.
- **Visual continuity checklist:**
  - Consistent prop scale across cuts (objects never shrink/teleport between shots).
  - Zero weapon/prop clipping through faces, hands, or UI badges.
  - Real physical contact when characters hold or lift objects (both hands gripping heavy items).
  - No duplicated moons/lights/background props across cuts.

### Audio (`AAC 48 kHz stereo`, `192 kbps`, `-14.5 LUFS`)
- **TTS:** Use `gemini-3.8-flash-tts` via `google-genai` (read `GEMINI_API_KEY` exclusively from env / `.env` — **never** hardcode or commit keys).
- **Natural delivery:** Avoid forced sibilant whispers; use clean natural half-voice modulation when lowering tension.
- **Zero silence vacuums:** Keep a continuous subtle music/ambient bed with smooth crossfades across cuts so RMS never drops to dead digital silence (`-60 dB`). Use soft silence trimming (`-52 dB` with tail padding) so final syllables never clip off.
- **Mastering:** Normalize final mix with `ffmpeg loudnorm` to **`-14.5 LUFS` (`True Peak <= -1.0 dBTP`, `LRA <= 4.0 LU`)**.

### Captions
- Synced to **actual word-level timestamps** from `faster-whisper` (never guessed timing).
- **2–4 words per block**, bold outlined white text with accent highlight color, **no opaque box behind captions**, positioned cleanly in the lower safe zone above TikTok/Reels/Shorts UI buttons (`y ~ 1380–1520` on `1920px` height).

---

## 3. Mandatory QA Gate Before Approving Any Episode

Before presenting any rendered episode as ready to publish:

1. **Technical check:** Run `ffprobe` (confirm `1080x1920`, `30 fps`, `yuv420p`, `aac 48000 Hz stereo`), `ebur128` loudness (`~ -14.5 LUFS`), and 0.5s RMS audio scan (zero unintentional silence gaps).
2. **Mandatory `/reel-watch` review:**
   ```bash
   uv run --offline --with faster-whisper --with rapidocr --with onnxruntime --with imageio-ffmpeg \
     python .agents/skills/reel-watch/scripts/reel.py "<path-to-episode.mp4>" --engine local --max-frames 16 --llm off
   ```
3. **Visual frame inspection:** Read the extracted frames and transcript (`local.md`), verify zero spelling errors, zero clipping, zero continuity errors, and clear Frame 0 readability. Fix any defect before marking the episode final.

---

## 4. Packaging & Publishing Standards

### Episode Cover (`1080x1920` PNG)
- Keep consistent series framing across all episodes so the channel's Shorts/Reels tab looks like a cohesive catalog.
- **Strict Grid Safe Zone:** Keep ALL critical text and face/subject cleanly inside the **center `3:4` (`y = 260..1660`) and tighter Reels grid crop (`y = 330..1580`)** so top/bottom title lines are NEVER clipped on Instagram's Reels tab or YouTube's Shorts shelf.
- Always generate a quick cropped grid preview and visually inspect it before delivery.

### YouTube Channel Banner (`2560x1440`, `< 6 MB`)
- Full TV canvas: `2560x1440`
- Desktop strip: `2560x423` (`y = 508..931`)
- **All-device Mobile safe zone:** **`1546x423`** (`x = 507..2053`, `y = 508..931`) — place logo, channel name, and tagline dead-center inside this box.

### Metadata & Upload Checklist (YouTube Studio on Desktop)
- **Title:** `<= 50 characters`, strong hook in the first words, 1 word in **UPPERCASE**, **zero `#hashtags` in the title**.
- **Thumbnail:** Upload the dedicated episode cover in Studio (for Shorts tab, search, and suggested traffic).
- **Description & Tags:** For feed-driven story Shorts, keep description minimal or blank on YouTube (full caption + hashtags on Instagram/TikTok).
- **Related Video:** Always link to another episode or compilation on the channel.
- **AI Disclosure Checkbox:** YouTube's disclosure applies to *realistic* altered/synthetic people, places, or real-world events — stylized 2D cartoon/vector animation does not require flagging as synthetic realism.
- **Schedule at a fixed hour:** Always schedule uploads ahead of time at the same daily hour so YouTube finishes HD processing before publication.
- **First-minute Pinned Comment:** Post and pin a 1-tap comment prompt immediately at publish time to break the "empty comment box" effect.

---

## 5. 48-Hour Post-Publish Iteration Loop

- **NEVER delete or re-upload a stalled Short.** When a later Short goes viral, it pulls older episodes up automatically; deleting and re-uploading triggers duplicate/spam suppression.
- **Inspect 3 Studio metrics 48 hours after publish:**
  1. **Stayed to watch (`%`):** Target **`75%+`**. If low → strengthen **Frame 0** and the first 2 seconds on the next episode.
  2. **Average view duration:** Aim near `100%` of video length.
  3. **Exact drop-off second on the retention curve:** Identify the exact beat where viewers swipe away and eliminate that pattern in the next episode.
