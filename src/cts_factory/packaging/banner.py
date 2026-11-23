"""YouTube Channel Banner (2560x1440, <6MB) and safe-zone verification preview."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from cts_factory.config import BrandConfig
from cts_factory.engine.materials import Palette, build_stage_background, scale_rgb
from cts_factory.engine.primitives import draw_dotted_arc, draw_force_arrow, draw_gear_25d, load_font


def build_channel_banner(
    brand: BrandConfig,
    marca_dir: Path,
    repo_root: Path | None = None,
) -> tuple[Path, Path]:
    """Generate 2560x1440 YouTube banner (<6MB) + safe-zone guide preview under marca/."""
    marca_dir.mkdir(parents=True, exist_ok=True)
    sz = brand.visual_style.safe_zones
    w, h = sz.youtube_banner_width, sz.youtube_banner_height
    mob = sz.youtube_banner_mobile
    desk = sz.youtube_banner_desktop
    p = Palette.from_brand(brand)

    img = build_stage_background(w, h, p, spot_color=p.cyan, spot_cy=0.50, grid_step=96)
    draw = ImageDraw.Draw(img)

    # Subtle outer desktop-strip technical CAD flanking elements (outside mobile safe box)
    cy = (mob.y_min + mob.y_max) // 2  # 719
    draw_gear_25d(draw, 260, cy, 150, 18, 0.3, p.steel_dark, scale_rgb(p.steel_dark, 0.65), p.ink, depth_px=18.0)
    draw_gear_25d(draw, w - 260, cy, 150, 18, -0.3, p.steel_dark, scale_rgb(p.steel_dark, 0.65), p.ink, depth_px=18.0)
    draw.line([(60, desk.y_min + 12), (w - 60, desk.y_min + 12)], fill=p.bg_grid, width=2)
    draw.line([(60, desk.y_max - 12), (w - 60, desk.y_max - 12)], fill=p.bg_grid, width=2)

    # --- ALL critical logo, name, handle, and tagline strictly inside mobile safe box (x=507..2053, y=508..931) ---
    emblem_cx = mob.x_min + 215
    emblem_cy = cy
    draw_dotted_arc(draw, emblem_cx, emblem_cy, 150, 0, 360, p.cyan, width=4, step_deg=10)
    draw_gear_25d(draw, emblem_cx, emblem_cy, 118, 14, 0.25, p.brass, scale_rgb(p.brass, 0.58), p.ink, depth_px=16.0, hub_col=p.amber)
    draw_force_arrow(draw, emblem_cx - 175, emblem_cy, emblem_cx - 125, emblem_cy, p.amber, width=9, head_len=18, head_w=14)

    font_black = str(brand.visual_style.resolve_font_path("primary", repo_root=repo_root))
    font_bold = str(brand.visual_style.resolve_font_path("secondary", repo_root=repo_root))

    text_x = mob.x_min + 415
    f_title = load_font(font_black, 112)
    f_tag = load_font(font_bold, 38)
    f_handle = load_font(font_bold, 30)

    # Two-tone brand lockup: FAILSAFE (white) + LAB (safety yellow)
    part1 = "FAILSAFE "
    part2 = "LAB"
    b1 = draw.textbbox((0, 0), part1, font=f_title, stroke_width=6)
    w1 = b1[2] - b1[0]
    title_y = mob.y_min + 76
    draw.text((text_x + 4, title_y + 5), part1 + part2, font=f_title, fill=p.ink, stroke_width=7, stroke_fill=p.ink)
    draw.text((text_x, title_y), part1, font=f_title, fill=p.text_primary, stroke_width=6, stroke_fill=p.ink)
    draw.text((text_x + w1, title_y), part2, font=f_title, fill=p.text_highlight, stroke_width=6, stroke_fill=p.ink)

    # Accent divider bar
    bar_y = title_y + 132
    draw.rounded_rectangle([text_x, bar_y, text_x + 920, bar_y + 8], radius=4, fill=p.cyan)
    draw.rounded_rectangle([text_x, bar_y, text_x + 280, bar_y + 8], radius=4, fill=p.amber)

    # Tagline + handle
    tag_y = bar_y + 24
    draw.text((text_x, tag_y), brand.tagline.upper(), font=f_tag, fill=p.text_primary)
    draw.text((text_x, tag_y + 56), f"{brand.handle}   //   ENGINEERING & FAILURE PHYSICS", font=f_handle, fill=p.cyan)

    banner_path = marca_dir / "youtube_banner.png"
    img.save(banner_path, format="PNG", optimize=True)

    # Safe-zone preview overlay image
    preview = img.copy()
    pdraw = ImageDraw.Draw(preview)
    pdraw.rectangle([desk.x_min + 2, desk.y_min, desk.x_max - 2, desk.y_max], outline=p.cyan, width=6)
    pdraw.rectangle([mob.x_min, mob.y_min, mob.x_max, mob.y_max], outline=p.emerald, width=8)
    f_note = load_font(font_bold, 32)
    pdraw.text((desk.x_min + 30, desk.y_min - 44), "DESKTOP STRIP (2560x423)", font=f_note, fill=p.cyan)
    pdraw.text((mob.x_min + 12, mob.y_min - 44), "MOBILE SAFE ZONE (1546x423)", font=f_note, fill=p.emerald)
    preview_path = marca_dir / "youtube_banner_preview.png"
    preview.save(preview_path, format="PNG", optimize=True)

    return banner_path, preview_path
