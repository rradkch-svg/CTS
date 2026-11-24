"""Outlined no-box word-highlighted caption renderer strictly inside the T7 safe zone."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cts_factory.config import BrandConfig, CaptionTrack


def _hex_rgb(hex_str: str) -> tuple[int, int, int]:
    s = hex_str.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


@lru_cache(maxsize=32)
def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, size=size)


def draw_caption(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    t: float,
    track: CaptionTrack,
    brand: BrandConfig,
    repo_root: Path | None = None,
) -> None:
    """Render the active 2-4 word caption block with bold outline and NO opaque background box."""
    block = track.block_at(t)
    if block is None or not block.words:
        return

    sz = brand.visual_style.safe_zones.captions
    max_width = min(sz.width, sz.max_width_px or sz.width)
    center_x = (sz.x_min + sz.x_max) // 2
    center_y = (sz.y_min + sz.y_max) // 2

    palette = brand.visual_style.palette
    col_primary = _hex_rgb(palette.get("text_primary", "#F8FAFC"))
    col_highlight = _hex_rgb(palette.get("text_highlight", "#FFC83D"))
    col_stroke = _hex_rgb(palette.get("text_stroke", "#060A12"))

    font_path = str(brand.visual_style.resolve_font_path("secondary", repo_root=repo_root))
    tokens = [w.text.upper() for w in block.words]

    # Pick largest crisp font size that fits cleanly inside max_width (<= 820px) and safe height
    font_size = 56
    font = _load_font(font_path, font_size)
    space_w = 20
    while font_size >= 36:
        font = _load_font(font_path, font_size)
        space_w = max(16, int(font_size * 0.36))
        widths = [draw.textbbox((0, 0), tok, font=font, stroke_width=5)[2] for tok in tokens]
        total_w = sum(widths) + space_w * max(0, len(tokens) - 1)
        if total_w <= max_width - 20:
            break
        font_size -= 4

    widths = [draw.textbbox((0, 0), tok, font=font, stroke_width=5)[2] for tok in tokens]
    total_w = sum(widths) + space_w * max(0, len(tokens) - 1)
    sample_box = draw.textbbox((0, 0), "Ag", font=font, stroke_width=5)
    line_h = sample_box[3] - sample_box[1]

    # Keep captions strictly inside [sz.x_min, min(sz.x_max, 860)] and cleanly near top of caption safe band (<= 1420)
    safe_x_max = min(sz.x_max, 875)
    safe_cx = (sz.x_min + safe_x_max) // 2
    x = max(sz.x_min, min(safe_x_max - total_w, safe_cx - total_w // 2))
    y_base = max(sz.y_min + 2, min(1418 - line_h, sz.y_min + 12))

    # Determine which word is currently spoken (fallback to last word <= t)
    active_idx = 0
    for idx, w in enumerate(block.words):
        if w.start_s <= t <= w.end_s:
            active_idx = idx
            break
        if t >= w.start_s:
            active_idx = idx

    stroke_w = max(5, font_size // 10)
    for idx, (w, tok, tw) in enumerate(zip(block.words, tokens, widths, strict=True)):
        is_active = idx == active_idx
        fill = col_highlight if (is_active or w.emphasize) else col_primary
        y_off = -3 if is_active else 0
        # Subtle drop shadow (outline-only, zero opaque box!)
        draw.text(
            (x + 3, y_base + y_off + 4),
            tok,
            font=font,
            fill=col_stroke,
            stroke_width=stroke_w,
            stroke_fill=col_stroke,
        )
        draw.text(
            (x, y_base + y_off),
            tok,
            font=font,
            fill=fill,
            stroke_width=stroke_w,
            stroke_fill=col_stroke,
        )
        x += tw + space_w
