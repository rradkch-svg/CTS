"""Opaque-box visual, safe-zone, luminance, and contrast helpers.

Strictly stdlib + ``PIL`` + ``numpy``. Never imports from ``src/`` or ``cts_factory``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

# Canonical safe-zone constants (PROJECT.md T7 & shorts-factory/SKILL.md)
FRAME_SIZE: tuple[int, int] = (1080, 1920)
HOOK_SAFE_ZONE: tuple[int, int, int, int] = (90, 260, 990, 460)
SCENE_VIEWPORT_ZONE: tuple[int, int, int, int] = (0, 460, 1080, 1360)
HERO_CENTER_ZONE: tuple[int, int, int, int] = (80, 480, 1000, 1360)
CAPTION_SAFE_ZONE: tuple[int, int, int, int] = (110, 1380, 930, 1520)
PLATFORM_RIGHT_UI_ZONE: tuple[int, int, int, int] = (955, 1380, 1075, 1520)
PLATFORM_BOTTOM_CHROME_Y: int = 1600
COVER_REELS_SAFE_ZONE: tuple[int, int, int, int] = (90, 330, 990, 1580)
COVER_3X4_SAFE_ZONE: tuple[int, int, int, int] = (90, 260, 990, 1660)
COVER_FORBIDDEN_TOP_Y: int = 255
COVER_FORBIDDEN_BOTTOM_Y: int = 1665
COVER_TIGHT_REELS_TOP_Y: int = 315
COVER_TIGHT_REELS_BOTTOM_Y: int = 1595

BANNER_SIZE: tuple[int, int] = (2560, 1440)
BANNER_MAX_BYTES: int = 6 * 1024 * 1024
BANNER_STRICT_MAX_BYTES: int = 6_000_000
BANNER_DESKTOP_STRIP: tuple[int, int, int, int] = (0, 508, 2560, 931)
BANNER_MOBILE_SAFE_ZONE: tuple[int, int, int, int] = (507, 508, 2053, 931)


@dataclass(frozen=True)
class ImageInfo:
    """Decoded image file metadata including alpha integrity."""

    path: Path
    width: int
    height: int
    mode: str
    fmt: str | None
    size_bytes: int
    is_valid_png: bool
    has_alpha: bool
    min_alpha: int
    has_alpha_holes: bool


@dataclass(frozen=True)
class ZoneMetrics:
    """Rec.709 luminance, contrast, edge density, and median color inside a box."""

    box: tuple[int, int, int, int]
    mean_lum: float
    std_lum: float
    p05_lum: float
    p95_lum: float
    luma_spread: float
    wcag_contrast_p95_p05: float
    edge_density: float
    bright_pixel_ratio: float
    bright_stroke_ratio: float
    median_rgb: tuple[float, float, float]


@dataclass(frozen=True)
class Frame0Report:
    """Visual verification report for Frame 0 (``t=0.0s``) feed cover hook."""

    ok: bool
    size: tuple[int, int]
    full_metrics: ZoneMetrics
    hook_metrics: ZoneMetrics
    hero_metrics: ZoneMetrics
    edge_clipped: bool
    fade_ratio: float | None
    frame15_hook_spread: float | None
    errors: list[str]


@dataclass(frozen=True)
class CaptionVisualReport:
    """Visual verification report for lower burned-in caption band across frames."""

    ok: bool
    frames_checked: int
    active_caption_ratio: float
    opaque_box_detected: bool
    opaque_box_frame_count: int
    right_ui_leak_ratio: float
    has_white_text: bool
    has_accent_highlight: bool | None
    errors: list[str]


@dataclass(frozen=True)
class CoverReport:
    """Visual safe-zone and file-integrity report for a 1080x1920 episode cover."""

    ok: bool
    size: tuple[int, int]
    size_bytes: int | None
    min_alpha: int
    safe_zone_metrics: ZoneMetrics
    outer_top_metrics: ZoneMetrics
    outer_bottom_metrics: ZoneMetrics
    tight_top_metrics: ZoneMetrics
    tight_bottom_metrics: ZoneMetrics
    outer_border_median_rgb: tuple[float, float, float]
    errors: list[str]


@dataclass(frozen=True)
class BannerReport:
    """Visual safe-zone and file-integrity report for a 2560x1440 YouTube banner."""

    ok: bool
    size: tuple[int, int]
    size_bytes: int
    min_alpha: int
    mobile_metrics: ZoneMetrics
    desktop_left_metrics: ZoneMetrics
    desktop_right_metrics: ZoneMetrics
    tv_top_metrics: ZoneMetrics
    tv_bottom_metrics: ZoneMetrics
    border_collision: bool
    tv_strip_median_rgb: tuple[float, float, float]
    errors: list[str]


# ---------------------------------------------------------------------------
# Color, luminance, and basic image primitives
# ---------------------------------------------------------------------------


def parse_hex_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse ``#RRGGBB``, ``RRGGBB``, or ``#RGB`` into an ``(R, G, B)`` tuple."""
    if not isinstance(hex_str, str):
        raise ValueError(f"Expected hex color string, got {type(hex_str).__name__}")
    s = hex_str.strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{3}", s):
        s = "".join(ch * 2 for ch in s)
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", s):
        raise ValueError(f"Invalid hex color string: {hex_str!r}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _coerce_rgb(color: tuple[int, int, int] | str) -> tuple[int, int, int]:
    if isinstance(color, str):
        return parse_hex_rgb(color)
    r, g, b = int(color[0]), int(color[1]), int(color[2])
    return (r, g, b)


def _srgb_linearize_channel(val_0_255: float) -> float:
    s = max(0.0, min(1.0, val_0_255 / 255.0))
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def wcag_contrast_ratio(
    rgb1: tuple[int, int, int] | str, rgb2: tuple[int, int, int] | str
) -> float:
    """Compute exact W3C WCAG 2.1 linearized sRGB contrast ratio."""
    r1, g1, b1 = _coerce_rgb(rgb1)
    r2, g2, b2 = _coerce_rgb(rgb2)
    l1 = (
        0.2126 * _srgb_linearize_channel(r1)
        + 0.7152 * _srgb_linearize_channel(g1)
        + 0.0722 * _srgb_linearize_channel(b1)
    )
    l2 = (
        0.2126 * _srgb_linearize_channel(r2)
        + 0.7152 * _srgb_linearize_channel(g2)
        + 0.0722 * _srgb_linearize_channel(b2)
    )
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def luma_to_wcag(lum_hi: float, lum_lo: float) -> float:
    """Estimate WCAG contrast ratio between two 0..255 sRGB luma values."""
    l_hi = _srgb_linearize_channel(max(lum_hi, lum_lo))
    l_lo = _srgb_linearize_channel(min(lum_hi, lum_lo))
    return (l_hi + 0.05) / (l_lo + 0.05)


def rgb_distance(rgb1: Sequence[float], rgb2: Sequence[float]) -> float:
    """Compute Euclidean distance in 8-bit RGB space."""
    return math.sqrt(
        (float(rgb1[0]) - float(rgb2[0])) ** 2
        + (float(rgb1[1]) - float(rgb2[1])) ** 2
        + (float(rgb1[2]) - float(rgb2[2])) ** 2
    )


def to_rgb_array(img: Image.Image) -> np.ndarray:
    """Convert a PIL image into an ``(H, W, 3)`` uint8 RGB NumPy array."""
    rgb_img = img if img.mode == "RGB" else img.convert("RGB")
    return np.asarray(rgb_img, dtype=np.uint8)


def relative_luminance(rgb: np.ndarray) -> np.ndarray:
    """Compute Rec.709 0..255 luma array from an ``(..., 3)`` RGB array."""
    arr = rgb.astype(np.float32)
    return 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]


