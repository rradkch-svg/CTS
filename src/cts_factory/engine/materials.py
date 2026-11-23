"""Color palette, metallic 3-face shading, and cached volumetric blueprint stage backgrounds."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import BrandConfig


def hex_rgb(hex_str: str) -> tuple[int, int, int]:
    s = hex_str.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def lerp_color(
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(round(c1[0] + (c2[0] - c1[0]) * t)),
        int(round(c1[1] + (c2[1] - c1[1]) * t)),
        int(round(c1[2] + (c2[2] - c1[2]) * t)),
    )


def scale_rgb(c: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return (
        max(0, min(255, int(round(c[0] * factor)))),
        max(0, min(255, int(round(c[1] * factor)))),
        max(0, min(255, int(round(c[2] * factor)))),
    )


@dataclass(frozen=True)
class Palette:
    bg_dark: tuple[int, int, int]
    bg_grid: tuple[int, int, int]
    surface_panel: tuple[int, int, int]
    steel_dark: tuple[int, int, int]
    steel_mid: tuple[int, int, int]
    steel_light: tuple[int, int, int]
    brass: tuple[int, int, int]
    amber: tuple[int, int, int]
    cyan: tuple[int, int, int]
    danger: tuple[int, int, int]
    emerald: tuple[int, int, int]
    text_primary: tuple[int, int, int]
    text_highlight: tuple[int, int, int]
    ink: tuple[int, int, int]

    @classmethod
    def from_brand(cls, brand: BrandConfig) -> Palette:
        p = brand.visual_style.palette
        return cls(
            bg_dark=hex_rgb(p.get("background_dark", "#0B1220")),
            bg_grid=hex_rgb(p.get("background_grid", "#15243D")),
            surface_panel=hex_rgb(p.get("surface_panel", "#121E33")),
            steel_dark=hex_rgb(p.get("steel_dark", "#3A4B63")),
            steel_mid=hex_rgb(p.get("steel_mid", "#6E839E")),
            steel_light=hex_rgb(p.get("steel_light", "#B8C7D9")),
            brass=hex_rgb(p.get("brass_accent", "#D4A24C")),
            amber=hex_rgb(p.get("primary_accent", "#FF8C1A")),
            cyan=hex_rgb(p.get("secondary_accent", "#00D4FF")),
            danger=hex_rgb(p.get("danger_stress", "#FF2E4C")),
            emerald=hex_rgb(p.get("safe_lock", "#2EE58B")),
            text_primary=hex_rgb(p.get("text_primary", "#F8FAFC")),
            text_highlight=hex_rgb(p.get("text_highlight", "#FFC83D")),
            ink=hex_rgb(p.get("text_stroke", "#060A12")),
        )


def build_stage_background(
    width: int,
    height: int,
    palette: Palette,
    spot_color: tuple[int, int, int] | None = None,
    spot_cy: float = 0.50,
    grid_step: int = 72,
    ocean_gradient: bool = False,
) -> Image.Image:
    """Pre-render deep-blueprint volumetric spotlight stage + subtle isometric CAD grid.

    Cached once per scene/mood so per-frame copy takes <1ms on 2 CPU cores.
    """
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xx - width * 0.5) / (width * 0.55)
    ny = (yy - height * spot_cy) / (height * 0.36)
    dist2 = nx * nx + ny * ny

    # Overhead volumetric spotlight cone + radial focal bloom
    radial = np.exp(-dist2 * 1.45)
    cone_x = np.abs(xx - width * 0.5) / (width * 0.16 + yy * 0.34)
    cone = np.clip(1.0 - cone_x * cone_x, 0.0, 1.0) * np.exp(-((yy / height) * 0.9))

    base = np.zeros((height, width, 3), dtype=np.float32)
    bg = np.array(palette.bg_dark, dtype=np.float32)
    if ocean_gradient:
        depth_t = np.clip(yy / height, 0.0, 1.0)
        top_c = np.array([12.0, 34.0, 62.0], dtype=np.float32)
        bot_c = np.array([4.0, 9.0, 18.0], dtype=np.float32)
        base[:] = top_c[None, None, :] * (1.0 - depth_t[:, :, None]) + bot_c[None, None, :] * depth_t[:, :, None]
    else:
        base[:] = bg[None, None, :]

    accent = np.array(spot_color or palette.cyan, dtype=np.float32)
    mid_blue = np.array([22.0, 44.0, 78.0], dtype=np.float32)
    base += mid_blue[None, None, :] * (radial[:, :, None] * 0.65 + cone[:, :, None] * 0.30)
    base += accent[None, None, :] * (radial[:, :, None] * 0.13 + cone[:, :, None] * 0.07)

    # Subtle edge vignette for contrast around HUD and captions
    vx = (xx - width * 0.5) / (width * 0.62)
    vy = (yy - height * 0.5) / (height * 0.58)
    vig = np.clip(1.0 - 0.38 * (vx * vx + vy * vy), 0.52, 1.0)
    base *= vig[:, :, None]

    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # Subtle 30-deg isometric CAD blueprint lines + fine crosshair ticks
    grid_rgba = (*palette.bg_grid, 85)
    for x in range(-height, width + height, grid_step):
        draw.line([(x, 0), (x + int(height * 1.732), height)], fill=grid_rgba, width=1)
        draw.line([(x, 0), (x - int(height * 1.732), height)], fill=grid_rgba, width=1)

    # Clean technical border reticle lines (outside caption/hook areas)
    frame_rgba = (*palette.steel_mid, 55)
    draw.rectangle([28, 28, width - 28, height - 28], outline=frame_rgba, width=2)
    for cx_m, cy_m in ((48, 48), (width - 48, 48), (48, height - 48), (width - 48, height - 48)):
        draw.line([(cx_m - 12, cy_m), (cx_m + 12, cy_m)], fill=(*palette.cyan, 110), width=2)
        draw.line([(cx_m, cy_m - 12), (cx_m, cy_m + 12)], fill=(*palette.cyan, 110), width=2)

    return img
