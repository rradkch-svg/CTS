"""Procedural PBR-style studio material textures (cached once for fast cv2.warpPerspective)."""

from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np


def _panel_ao_mask(h: int, w: int, border: float = 0.10) -> np.ndarray:
    """Soft ambient-occlusion edge darkening + subtle machined panel bevel highlight."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = xx / max(1, w - 1)
    v = yy / max(1, h - 1)
    edge = np.minimum(np.minimum(u, 1.0 - u), np.minimum(v, 1.0 - v))
    ao = 0.84 + 0.16 * np.clip(edge / border, 0.0, 1.0)
    sheen = 1.06 - 0.14 * (0.55 * u + 0.45 * v)
    return (ao * sheen).astype(np.float32)


@lru_cache(maxsize=32)
def get_material_texture(kind: str, size: int = 256) -> np.ndarray:
    """Return a seamless studio PBR albedo/sheen texture (H x W x 3, float32 in [0, 1.3])."""
    rng = np.random.default_rng(abs(hash(kind)) % (2**32))
    h = w = size
    ao = _panel_ao_mask(h, w)

    if kind == "concrete":
        # Porous architectural reinforced concrete (matte mineral aggregate + subtle form lines, zero metallic rivets!)
        coarse = rng.normal(1.0, 0.075, (h // 4, w // 4)).astype(np.float32)
        coarse = cv2.resize(coarse, (w, h), interpolation=cv2.INTER_LINEAR)
        fine = rng.normal(1.0, 0.055, (h, w)).astype(np.float32)
        fine = cv2.GaussianBlur(fine, (3, 3), 0)
        tex = np.clip((0.62 * coarse + 0.38 * fine) * (0.90 + 0.10 * ao), 0.58, 1.18)
        # Subtle formwork seam lines
        for gy in (h // 3, (2 * h) // 3):
            tex[max(0, gy - 1) : min(h, gy + 1), :] *= 0.88
        return np.stack([tex * 0.99, tex, tex * 1.01], axis=2).astype(np.float32)

    if kind == "matte":
        # Clean satin-matte polymer / resin / fabric (zero rivets, soft AO)
        grain = rng.normal(1.0, 0.025, (h // 2, w // 2)).astype(np.float32)
        grain = cv2.resize(grain, (w, h), interpolation=cv2.INTER_LINEAR)
        tex = np.clip(grain * ao, 0.65, 1.15)
        return np.stack([tex, tex, tex], axis=2).astype(np.float32)

    if kind == "painted_metal":
        # Smooth automotive / aerospace gloss clearcoat paint (zero rivets)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        diag = np.exp(-(((xx / w + yy / h) - 0.85) ** 2) / 0.07) * 0.18
        tex = np.clip((1.0 + diag) * ao, 0.55, 1.25)
        return np.stack([tex, tex, tex], axis=2).astype(np.float32)

    if kind == "brushed_steel":
        # Clean fine anisotropic brushed metal grain + soft specular band (NO distorted black corner dots!)
        streaks = rng.normal(1.0, 0.038, (h, w // 8)).astype(np.float32)
        streaks = cv2.resize(streaks, (w, h), interpolation=cv2.INTER_LINEAR)
        streaks = cv2.GaussianBlur(streaks, (15, 3), 0)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        diag = np.exp(-(((xx / w + yy / h) - 0.85) ** 2) / 0.06) * 0.20
        tex = np.clip((streaks + diag) * ao, 0.48, 1.28)
        return np.stack([tex, tex * 1.01, tex * 1.02], axis=2).astype(np.float32)

    if kind == "carbon_weave":
        # Fine realistic 2x2 twill carbon-fiber weave pattern (cell=8, crisp aerospace look)
        yy, xx = np.mgrid[0:h, 0:w]
        cell = 8
        phase = ((xx // cell) + (yy // cell)) % 2
        fx = (xx % cell) / float(cell)
        fy = (yy % cell) / float(cell)
        weave_h = 0.78 + 0.28 * np.sin(fx * np.pi) * (0.88 + 0.12 * np.sin(fy * np.pi))
        weave_v = 0.68 + 0.26 * np.sin(fy * np.pi) * (0.88 + 0.12 * np.sin(fx * np.pi))
        pat = np.where(phase == 0, weave_h, weave_v).astype(np.float32) * ao
        return np.stack([pat * 1.03, pat, pat * 0.97], axis=2).astype(np.float32)

    if kind == "machined_brass":
        # Clean vertical/diagonal anisotropic brushed CNC-milled brass/gold metal sheen (zero distorted corner dots!)
        streaks = rng.normal(1.0, 0.035, (h // 8, w)).astype(np.float32)
        streaks = cv2.resize(streaks, (w, h), interpolation=cv2.INTER_LINEAR)
        streaks = cv2.GaussianBlur(streaks, (3, 15), 0)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        diag = np.exp(-(((xx / w + yy / h) - 0.90) ** 2) / 0.05) * 0.24
        tex = np.clip((streaks + diag) * ao, 0.50, 1.30)
        return np.stack([tex * 0.90, tex * 1.01, tex * 1.06], axis=2).astype(np.float32)

    if kind == "hazard_plate":
        tex = get_material_texture("brushed_steel", size).copy()
        yy, xx = np.mgrid[0:h, 0:w]
        stripe_band = yy > int(h * 0.78)
        diag_stripe = ((xx + yy) // 22) % 2 == 0
        mask = stripe_band & diag_stripe
        tex[mask] = np.array([0.22, 0.22, 0.24], dtype=np.float32)
        return tex

    if kind == "cabin_wall":
        tex = get_material_texture("brushed_steel", size).copy()
        for gx in (int(w * 0.33), int(w * 0.67)):
            tex[:, max(0, gx - 2) : min(w, gx + 2)] *= 0.65
            tex[:, min(w - 1, gx + 2) : min(w, gx + 4)] *= 1.15
        return tex

    return np.stack([ao, ao, ao], axis=2).astype(np.float32)