def _extract_min_alpha(img: Image.Image) -> tuple[bool, int]:
    bands = img.getbands()
    if "A" in bands:
        alpha = np.asarray(img.getchannel("A"), dtype=np.uint8)
        return True, int(alpha.min())
    if img.mode == "P" and "transparency" in img.info:
        rgba = img.convert("RGBA")
        alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
        return True, int(alpha.min())
    return False, 255


def inspect_image(path: Path) -> ImageInfo:
    """Decode an image file completely and inspect dimensions, format, size, and alpha."""
    p = Path(path).resolve()
    size_bytes = p.stat().st_size
    with Image.open(p) as img:
        img.load()
        fmt = img.format
        width, height = img.size
        mode = img.mode
        has_alpha, min_alpha = _extract_min_alpha(img)

    return ImageInfo(
        path=p,
        width=width,
        height=height,
        mode=mode,
        fmt=fmt,
        size_bytes=size_bytes,
        is_valid_png=(fmt == "PNG"),
        has_alpha=has_alpha,
        min_alpha=min_alpha,
        has_alpha_holes=(min_alpha < 255),
    )


def palette_color_present(
    rgb_arr: np.ndarray | Image.Image,
    hex_or_rgb: tuple[int, int, int] | str,
    *,
    max_dist: float = 25.0,
    min_pixels: int = 25,
    min_ratio: float = 0.0,
) -> tuple[bool, int, float]:
    """Check whether ``hex_or_rgb`` is present in ``rgb_arr`` within Euclidean ``max_dist``."""
    arr = to_rgb_array(rgb_arr) if isinstance(rgb_arr, Image.Image) else rgb_arr
    target = np.array(_coerce_rgb(hex_or_rgb), dtype=np.float32)
    diff = arr.astype(np.float32) - target
    dist = np.sqrt(np.sum(diff * diff, axis=-1))
    matches = int(np.sum(dist <= max_dist))
    total = int(arr.shape[0] * arr.shape[1]) if arr.ndim >= 2 else 1
    ratio = matches / float(max(total, 1))
    return (matches >= min_pixels and ratio >= min_ratio, matches, ratio)


