"""Cohesive 1080x1920 episode covers, strict grid crop previews, and publish pack export."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from cts_factory.config import BrandConfig, EpisodeScript
from cts_factory.engine.materials import Palette
from cts_factory.engine.primitives import load_font
from cts_factory.episodes.base import EpisodeScene


def _draw_cover_text_centered(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    x_min: int,
    x_max: int,
    y_start: int,
    font_path: str,
    p: Palette,
) -> None:
    max_w = x_max - x_min - 24
    font_size = 76
    while font_size >= 40:
        f = load_font(font_path, font_size)
        widest = max(draw.textbbox((0, 0), ln.upper(), font=f, stroke_width=6)[2] for ln in lines)
        if widest <= max_w:
            break
        font_size -= 4
    f = load_font(font_path, font_size)
    lh = draw.textbbox((0, 0), "Ag", font=f, stroke_width=6)[3] + 10
    cx = (x_min + x_max) // 2
    y = y_start
    for idx, raw_ln in enumerate(lines):
        ln = raw_ln.upper()
        bb = draw.textbbox((0, 0), ln, font=f, stroke_width=6)
        tw = bb[2] - bb[0]
        x = max(x_min, min(x_max - tw, cx - tw // 2))
        col = p.text_highlight if idx == len(lines) - 1 else p.text_primary
        draw.text((x + 4, y + 5), ln, font=f, fill=p.ink, stroke_width=7, stroke_fill=p.ink)
        draw.text((x, y), ln, font=f, fill=col, stroke_width=6, stroke_fill=p.ink)
        y += lh


def build_episode_package(
    brand: BrandConfig,
    script: EpisodeScript,
    scene: EpisodeScene,
    episode_dir: Path,
    repo_root: Path | None = None,
) -> dict[str, Path]:
    """Generate 1080x1920 cover.png, cover_grid_preview.png, publish_meta.json, and checklist."""
    episode_dir.mkdir(parents=True, exist_ok=True)
    w, h = brand.video_spec.width, brand.video_spec.height
    p = Palette.from_brand(brand)
    grid = brand.visual_style.safe_zones.cover_reels_grid  # x=90..990, y=330..1580
    r34 = brand.visual_style.safe_zones.cover_3x4          # x=90..990, y=260..1660

    scene.prepare(brand, script, None)
    cover = Image.new("RGB", (w, h), p.bg_dark)
    draw = ImageDraw.Draw(cover)
    scene.render_cover_hero(cover, draw)

    font_black = str(brand.visual_style.resolve_font_path("primary", repo_root=repo_root))
    font_bold = str(brand.visual_style.resolve_font_path("secondary", repo_root=repo_root))

    # Top series badge strictly inside Reels grid safe zone (y=345..410)
    f_series = load_font(font_bold, 28)
    badge = f"{brand.channel_name.upper()}  //  EP {script.episode_id[-2:]}"
    bb = draw.textbbox((0, 0), badge, font=f_series)
    bw = (bb[2] - bb[0]) + 56
    bx0 = (w - bw) // 2
    draw.rounded_rectangle([bx0, grid.y_min + 18, bx0 + bw, grid.y_min + 76], radius=14, fill=p.surface_panel, outline=p.cyan, width=3)
    draw.text((bx0 + 28, grid.y_min + 30), badge, font=f_series, fill=p.cyan)

    # Bold 2-line headline strictly inside y=430..610 (well inside y=330..1580)
    _draw_cover_text_centered(
        draw,
        lines=script.cover_headline or [script.hook_text],
        x_min=grid.x_min,
        x_max=grid.x_max,
        y_start=grid.y_min + 102,
        font_path=font_black,
        p=p,
    )

    # Bottom series bar strictly inside y=1470..1560 (clears Reels y=1580 bottom crop!)
    pill_text = f"2.5D CAD CUTAWAY  •  {brand.handle.upper()}"
    f_bot = load_font(font_bold, 28)
    pb = draw.textbbox((0, 0), pill_text, font=f_bot)
    pw = (pb[2] - pb[0]) + 60
    px0 = (w - pw) // 2
    py0 = grid.y_max - 92
    draw.rounded_rectangle([px0, py0, px0 + pw, py0 + 64], radius=14, fill=p.surface_panel, outline=p.amber, width=3)
    draw.text((px0 + 30, py0 + 16), pill_text, font=f_bot, fill=p.text_highlight)

    cover_path = episode_dir / "cover.png"
    cover.save(cover_path, format="PNG", optimize=True)

    # --- Side-by-side grid crop verification sheet ---
    # Panel 1: full 9:16 with safe guides; Panel 2: 3:4 crop; Panel 3: Reels tight grid crop
    thumb_h = 960
    p1 = cover.copy()
    d1 = ImageDraw.Draw(p1)
    d1.rectangle([r34.x_min, r34.y_min, r34.x_max, r34.y_max], outline=p.cyan, width=6)
    d1.rectangle([grid.x_min, grid.y_min, grid.x_max, grid.y_max], outline=p.emerald, width=6)
    p1_s = p1.resize((540, thumb_h), Image.Resampling.LANCZOS)

    c34 = cover.crop((0, r34.y_min, w, r34.y_max))
    c34_s = c34.resize((int(540 * (w / (r34.y_max - r34.y_min)) * (r34.y_max - r34.y_min) / w), int(540 * (r34.y_max - r34.y_min) / w)), Image.Resampling.LANCZOS)

    creels = cover.crop((0, grid.y_min, w, grid.y_max))
    creels_s = creels.resize((540, int(540 * (grid.y_max - grid.y_min) / w)), Image.Resampling.LANCZOS)

    sheet = Image.new("RGB", (1740, 1080), p.bg_dark)
    sdraw = ImageDraw.Draw(sheet)
    f_hdr = load_font(font_bold, 26)
    sheet.paste(p1_s, (30, 80))
    sdraw.text((30, 32), "1. FULL 9:16 + SAFE GUIDES", font=f_hdr, fill=p.text_primary)
    sheet.paste(c34_s, (600, 80 + (thumb_h - c34_s.height) // 2))
    sdraw.text((600, 32), "2. YOUTUBE 3:4 CROP (y=260..1660)", font=f_hdr, fill=p.cyan)
    sheet.paste(creels_s, (1170, 80 + (thumb_h - creels_s.height) // 2))
    sdraw.text((1170, 32), "3. REELS GRID CROP (y=330..1580)", font=f_hdr, fill=p.emerald)

    preview_path = episode_dir / "cover_grid_preview.png"
    sheet.save(preview_path, format="PNG", optimize=True)

    # --- Export publish_meta.json & PUBLISH_CHECKLIST.md ---
    pm = script.publish_meta
    meta_payload = {
        "episode_id": script.episode_id,
        "slug": script.slug,
        "channel_name": brand.channel_name,
        "handle": brand.handle,
        "language": brand.language,
        "youtube_title": pm.youtube_title,
        "youtube_title_length": len(pm.youtube_title),
        "youtube_description": pm.youtube_description,
        "ig_tiktok_caption": pm.ig_tiktok_caption,
        "hashtags": list(pm.hashtags),
        "pinned_comment": pm.pinned_comment,
        "related_video_slot": pm.related_video_slot,
        "schedule_hour": pm.schedule_hour,
        "ai_disclosure": pm.ai_disclosure,
        "never_delete_stalled_shorts": brand.publishing.never_delete_stalled_shorts,
        "review_metrics_after_hours": brand.publishing.review_metrics_after_hours,
        "stayed_to_watch_target_pct": brand.publishing.stayed_to_watch_target_pct,
    }
    meta_path = episode_dir / "publish_meta.json"
    meta_path.write_text(json.dumps(meta_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    checklist_md = f"""# Publishing Checklist — `{script.slug}` ({brand.channel_name})

