"""Episode 07: How a Jet Engine SURVIVES Swallowing a Bird — Upgraded True 3D Turbofan + BOLT's Yellow Mini-Jet."""

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

TITANIUM_LIGHT = (196, 212, 232)
TITANIUM_MID = (124, 144, 172)
TITANIUM_DARK = (54, 68, 92)
CARBON_DARK = (34, 44, 62)
JET_YELLOW = (255, 206, 36)
JET_YELLOW_DARK = (224, 152, 22)
JET_NAVY = (24, 38, 60)
GLASS_BLUE = (42, 168, 220)
KEVLAR_GOLD = (232, 182, 58)
CORE_ORANGE = (255, 118, 28)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


def _build_sky_backdrop_bgr(w: int, h: int, horizon_y: int = 1280) -> np.ndarray:
    """Smooth twilight aerospace sky with soft feathered horizon and blurred cloud layer (BGR)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    hy = horizon_y / float(h)

    # Smooth continuous atmospheric blend across horizon (no hard razor edge!)
    below = 1.0 / (1.0 + np.exp(-(ys - hy) * 28.0))
    above = 1.0 - below

    sky_t = np.clip(ys / max(0.01, hy), 0.0, 1.0)
    sky_r = 12.0 + 46.0 * (sky_t ** 2.2) + 58.0 * (sky_t ** 4.8)
    sky_g = 24.0 + 92.0 * (sky_t ** 1.7) + 46.0 * (sky_t ** 4.0)
    sky_b = 58.0 + 114.0 * (sky_t ** 1.3) + 22.0 * (sky_t ** 3.6)

    sun_glow = np.exp(-((xs / 0.62) ** 2 + ((ys - hy * 0.94) / 0.14) ** 2))
    sky_r = sky_r + 56.0 * sun_glow
    sky_g = sky_g + 46.0 * sun_glow
    sky_b = sky_b + 24.0 * sun_glow

    deck_t = np.clip((ys - hy) / max(0.01, 1.0 - hy), 0.0, 1.0)
    deck_r = 46.0 * (1.0 - deck_t * 0.65) + 14.0 * deck_t
    deck_g = 64.0 * (1.0 - deck_t * 0.62) + 22.0 * deck_t
    deck_b = 98.0 * (1.0 - deck_t * 0.55) + 40.0 * deck_t

    img = np.zeros((h, w, 3), dtype=np.float32)
    img[:, :, 2] = sky_r * above + deck_r * below
    img[:, :, 1] = sky_g * above + deck_g * below
    img[:, :, 0] = sky_b * above + deck_b * below
    bgr = np.clip(img, 0, 255).astype(np.uint8)

    # Soft Gaussian-blurred atmospheric cloud puffs (never flat hard ellipses!)
    cloud_layer = np.zeros((h, w, 3), dtype=np.uint8)
    rng = np.random.default_rng(707)
    for _ in range(14):
        cx = int(rng.integers(60, w - 60))
        cy = int(rng.integers(horizon_y - 70, horizon_y + 120))
        rx = int(rng.integers(110, 240))
        ry = int(rng.integers(24, 52))
        cv2.ellipse(cloud_layer, (cx, cy), (rx, ry), 0, 0, 360, (140, 128, 122), -1, lineType=cv2.LINE_AA)
    cloud_layer = cv2.GaussianBlur(cloud_layer, (61, 35), 0)
    bgr = cv2.addWeighted(bgr, 1.0, cloud_layer, 0.28, 0)
    return bgr


@register_scene("ep07_jet_engine_bird_strike")
class JetEngineBirdStrikeScene(EpisodeScene):
    """Articulated 12-beat True 3D High-Bypass Turbofan + BOLT's Yellow Mini-Jet."""

    slug = "ep07_jet_engine_bird_strike"
    episode_id = "ep07"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_studio_bgr: np.ndarray | None = None
        self.bg_alert_bgr: np.ndarray | None = None
        self.bg_safe_bgr: np.ndarray | None = None
        self.bg_sky_bgr: np.ndarray | None = None
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
        self.bg_studio_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.cyan)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_alert_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.danger)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_safe_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.emerald)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_sky_bgr = _build_sky_backdrop_bgr(w, h, horizon_y=1240)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_shell_arc(
        self,
        sc: Scene3D,
        _p,
        x0: float,
        r0: float,
        x1: float,
        r1: float,
        ang_start: float,
        ang_end: float,
        steps: int,
        rgb: tuple[int, int, int],
        metallic: float = 0.65,
        emissive: float = 0.0,
        bloom: bool = False,
        bulge_fn=None,
    ) -> None:
        """Continuous sectioned 3D cylindrical shell (real metallic cutaway casing, NOT wire sticks!)."""
        angs = np.linspace(ang_start, ang_end, steps + 1)
        for i in range(steps):
            a0, a1 = float(angs[i]), float(angs[i + 1])
            b0 = bulge_fn(a0) if bulge_fn else 0.0
            b1 = bulge_fn(a1) if bulge_fn else 0.0
            q = np.array(
                [
                    _p(x0, math.sin(a0) * (r0 + b0), math.cos(a0) * (r0 + b0)),
                    _p(x0, math.sin(a1) * (r0 + b1), math.cos(a1) * (r0 + b1)),
                    _p(x1, math.sin(a1) * (r1 + b1), math.cos(a1) * (r1 + b1)),
                    _p(x1, math.sin(a0) * (r1 + b0), math.cos(a0) * (r1 + b0)),
                ],
                dtype=np.float32,
            )
            sc.add_quad(q, rgb=rgb, metallic=metallic, emissive=emissive, double_sided=True, bevel_edge=False, bloom=bloom)

    def _add_3d_turbofan(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        spin: float = 0.0,
        cutaway: bool = False,
        kevlar_glow: float = 0.0,
        kevlar_bulge: float = 0.0,
        missing_blade_idx: int = -1,
        detached_blade_t: float = 0.0,
        show_core_fire: bool = True,
        bypass_highlight: float = 0.0,
    ) -> None:
        """Detailed 3D High-Bypass Turbofan with real sectioned shell cutaway and wide-chord fan blades."""
        R = rot_matrix(0.0, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Structural overhead mounting pylon so the engine is grounded in aerospace context
        sc.add_box(_p(-0.15, 1.72, -0.15), (1.35 * scale, 0.56 * scale, 0.34 * scale), TITANIUM_DARK, rot=(0.0, yaw, pitch), metallic=0.72, texture="painted_metal")

        if not cutaway:
            sc.add_cylinder(_p(1.38, 0.0, 0.0), _p(1.12, 0.0, 0.0), 1.38 * scale, 1.54 * scale, TITANIUM_LIGHT, segments=26, metallic=0.80, caps=False)
            sc.add_cylinder(_p(1.12, 0.0, 0.0), _p(-0.95, 0.0, 0.0), 1.54 * scale, 1.46 * scale, TITANIUM_MID, segments=26, metallic=0.62, caps=False)
            sc.add_cylinder(_p(-0.95, 0.0, 0.0), _p(-1.82, 0.0, 0.0), 1.46 * scale, 1.06 * scale, TITANIUM_DARK, segments=22, metallic=0.68, caps=False)
            # Clean non-overlapping yellow racing accent band (slightly larger radius on narrow strip)
            sc.add_cylinder(_p(0.56, 0.0, 0.0), _p(0.30, 0.0, 0.0), 1.565 * scale, 1.565 * scale, JET_YELLOW, segments=26, metallic=0.45, caps=False)
        else:
            # REAL sectioned 210° metallic cutaway nacelle (back & bottom wall solid, front-top cleanly cut away!)
            a_s, a_e = math.pi * 0.42, math.pi * 1.72
            self._add_shell_arc(sc, _p, 1.34, 1.40, 1.08, 1.52, a_s, a_e, 14, TITANIUM_LIGHT, metallic=0.80)
            self._add_shell_arc(sc, _p, 1.08, 1.52, -0.95, 1.44, a_s, a_e, 14, TITANIUM_MID, metallic=0.62)
            self._add_shell_arc(sc, _p, -0.95, 1.44, -1.78, 1.06, a_s, a_e, 12, TITANIUM_DARK, metallic=0.68)
            # Crisp glowing cyan machined section edge rims along the cutaway edges
            for edge_a in (a_s, a_e):
                ey, ez = math.sin(edge_a) * 1.48, math.cos(edge_a) * 1.48
                sc.add_cylinder(_p(1.22, ey * 0.96, ez * 0.96), _p(-1.68, ey * 0.74, ez * 0.74), 0.045 * scale, 0.040 * scale, TITANIUM_LIGHT, segments=8, metallic=0.85)

        # Wide woven Kevlar containment belt wrapping the fan plane!
        if kevlar_glow > 0.02 or cutaway:
            k_col = lerp_color(KEVLAR_GOLD, AMBER, clamp(kevlar_glow, 0.0, 1.0))
            ka0 = math.pi * 0.34 if cutaway else 0.0
            ka1 = math.pi * 1.78 if cutaway else math.pi * 2.0
            self._add_shell_arc(
                sc,
                _p,
                0.92,
                1.56,
                0.42,
                1.56,
                ka0,
                ka1,
                16,
                k_col,
                metallic=0.35,
                emissive=0.28 * kevlar_glow,
                bloom=kevlar_glow > 0.55,
                bulge_fn=lambda a: kevlar_bulge * math.exp(-((a - 1.25) / 0.45) ** 2),
            )

        # Inner high-pressure compressor & combustor core (only ~20% cross-section!)
        sc.add_cylinder(_p(0.32, 0.0, 0.0), _p(-1.45, 0.0, 0.0), 0.48 * scale, 0.42 * scale, TITANIUM_DARK, segments=16, metallic=0.75)
        # Only glow core fire inside cutaway (NEVER bleed bloom through closed opaque nacelle!)
        if show_core_fire and cutaway:
            sc.add_cylinder(_p(-0.32, 0.0, 0.0), _p(-1.10, 0.0, 0.0), 0.52 * scale, 0.45 * scale, CORE_ORANGE, segments=16, emissive=0.68, bloom=True)
            sc.add_cylinder(_p(-1.42, 0.0, 0.0), _p(-2.05, 0.0, 0.0), 0.36 * scale, 0.08 * scale, TITANIUM_MID, segments=14, metallic=0.72)
        elif not cutaway:
            sc.add_cylinder(_p(-1.42, 0.0, 0.0), _p(-2.02, 0.0, 0.0), 0.36 * scale, 0.08 * scale, TITANIUM_MID, segments=14, metallic=0.72)

        # Smooth glowing cyan bypass airflow streamlines inside the 80% outer bypass duct
        if bypass_highlight > 0.05:
            for lane in range(5):
                la = math.pi * 0.55 + lane * (math.pi * 0.26)
                ly = math.sin(la) * 0.98
                lz = math.cos(la) * 0.98
                phase = (spin * 0.22 + lane * 0.20) % 1.0
                fx0 = 0.65 - phase * 1.90
                fx1 = fx0 - 0.52
                sc.add_cylinder(
                    _p(fx0, ly, lz),
                    _p(fx1, ly * 0.90, lz * 0.90),
                    0.048 * scale,
                    0.026 * scale,
                    CYAN,
                    segments=8,
                    emissive=0.72 * bypass_highlight,
                    bloom=True,
                )

        # Sharp painted spinner nose cone with flush spiral stripe (no bulging warts!)
        sc.add_cylinder(_p(0.84, 0.0, 0.0), _p(1.56, 0.0, 0.0), 0.44 * scale, 0.04 * scale, CARBON_DARK, segments=22, metallic=0.55)
        sc.add_sphere(_p(1.54, 0.0, 0.0), 0.048 * scale, TITANIUM_LIGHT, metallic=0.85)
        for k in range(8):
            kt0 = k / 8.0
            kt1 = (k + 1) / 8.0
            sx0, sx1 = 0.92 + kt0 * 0.54, 0.92 + kt1 * 0.54
            sr0, sr1 = 0.40 * (1.0 - kt0) + 0.05, 0.40 * (1.0 - kt1) + 0.05
            sa0, sa1 = spin + kt0 * 3.8, spin + kt1 * 3.8
            sc.add_cylinder(
                _p(sx0, math.sin(sa0) * sr0, math.cos(sa0) * sr0),
                _p(sx1, math.sin(sa1) * sr1, math.cos(sa1) * sr1),
                0.026 * scale,
                0.022 * scale,
                (244, 248, 255),
                segments=6,
                emissive=0.25,
            )

        # 14 wide-chord curved titanium fan blades (proper flat twisted airfoil paddles, NOT thin bike spokes!)
        n_blades = 14
        for bi in range(n_blades):
            ang = spin + bi * (2.0 * math.pi / n_blades)
            if bi == missing_blade_idx:
                # Detached titanium blade flying outward until it slams directly INTO the Kevlar containment belt!
                fly_a = 1.25
                rad_fly = 0.72 + detached_blade_t * 0.76
                b_col = lerp_color(TITANIUM_LIGHT, AMBER, clamp(detached_blade_t * 1.1, 0.0, 1.0))
                sc.add_box(
                    _p(0.68, math.sin(fly_a) * rad_fly, math.cos(fly_a) * rad_fly),
                    (0.24 * scale, 0.68 * scale, 0.06 * scale),
                    b_col,
                    rot=(fly_a - math.pi * 0.5 + detached_blade_t * 0.35, yaw + 0.32, pitch),
                    metallic=0.82,
                    emissive=0.25 if detached_blade_t > 0.4 else 0.0,
                    texture="brushed_steel",
                )
                continue
            r_mid = 0.88
            by = math.sin(ang) * r_mid
            bz = math.cos(ang) * r_mid
            sc.add_box(
                _p(0.70, by, bz),
                (0.26 * scale, 0.94 * scale, 0.048 * scale),
                TITANIUM_LIGHT if bi % 2 == 0 else TITANIUM_MID,
                rot=(ang - math.pi * 0.5, yaw + 0.35, pitch),
                metallic=0.84,
                texture="brushed_steel",
            )

    def _add_3d_yellow_minijet(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        t: float = 0.0,
        with_pilot: bool = True,
        pilot_pose: str = "pilot_sub",
        pilot_emotion: str = "curious",
        afterburner_left: bool = True,
        afterburner_right: bool = True,
        afterburner_main: bool = True,
    ) -> None:
        """BOLT's Signature 3D Yellow Mini-Jet (zero Z-fighting, clean cockpit, independent twin pods)."""
        R = rot_matrix(roll, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Smooth 22-segment streamlined fuselage loft (zero overlapping Z-fighting cylinders!)
        loft = [(1.66, 0.08), (1.12, 0.34), (0.36, 0.48), (-0.64, 0.44), (-1.54, 0.24)]
        for (x0, r0), (x1, r1) in zip(loft[:-1], loft[1:]):
            sc.add_cylinder(_p(x0, 0.0, 0.0), _p(x1, 0.0, 0.0), r0 * scale, r1 * scale, JET_YELLOW, segments=22, metallic=0.45, caps=False)
        sc.add_sphere(_p(1.66, 0.0, 0.0), 0.095 * scale, TITANIUM_LIGHT, metallic=0.85)
        # Clean crisp navy accent collar band (non-overlapping narrow ring at nose root)
        sc.add_cylinder(_p(0.88, 0.0, 0.0), _p(0.72, 0.0, 0.0), 0.415 * scale, 0.445 * scale, JET_NAVY, segments=22, metallic=0.42, caps=False)

        # Open cockpit coaming rim + dark interior well + front sapphire windscreen
        sc.add_cylinder(_p(0.26, 0.34, 0.0), _p(0.22, 0.58, 0.0), 0.38 * scale, 0.34 * scale, JET_NAVY, segments=18, metallic=0.55)
        sc.add_cylinder(_p(0.24, 0.56, 0.0), _p(0.24, 0.60, 0.0), 0.30 * scale, 0.30 * scale, (14, 20, 32), segments=16, metallic=0.15)
        sc.add_sphere(_p(0.60, 0.44, 0.0), 0.24 * scale, GLASS_BLUE, metallic=0.78, rim_rgb=CYAN)

        # Swept yellow main wings + underwing mini-turbofan pods (independent left/right thrust!)
        for sz in (-1, 1):
            sc.add_box(_p(-0.18, -0.04, sz * 1.06), (0.68 * scale, 0.068 * scale, 1.40 * scale), JET_YELLOW_DARK, rot=(roll, yaw - sz * 0.26, pitch), metallic=0.48, texture="painted_metal")
            tip_col = EMERALD if sz > 0 else DANGER
            sc.add_sphere(_p(-0.42, -0.02, sz * 1.74), 0.072 * scale, tip_col, emissive=0.85, bloom=True)
            is_on = afterburner_right if sz > 0 else afterburner_left
            pod_col = TITANIUM_LIGHT if is_on else TITANIUM_DARK
            sc.add_cylinder(_p(0.24, -0.32, sz * 0.82), _p(-0.48, -0.32, sz * 0.82), 0.24 * scale, 0.20 * scale, pod_col, segments=16, metallic=0.78)
            sc.add_sphere(_p(0.26, -0.32, sz * 0.82), 0.14 * scale, CARBON_DARK if is_on else DANGER, metallic=0.55, emissive=0.0 if is_on else 0.45)
            if is_on:
                sc.add_cylinder(_p(-0.50, -0.32, sz * 0.82), _p(-0.88, -0.32, sz * 0.82), 0.13 * scale, 0.03 * scale, CYAN, segments=10, emissive=0.82, bloom=True)
            else:
                # Subtle dark smoke puff trail showing failed engine cleanly shut down!
                for sk in range(3):
                    ph = (t * 1.6 + sk * 0.33) % 1.0
                    sc.add_sphere(_p(-0.56 - ph * 0.72, -0.30 + ph * 0.16, sz * 0.82), (0.09 + ph * 0.07) * scale, (95, 102, 118), metallic=0.05)

        # Swept vertical tail fin + horizontal stabilizers
        sc.add_box(_p(-1.26, 0.46, 0.0), (0.58 * scale, 0.72 * scale, 0.065 * scale), JET_YELLOW_DARK, rot=(roll, yaw, pitch - 0.22), metallic=0.50, texture="painted_metal")
        sc.add_box(_p(-1.32, 0.08, 0.0), (0.40 * scale, 0.058 * scale, 1.18 * scale), JET_NAVY, rot=(roll, yaw, pitch), metallic=0.52, texture="painted_metal")

        # Rear exhaust nozzle
        sc.add_cylinder(_p(-1.52, 0.0, 0.0), _p(-1.74, 0.0, 0.0), 0.25 * scale, 0.20 * scale, TITANIUM_DARK, segments=16, metallic=0.78)
        if afterburner_main:
            flicker = 0.88 + 0.16 * math.sin(t * 28.0)
            sc.add_cylinder(_p(-1.74, 0.0, 0.0), _p(-1.74 - 0.56 * flicker, 0.0, 0.0), 0.16 * scale, 0.04 * scale, CORE_ORANGE, segments=10, emissive=0.88, bloom=True)

        # Seated pilot cleanly inside cockpit rim (show_legs=False guarantees zero fuselage clipping!)
        if with_pilot:
            add_crash_test_dummy(
                sc,
                pos=_p(0.22, 0.56, 0.0),
                scale=0.56 * scale,
                yaw=yaw + 0.18,
                pose=pilot_pose,
                emotion=pilot_emotion,
                t=t,
                ground_shadow=False,
                show_legs=False,
            )

    def _add_kinetic_bird_silhouette(
        self,
        sc: Scene3D,
        pos: tuple[float, float, float],
        scale: float = 0.52,
        wing_t: float = 0.0,
    ) -> None:
        """Unmistakable aerodynamic bird silhouette flying leftward (-X) toward the turbofan intake."""
        x, y, z = pos
        flap = math.sin(wing_t * 14.0) * 0.20
        body_col = (232, 238, 246)
        wing_col = (186, 200, 218)
        # Sleek teardrop torso + neck + head + amber beak pointing LEFT (-X into engine!)
        sc.add_cylinder((x + 0.45 * scale, y - 0.04 * scale, z), (x - 0.32 * scale, y + 0.04 * scale, z), 0.08 * scale, 0.17 * scale, body_col, segments=12, metallic=0.22)
        sc.add_sphere((x - 0.40 * scale, y + 0.08 * scale, z), 0.13 * scale, body_col, metallic=0.20)
        sc.add_cylinder((x - 0.48 * scale, y + 0.08 * scale, z), (x - 0.72 * scale, y + 0.05 * scale, z), 0.055 * scale, 0.012 * scale, AMBER, segments=8, metallic=0.25)
        # Swept V-shaped wings (clearly readable silhouette from 3/4 view!)
        for sz in (-1, 1):
            sc.add_box(
                (x + 0.02 * scale, y + (0.18 + flap) * scale, z + sz * 0.42 * scale),
                (0.32 * scale, 0.045 * scale, 0.78 * scale),
                wing_col,
                rot=(sz * (0.38 + flap), sz * 0.25, 0.0),
                metallic=0.22,
                texture="matte",
            )
            # Wingtip feather extension
            sc.add_box(
                (x + 0.16 * scale, y + (0.34 + flap * 1.4) * scale, z + sz * 0.88 * scale),
                (0.22 * scale, 0.038 * scale, 0.44 * scale),
                (110, 128, 152),
                rot=(sz * (0.55 + flap), sz * 0.35, 0.0),
                metallic=0.20,
                texture="matte",
            )

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

        bg = self.bg_studio_bgr
        if scene_key in ("turbofan_impact_hero", "blade_off_snap"):
            bg = self.bg_alert_bgr
        elif scene_key in ("kevlar_catch_climax", "thrust_margin_bars"):
            bg = self.bg_safe_bgr
        elif scene_key in ("bolt_jet_safe_cruise", "verdict_cta_card"):
            bg = self.bg_sky_bgr
        assert bg is not None

        cam = Camera3D(eye=(0.0, 0.8, 7.6), target=(0.0, -0.05, 0.0), fov_deg=41.0, width=w, height=h)
        sc = Scene3D(cam)

        if scene_key == "turbofan_impact_hero":
            shake = math.sin(t * 48.0) * 0.09 if (prog > 0.45 and not is_cover) else 0.0
            cam.eye = (0.75 + shake, 0.62, 7.4 if is_cover else 7.1)
            cam.target = (0.10, 0.18 if is_cover else -0.05, 0.0)
            self._add_3d_turbofan(sc, center=(-0.72, -0.10, 0.0), scale=0.96, yaw=-0.46, spin=t * 14.0, cutaway=False, kevlar_glow=0.35, show_core_fire=False)
            # Clear bird silhouette flying leftward into the intake with cyan/amber slipstream trails BEHIND it!
            bx = 2.05 - ease_out_cubic(min(1.0, prog * 1.15)) * 1.15 if not is_cover else 1.48
            self._add_kinetic_bird_silhouette(sc, (bx, 0.12, 0.48), scale=0.62, wing_t=t)
            for k in range(3):
                ky = 0.12 + (k - 1) * 0.16
                sc.add_cylinder((bx + 0.45, ky, 0.48), (bx + 1.15, ky, 0.48), 0.024, 0.008, CYAN, segments=6, emissive=0.75, bloom=True)
            if prog > 0.55 and not is_cover:
                impact_p = clamp((prog - 0.55) / 0.45, 0.0, 1.0)
                overlays_2d.append(lambda d, ip=impact_p: draw_sparks(d, 590, 940, ip, 16, 150, 130, p, seed=701))

        elif scene_key == "bolt_jet_wave_intro":
            # Narrator directly greets BOLT: "Hey Bolt, wave before we fire the test cannon!"
            cam.eye = (0.2, 0.72, 7.2)
            cam.target = (0.0, 0.12, 0.0)
            sc.add_floor_grid(y_level=-1.55, span=7.0, step=1.0, t=t, particles=True)
            # Test cannon rig on right + spinning test turbofan cleanly separated behind!
            self._add_3d_turbofan(sc, center=(1.85, 0.45, -2.35), scale=0.62, yaw=-0.52, spin=t * 11.0, kevlar_glow=0.20, show_core_fire=False)
            bob = math.sin(t * 3.0) * 0.05
            self._add_3d_yellow_minijet(
                sc,
                center=(-0.25, -0.35 + bob, 0.40),
                scale=1.06,
                yaw=0.22,
                pitch=0.04,
                t=t,
                with_pilot=True,
                pilot_pose="relief_wave",
                pilot_emotion="cta",
                afterburner_left=False,
                afterburner_right=False,
                afterburner_main=False,
            )

        elif scene_key == "spinner_cone_deflect":
            cam.eye = (1.1, 0.55, 6.6)
            cam.target = (0.15, -0.05, 0.0)
            self._add_3d_turbofan(sc, center=(-0.45, -0.10, 0.0), scale=1.02, yaw=-0.38, spin=t * 12.0, cutaway=False, show_core_fire=False)
            # Clean curved outward deflection arcs peeling off the sharp nose cone
            for ang in (-0.80, -0.32, 0.32, 0.80):
                ph = (t * 2.2 + abs(ang)) % 1.0
                x0 = 1.65 - ph * 1.05
                rad = 0.08 + (ph ** 1.35) * 0.95
                sc.add_sphere((x0, -0.10 + math.sin(ang) * rad, math.cos(ang) * rad * 0.55 + 0.2), 0.085, AMBER, emissive=0.78, bloom=True)
                sc.add_cylinder(
                    (1.50, -0.10, 0.22),
                    (0.65, -0.10 + math.sin(ang) * 0.98, math.cos(ang) * 0.58 + 0.22),
                    0.024,
                    0.038,
                    CYAN,
                    segments=6,
                    emissive=0.62,
                    bloom=True,
                )

        elif scene_key == "titanium_fan_blades":
            # Swept curved scimitar hollow titanium fan blade (true twisted airfoil silhouette, NOT stacked blocks with X!)
            cam.eye = (0.2, 0.55, 6.4)
            cam.target = (0.0, 0.0, 0.0)
            sc.add_floor_grid(y_level=-1.85, span=6.5, step=1.0, t=t, particles=True)
            rot_y = -0.32 + math.sin(t * 1.8) * 0.30
            # Machined dovetail root with contact shadow
            sc.add_ground_shadow((0.25, -1.78, 0.0), 0.72, 0.55, opacity=0.45)
            sc.add_box((0.25, -1.48, 0.0), (0.68, 0.38, 0.34), TITANIUM_DARK, rot=(0.0, rot_y, 0.0), metallic=0.80)
            # Smooth scimitar curved airfoil segments with hollow titanium truss cutaway window
            for seg in range(9):
                st = seg / 8.0
                sy = -1.16 + st * 2.38
                sx = 0.25 + math.sin(st * math.pi) * 0.34  # Real curved scimitar sweep!
                twist = rot_y + st * 0.42
                w_seg = 0.78 + math.sin(st * math.pi * 0.85) * 0.28
                # Leading & trailing titanium airfoil edges
                sc.add_box((sx, sy, -0.06), (w_seg, 0.30, 0.065), TITANIUM_LIGHT if seg % 2 == 0 else TITANIUM_MID, rot=(0.0, twist, -0.18 * math.cos(st * math.pi)), metallic=0.86)
                # Subtle internal titanium honeycomb spar ribs inside mid-span
                if 2 <= seg <= 6:
                    sc.add_cylinder((sx - w_seg * 0.28, sy - 0.11, 0.04), (sx + w_seg * 0.28, sy + 0.11, 0.04), 0.022, 0.022, CYAN, segments=6, emissive=0.55)
            add_crash_test_dummy(sc, pos=(-1.55, -0.60, 0.45), scale=0.80, yaw=0.35, pose="point_right", emotion="curious", t=t)

        elif scene_key == "blade_radial_fling":
            cam.eye = (0.85, 0.55, 6.7)
            cam.target = (0.0, 0.0, 0.0)
            self._add_3d_turbofan(sc, center=(0.0, 0.0, 0.0), scale=1.04, yaw=-0.52, spin=t * 15.0, cutaway=True, bypass_highlight=0.75)
            for i in range(10):
                ph = (t * 2.2 + i * 0.11) % 1.0
                ang = i * 0.62 + ph * 2.2
                rad = 0.35 + ph * 1.02
                sc.add_sphere((0.55 - ph * 1.45, math.sin(ang) * rad, math.cos(ang) * rad), 0.075, AMBER, emissive=0.78, bloom=True)

        elif scene_key == "bypass_duct_xray":
            cam.eye = (0.0, 0.48, 7.4)
            cam.target = (0.0, 0.05, 0.0)
            self._add_3d_turbofan(sc, center=(0.0, 0.10, 0.0), scale=1.06, yaw=-0.12, spin=t * 12.0, cutaway=True, show_core_fire=True, bypass_highlight=1.0)

            def _bypass_labels(d: ImageDraw.ImageDraw) -> None:
                f_b = load_font(self.font_black, 26)
                f_s = load_font(self.font_bold, 20)
                # Placed cleanly BELOW the HUD badge (y=620+) and strictly inside x <= 850!
                d.rounded_rectangle([84, 628, 430, 706], radius=14, fill=p.surface_panel, outline=p.cyan, width=3)
                d.text((102, 638), "80% BYPASS DUCT", font=f_b, fill=p.cyan)
                d.text((102, 672), "HOLLOW OUTER TUNNEL", font=f_s, fill=TITANIUM_LIGHT)
                d.rounded_rectangle([470, 1218, 848, 1296], radius=14, fill=p.surface_panel, outline=p.amber, width=3)
                d.text((488, 1228), "20% INNER CORE", font=f_b, fill=p.amber)
                d.text((488, 1262), "PROTECTED CENTER", font=f_s, fill=TITANIUM_LIGHT)

            overlays_2d.append(_bypass_labels)

        elif scene_key == "debris_bypass_exit":
            # Narrator: "Hold tight, Bolt!" -> BOLT safely to the foreground-left on observation deck (NOT behind hot exhaust!)
            cam.eye = (0.0, 0.65, 7.6)
            cam.target = (0.0, 0.0, 0.0)
            self._add_3d_turbofan(sc, center=(0.35, 0.35, -0.55), scale=0.92, yaw=-0.22, spin=t * 16.0, cutaway=True, show_core_fire=True, bypass_highlight=1.0)
            for i in range(10):
                ph = (t * 2.6 + i * 0.10) % 1.0
                ex = 0.85 - ph * 2.45
                ey = (0.94 if i % 2 == 0 else -0.86) + 0.35
                sc.add_cylinder((ex + 0.22, ey, -0.35), (ex, ey, -0.35), 0.038, 0.022, AMBER, emissive=0.78, bloom=True, segments=6)
            add_crash_test_dummy(
                sc,
                pos=(-1.55, -0.95, 1.05),
                scale=0.76,
                yaw=0.38,
                pose="brace_impact",
                emotion="brace",
                t=t,
            )

        elif scene_key == "blade_off_snap":
            shake = math.sin(t * 54.0) * 0.11 * clamp((prog - 0.25) * 2.5, 0.0, 1.0)
            cam.eye = (0.85 + shake, 0.45, 6.0)
            cam.target = (0.15, 0.15, 0.0)
            snap_t = ease_out_cubic(clamp((prog - 0.22) / 0.78, 0.0, 1.0))
            self._add_3d_turbofan(
                sc,
                center=(-0.20, 0.0, 0.0),
                scale=1.10,
                yaw=-0.45,
                spin=t * 16.0,
                cutaway=True,
                kevlar_glow=0.35 + snap_t * 0.55,
                kevlar_bulge=snap_t * 0.18,
                missing_blade_idx=3 if prog > 0.22 else -1,
                detached_blade_t=snap_t,
            )
            if prog > 0.25:
                overlays_2d.append(lambda d, sp=snap_t: draw_sparks(d, 560, 740, sp, 18, 155, 130, p, seed=708))

        elif scene_key == "kevlar_catch_climax":
            cam.eye = (0.55, 0.52, 6.2)
            cam.target = (0.0, 0.12, 0.0)
            catch_p = ease_out_cubic(clamp(prog * 1.25, 0.0, 1.0))
            bulge = math.sin(catch_p * math.pi) * 0.28 + 0.14 * catch_p
            self._add_3d_turbofan(
                sc,
                center=(-0.15, 0.05, 0.0),
                scale=1.06,
                yaw=-0.42,
                spin=t * (10.0 * (1.0 - catch_p * 0.7)),
                cutaway=True,
                kevlar_glow=1.0,
                kevlar_bulge=bulge,
                missing_blade_idx=3,
                detached_blade_t=1.0,
            )
            overlays_2d.append(lambda d, cp=catch_p: draw_sparks(d, 540, 720, cp, 16, 150, 125, p, seed=709))
            overlays_2d.append(
                lambda d, cp=catch_p: draw_pressure_gauge(
                    d, 175, 1185, 88, 0.35 + 0.65 * cp, "KEVLAR BELT", "100% CAUGHT", p, self.font_black, invert_scale=True
                )
            )

        elif scene_key == "thrust_margin_bars":
            # SINGLE BOLT piloting the Yellow Mini-Jet with LEFT engine shut down & smoking, RIGHT engine at 100% climb!
            cam.eye = (0.0, 0.68, 7.4)
            cam.target = (0.0, -0.15, 0.0)
            self._add_3d_yellow_minijet(
                sc,
                center=(0.0, 0.68, 0.0),
                scale=0.98,
                yaw=-0.38,
                pitch=0.14,
                t=t,
                with_pilot=True,
                pilot_pose="pilot_sub",
                pilot_emotion="relief",
                afterburner_left=False,
                afterburner_right=True,
                afterburner_main=False,
            )
            bar_p = ease_out_cubic(clamp(prog * 1.4, 0.0, 1.0))
            overlays_2d.append(
                lambda d, bp=bar_p: draw_comparison_bars(
                    d,
                    82,
                    1115,
                    774,
                    225,
                    [
                        ("2 ENGINES NORMAL", "200% THRUST", 1.0, p.cyan),
                        ("1 ENGINE FAILED", "100% SAFE CLIMB", 0.50, p.emerald),
                    ],
                    bp,
                    p,
                    self.font_black,
                )
            )

        elif scene_key == "bolt_jet_safe_cruise":
            # Narrator: "Nice landing, Bolt!" -> 3D runway tarmac strip below the twilight sky!
            cam.eye = (0.0, 0.72, 7.3)
            cam.target = (0.0, 0.05, 0.0)
            # Clean 3D asphalt runway with centerline dashes beneath the jet!
            sc.add_box((0.0, -1.35, 0.0), (9.0, 0.16, 2.4), (44, 52, 66), metallic=0.12, texture="concrete")
            for dx in (-2.6, -1.3, 0.0, 1.3, 2.6):
                sc.add_box((dx, -1.25, 0.0), (0.68, 0.03, 0.14), (238, 242, 248), metallic=0.10, texture="matte")
            glide = ease_in_out_cubic(prog)
            # Jet touches down smoothly onto the runway!
            jet_y = -0.38 - glide * 0.34
            self._add_3d_yellow_minijet(
                sc,
                center=(-0.35 + glide * 0.42, jet_y, 0.18),
                scale=1.08,
                yaw=-0.22 + glide * 0.16,
                pitch=0.08 * (1.0 - glide),
                t=t,
                with_pilot=True,
                pilot_pose="relief_wave",
                pilot_emotion="relief",
                afterburner_left=False,
                afterburner_right=True,
                afterburner_main=False,
            )

        else:  # verdict_cta_card
            cam.eye = (0.0, 0.72, 7.4)
            cam.target = (0.0, 0.05, 0.0)
            sc.add_box((0.0, -1.35, 0.0), (9.0, 0.16, 2.4), (44, 52, 66), metallic=0.12, texture="concrete")
            for dx in (-2.6, -1.3, 0.0, 1.3, 2.6):
                sc.add_box((dx, -1.25, 0.0), (0.68, 0.03, 0.14), (238, 242, 248), metallic=0.10, texture="matte")
            self._add_3d_yellow_minijet(
                sc,
                center=(0.0, -0.68, 0.10),
                scale=1.05,
                yaw=-0.18,
                pitch=0.0,
                t=t,
                with_pilot=True,
                pilot_pose="cta_shrug",
                pilot_emotion="cta",
                afterburner_left=False,
                afterburner_right=False,
                afterburner_main=False,
            )
            overlays_2d.append(lambda d: draw_cta_buttons(d, t, p, self.font_black, by=1145))

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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "turbofan_impact_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("turbofan_impact_hero", t=0.45, prog=0.45, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
