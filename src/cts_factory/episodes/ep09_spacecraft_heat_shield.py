"""Episode 09: How a 3-Inch Shield Survives 5,000°F Reentry — Upgraded True 3D Space Capsule, Open Cutaway Cabin, Concave Parachutes & Ocean Splashdown."""

from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette, build_stage_background, lerp_color
from cts_factory.engine.primitives import (
    draw_comparison_bars,
    draw_cta_buttons,
    draw_pressure_gauge,
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D, rot_matrix
from cts_factory.episodes.base import EpisodeScene, register_scene

HULL_WHITE = (224, 232, 242)
HULL_DARK = (42, 50, 64)
TITANIUM_LIGHT = (192, 208, 228)
CAPSULE_YELLOW = (255, 206, 36)
CAPSULE_NAVY = (24, 38, 60)
SHIELD_RESIN = (188, 128, 66)
SHIELD_CHAR = (38, 34, 38)
PLASMA_HOT = (255, 118, 26)
PLASMA_WHITE = (255, 236, 178)
CHUTE_ORANGE = (246, 104, 34)
GLASS_BLUE = (42, 168, 224)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


def _build_orbit_backdrop_bgr(w: int, h: int) -> np.ndarray:
    """Deep starry orbit + realistic wide planetary Earth horizon curvature at bottom (BGR)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    img = np.zeros((h, w, 3), dtype=np.float32)

    img[:, :, 2] = 5.0 + 8.0 * ys
    img[:, :, 1] = 9.0 + 16.0 * ys
    img[:, :, 0] = 20.0 + 30.0 * ys

    # Wide gentle planetary radius (feels like real LEO orbit, not a small floating ball!)
    r_earth = np.sqrt((xs * 0.55) ** 2 + ((ys - 2.35) * 1.45) ** 2)
    limb = np.exp(-((r_earth - 2.08) / 0.055) ** 2)
    earth_body = (r_earth < 2.06).astype(np.float32)
    img[:, :, 2] += 36.0 * limb + 14.0 * earth_body
    img[:, :, 1] += 136.0 * limb + 62.0 * earth_body
    img[:, :, 0] += 225.0 * limb + 142.0 * earth_body
    bgr = np.clip(img, 0, 255).astype(np.uint8)

    rng = np.random.default_rng(909)
    for _ in range(75):
        sx = int(rng.integers(24, w - 24))
        sy = int(rng.integers(140, int(h * 0.65)))
        # Keep stars clear of top hook text center (y=260..460)
        if 250 < sy < 470 and 180 < sx < 900:
            continue
        sr = int(rng.choice([1, 1, 2]))
        bright = int(rng.integers(155, 240))
        cv2.circle(bgr, (sx, sy), sr, (bright, bright, min(255, bright + 10)), -1, lineType=cv2.LINE_AA)
    return bgr


def _build_daylight_ocean_backdrop_bgr(w: int, h: int, waterline_y: int = 1140) -> np.ndarray:
    """Clean sunlit coastal sky + soft atmospheric mist horizon + deep turquoise ocean (NO daytime stars!)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    wl = waterline_y / float(h)

    below = 1.0 / (1.0 + np.exp(-(ys - wl) * 32.0))
    above = 1.0 - below

    sky_t = np.clip(ys / max(0.01, wl), 0.0, 1.0)
    sky_r = 18.0 + 62.0 * (sky_t ** 1.9) + 46.0 * (sky_t ** 4.5)
    sky_g = 46.0 + 114.0 * (sky_t ** 1.5) + 34.0 * (sky_t ** 4.0)
    sky_b = 98.0 + 112.0 * (sky_t ** 1.2) + 18.0 * (sky_t ** 3.6)

    sun = np.exp(-((xs / 0.58) ** 2 + ((ys - wl * 0.90) / 0.16) ** 2))
    sky_r = sky_r + 52.0 * sun
    sky_g = sky_g + 44.0 * sun
    sky_b = sky_b + 24.0 * sun

    sea_t = np.clip((ys - wl) / max(0.01, 1.0 - wl), 0.0, 1.0)
    sea_r = 24.0 * (1.0 - sea_t * 0.72) + 6.0 * sea_t
    sea_g = 118.0 * ((1.0 - sea_t) ** 1.3) + 20.0 * sea_t
    sea_b = 162.0 * ((1.0 - sea_t) ** 1.1) + 46.0 * sea_t

    img = np.zeros((h, w, 3), dtype=np.float32)
    img[:, :, 2] = sky_r * above + sea_r * below
    img[:, :, 1] = sky_g * above + sea_g * below
    img[:, :, 0] = sky_b * above + sea_b * below
    bgr = np.clip(img, 0, 255).astype(np.uint8)

    # Subtle sunlit ocean shimmer bands
    rng = np.random.default_rng(915)
    shimmer = np.zeros_like(bgr)
    for _ in range(28):
        sx = int(rng.integers(60, w - 60))
        sy = int(rng.integers(waterline_y + 18, h - 180))
        sw = int(rng.integers(36, 130))
        cv2.line(shimmer, (sx - sw, sy), (sx + sw, sy), (160, 145, 95), 2, lineType=cv2.LINE_AA)
    shimmer = cv2.GaussianBlur(shimmer, (19, 5), 0)
    return cv2.addWeighted(bgr, 1.0, shimmer, 0.28, 0)


@register_scene("ep09_spacecraft_heat_shield")
class SpacecraftHeatShieldScene(EpisodeScene):
    """Articulated 12-beat True 3D Spacecraft Reentry, Detached Bow Shock & Triple-Chute Splashdown."""

    slug = "ep09_spacecraft_heat_shield"
    episode_id = "ep09"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_orbit_bgr: np.ndarray | None = None
        self.bg_studio_bgr: np.ndarray | None = None
        self.bg_alert_bgr: np.ndarray | None = None
        self.bg_ocean_bgr: np.ndarray | None = None
        self.font_bold: str = ""
        self.font_black: str = ""
        self.beat_map: dict[str, tuple[str, str]] = {}

    def prepare(
        self,
        brand: BrandConfig,
        script: EpisodeScript,
        timeline: AudioTimeline | None = None,
    ) -> None:
        self.brand = brand
        self.script = script
        self.palette = Palette.from_brand(brand)
        w, h = brand.video_spec.width, brand.video_spec.height
        self.bg_orbit_bgr = _build_orbit_backdrop_bgr(w, h)
        self.bg_studio_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.cyan)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_alert_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.amber)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_ocean_bgr = _build_daylight_ocean_backdrop_bgr(w, h, waterline_y=1140)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_space_capsule(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        t: float = 0.0,
        plasma: float = 0.0,
        bow_shock_gap: float = 0.0,
        charred: float = 0.0,
        cutaway_cabin: bool = False,
        open_hatch: bool = False,
        flotation_collar: bool = False,
        hide_bottom_submerged: bool = False,
    ) -> None:
        """Detailed 3D Reentry Capsule with smooth bow-shock arc, true 180-deg cabin cutaway & open hatch."""
        R = rot_matrix(roll, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Blunt curved 3-inch ablative heat shield base (-Y) — hidden if submerged during ocean splashdown
        if not hide_bottom_submerged:
            shield_col = lerp_color(SHIELD_RESIN, SHIELD_CHAR, clamp(charred, 0.0, 1.0))
            if plasma > 0.2:
                shield_col = lerp_color(shield_col, PLASMA_HOT, plasma * 0.35)
            sc.add_cylinder(_p(0.0, -0.78, 0.0), _p(0.0, -0.52, 0.0), 1.06 * scale, 1.24 * scale, shield_col, segments=24, metallic=0.20, emissive=0.22 * plasma)
            sc.add_sphere(_p(0.0, -0.78, 0.0), 1.05 * scale, shield_col, metallic=0.20, squash_y=0.28, emissive=0.25 * plasma)

        # Smooth continuous inflatable yellow flotation ring (overlapping torus spheres, zero notched gaps!)
        if flotation_collar:
            for i in range(24):
                a0 = i * (2.0 * math.pi / 24)
                sc.add_sphere(_p(math.cos(a0) * 1.28, -0.44, math.sin(a0) * 1.28), 0.21 * scale, CAPSULE_YELLOW, metallic=0.22)

        # Main conical pressurized crew module hull
        if not cutaway_cabin:
            sc.add_cylinder(_p(0.0, -0.52, 0.0), _p(0.0, 0.72, 0.0), 1.22 * scale, 0.62 * scale, HULL_WHITE, segments=26, metallic=0.38)
            sc.add_cylinder(_p(0.0, -0.18, 0.0), _p(0.0, -0.02, 0.0), 1.09 * scale, 1.01 * scale, CAPSULE_YELLOW, segments=26, metallic=0.45, caps=False)
            sc.add_cylinder(_p(0.0, -0.26, 0.0), _p(0.0, -0.18, 0.0), 1.13 * scale, 1.09 * scale, CAPSULE_NAVY, segments=26, metallic=0.42, caps=False)
            # Cleanly proud camera-facing circular sapphire crew window (+Z) so hull never clips it!
            sc.add_cylinder(_p(0.0, 0.22, 0.84), _p(0.0, 0.22, 0.96), 0.26 * scale, 0.24 * scale, TITANIUM_LIGHT, segments=16, metallic=0.80)
            sc.add_sphere(_p(0.0, 0.22, 0.94), 0.20 * scale, GLASS_BLUE, metallic=0.75, emissive=0.28, rim_rgb=CYAN)
        else:
            # TRUE 180° BACK-WALL CUTAWAY (only back half z <= 0 rendered, front 100% OPEN so BOLT is crystal clear!)
            angs = np.linspace(math.pi, 2.0 * math.pi, 14)
            for i in range(len(angs) - 1):
                a0, a1 = float(angs[i]), float(angs[i + 1])
                q = np.array(
                    [
                        _p(math.cos(a0) * 1.20, -0.50, math.sin(a0) * 1.20),
                        _p(math.cos(a1) * 1.20, -0.50, math.sin(a1) * 1.20),
                        _p(math.cos(a1) * 0.62, 0.72, math.sin(a1) * 0.62),
                        _p(math.cos(a0) * 0.62, 0.72, math.sin(a0) * 0.62),
                    ],
                    dtype=np.float32,
                )
                sc.add_quad(q, rgb=(48, 62, 86), metallic=0.35, double_sided=True)
            # Cool emerald-rimmed 72°F insulated cabin floor + seat backrest inside
            sc.add_cylinder(_p(0.0, -0.46, 0.0), _p(0.0, -0.36, 0.0), 1.06 * scale, 1.06 * scale, EMERALD, segments=20, emissive=0.32)
            sc.add_box(_p(0.0, 0.05, -0.38), (0.62 * scale, 0.72 * scale, 0.14 * scale), CAPSULE_NAVY, metallic=0.35, texture="matte")

        # Top titanium docking ring (hollow open hatch rim if open_hatch=True so BOLT emerges naturally!)
        sc.add_cylinder(_p(0.0, 0.72, 0.0), _p(0.0, 1.00, 0.0), 0.62 * scale, 0.54 * scale, HULL_DARK, segments=22, metallic=0.68, caps=not open_hatch)
        sc.add_cylinder(_p(0.0, 0.96, 0.0), _p(0.0, 1.08, 0.0), 0.58 * scale, 0.58 * scale, TITANIUM_LIGHT, segments=22, metallic=0.82, caps=not open_hatch)
        if open_hatch:
            sc.add_cylinder(_p(0.0, 1.04, 0.0), _p(0.0, 1.09, 0.0), 0.46 * scale, 0.46 * scale, (12, 18, 28), segments=18, metallic=0.10)

        for sx in (-1, 1):
            sc.add_box(_p(sx * 0.98, -0.12, 0.0), (0.18 * scale, 0.26 * scale, 0.18 * scale), HULL_DARK, rot=(roll, yaw, pitch), metallic=0.70, texture="painted_metal")

        # SMOOTH CONTINUOUS DETACHED BOW SHOCK ARC (connected parabolic plasma tube, NOT pearl necklace or floating cones!)
        if plasma > 0.05:
            gap = 0.26 + bow_shock_gap * 0.34
            pts_shock = []
            for i in range(15):
                u = (i / 14.0) * 2.0 - 1.0
                sx = u * 1.62
                sy = -0.96 - gap + (u * u) * 0.88
                pts_shock.append(_p(sx, sy, 0.08))
            for i in range(len(pts_shock) - 1):
                u_mid = abs(((i + 0.5) / 14.0) * 2.0 - 1.0)
                col_outer = lerp_color(PLASMA_HOT, DANGER, clamp(u_mid * 0.9, 0.0, 1.0))
                r_out = (0.12 - u_mid * 0.045) * scale
                sc.add_cylinder(pts_shock[i], pts_shock[i + 1], r_out, r_out * 0.96, col_outer, segments=8, emissive=0.78 * plasma, bloom=True, caps=False)
                if u_mid < 0.45:
                    sc.add_cylinder(pts_shock[i], pts_shock[i + 1], r_out * 0.45, r_out * 0.45, PLASMA_WHITE, segments=6, emissive=0.88 * plasma, caps=False)
            # Continuous sweeping plasma wake ribbons curling smoothly up past the capsule flanks
            for side in (-1, 1):
                w_pts = []
                for k in range(7):
                    kt = k / 6.0
                    px = side * (1.56 + kt * 0.32 + math.sin(t * 7.0 + kt * 4.0) * 0.04)
                    py = -0.14 - gap * 0.4 + kt * 1.95
                    w_pts.append(_p(px, py, -0.05))
                for k in range(len(w_pts) - 1):
                    col_w = lerp_color(PLASMA_HOT, DANGER, k / 6.0)
                    r_w = (0.068 * (1.0 - k / 7.5)) * scale
                    sc.add_cylinder(w_pts[k], w_pts[k + 1], r_w, r_w * 0.82, col_w, segments=6, emissive=0.72 * plasma, bloom=True, caps=False)

        # Clean smooth cyan dead-air buffer ribbon tucked in the standoff gap
        if bow_shock_gap > 0.35:
            b_pts = [_p((j / 6.0 * 2.0 - 1.0) * 0.95, -1.00 + ((j / 6.0 * 2.0 - 1.0) ** 2) * 0.16, 0.14) for j in range(7)]
            for q0, q1 in zip(b_pts[:-1], b_pts[1:]):
                sc.add_cylinder(q0, q1, 0.045 * scale, 0.045 * scale, CYAN, segments=6, emissive=0.68, bloom=True, caps=False)

    def _add_3d_parachutes(
        self,
        sc: Scene3D,
        capsule_top: tuple[float, float, float],
        bloom_p: float,
        t: float,
    ) -> None:
        """Three true CONCAVE OPEN-SKIRT 3D striped main parachutes with shroud lines tied to rim."""
        cx, cy, cz = capsule_top
        open_s = max(0.18, ease_out_cubic(bloom_p))
        offsets = [(-1.32, 2.35, -0.22), (0.0, 2.68, 0.18), (1.32, 2.35, -0.22)]
        for idx, (ox, oy, oz) in enumerate(offsets):
            sway = math.sin(t * 2.4 + idx * 1.4) * 0.07
            px = cx + ox * open_s + sway
            py = cy + oy * (0.45 + 0.55 * open_s)
            pz = cz + oz * open_s
            rad = 0.80 * open_s

            # True open-bottom hollow hemispherical canopy made of 3 lofted curved bands (NO solid ball!)
            # Dark concave interior cavity visible from underneath!
            sc.add_cylinder((px, py - rad * 0.08, pz), (px, py + rad * 0.02, pz), rad * 0.94, rad * 0.84, (44, 34, 32), segments=16, metallic=0.05, caps=True)
            # Outer alternating orange & white curved fabric gore rings (lower skirt -> mid band -> crown)
            sc.add_cylinder((px, py - rad * 0.10, pz), (px, py + rad * 0.22, pz), rad * 0.98, rad * 0.88, CHUTE_ORANGE, segments=16, metallic=0.10, caps=False)
            sc.add_cylinder((px, py + rad * 0.22, pz), (px, py + rad * 0.46, pz), rad * 0.88, rad * 0.58, HULL_WHITE, segments=16, metallic=0.10, caps=False)
            sc.add_cylinder((px, py + rad * 0.46, pz), (px, py + rad * 0.62, pz), rad * 0.58, rad * 0.18, CHUTE_ORANGE, segments=16, metallic=0.10, caps=True)
            # 6 crisp shroud cords anchored cleanly to the open bottom skirt rim!
            for a_idx in range(6):
                ang = a_idx * (2.0 * math.pi / 6.0) + 0.25
                rx = px + math.cos(ang) * rad * 0.95
                rz = pz + math.sin(ang) * rad * 0.95
                sc.add_cylinder((cx, cy, cz), (rx, py - rad * 0.08, rz), 0.015, 0.012, TITANIUM_LIGHT, segments=5, metallic=0.45)

    def _add_splashdown_water_surface(self, sc: Scene3D, t: float, center_y: float = -0.62) -> None:
        """3D translucent ocean wave plane + white splashdown foam ring wrapping the capsule base."""
        # Translucent foreground turquoise ocean water sheet wrapping around the capsule
        q_sea = np.array(
            [
                [-4.5, center_y, 2.2],
                [4.5, center_y, 2.2],
                [4.5, center_y, -2.5],
                [-4.5, center_y, -2.5],
            ],
            dtype=np.float32,
        )
        sc.add_quad(q_sea, rgb=(24, 132, 186), metallic=0.22, double_sided=True, alpha=0.68)
        # Animated white ocean foam collar & gentle splash droplets right where capsule meets water!
        for i in range(18):
            a = i * (2.0 * math.pi / 18.0) + t * 0.35
            wob = 0.06 * math.sin(t * 4.5 + i * 1.2)
            fx = math.cos(a) * (1.42 + wob)
            fz = math.sin(a) * (1.42 + wob)
            sc.add_sphere((fx, center_y + 0.03, fz), 0.13, (232, 246, 255), metallic=0.05)

    def _render_scene_3d(
        self,
        scene_key: str,
        t: float,
        prog: float,
        rms: float,
        is_cover: bool = False,
    ) -> tuple[np.ndarray, list]:
        assert self.brand is not None and self.palette is not None
        p = self.palette
        w, h = self.brand.video_spec.width, self.brand.video_spec.height
        overlays_2d: list = []

        bg = self.bg_orbit_bgr
        if scene_key in ("sharp_vs_blunt_nose", "ablative_layers_cutaway", "temp_gradient_bars"):
            bg = self.bg_studio_bgr
        elif scene_key in ("triple_chute_descent", "bolt_ocean_splashdown", "verdict_cta_card"):
            bg = self.bg_ocean_bgr
        assert bg is not None

        cam = Camera3D(eye=(0.0, 0.4, 7.2), target=(0.0, -0.05, 0.0), fov_deg=41.0, width=w, height=h)
        sc = Scene3D(cam)

        if scene_key == "capsule_plasma_hero":
            shake = math.sin(t * 48.0) * 0.07 if not is_cover else 0.0
            cam.eye = (0.42 + shake, 0.35, 7.6 if is_cover else 6.6)
            cam.target = (0.0, 0.34 if is_cover else -0.15, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, -0.08 if is_cover else 0.05, 0.0), scale=0.94 if is_cover else 1.08, yaw=0.14, pitch=-0.22, t=t, plasma=1.0, bow_shock_gap=0.4, charred=0.6)
            if not is_cover:
                overlays_2d.append(lambda d: draw_sparks(d, 540, 1140, prog, 14, 155, 130, p, seed=901))

        elif scene_key == "bolt_capsule_wave":
            # Narrator: "Buckle up, Bolt — wave goodbye to space!" -> BOLT waves cleanly from OPEN top hatch (no plasma yet!)
            cam.eye = (0.0, 0.58, 7.1)
            cam.target = (0.0, 0.18, 0.0)
            bob = math.sin(t * 2.6) * 0.05
            self._add_3d_space_capsule(sc, center=(0.0, -0.62 + bob, 0.0), scale=1.06, yaw=0.10, pitch=-0.04, t=t, plasma=0.0, open_hatch=True)
            add_crash_test_dummy(
                sc,
                pos=(0.0, 0.44 + bob, 0.02),
                scale=0.66,
                yaw=0.04 + math.sin(t * 2.2) * 0.10,
                pose="relief_wave",
                emotion="cta",
                t=t,
                ground_shadow=False,
                show_legs=False,
            )

        elif scene_key == "air_compression_shock":
            cam.eye = (0.0, 0.25, 6.8)
            cam.target = (0.0, -0.25, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.45, 0.0), scale=1.02, yaw=0.08, pitch=0.0, t=t, plasma=0.85, bow_shock_gap=0.25)
            # Turbulent organically scattered air molecules compressing and heating under the blunt belly!
            for i in range(16):
                ph = (t * 2.1 + i * 0.067) % 1.0
                spread = 1.0 + ph * 0.45
                mx = math.sin(i * 2.7 + ph * 1.4) * 1.25 * spread
                my = -2.35 + (ph ** 0.72) * 1.42
                mz = math.cos(i * 1.9) * 0.28 + 0.15
                col = lerp_color(CYAN, PLASMA_HOT, clamp((ph - 0.42) * 2.2, 0.0, 1.0))
                sc.add_sphere((mx, my, mz), 0.085, col, emissive=0.55 + ph * 0.30, bloom=ph > 0.5)

        elif scene_key == "sharp_vs_blunt_nose":
            # Wider camera so BOTH nose cones + plasma stay strictly inside frame, labels cleanly at y=1185 (ZERO badge collision!)
            cam.eye = (0.0, 0.32, 8.2)
            cam.target = (0.0, -0.08, 0.0)
            # LEFT: Sharp needle nose cone melting inside attached red shockwave
            sc.add_cylinder((-1.42, 0.68, 0.0), (-1.42, -0.92, 0.0), 0.68, 0.04, TITANIUM_LIGHT, segments=20, metallic=0.78)
            sc.add_sphere((-1.42, -0.88, 0.0), 0.26, DANGER, emissive=0.82, bloom=True)
            for s in (-1, 1):
                sc.add_cylinder((-1.42, -0.98, 0.05), (-1.42 + s * 0.84, 0.55, 0.05), 0.04, 0.032, DANGER, segments=6, emissive=0.75, bloom=True)
            # RIGHT: Blunt capsule deflecting detached bow shock safely away
            self._add_3d_space_capsule(sc, center=(1.32, 0.18, 0.0), scale=0.72, yaw=0.0, pitch=0.0, t=t, plasma=0.92, bow_shock_gap=0.85)
            overlays_2d.append(lambda d: draw_sparks(d, 315, 1065, prog, 14, 130, 115, p, seed=904))

            def _vs_tags(d: ImageDraw.ImageDraw) -> None:
                f_b = load_font(self.font_black, 26)
                # Placed cleanly BELOW both 3D shapes and strictly inside x <= 855!
                d.rounded_rectangle([78, 1205, 428, 1268], radius=14, fill=p.surface_panel, outline=p.danger, width=3)
                d.text((104, 1220), "POINTY = MELTS", font=f_b, fill=p.danger)
                d.rounded_rectangle([462, 1205, 852, 1268], radius=14, fill=p.surface_panel, outline=p.emerald, width=3)
                d.text((484, 1220), "BLUNT = DEFLECTS", font=f_b, fill=p.emerald)

            overlays_2d.append(_vs_tags)

        elif scene_key == "detached_bow_shock":
            cam.eye = (0.0, 0.25, 6.8)
            cam.target = (0.0, -0.20, 0.0)
            self._add_3d_space_capsule(sc, center=(0.15, 0.35, 0.0), scale=1.02, yaw=0.06, pitch=0.0, t=t, plasma=1.0, bow_shock_gap=1.0)
            overlays_2d.append(
                lambda d: draw_pressure_gauge(d, 165, 1215, 84, 0.98, "DEFLECTED", "98% PUSHED", p, self.font_black, invert_scale=True)
            )

        elif scene_key == "bolt_bow_shock_gap":
            # Narrator: "Relax, Bolt — that curve traps a dead-air buffer ahead of you!"
            # TRUE OPEN FRONT CUTAWAY so BOLT is 100% VISIBLE chilling inside the cool 72°F cabin!
            cam.eye = (0.0, 0.28, 6.4)
            cam.target = (0.0, -0.15, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.22, 0.0), scale=1.18, yaw=0.0, pitch=0.0, t=t, plasma=0.92, bow_shock_gap=1.0, cutaway_cabin=True)
            add_crash_test_dummy(sc, pos=(0.0, 0.26, 0.22), scale=0.62, yaw=0.04, pose="explain", emotion="relief", t=t, ground_shadow=False)

        elif scene_key == "ablative_layers_cutaway":
            # Labeled 3-layer ablative honeycomb cutaway + BOLT cleanly clear of the blocks!
            cam.eye = (0.25, 0.45, 7.0)
            cam.target = (0.0, 0.0, 0.0)
            sep = 0.20 + 0.38 * ease_out_cubic(prog)
            # Top layer: Cool Titanium Cabin Floor
            sc.add_box((0.48, 0.92 + sep * 0.5, 0.0), (2.25, 0.24, 1.35), TITANIUM_LIGHT, metallic=0.80, texture="brushed_steel")
            # Mid layer: 3-inch Phenolic Resin Honeycomb Core (hexagonal cells!)
            sc.add_box((0.48, 0.18, 0.0), (2.25, 0.56, 1.35), SHIELD_RESIN, metallic=0.14, texture="matte")
            for hx in (-0.30, 0.18, 0.66, 1.14):
                for hy in (0.04, 0.32):
                    sc.add_cylinder((hx, hy, 0.66), (hx, hy, 0.72), 0.11, 0.11, AMBER, segments=6, metallic=0.25)
            # Bottom layer: Charring outer ablative layer
            sc.add_box((0.48, -0.66 - sep * 0.5, 0.0), (2.25, 0.28, 1.35), SHIELD_CHAR, metallic=0.10, texture="concrete")
            sc.add_box((0.48, -0.84 - sep * 0.5, 0.0), (2.18, 0.10, 1.28), PLASMA_HOT, emissive=0.72, bloom=True)
            add_crash_test_dummy(sc, pos=(-1.62, -0.35, 0.45), scale=0.76, yaw=0.38, pose="point_right", emotion="curious", t=t, ground_shadow=False)

            def _layer_labels(d: ImageDraw.ImageDraw) -> None:
                f_l = load_font(self.font_black, 22)
                for txt, ly, col in (
                    ("TITANIUM CABIN (72°F)", 730, p.cyan),
                    ("3-IN HONEYCOMB RESIN", 930, p.amber),
                    ("SACRIFICIAL CHAR LAYER", 1140, p.danger),
                ):
                    bb = d.textbbox((0, 0), txt, font=f_l)
                    tw = bb[2] - bb[0]
                    bx0 = min(848 - tw - 24, 485)
                    d.rounded_rectangle([bx0, ly, bx0 + tw + 24, ly + 38], radius=10, fill=p.surface_panel, outline=col, width=2)
                    d.text((bx0 + 12, ly + 6), txt, font=f_l, fill=col)

            overlays_2d.append(_layer_labels)

        elif scene_key == "ablative_gas_shedding":
            # Kept in ORBIT backdrop for visual continuity during hypersonic reentry!
            cam.eye = (0.0, 0.25, 6.4)
            cam.target = (0.0, -0.22, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.40, 0.0), scale=1.08, yaw=0.06, pitch=0.0, t=t, plasma=0.92, bow_shock_gap=0.75, charred=1.0)
            # Glowing sacrificial gas streaks peeling off the bottom shield and carrying heat outward
            for i in range(12):
                ph = (t * 2.4 + i * 0.085) % 1.0
                side = -1 if i % 2 == 0 else 1
                gx0 = side * (0.25 + ph * 1.55)
                gy0 = -0.60 - (1.0 - ph) * 0.22 + ph * 1.35
                sc.add_cylinder((gx0, gy0, 0.24), (gx0 + side * 0.22, gy0 + 0.18, 0.24), 0.048 * (1.0 - ph * 0.4), 0.015, PLASMA_WHITE if ph < 0.4 else AMBER, segments=6, emissive=0.78, bloom=True)

        elif scene_key == "temp_gradient_bars":
            # Clean unobstructed capsule above + mathematically honest bars (72°F vs 5,000°F) strictly in x <= 860!
            cam.eye = (0.0, 0.65, 7.8)
            cam.target = (0.0, -0.15, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.72, -0.20), scale=0.86, yaw=0.12, pitch=-0.14, t=t, plasma=0.88, bow_shock_gap=0.7, charred=0.9)
            bar_p = ease_out_cubic(clamp(prog * 1.4, 0.0, 1.0))
            overlays_2d.append(
                lambda d, bp=bar_p: draw_comparison_bars(
                    d,
                    82,
                    1115,
                    774,
                    225,
                    [
                        ("OUTSIDE PLASMA", "5,000°F", 1.0, p.danger),
                        ("INSIDE CABIN (3 IN)", "72°F", 0.025, p.emerald),
                    ],
                    bp,
                    p,
                    self.font_black,
                )
            )

        elif scene_key == "triple_chute_descent":
            cam.eye = (0.0, 0.55, 8.6)
            cam.target = (0.0, 0.65, 0.0)
            chute_p = clamp(prog * 1.35, 0.0, 1.0)
            cap_y = 0.45 - prog * 0.68
            sway = math.sin(t * 2.2) * 0.08
            self._add_3d_space_capsule(sc, center=(sway, cap_y, 0.0), scale=0.82, yaw=0.10, roll=sway * 0.35, t=t, plasma=0.0, charred=1.0)
            self._add_3d_parachutes(sc, (sway, cap_y + 0.88, 0.0), bloom_p=chute_p, t=t)

        elif scene_key == "bolt_ocean_splashdown":
            # Narrator: "Welcome home, Bolt!" -> Capsule genuinely sitting IN the 3D ocean with foam ring!
            cam.eye = (0.0, 0.68, 7.2)
            cam.target = (0.0, 0.05, 0.0)
            bob = math.sin(t * 3.0) * 0.05
            self._add_splashdown_water_surface(sc, t=t, center_y=-0.88)
            self._add_3d_space_capsule(
                sc,
                center=(0.0, -0.52 + bob, 0.08),
                scale=1.02,
                yaw=0.08,
                roll=math.sin(t * 2.2) * 0.04,
                t=t,
                plasma=0.0,
                charred=1.0,
                open_hatch=True,
                flotation_collar=True,
                hide_bottom_submerged=True,
            )
            add_crash_test_dummy(
                sc,
                pos=(0.0, 0.50 + bob, 0.08),
                scale=0.66,
                yaw=0.06,
                pose="relief_wave",
                emotion="relief",
                t=t,
                ground_shadow=False,
                show_legs=False,
            )

        else:  # verdict_cta_card
            cam.eye = (0.0, 0.68, 7.4)
            cam.target = (0.0, 0.05, 0.0)
            bob = math.sin(t * 3.0) * 0.05
            self._add_splashdown_water_surface(sc, t=t, center_y=-0.92)
            self._add_3d_space_capsule(
                sc,
                center=(0.0, -0.56 + bob, 0.08),
                scale=0.98,
                yaw=0.08,
                roll=math.sin(t * 2.0) * 0.04,
                t=t,
                plasma=0.0,
                charred=1.0,
                open_hatch=True,
                flotation_collar=True,
                hide_bottom_submerged=True,
            )
            add_crash_test_dummy(
                sc,
                pos=(0.0, 0.44 + bob, 0.08),
                scale=0.66,
                yaw=math.sin(t * 2.2) * 0.14,
                pose="cta_shrug",
                emotion="cta",
                t=t,
                ground_shadow=False,
                show_legs=False,
            )
            overlays_2d.append(lambda d: draw_cta_buttons(d, t, p, self.font_black, by=1150))

        rendered_bgr = sc.render_to_bgr(bg)
        return rendered_bgr, overlays_2d

    def render_frame(
        self,
        frame_idx: int,
        t: float,
        beat_id: str,
        beat_progress: float,
        rms: float,
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
    ) -> None:
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "capsule_plasma_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("capsule_plasma_hero", t=0.45, prog=0.55, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
