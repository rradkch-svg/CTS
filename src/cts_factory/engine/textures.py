"""Procedural PBR-style studio material textures (cached once for fast cv2.warpPerspective)."""

from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np


def _panel_ao_mask(h: int, w: int, border: float = 0.12) -> np.ndarray:
    """Soft ambient-occlusion edge darkening + subtle machined panel bevel highlight."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = xx / max(1, w - 1)
    v = yy / max(1, h - 1)
    edge = np.minimum(np.minimum(u, 1.0 - u), np.minimum(v, 1.0 - v))
    ao = 0.78 + 0.22 * np.clip(edge / border, 0.0, 1.0)
    # Subtle top-left metallic sheen gradient
    sheen = 1.08 - 0.18 * (0.55 * u + 0.45 * v)
    return (ao * sheen).astype(np.float32)


@lru_cache(maxsize=24)
def get_material_texture(kind: str, size: int = 256) -> np.ndarray:
    """Return a seamless studio PBR albedo/sheen texture (H x W x 3, float32 in [0, 1.3])."""
    rng = np.random.default_rng(abs(hash(kind)) % (2**32))
    h = w = size
    ao = _panel_ao_mask(h, w)

    if kind == "brushed_steel":
        # Fine anisotropic horizontal brushed metal grain + subtle diagonal specular band
        streaks = rng.normal(1.0, 0.045, (h, w // 8)).astype(np.float32)
        streaks = cv2.resize(streaks, (w, h), interpolation=cv2.INTER_LINEAR)
        streaks = cv2.GaussianBlur(streaks, (15, 3), 0)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        diag = np.exp(-(((xx / w + yy / h) - 0.85) ** 2) / 0.06) * 0.22
        tex = np.clip((streaks + diag) * ao, 0.4, 1.35)
        out = np.stack([tex, tex * 1.01, tex * 1.03], axis=2)  # Slight cool steel tint (BGR)
        # Subtle corner hex rivets
        for ry, rx in ((16, 16), (16, w - 16), (h - 16, 16), (h - 16, w - 16)):
            cv2.circle(out, (rx, ry), 4, (0.52, 0.50, 0.48), -1, lineType=cv2.LINE_AA)
            cv2.circle(out, (rx - 1, ry - 1), 2, (1.15, 1.12, 1.10), -1, lineType=cv2.LINE_AA)
        return out.astype(np.float32)

    if kind == "carbon_weave":
        # Realistic 2x2 twill carbon-fiber weave pattern!
        yy, xx = np.mgrid[0:h, 0:w]
        cell = 16
        phase = ((xx // cell) + (yy // cell)) % 2
        fx = (xx % cell) / float(cell)
        fy = (yy % cell) / float(cell)
        weave_h = 0.72 + 0.36 * np.sin(fx * np.pi) * (0.85 + 0.15 * np.sin(fy * np.pi))
        weave_v = 0.62 + 0.34 * np.sin(fy * np.pi) * (0.85 + 0.15 * np.sin(fx * np.pi))
        pat = np.where(phase == 0, weave_h, weave_v).astype(np.float32) * ao
        return np.stack([pat * 1.04, pat, pat * 0.96], axis=2).astype(np.float32)

    if kind == "machined_brass":
        # Radial/linear turned metallic brass sheen
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot((xx - w * 0.5) / w, (yy - h * 0.5) / h)
        rings = 0.94 + 0.08 * np.sin(r * 95.0)
        diag = np.exp(-(((xx / w - yy / h) + 0.15) ** 2) / 0.08) * 0.25
        tex = np.clip((rings + diag) * ao, 0.45, 1.35)
        return np.stack([tex * 0.92, tex * 1.02, tex * 1.06], axis=2).astype(np.float32)

    if kind == "hazard_plate":
        # Brushed steel with crisp recessed industrial caution stripe along bottom edge
        tex = get_material_texture("brushed_steel", size).copy()
        yy, xx = np.mgrid[0:h, 0:w]
        stripe_band = yy > int(h * 0.78)
        diag_stripe = ((xx + yy) // 22) % 2 == 0
        mask = stripe_band & diag_stripe
        tex[mask] = np.array([0.22, 0.22, 0.24], dtype=np.float32)
        return tex

    if kind == "cabin_wall":
        # Architectural ribbed dark titanium interior elevator wall
        tex = get_material_texture("brushed_steel", size).copy()
        for gx in (int(w * 0.33), int(w * 0.67)):
            tex[:, max(0, gx - 2) : min(w, gx + 2)] *= 0.58
            tex[:, min(w - 1, gx + 2) : min(w, gx + 4)] *= 1.18
        return tex

    # Default smooth studio anodized metal with soft bevel AO
    return np.stack([ao, ao, ao], axis=2).astype(np.float32)
