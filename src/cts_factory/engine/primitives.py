"""2.5D CAD vector drawing primitives: prisms, cylinders, gears, arrows, gauges, bars, HUD & hooks."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cts_factory.config import BrandConfig, Callout
from cts_factory.engine.materials import Palette, lerp_color, scale_rgb
from cts_factory.engine.projection import CameraState, clamp, project_iso


@lru_cache(maxsize=64)
def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def draw_iso_box(
    draw: ImageDraw.ImageDraw,
    cam: CameraState,
    x0: float,
    y0: float,
    z0: float,
    dx: float,
    dy: float,
    dz: float,
    top_col: tuple[int, int, int],
    left_col: tuple[int, int, int],
    right_col: tuple[int, int, int],
    ink_col: tuple[int, int, int] = (6, 10, 18),
    rim_col: tuple[int, int, int] | None = None,
    outline_w: int = 3,
) -> None:
    """Draw a 3-face shaded 2.5D isometric machined block with specular rim highlight."""
    p000 = project_iso(x0, y0, z0, cam)
    p100 = project_iso(x0 + dx, y0, z0, cam)
    p010 = project_iso(x0, y0 + dy, z0, cam)
    p110 = project_iso(x0 + dx, y0 + dy, z0, cam)
    p001 = project_iso(x0, y0, z0 + dz, cam)
    p101 = project_iso(x0 + dx, y0, z0 + dz, cam)
    p011 = project_iso(x0, y0 + dy, z0 + dz, cam)
    p111 = project_iso(x0 + dx, y0 + dy, z0 + dz, cam)

    # Left-front face (y = y0 + dy)
    draw.polygon([p010, p110, p111, p011], fill=left_col, outline=ink_col, width=outline_w)
    # Right-front face (x = x0 + dx)
    draw.polygon([p100, p110, p111, p101], fill=right_col, outline=ink_col, width=outline_w)
    # Top face (z = z0 + dz)
    draw.polygon([p001, p101, p111, p011], fill=top_col, outline=ink_col, width=outline_w)

    # Crisp metallic specular rim along lit upper edges
    rim = rim_col or scale_rgb(top_col, 1.28)
    draw.line([p001, p101, p111], fill=rim, width=max(2, outline_w - 1))
    draw.line([p111, p110], fill=scale_rgb(top_col, 1.1), width=2)


def draw_bevel_rect(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    fill: tuple[int, int, int],
    ink: tuple[int, int, int] = (6, 10, 18),
    depth: float = 14.0,
    radius: int = 8,
    rim_col: tuple[int, int, int] | None = None,
) -> None:
    """Draw a 2.5D extruded orthographic machined panel/block with top & side bevels."""
    # Right side extrusion
    side_col = scale_rgb(fill, 0.58)
    top_col = scale_rgb(fill, 1.22)
    draw.polygon(
        [(x1, y0), (x1 + depth, y0 - depth * 0.6), (x1 + depth, y1 - depth * 0.6), (x1, y1)],
        fill=side_col,
        outline=ink,
        width=3,
    )
    draw.polygon(
        [(x0, y0), (x0 + depth, y0 - depth * 0.6), (x1 + depth, y0 - depth * 0.6), (x1, y0)],
        fill=top_col,
        outline=ink,
        width=3,
    )
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=ink, width=3)
    rim = rim_col or scale_rgb(fill, 1.38)
    draw.line([(x0 + radius, y0 + 2), (x1 - radius, y0 + 2)], fill=rim, width=2)


def draw_gear_25d(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    outer_r: float,
    teeth: int,
    angle_rad: float,
    face_col: tuple[int, int, int],
    side_col: tuple[int, int, int],
    ink_col: tuple[int, int, int] = (6, 10, 18),
    depth_px: float = 16.0,
    hub_col: tuple[int, int, int] | None = None,
) -> None:
    """Draw an articulated 2.5D extruded spur gear / centrifugal flywheel."""
    inner_r = outer_r * 0.80
    pts_front: list[tuple[float, float]] = []
    pts_back: list[tuple[float, float]] = []
    step = (2.0 * math.pi) / teeth
    for i in range(teeth):
        a0 = angle_rad + i * step
        a1 = a0 + step * 0.22
        a2 = a0 + step * 0.45
        a3 = a0 + step * 0.72
        for a, r in ((a0, inner_r), (a1, outer_r), (a2, outer_r), (a3, inner_r)):
            px = cx + math.cos(a) * r
            py = cy + math.sin(a) * r
            pts_front.append((px, py))
            pts_back.append((px + depth_px, py - depth_px * 0.5))

    # Draw back extrusion shadow body
    draw.polygon(pts_back, fill=side_col, outline=ink_col, width=3)
    # Connect outer rim depth quads on upper-right silhouette
    for i in range(len(pts_front)):
        p1 = pts_front[i]
        p2 = pts_front[(i + 1) % len(pts_front)]
        b1 = pts_back[i]
        b2 = pts_back[(i + 1) % len(pts_back)]
        if (p1[0] + p2[0]) * 0.5 >= cx - outer_r * 0.2 or (p1[1] + p2[1]) * 0.5 <= cy + outer_r * 0.2:
            draw.polygon([p1, p2, b2, b1], fill=side_col)

    # Front machined face
    draw.polygon(pts_front, fill=face_col, outline=ink_col, width=3)

    # Recessed web + radial spokes
    web_r = outer_r * 0.62
    draw.ellipse(
        [cx - web_r, cy - web_r, cx + web_r, cy + web_r],
        fill=scale_rgb(face_col, 0.72),
        outline=ink_col,
        width=3,
    )
    for s in range(4):
        sa = angle_rad + s * (math.pi * 0.5)
        x2 = cx + math.cos(sa) * web_r
        y2 = cy + math.sin(sa) * web_r
        draw.line([(cx, cy), (x2, y2)], fill=scale_rgb(face_col, 1.15), width=max(6, int(outer_r * 0.13)))
        draw.line([(cx, cy), (x2, y2)], fill=ink_col, width=2)

    # Center machined axle hub
    hub_r = outer_r * 0.24
    draw.ellipse(
        [cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r],
        fill=hub_col or scale_rgb(face_col, 1.25),
        outline=ink_col,
        width=3,
    )
    bolt_r = hub_r * 0.38
    draw.ellipse(
        [cx - bolt_r, cy - bolt_r, cx + bolt_r, cy + bolt_r],
        fill=ink_col,
    )


def draw_force_arrow(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: tuple[int, int, int],
    width: int = 12,
    head_len: float = 28.0,
    head_w: float = 22.0,
    pulse: float = 0.0,
    ink: tuple[int, int, int] = (6, 10, 18),
) -> None:
    """Draw a glowing high-contrast engineering force vector arrow."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 8.0:
        return
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux

    # Optional subtle pulse along shaft
    shift = (pulse % 1.0) * 10.0
    sx0, sy0 = x0 + ux * shift * 0.3, y0 + uy * shift * 0.3
    shaft_end_x = x1 - ux * head_len
    shaft_end_y = y1 - uy * head_len

    # Dark ink silhouette under-stroke for crisp contrast
    draw.line([(sx0, sy0), (shaft_end_x, shaft_end_y)], fill=ink, width=width + 8)
    head_pts = [
        (x1, y1),
        (shaft_end_x + px * head_w, shaft_end_y + py * head_w),
        (shaft_end_x - px * head_w, shaft_end_y - py * head_w),
    ]
    draw.polygon(head_pts, fill=color, outline=ink, width=4)
    draw.line([(sx0, sy0), (shaft_end_x + ux * 4, shaft_end_y + uy * 4)], fill=color, width=width)
    # Bright inner core highlight
    core = lerp_color(color, (255, 255, 255), 0.55)
    draw.line([(sx0 + ux * 4, sy0 + uy * 4), (shaft_end_x, shaft_end_y)], fill=core, width=max(2, width // 3))


def draw_dotted_arc(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    radius: float,
    start_deg: float,
    end_deg: float,
    color: tuple[int, int, int],
    width: int = 4,
    step_deg: float = 8.0,
) -> None:
    """Draw a clean dotted technical measurement arc (inspired by reference telemetry)."""
    deg = start_deg
    while deg < end_deg:
        a1 = math.radians(deg)
        a2 = math.radians(min(end_deg, deg + step_deg * 0.5))
        p1 = (cx + math.cos(a1) * radius, cy + math.sin(a1) * radius)
        p2 = (cx + math.cos(a2) * radius, cy + math.sin(a2) * radius)
        draw.line([p1, p2], fill=color, width=width)
        deg += step_deg


def draw_sparks(
    draw: ImageDraw.ImageDraw,
    ox: float,
    oy: float,
    t: float,
    count: int,
    spread_x: float,
    spread_y: float,
    palette: Palette,
    seed: int = 7,
) -> None:
    """Draw crisp deterministic animated friction / cable-snap metallic sparks."""
    for i in range(count):
        phase = ((t * 2.4 + i * 0.17 + seed * 0.13) % 1.0)
        ang = math.sin(i * 12.9898 + seed * 78.233) * 1.4
        vx = math.cos(ang) * spread_x * (0.45 + 0.55 * ((i * 37) % 10) / 10.0)
        vy = math.sin(ang) * spread_y - 45.0
        x = ox + vx * phase
        y = oy + vy * phase + 180.0 * phase * phase
        x_prev = ox + vx * max(0.0, phase - 0.08)
        y_prev = oy + vy * max(0.0, phase - 0.08) + 180.0 * max(0.0, phase - 0.08) ** 2
        col = lerp_color(palette.text_highlight, palette.amber, phase)
        if phase < 0.88:
            draw.line([(x_prev, y_prev), (x, y)], fill=col, width=max(2, int(5 * (1.0 - phase))))
            r = max(2.0, 5.0 * (1.0 - phase))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 252, 220))