def zone_metrics(rgb: np.ndarray, box: tuple[int, int, int, int]) -> ZoneMetrics:
    """Compute Rec.709 luminance, WCAG p95/p05 contrast, edge density, and stroke metrics."""
    h, w = rgb.shape[:2]
    x0 = max(0, min(w - 1, int(box[0])))
    y0 = max(0, min(h - 1, int(box[1])))
    x1 = max(x0 + 1, min(w, int(box[2])))
    y1 = max(y0 + 1, min(h, int(box[3])))

    crop = rgb[y0:y1, x0:x1]
    lum = relative_luminance(crop)
    mean_lum = float(np.mean(lum))
    std_lum = float(np.std(lum))
    p05_lum = float(np.percentile(lum, 5))
    p95_lum = float(np.percentile(lum, 95))
    luma_spread = p95_lum - p05_lum
    wcag = luma_to_wcag(p95_lum, p05_lum)

    if lum.shape[0] >= 2 and lum.shape[1] >= 2:
        gx = np.abs(np.diff(lum, axis=1))[:-1, :]
        gy = np.abs(np.diff(lum, axis=0))[:, :-1]
        grad = np.maximum(gx, gy)
        lum_inner = lum[:-1, :-1]
        edge_density = float(np.mean(grad > 25.0))
        bright_stroke_ratio = float(np.mean((lum_inner > 195.0) & (grad > 35.0)))
    else:
        edge_density = 0.0
        bright_stroke_ratio = 0.0

    bright_pixel_ratio = float(np.mean(lum > 205.0))
    med = np.median(crop.reshape(-1, 3), axis=0)
    median_rgb = (float(med[0]), float(med[1]), float(med[2]))

    return ZoneMetrics(
        box=(x0, y0, x1, y1),
        mean_lum=mean_lum,
        std_lum=std_lum,
        p05_lum=p05_lum,
        p95_lum=p95_lum,
        luma_spread=luma_spread,
        wcag_contrast_p95_p05=wcag,
        edge_density=edge_density,
        bright_pixel_ratio=bright_pixel_ratio,
        bright_stroke_ratio=bright_stroke_ratio,
        median_rgb=median_rgb,
    )


# ---------------------------------------------------------------------------
# Composite visual checkers
# ---------------------------------------------------------------------------