## YouTube Shorts (Desktop Studio)
- **Title ({len(pm.youtube_title)} / 50 chars, 1 ALL-CAPS, 0 `#`):** `{pm.youtube_title}`
- **Description:** *(Leave minimal/blank for feed-driven story Shorts)*
- **Thumbnail / Cover:** Upload `cover.png` (`1080x1920`, verified against `cover_grid_preview.png`)
- **Related Video:** Link to `{pm.related_video_slot}`
- **AI Disclosure Checkbox:** `{"Checked" if pm.ai_disclosure else "Unchecked (stylized 2.5D CAD vector animation)"}`
- **Schedule:** Fixed daily slot at **`{pm.schedule_hour}`**
- **First-Minute Pinned Comment:**
  > {pm.pinned_comment}

## TikTok (>61s Creator Rewards) & Instagram Reels
- **Caption:**
  > {pm.ig_tiktok_caption}
- **Hashtags:** `{" ".join(pm.hashtags)}`

## 48-Hour Post-Publish Iteration Loop
- **Rule:** NEVER delete or re-upload a stalled Short.
- **Check at T+48h:**
  1. **Stayed to watch (%):** Target **`>= {brand.publishing.stayed_to_watch_target_pct:.0f}%`** (if lower, strengthen Frame 0 + first 2s on next episode).
  2. **Average view duration:** Target near **`100%`** of video length.
  3. **Retention curve drop-off second:** Identify the exact beat where viewers swipe away and tighten that beat structure on the next episode.
"""
    checklist_path = episode_dir / "PUBLISH_CHECKLIST.md"
    checklist_path.write_text(checklist_md, encoding="utf-8")

    return {
        "cover": cover_path,
        "cover_grid_preview": preview_path,
        "publish_meta": meta_path,
        "publish_checklist": checklist_path,
    }