def draw_pressure_gauge(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    radius: float,
    value_0_to_1: float,
    label: str,
    reading: str,
    palette: Palette,
    font_path: str,
    invert_scale: bool = False,
) -> None:
    """Draw a high-contrast engineering dial strictly inside safe zones with auto-fitted typography."""
    # Strict TikTok/Reels/Shorts right-UI safe clamp (x_max <= 855, x_min >= 52)
    cx = max(52.0 + radius + 8.0, min(855.0 - radius - 8.0, cx))
    v = clamp(value_0_to_1)
    draw.ellipse(
        [cx - radius - 6, cy - radius - 6, cx + radius + 6, cy + radius + 6],
        fill=palette.steel_dark,
        outline=palette.ink,
        width=4,
    )
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=palette.surface_panel,
        outline=palette.steel_light,
        width=2,
    )
    # Color arc segments (green -> amber -> crimson, or reversed if invert_scale)
    for seg_i in range(24):
        frac = seg_i / 24.0
        a = math.radians(140.0 + frac * 260.0)
        eff = (1.0 - frac) if invert_scale else frac
        col = palette.emerald if eff < 0.55 else (palette.amber if eff < 0.80 else palette.danger)
        p_in = (cx + math.cos(a) * radius * 0.76, cy + math.sin(a) * radius * 0.76)
        p_out = (cx + math.cos(a) * radius * 0.90, cy + math.sin(a) * radius * 0.90)
        draw.line([p_in, p_out], fill=col, width=4)

    # Needle drawn BEFORE readout plate so needle never crosses over text!
    needle_ang = math.radians(140.0 + v * 260.0)
    nx = cx + math.cos(needle_ang) * radius * 0.70
    ny = cy + math.sin(needle_ang) * radius * 0.70
    eff_v = (1.0 - v) if invert_scale else v
    needle_col = palette.danger if eff_v > 0.78 else (palette.emerald if eff_v < 0.45 else palette.amber)
    draw.line([(cx, cy), (nx, ny)], fill=needle_col, width=5)
    draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=palette.text_primary, outline=palette.ink, width=2)

    # Crisp dark readout backing pill inside lower half of dial so text never collides with needle/ticks
    max_txt_w = radius * 1.46
    lbl_sz = max(12, int(radius * 0.17))
    while lbl_sz > 11:
        f_lbl = load_font(font_path, lbl_sz)
        lb = draw.textbbox((0, 0), label, font=f_lbl)
        if (lb[2] - lb[0]) <= max_txt_w:
            break
        lbl_sz -= 1
    f_lbl = load_font(font_path, lbl_sz)
    lb = draw.textbbox((0, 0), label, font=f_lbl)

    val_sz = max(14, int(radius * 0.23))
    while val_sz > 12:
        f_val = load_font(font_path, val_sz)
        vb = draw.textbbox((0, 0), reading, font=f_val)
        if (vb[2] - vb[0]) <= max_txt_w:
            break
        val_sz -= 1
    f_val = load_font(font_path, val_sz)
    vb = draw.textbbox((0, 0), reading, font=f_val)

    plate_w = min(radius * 1.62, max(lb[2] - lb[0], vb[2] - vb[0]) + 18)
    plate_y0 = cy + radius * 0.16
    plate_y1 = cy + radius * 0.76
    draw.rounded_rectangle(
        [cx - plate_w * 0.5, plate_y0, cx + plate_w * 0.5, plate_y1],
        radius=8,
        fill=(10, 18, 30),
        outline=palette.steel_dark,
        width=1,
    )
    val_col = palette.emerald if invert_scale and v > 0.6 else (palette.text_highlight if eff_v > 0.72 else palette.cyan)
    draw.text((cx - (lb[2] - lb[0]) / 2, plate_y0 + 5 - lb[1]), label, font=f_lbl, fill=palette.steel_light)
    draw.text((cx - (vb[2] - vb[0]) / 2, plate_y0 + (plate_y1 - plate_y0) * 0.48 - vb[1]), reading, font=f_val, fill=val_col)