def check_frame0_hook(
    frame0: Image.Image, frame15: Image.Image | None = None
) -> Frame0Report:
    """Validate Frame 0 (``t=0.0s``) instant visibility, top hook contrast, and anti-fade-in."""
    errors: list[str] = []
    size = frame0.size
    rgb0 = to_rgb_array(frame0)
    full_m = zone_metrics(rgb0, (0, 0, size[0], size[1]))
    hook_m = zone_metrics(rgb0, HOOK_SAFE_ZONE)
    hero_m = zone_metrics(rgb0, HERO_CENTER_ZONE)

    if size != FRAME_SIZE:
        errors.append(f"frame0 size {size} != {FRAME_SIZE}")
    if full_m.mean_lum < 20.0:
        errors.append(f"frame0 mean_lum {full_m.mean_lum:.2f} < 20.0 (dark/black start)")
    if full_m.std_lum < 25.0:
        errors.append(f"frame0 std_lum {full_m.std_lum:.2f} < 25.0 (flat/blank start)")
    if hook_m.luma_spread < 100.0:
        errors.append(f"frame0 hook luma_spread {hook_m.luma_spread:.2f} < 100.0")
    if hook_m.wcag_contrast_p95_p05 < 3.0:
        errors.append(
            f"frame0 hook WCAG contrast {hook_m.wcag_contrast_p95_p05:.2f} < 3.0"
        )
    if hero_m.std_lum < 12.0 or hero_m.edge_density < 0.01:
        errors.append(
            f"frame0 center hero lacks visual detail (std={hero_m.std_lum:.2f}, edge={hero_m.edge_density:.4f})"
        )

    left_edge = zone_metrics(rgb0, (0, 260, 40, 460))
    right_edge = zone_metrics(rgb0, (1040, 260, 1080, 460))
    top_edge = zone_metrics(rgb0, (90, 0, 990, 200))
    edge_clipped = (
        left_edge.bright_stroke_ratio >= 0.005
        or right_edge.bright_stroke_ratio >= 0.005
        or top_edge.bright_stroke_ratio >= 0.005
    )
    if edge_clipped:
        errors.append(
            "frame0 hook text clips extreme edge margins "
            f"(L={left_edge.bright_stroke_ratio:.4f}, R={right_edge.bright_stroke_ratio:.4f}, "
            f"T={top_edge.bright_stroke_ratio:.4f})"
        )

    fade_ratio: float | None = None
    frame15_hook_spread: float | None = None
    if frame15 is not None:
        rgb15 = to_rgb_array(frame15)
        full15 = zone_metrics(rgb15, (0, 0, frame15.size[0], frame15.size[1]))
        hook15 = zone_metrics(rgb15, HOOK_SAFE_ZONE)
        fade_ratio = full_m.mean_lum / max(full15.mean_lum, 1.0)
        frame15_hook_spread = hook15.luma_spread
        if fade_ratio < 0.75:
            errors.append(
                f"frame0 fade-in detected: luma(f0)/luma(f15) = {fade_ratio:.3f} < 0.75"
            )
        if frame15_hook_spread < 80.0:
            errors.append(
                f"frame15 hook text did not persist cleanly (spread={frame15_hook_spread:.2f} < 80.0)"
            )

    return Frame0Report(
        ok=len(errors) == 0,
        size=size,
        full_metrics=full_m,
        hook_metrics=hook_m,
        hero_metrics=hero_m,
        edge_clipped=edge_clipped,
        fade_ratio=fade_ratio,
        frame15_hook_spread=frame15_hook_spread,
        errors=errors,
    )


def _detect_opaque_caption_box(rgb: np.ndarray) -> bool:
    """Zero-FP dual-boundary check for an opaque solid rectangle behind captions."""
    inner = rgb[1395:1505, 140:900]
    above = rgb[1335:1370, 140:900]
    below = rgb[1530:1565, 140:900]

    lum_in = relative_luminance(inner)
    bg_mask = lum_in < 80.0
    if float(np.mean(bg_mask)) < 0.35:
        return False

    bg_pixels = inner[bg_mask].astype(np.float32)
    med_in = np.median(bg_pixels, axis=0)
    l1_dev = np.abs(bg_pixels - med_in).sum(axis=1)
    uniform_frac = float(np.mean(l1_dev <= 9.0))
    if uniform_frac < 0.80:
        return False

    med_above = np.median(above.reshape(-1, 3).astype(np.float32), axis=0)
    med_below = np.median(below.reshape(-1, 3).astype(np.float32), axis=0)
    jump_above = float(np.abs(med_in - med_above).sum())
    jump_below = float(np.abs(med_in - med_below).sum())
    return min(jump_above, jump_below) >= 22.0


