"""YouTube Channel Banner (2560x1440, <6MB) featuring 3D Crash-Test Dummy 'UNIT-01' & 3D CAD gear."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import BrandConfig
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette, build_stage_background, scale_rgb
from cts_factory.engine.primitives import draw_dotted_arc, draw_gear_25d, load_font
from cts_factory.engine.renderer3d import Camera3D, Scene3D


def build_channel_banner(
    brand: BrandConfig,
    marca_dir: Path,
    repo_root: Path | None = None,
) -> tuple[Path, Path]:
    """Generate 2560x1440 YouTube banner (<6MB) + safe-zone guide preview featuring 3D UNIT-01."""
    marca_dir.mkdir(parents=True, exist_ok=True)
    sz = brand.visual_style.safe_zones
    w, h = sz.youtube_banner_width, sz.youtube_banner_height
    mob = sz.youtube_banner_mobile
    desk = sz.youtube_banner_desktop
    p = Palette.from_brand(brand)

    base_img = build_stage_background(w, h, p, spot_color=p.cyan, spot_cy=0.50, grid_step=96)
    bg_bgr = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    # Render true 3D Crash-Test Dummy ('UNIT-01') + 3D brass gear strictly inside the left side of mobile safe box!
    cam = Camera3D(eye=(0.3, 0.20, 17.5), target=(0.0, 0.10, 0.0), fov_deg=28.0, width=w, height=h, cy_offset=0.0)
    sc = Scene3D(cam)
    sc.add_gear_3d((-1.85, 0.12, -0.55), 0.70, 0.22, 16, 0.3, (218, 168, 72), rot=(0.15, 0.30, 0.0), metallic=0.72)
    add_crash_test_dummy(sc, pos=(-1.60, -0.05, 0.25), scale=0.46, yaw=0.35, pose="point_right", emotion="engineer", t=0.4)
    # Flanking desktop-strip 3D gears
    sc.add_gear_3d((-3.75, 0.12, -0.4), 0.65, 0.22, 16, 0.2, (82, 102, 132), rot=(0.1, 0.25, 0.0), metallic=0.65)
    sc.add_gear_3d((3.75, 0.12, -0.4), 0.65, 0.22, 16, -0.2, (82, 102, 132), rot=(0.1, -0.25, 0.0), metallic=0.65)

    rendered_bgr = sc.render_to_bgr(bg_bgr)
    img = Image.fromarray(cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB), mode="RGB")
    draw = ImageDraw.Draw(img)

    draw.line([(60, desk.y_min + 12), (w - 60, desk.y_min + 12)], fill=p.bg_grid, width=2)
    draw.line([(60, desk.y_max - 12), (w - 60, desk.y_max - 12)], fill=p.bg_grid, width=2)

    font_black = str(brand.visual_style.resolve_font_path("primary", repo_root=repo_root))
    font_bold = str(brand.visual_style.resolve_font_path("secondary", repo_root=repo_root))

    text_x = mob.x_min + 430
    f_title = load_font(font_black, 110)
    f_tag = load_font(font_bold, 38)
    f_handle = load_font(font_bold, 30)

    part1 = "FAILSAFE "
    part2 = "LAB"
    b1 = draw.textbbox((0, 0), part1, font=f_title, stroke_width=6)
    w1 = b1[2] - b1[0]
    title_y = mob.y_min + 76
    draw.text((text_x + 4, title_y + 5), part1 + part2, font=f_title, fill=p.ink, stroke_width=7, stroke_fill=p.ink)
    draw.text((text_x, title_y), part1, font=f_title, fill=p.text_primary, stroke_width=6, stroke_fill=p.ink)
    draw.text((text_x + w1, title_y), part2, font=f_title, fill=p.text_highlight, stroke_width=6, stroke_fill=p.ink)

    bar_y = title_y + 132
    draw.rounded_rectangle([text_x, bar_y, text_x + 920, bar_y + 8], radius=4, fill=p.cyan)
    draw.rounded_rectangle([text_x, bar_y, text_x + 280, bar_y + 8], radius=4, fill=p.amber)

    tag_y = bar_y + 24
    draw.text((text_x, tag_y), brand.tagline.upper(), font=f_tag, fill=p.text_primary)
    draw.text((text_x, tag_y + 56), f"{brand.handle}   //   3D ENGINEERING & CRASH-TEST PHYSICS", font=f_handle, fill=p.cyan)

    banner_path = marca_dir / "youtube_banner.png"
    img.save(banner_path, format="PNG", optimize=True)

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