def draw_comparison_bars(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    width: float,
    height: float,
    items: list[tuple[str, str, float, tuple[int, int, int]]],
    progress: float,
    palette: Palette,
    font_path: str,
) -> None:
    """Draw a sleek live comparison bar chart strictly inside x <= 860 (TikTok/Reels/Shorts safe)."""
    # Strict right safe-zone clamp so right-aligned numbers are NEVER hidden under platform UI!
    max_x1 = 860.0
    if x0 + width > max_x1:
        width = min(width, max_x1 - max(72.0, x0))
        if width < 520.0:
            x0 = max(72.0, max_x1 - 540.0)
            width = max_x1 - x0

    p = clamp(max(0.45, progress))
    draw.rounded_rectangle(
        [x0, y0, x0 + width, y0 + height],
        radius=18,
        fill=palette.surface_panel,
        outline=palette.steel_mid,
        width=3,
    )
    n = max(1, len(items))
    row_h = (height - 40) / n
    pad_x = 22
    for idx, (label, val_str, frac, color) in enumerate(items):
        ry = y0 + 20 + idx * row_h
        # Auto-fit label & value fonts so they never collide on narrower safe-zone widths
        f_lbl_sz = 24
        f_val_sz = 26
        while f_lbl_sz > 16:
            f_lbl = load_font(font_path, f_lbl_sz)
            f_val = load_font(font_path, f_val_sz)
            lw = draw.textbbox((0, 0), label, font=f_lbl)[2]
            vw = draw.textbbox((0, 0), val_str, font=f_val)[2]
            if lw + vw + 24 <= width - pad_x * 2:
                break
            f_lbl_sz -= 2
            f_val_sz = max(18, f_val_sz - 2)
        f_lbl = load_font(font_path, f_lbl_sz)
        f_val = load_font(font_path, f_val_sz)
        draw.text((x0 + pad_x, ry), label, font=f_lbl, fill=palette.text_primary)
        vb = draw.textbbox((0, 0), val_str, font=f_val)
        draw.text((x0 + width - pad_x - (vb[2] - vb[0]), ry - 1), val_str, font=f_val, fill=color)

        bar_y = ry + 34
        bar_h = min(34.0, row_h * 0.36)
        bar_max_w = width - pad_x * 2
        draw.rounded_rectangle(
            [x0 + pad_x, bar_y, x0 + pad_x + bar_max_w, bar_y + bar_h],
            radius=8,
            fill=palette.bg_dark,
            outline=palette.steel_dark,
            width=2,
        )
        eff_frac = clamp(frac)
        if eff_frac > 0.005:
            fill_w = max(10.0, bar_max_w * eff_frac * p)
            draw.rounded_rectangle(
                [x0 + pad_x, bar_y, x0 + pad_x + fill_w, bar_y + bar_h],
                radius=8,
                fill=color,
                outline=palette.ink,
                width=2,
            )


