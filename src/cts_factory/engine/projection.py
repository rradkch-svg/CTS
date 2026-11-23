"""2.5D orthographic/isometric projection, 5 canonical camera presets, and easing math."""

from __future__ import annotations

import math
from dataclasses import dataclass

ISO_COS = math.cos(math.radians(30.0))  # ~0.8660
ISO_SIN = math.sin(math.radians(30.0))  # 0.5000


def clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if val < lo else (hi if val > hi else val)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_out_cubic(t: float) -> float:
    t = clamp(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = clamp(t)
    return 4.0 * t * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def ease_out_back(t: float) -> float:
    t = clamp(t)
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * ((t - 1.0) ** 3) + c1 * ((t - 1.0) ** 2)


@dataclass(frozen=True)
class CameraState:
    """2.5D viewport parameters for a canonical camera preset."""

    cx: float
    cy: float
    scale: float
    pitch: float = 0.50
    shake_amp: float = 0.0


CAMERA_PRESETS: dict[str, CameraState] = {
    "FRAME0_HERO": CameraState(cx=540.0, cy=975.0, scale=1.24, pitch=0.48, shake_amp=6.0),
    "ISO_WIDE": CameraState(cx=540.0, cy=990.0, scale=1.00, pitch=0.50, shake_amp=1.5),
    "MACRO_CUTAWAY": CameraState(cx=540.0, cy=990.0, scale=1.35, pitch=0.45, shake_amp=3.0),
    "EXPLODED_BLUEPRINT": CameraState(cx=540.0, cy=985.0, scale=1.12, pitch=0.52, shake_amp=1.0),
    "IMPACT_CLOSEUP": CameraState(cx=540.0, cy=985.0, scale=1.45, pitch=0.44, shake_amp=10.0),
}


def get_camera(preset: str, t: float, rms: float = 0.0, impact: float = 0.0) -> CameraState:
    """Return subtle breathing + impact-coupled camera state for a preset."""
    base = CAMERA_PRESETS.get(preset, CAMERA_PRESETS["ISO_WIDE"])
    breathe_x = math.sin(t * 0.85) * 4.5
    breathe_y = math.cos(t * 0.65) * 3.5
    shake = (base.shake_amp * max(impact, rms * 0.25)) if (impact > 0.01 or rms > 0.35) else 0.0
    sx = math.sin(t * 67.0) * shake
    sy = math.cos(t * 83.0) * shake
    return CameraState(
        cx=base.cx + breathe_x + sx,
        cy=base.cy + breathe_y + sy,
        scale=base.scale * (1.0 + 0.012 * math.sin(t * 0.7)),
        pitch=base.pitch,
        shake_amp=base.shake_amp,
    )


def project_iso(
    x: float,
    y: float,
    z: float,
    cam: CameraState,
) -> tuple[float, float]:
    """Project 3D right-handed CAD coords (x=right-down, y=left-down, z=up) to 2D pixels."""
    px = cam.cx + (x - y) * ISO_COS * cam.scale
    py = cam.cy + ((x + y) * cam.pitch - z) * cam.scale
    return (px, py)