def check_caption_band(
    frames: Sequence[Image.Image],
    *,
    accent_rgbs: Sequence[tuple[int, int, int] | str] | None = None,
    active_fraction_min: float = 0.5,
    accent_max_dist: float = 48.0,
) -> CaptionVisualReport:
    """Validate burned-in captions: contrast, no opaque box, right-UI clearance, white+accent."""
    if not frames:
        return CaptionVisualReport(
            ok=False,
            frames_checked=0,
            active_caption_ratio=0.0,
            opaque_box_detected=False,
            opaque_box_frame_count=0,
            right_ui_leak_ratio=0.0,
            has_white_text=False,
            has_accent_highlight=False if accent_rgbs else None,
            errors=["no frames provided to check_caption_band"],
        )

    errors: list[str] = []
    active_count = 0
    opaque_box_count = 0
    right_leak_count = 0
    white_text_found = False
    accent_found = False
    coerced_accents = [_coerce_rgb(c) for c in accent_rgbs] if accent_rgbs else []

    for idx, frame in enumerate(frames):
        if frame.size != FRAME_SIZE:
            errors.append(f"frame[{idx}] size {frame.size} != {FRAME_SIZE}")
            continue
        rgb = to_rgb_array(frame)
        cap_m = zone_metrics(rgb, CAPTION_SAFE_ZONE)
        right_m = zone_metrics(rgb, PLATFORM_RIGHT_UI_ZONE)

        is_active = cap_m.luma_spread >= 80.0 and cap_m.bright_stroke_ratio >= 0.003
        if is_active:
            active_count += 1
            cap_crop = rgb[
                CAPTION_SAFE_ZONE[1] : CAPTION_SAFE_ZONE[3],
                CAPTION_SAFE_ZONE[0] : CAPTION_SAFE_ZONE[2],
            ]
            cap_lum = relative_luminance(cap_crop)
            if int(np.sum(cap_lum > 220.0)) >= 30:
                white_text_found = True
            if coerced_accents and not accent_found:
                for col in coerced_accents:
                    present, _, _ = palette_color_present(
                        cap_crop, col, max_dist=accent_max_dist, min_pixels=20
                    )
                    if present:
                        accent_found = True
                        break

        if _detect_opaque_caption_box(rgb):
            opaque_box_count += 1

        if right_m.bright_stroke_ratio >= 0.005 and (
            cap_m.bright_stroke_ratio <= 0.0
            or right_m.bright_stroke_ratio >= 0.25 * cap_m.bright_stroke_ratio
        ):
            right_leak_count += 1

    total = len(frames)
    active_ratio = active_count / float(total)
    right_leak_ratio = right_leak_count / float(total)
    opaque_box_detected = opaque_box_count > 0

    if active_ratio < active_fraction_min:
        errors.append(
            f"active caption fraction {active_ratio:.2f} < {active_fraction_min:.2f} ({active_count}/{total})"
        )
    if opaque_box_detected:
        errors.append(
            f"opaque solid rectangle box detected behind captions on {opaque_box_count}/{total} frames"
        )
    if right_leak_ratio > 0.15:
        errors.append(
            f"caption strokes encroach right-side platform UI (x>955) on {right_leak_count}/{total} frames"
        )
    if active_fraction_min > 0 and not white_text_found:
        errors.append("no high-contrast white text pixels (luma>220) found in caption band")
    if coerced_accents and active_fraction_min > 0 and not accent_found:
        errors.append("no brand accent highlight color detected inside caption band")

    return CaptionVisualReport(
        ok=len(errors) == 0,
        frames_checked=total,
        active_caption_ratio=active_ratio,
        opaque_box_detected=opaque_box_detected,
        opaque_box_frame_count=opaque_box_count,
        right_ui_leak_ratio=right_leak_ratio,
        has_white_text=white_text_found,
        has_accent_highlight=(accent_found if coerced_accents else None),
        errors=errors,
    )