def draw_cta_buttons(
    draw: ImageDraw.ImageDraw,
    t: float,
    palette: Palette,
    font_path: str,
    by: int = 1140,
    left_bx: int = 235,
    right_bx: int = 720,
    right_col: tuple[int, int, int] | None = None,
) -> None:
    """Draw YES / NO verdict pills strictly inside TikTok/Reels/Shorts safe zone (x <= 855)."""
    pulse = 1.0 + 0.035 * math.sin(t * 7.0)
    bw = int(116 * pulse)
    bh = int(76 * pulse)
    # Guarantee right edge <= 852
    right_bx = min(right_bx, 852 - bw)
    r_col = right_col or palette.amber
    f = load_font(font_path, 42)
    for label, bx, col in (("YES", left_bx, palette.cyan), ("NO", right_bx, r_col)):
        draw.rounded_rectangle(
            [bx - bw, by, bx + bw, by + bh],
            radius=18,
            fill=palette.surface_panel,
            outline=col,
            width=5,
        )
        bb = draw.textbbox((0, 0), label, font=f)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]
        draw.text((bx - tw / 2 - bb[0], by + (bh - th) / 2 - bb[1]), label, font=f, fill=col)


def draw_top_hook(
    draw: ImageDraw.ImageDraw,
    hook_text: str,
    brand: BrandConfig,
    palette: Palette,
    repo_root: Path | None = None,
) -> None:
    """Draw bold Frame 0 two-tone white + yellow outlined hook strictly inside Reels/TikTok/Shorts safe zone.

    Hard-clamped to x <= 865 (symmetrically centered at cx=540) and y >= 305 so the headline never collides
    with the Instagram Reels profile grid top-right play badge when Frame 0 is used as the thumbnail.
    """
    sz = brand.visual_style.safe_zones.top_hook
    safe_x_max = min(sz.x_max, 865)
    safe_x_min = max(sz.x_min, 1080 - safe_x_max)
    safe_y_min = max(sz.y_min, 305)
    safe_y_max = max(safe_y_min + 120, sz.y_max)
    safe_w = max(240, safe_x_max - safe_x_min)
    safe_h = safe_y_max - safe_y_min
    font_path = str(brand.visual_style.resolve_font_path("primary", repo_root=repo_root))

    words = hook_text.strip().upper().split()
    if len(words) >= 4:
        mid = len(words) // 2
        # Avoid splitting number from unit (e.g. "40" / "FT")
        if mid > 1 and words[mid - 1].replace(",", "").replace(".", "").isdigit():
            mid -= 1
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
    else:
        lines = [hook_text.strip().upper()]

    font_size = 74 if len(lines) == 1 else 62
    while font_size >= 30:
        font = load_font(font_path, font_size)
        sp_w = max(14, int(font_size * 0.32))
        max_w = max(
            sum(draw.textbbox((0, 0), w, font=font, stroke_width=5)[2] for w in ln.split())
            + sp_w * max(0, len(ln.split()) - 1)
            for ln in lines
        )
        line_h = draw.textbbox((0, 0), "Ag", font=font, stroke_width=5)[3]
        total_h = line_h * len(lines) + (12 if len(lines) > 1 else 0)
        if max_w <= safe_w - 16 and total_h <= safe_h - 8:
            break
        font_size -= 2

    font = load_font(font_path, font_size)
    sp_w = max(14, int(font_size * 0.32))
    line_h = draw.textbbox((0, 0), "Ag", font=font, stroke_width=5)[3]
    gap = 12 if len(lines) > 1 else 0
    total_h = line_h * len(lines) + gap
    y = safe_y_min + max(0, (safe_h - total_h) // 2)
    cx = (safe_x_min + safe_x_max) // 2

    for idx, ln in enumerate(lines):
        toks = ln.split()
        ws = [draw.textbbox((0, 0), w, font=font, stroke_width=5)[2] for w in toks]
        tw = sum(ws) + sp_w * max(0, len(toks) - 1)
        x = max(safe_x_min, min(safe_x_max - tw - 6, cx - tw // 2))
        fill = palette.text_highlight if idx == len(lines) - 1 else palette.text_primary
        for w, ww in zip(toks, ws):
            draw.text((x + 4, y + 5), w, font=font, fill=palette.ink, stroke_width=6, stroke_fill=palette.ink)
            draw.text((x, y), w, font=font, fill=fill, stroke_width=5, stroke_fill=palette.ink)
            x += ww + sp_w
        y += line_h + gap


def draw_hud_callout(
    draw: ImageDraw.ImageDraw,
    callout: Callout,
    brand: BrandConfig,
    palette: Palette,
    accent_color: tuple[int, int, int] | None = None,
    progress: float = 1.0,
    repo_root: Path | None = None,
) -> None:
    """Draw sleek dark-navy telemetry pill strictly inside x=90..850, y=490..610 (Beats 2-12 only)."""
    sz = brand.visual_style.safe_zones.callout_hud
    font_lbl_path = str(brand.visual_style.resolve_font_path("secondary", repo_root=repo_root))
    font_val_path = str(brand.visual_style.resolve_font_path("primary", repo_root=repo_root))

    f_lbl = load_font(font_lbl_path, 21)
    f_val = load_font(font_val_path, 35)

    lbl = callout.label.upper()
    val = callout.value.upper()
    lb = draw.textbbox((0, 0), lbl, font=f_lbl)
    vb = draw.textbbox((0, 0), val, font=f_val)
    inner_w = max(lb[2] - lb[0], vb[2] - vb[0])
    box_w = min(sz.width - 10, max(260, inner_w + 64))
    box_h = min(sz.height - 20, 106)

    slide = int((1.0 - clamp(progress * 4.0)) * -22)
    x0 = sz.x_min + slide
    y0 = sz.y_min + 6
    x1 = min(min(sz.x_max, 855), x0 + box_w)
    y1 = y0 + box_h

    accent = accent_color or palette.cyan
    draw.rounded_rectangle([x0 + 4, y0 + 5, x1 + 4, y1 + 5], radius=16, fill=(4, 7, 14))
    draw.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=palette.surface_panel, outline=accent, width=3)
    draw.rounded_rectangle([x0 + 12, y0 + 14, x0 + 22, y1 - 14], radius=4, fill=accent)

    draw.text((x0 + 36, y0 + 14), lbl, font=f_lbl, fill=palette.steel_light)
    draw.text((x0 + 36, y0 + 44), val, font=f_val, fill=palette.text_highlight)


def draw_brand_header(
    draw: ImageDraw.ImageDraw,
    brand: BrandConfig,
    palette: Palette,
    repo_root: Path | None = None,
) -> None:
    """Crisp non-intrusive top engineering header above y=230."""
    font_path = str(brand.visual_style.resolve_font_path("secondary", repo_root=repo_root))
    f = load_font(font_path, 23)
    tag = f"{brand.channel_name.upper()}  //  CAD TELEMETRY"
    bbox = draw.textbbox((0, 0), tag, font=f)
    tw = bbox[2] - bbox[0]
    x = (1080 - tw) // 2
    y = 116
    draw.text((x, y), tag, font=f, fill=(166, 188, 214))
    draw.line([(x - 36, y + 14), (x - 12, y + 14)], fill=palette.cyan, width=3)
    draw.line([(x + tw + 12, y + 14), (x + tw + 36, y + 14)], fill=palette.cyan, width=3)