def check_cover_safe_zones(
    cover: Image.Image | Path, *, size_bytes: int | None = None
) -> CoverReport:
    """Validate 1080x1920 episode cover contrast, alpha, file size, and outer/Reels safe zones."""
    errors: list[str] = []
    if isinstance(cover, (str, Path)):
        p = Path(cover).resolve()
        info = inspect_image(p)
        if not info.is_valid_png:
            errors.append(f"cover {p.name} is not a valid PNG (fmt={info.fmt})")
        size_bytes = info.size_bytes
        min_alpha = info.min_alpha
        with Image.open(p) as im:
            im.load()
            size = im.size
            rgb = to_rgb_array(im)
    else:
        _, min_alpha = _extract_min_alpha(cover)
        size = cover.size
        rgb = to_rgb_array(cover)

    if size != FRAME_SIZE:
        errors.append(f"cover size {size} != {FRAME_SIZE}")
    if min_alpha < 255:
        errors.append(f"cover contains transparent alpha holes (min_alpha={min_alpha} < 255)")
    if size_bytes is not None:
        if size_bytes < 20_000:
            errors.append(f"cover file size {size_bytes} bytes < 20,000 bytes")
        if size_bytes >= BANNER_STRICT_MAX_BYTES:
            errors.append(
                f"cover file size {size_bytes} bytes >= {BANNER_STRICT_MAX_BYTES} bytes"
            )

    safe_m = zone_metrics(rgb, COVER_REELS_SAFE_ZONE)
    outer_top = zone_metrics(rgb, (0, 0, FRAME_SIZE[0], COVER_FORBIDDEN_TOP_Y))
    outer_bot = zone_metrics(rgb, (0, COVER_FORBIDDEN_BOTTOM_Y, FRAME_SIZE[0], FRAME_SIZE[1]))
    tight_top = zone_metrics(rgb, (0, 0, FRAME_SIZE[0], COVER_TIGHT_REELS_TOP_Y))
    tight_bot = zone_metrics(rgb, (0, COVER_TIGHT_REELS_BOTTOM_Y, FRAME_SIZE[0], FRAME_SIZE[1]))

    if safe_m.luma_spread < 110.0:
        errors.append(
            f"cover Reels safe zone luma_spread {safe_m.luma_spread:.2f} < 110.0"
        )
    if safe_m.std_lum < 20.0:
        errors.append(f"cover Reels safe zone std_lum {safe_m.std_lum:.2f} < 20.0")
    if safe_m.edge_density < 0.01:
        errors.append(
            f"cover Reels safe zone edge_density {safe_m.edge_density:.4f} < 0.01"
        )

    for label, zm in (
        ("outer top (y<255)", outer_top),
        ("outer bottom (y>1665)", outer_bot),
        ("tight Reels top (y<315)", tight_top),
        ("tight Reels bottom (y>1595)", tight_bot),
    ):
        if zm.bright_stroke_ratio > 0.0025 or zm.bright_pixel_ratio > 0.015:
            errors.append(
                f"cover bright typography/elements clipped in {label} "
                f"(stroke={zm.bright_stroke_ratio:.4f}, bright={zm.bright_pixel_ratio:.4f})"
            )

    border_pixels = np.concatenate(
        [
            rgb[:COVER_FORBIDDEN_TOP_Y, :, :].reshape(-1, 3),
            rgb[COVER_FORBIDDEN_BOTTOM_Y:, :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    med = np.median(border_pixels, axis=0)
    outer_border_median_rgb = (float(med[0]), float(med[1]), float(med[2]))

    return CoverReport(
        ok=len(errors) == 0,
        size=size,
        size_bytes=size_bytes,
        min_alpha=min_alpha,
        safe_zone_metrics=safe_m,
        outer_top_metrics=outer_top,
        outer_bottom_metrics=outer_bot,
        tight_top_metrics=tight_top,
        tight_bottom_metrics=tight_bot,
        outer_border_median_rgb=outer_border_median_rgb,
        errors=errors,
    )


def check_youtube_banner(path: Path) -> BannerReport:
    """Validate 2560x1440 <6MB YouTube channel banner safe zones, border clearance, and TV fill."""
    p = Path(path).resolve()
    info = inspect_image(p)
    errors: list[str] = []

    if not info.is_valid_png:
        errors.append(f"banner {p.name} is not a valid PNG (fmt={info.fmt})")
    if (info.width, info.height) != BANNER_SIZE:
        errors.append(f"banner size {(info.width, info.height)} != {BANNER_SIZE}")
    if info.size_bytes >= BANNER_STRICT_MAX_BYTES:
        errors.append(
            f"banner size {info.size_bytes} bytes >= {BANNER_STRICT_MAX_BYTES} bytes (<6MB limit)"
        )
    if info.min_alpha < 255:
        errors.append(f"banner contains alpha holes (min_alpha={info.min_alpha} < 255)")

    with Image.open(p) as im:
        im.load()
        rgb = to_rgb_array(im)

    mobile_m = zone_metrics(rgb, BANNER_MOBILE_SAFE_ZONE)
    desk_l = zone_metrics(rgb, (0, 508, 500, 931))
    desk_r = zone_metrics(rgb, (2060, 508, 2560, 931))
    tv_top = zone_metrics(rgb, (0, 0, 2560, 480))
    tv_bot = zone_metrics(rgb, (0, 960, 2560, 1440))

    if mobile_m.luma_spread < 75.0:
        errors.append(
            f"banner mobile safe zone luma_spread {mobile_m.luma_spread:.2f} < 75.0"
        )
    if mobile_m.std_lum < 15.0:
        errors.append(
            f"banner mobile safe zone std_lum {mobile_m.std_lum:.2f} < 15.0"
        )
    if mobile_m.edge_density < 0.015:
        errors.append(
            f"banner mobile safe zone edge_density {mobile_m.edge_density:.4f} < 0.015"
        )

    # 14px strips centered on the 4 mobile safe-zone crop boundaries
    border_boxes = (
        ("left x=507", (500, 508, 514, 931)),
        ("right x=2053", (2046, 508, 2060, 931)),
        ("top y=508", (507, 501, 2053, 515)),
        ("bottom y=931", (507, 924, 2053, 938)),
    )
    border_collision = False
    for label, box in border_boxes:
        bm = zone_metrics(rgb, box)
        if bm.bright_stroke_ratio >= 0.015:
            border_collision = True
            errors.append(
                f"banner bright strokes abut mobile crop border {label} "
                f"(bright_stroke_ratio={bm.bright_stroke_ratio:.4f} >= 0.015)"
            )

    for label, zm in (
        ("TV top", tv_top),
        ("TV bottom", tv_bot),
        ("Desktop left", desk_l),
        ("Desktop right", desk_r),
    ):
        if not (5.0 <= zm.mean_lum <= 235.0):
            errors.append(
                f"banner {label} fill mean_lum {zm.mean_lum:.2f} outside [5.0, 235.0]"
            )

    tv_pixels = np.concatenate(
        [
            rgb[:480, :, :].reshape(-1, 3),
            rgb[960:, :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    tv_med = np.median(tv_pixels, axis=0)
    tv_strip_median_rgb = (float(tv_med[0]), float(tv_med[1]), float(tv_med[2]))

    return BannerReport(
        ok=len(errors) == 0,
        size=(info.width, info.height),
        size_bytes=info.size_bytes,
        min_alpha=info.min_alpha,
        mobile_metrics=mobile_m,
        desktop_left_metrics=desk_l,
        desktop_right_metrics=desk_r,
        tv_top_metrics=tv_top,
        tv_bottom_metrics=tv_bot,
        border_collision=border_collision,
        tv_strip_median_rgb=tv_strip_median_rgb,
        errors=errors,
    )
