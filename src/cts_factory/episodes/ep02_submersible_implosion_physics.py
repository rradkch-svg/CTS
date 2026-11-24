"""Episode 02: Why Deep-Sea Hulls IMPLODE in Milliseconds — True 3D Submarines + UNIT-01."""

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

STEEL_LIGHT = (188, 206, 226)
STEEL_MID = (112, 134, 162)
STEEL_DARK = (50, 66, 92)
CARBON_DARK = (38, 48, 66)
HULL_WHITE = (206, 220, 234)
SUB_YELLOW = (255, 206, 36)
SUB_YELLOW_DARK = (224, 152, 22)
SUB_NAVY = (26, 40, 62)
GLASS_BLUE = (32, 148, 198)
BRASS = (218, 168, 72)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


def _build_surface_background_bgr(w: int, h: int, waterline_y: int = 1135) -> np.ndarray:
    """Build a crisp open-air twilight sky + smoothly blended horizon + deep ocean backdrop (BGR)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    wl = waterline_y / float(h)

    img = np.zeros((h, w, 3), dtype=np.float32)

    # Smooth misty twilight horizon transition (no harsh ruler seam!)
    sea_blend = np.clip((ys - (wl - 0.015)) / 0.032, 0.0, 1.0)
    sky_blend = 1.0 - sea_blend

    sky_t = np.clip(ys / max(0.01, wl), 0.0, 1.0)
    sky_r = 12.0 + 36.0 * (sky_t ** 2.2) + 34.0 * (sky_t ** 5.0)
    sky_g = 24.0 + 94.0 * (sky_t ** 1.8) + 46.0 * (sky_t ** 4.5)
    sky_b = 54.0 + 114.0 * (sky_t ** 1.4) + 32.0 * (sky_t ** 4.0)

    glow = np.exp(-((xs / 0.58) ** 2 + ((ys - wl * 0.88) / 0.16) ** 2))
    sky_r = sky_r + 44.0 * glow
    sky_g = sky_g + 56.0 * glow
    sky_b = sky_b + 42.0 * glow

    sea_t = np.clip((ys - wl) / max(0.01, 1.0 - wl), 0.0, 1.0)
    sea_r = 22.0 * (1.0 - sea_t * 0.72) + 6.0 * sea_t
    sea_g = 108.0 * ((1.0 - sea_t) ** 1.35) + 18.0 * sea_t
    sea_b = 148.0 * ((1.0 - sea_t) ** 1.1) + 40.0 * sea_t

    img[:, :, 2] = sky_r * sky_blend + sea_r * sea_blend
    img[:, :, 1] = sky_g * sky_blend + sea_g * sea_blend
    img[:, :, 0] = sky_b * sky_blend + sea_b * sea_blend
    bgr = np.clip(img, 0, 255).astype(np.uint8)

    # Subtle twilight stars high in upper sky only
    rng = np.random.default_rng(42)
    for _ in range(32):
        sx = int(rng.integers(40, w - 40))
        sy = int(rng.integers(140, int(waterline_y * 0.58)))
        sr = int(rng.choice([1, 1, 2]))
        bright = int(rng.integers(150, 230))
        cv2.circle(bgr, (sx, sy), sr, (bright, bright, min(255, bright + 8)), -1, lineType=cv2.LINE_AA)
    return bgr


@register_scene("ep02_submersible_implosion_physics")
class SubmersibleImplosionScene(EpisodeScene):
    """Articulated 12-beat True 3D Submarines + Crash-Test Dummy ('UNIT-01') scene."""

    slug = "ep02_submersible_implosion_physics"
    episode_id = "ep02"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_ocean_bgr: np.ndarray | None = None
        self.bg_alert_bgr: np.ndarray | None = None
        self.bg_safe_bgr: np.ndarray | None = None
        self.bg_surface_bgr: np.ndarray | None = None
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
        self.bg_ocean_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.cyan, ocean_gradient=True)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_alert_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.danger, ocean_gradient=True)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_safe_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.emerald, ocean_gradient=True)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_surface_bgr = _build_surface_background_bgr(w, h, waterline_y=1135)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_yellow_submarine(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        t: float = 0.0,
        prop_speed: float = 18.0,
        with_pilot: bool = True,
        pilot_pose: str = "pilot_sub",
        pilot_emotion: str = "curious",
        headlights: bool = True,
        bubbles: bool = True,
        enclosed_canopy: bool = True,
    ) -> None:
        """Detailed Z-fight-free 3D Yellow Research Submarine with clear hydroplanes & enclosed glass dome canopy."""
        R = rot_matrix(0.0, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Smooth 22-segment teardrop yellow fuselage (ZERO duplicate overlapping mid-hull cylinders -> ZERO Z-fighting!)
        hull_profile = [
            (0.88, 0.56),
            (0.28, 0.64),
            (-0.48, 0.56),
            (-1.22, 0.36),
            (-1.72, 0.14),
        ]
        for (x0, r0), (x1, r1) in zip(hull_profile[:-1], hull_profile[1:]):
            sc.add_cylinder(
                _p(x0, 0.0, 0.0),
                _p(x1, 0.0, 0.0),
                r0 * scale,
                r1 * scale,
                SUB_YELLOW,
                segments=22,
                metallic=0.45,
                caps=False,
            )
        # Single clean non-overlapping navy racing collar ring at forward hull shoulder
        sc.add_cylinder(_p(0.66, 0.0, 0.0), _p(0.52, 0.0, 0.0), 0.605 * scale, 0.625 * scale, SUB_NAVY, segments=22, metallic=0.45, caps=False)

        # Glossy rounded yellow bow nose + sapphire panoramic front viewport + brass bezel
        sc.add_sphere(_p(0.88, 0.0, 0.0), 0.56 * scale, SUB_YELLOW, metallic=0.48)
        sc.add_cylinder(_p(1.22, 0.02, 0.0), _p(1.34, 0.02, 0.0), 0.35 * scale, 0.31 * scale, BRASS, segments=18, metallic=0.76)
        sc.add_sphere(_p(1.30, 0.02, 0.0), 0.28 * scale, GLASS_BLUE, metallic=0.75, rim_rgb=CYAN)

        # Side brass-rimmed glowing cyan portholes (100% clear of diving planes!)
        for px, pr in ((0.22, 0.15), (-0.30, 0.14)):
            sc.add_sphere(_p(px, 0.08, 0.56), pr * 1.18 * scale, BRASS, metallic=0.76)
            sc.add_sphere(_p(px, 0.08, 0.61), pr * 0.85 * scale, CYAN, metallic=0.35, emissive=0.45)

        # Raised yellow conning tower + brass pressure collar ring
        sc.add_cylinder(_p(0.10, 0.42, 0.0), _p(0.06, 0.78, 0.0), 0.42 * scale, 0.38 * scale, SUB_YELLOW, segments=20, metallic=0.48)
        sc.add_cylinder(_p(0.06, 0.75, 0.0), _p(0.06, 0.83, 0.0), 0.41 * scale, 0.41 * scale, BRASS, segments=20, metallic=0.78)
        # Chrome periscope mast + glowing cyan sonar beacon behind pilot
        sc.add_cylinder(_p(-0.42, 0.52, 0.0), _p(-0.42, 1.32, 0.0), 0.050 * scale, 0.046 * scale, STEEL_LIGHT, segments=10, metallic=0.82)
        sc.add_cylinder(_p(-0.42, 1.30, 0.0), _p(-0.16, 1.30, 0.0), 0.054 * scale, 0.062 * scale, STEEL_LIGHT, segments=10, metallic=0.82)
        sc.add_sphere(_p(-0.14, 1.30, 0.0), 0.078 * scale, CYAN, emissive=0.75, bloom=True)

        # Bow diving planes (hydroplanes) moved forward-low so they NEVER clip side portholes!
        for sz in (-1, 1):
            sc.add_box(_p(0.74, -0.18, sz * 0.68), (0.36 * scale, 0.065 * scale, 0.34 * scale), SUB_YELLOW_DARK, rot=(0.0, yaw, pitch), metallic=0.52)

        # Tail rudder fins
        sc.add_box(_p(-1.46, 0.34, 0.0), (0.48 * scale, 0.46 * scale, 0.07 * scale), SUB_YELLOW_DARK, rot=(0.0, yaw, pitch - 0.18), metallic=0.52)
        sc.add_box(_p(-1.46, -0.30, 0.0), (0.44 * scale, 0.36 * scale, 0.07 * scale), SUB_YELLOW_DARK, rot=(0.0, yaw, pitch + 0.16), metallic=0.52)
        sc.add_box(_p(-1.48, 0.0, 0.0), (0.38 * scale, 0.07 * scale, 0.88 * scale), SUB_NAVY, rot=(0.0, yaw, pitch), metallic=0.58)

        # Shrouded rear prop nozzle + spinning 4-blade brass propeller!
        sc.add_cylinder(_p(-1.66, 0.0, 0.0), _p(-1.86, 0.0, 0.0), 0.28 * scale, 0.24 * scale, STEEL_DARK, segments=16, metallic=0.72, caps=False)
        sc.add_sphere(_p(-1.84, 0.0, 0.0), 0.11 * scale, BRASS, metallic=0.78)
        spin = t * prop_speed
        for b_idx in range(4):
            ba = spin + b_idx * (math.pi * 0.5)
            by = math.cos(ba) * 0.28
            bz = math.sin(ba) * 0.28
            sc.add_cylinder(_p(-1.85, 0.0, 0.0), _p(-1.90, by, bz), 0.036 * scale, 0.068 * scale, AMBER, segments=8, metallic=0.72)

        # Landing skids beneath belly
        for sz in (-1, 1):
            sc.add_cylinder(_p(0.66, -0.74, sz * 0.34), _p(-0.76, -0.74, sz * 0.34), 0.055 * scale, 0.055 * scale, STEEL_DARK, segments=10, metallic=0.74)
            sc.add_cylinder(_p(0.36, -0.52, sz * 0.26), _p(0.36, -0.74, sz * 0.34), 0.040 * scale, 0.040 * scale, STEEL_MID, segments=8, metallic=0.70)
            sc.add_cylinder(_p(-0.42, -0.48, sz * 0.26), _p(-0.42, -0.74, sz * 0.34), 0.040 * scale, 0.040 * scale, STEEL_MID, segments=8, metallic=0.70)

        if headlights:
            for sz in (-1, 1):
                sc.add_sphere(_p(1.18, -0.26, sz * 0.34), 0.095 * scale, (255, 248, 195), emissive=0.78, bloom=True)

        if bubbles:
            for bi in range(5):
                phase = (t * 2.4 + bi * 0.20) % 1.0
                bx = -1.98 - phase * 0.85  # Compact trail so bubbles never overlap left depth ruler!
                by = math.sin(t * 6.0 + bi * 1.9) * 0.14 + phase * 0.42
                bz = math.cos(t * 5.0 + bi * 1.4) * 0.12
                br = (0.085 - 0.04 * phase) * scale
                sc.add_sphere(_p(bx, by, bz), br, (185, 242, 255), metallic=0.20, emissive=0.35, rim_rgb=CYAN)

        # Seated BOLT inside the conning cockpit (show_legs=False -> ZERO clipping!) + translucent pressure glass dome when underwater!
        if with_pilot:
            pilot_pos = _p(0.06, 0.72, 0.0)
            add_crash_test_dummy(
                sc,
                pos=pilot_pos,
                scale=0.46 * scale,
                yaw=yaw + 0.48,
                tilt_z=pitch * 0.85,
                pose=pilot_pose,
                emotion=pilot_emotion,
                t=t,
                ground_shadow=False,
                show_legs=False,
            )
            if enclosed_canopy:
                # Translucent sapphire pressure bubble canopy enclosing BOLT at 3,800m depth!
                sc.add_cylinder(_p(0.06, 0.82, 0.0), _p(0.06, 1.34, 0.0), 0.40 * scale, 0.24 * scale, GLASS_BLUE, segments=20, metallic=0.80, alpha=0.28, caps=False)
                sc.add_cylinder(_p(0.06, 1.32, 0.0), _p(0.06, 1.37, 0.0), 0.24 * scale, 0.12 * scale, CYAN, segments=16, metallic=0.80, alpha=0.32)

    def _add_3d_composite_hull(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        half_len: float = 1.25,
        radius: float = 0.78,
        seam_stress: float = 0.5,
        buckling: float = 0.0,
        cutaway_dummy: bool = False,
        dummy_pose: str = "panic_freefall",
        dummy_emotion: str = "panic",
        t: float = 0.0,
    ) -> None:
        """Detailed 3D deep-sea Composite Submersible with hatch/skids physically tethered during buckling collapse."""
        cx, cy, cz = center
        s = radius / 0.80
        # Effective mid-hull radius under buckling so dorsal hatch & skids NEVER detach/float in mid-air!
        mid_r = radius * (1.0 - buckling * 0.45)

        # 1. Tapered white fiberglass tail fairing + stabilizer fins
        tail_x0 = cx - half_len - 0.12 * s
        tail_x1 = cx - half_len - 0.78 * s
        tail_x2 = cx - half_len - 1.30 * s
        sc.add_cylinder((tail_x0, cy, cz), (tail_x1, cy, cz), radius * 0.90, radius * 0.56, HULL_WHITE, segments=18, metallic=0.62, caps=False)
        sc.add_cylinder((tail_x1, cy, cz), (tail_x2, cy, cz), radius * 0.56, radius * 0.16, HULL_WHITE, segments=18, metallic=0.62)
        sc.add_box((tail_x1 - 0.20 * s, cy + 0.42 * s, cz), (0.50 * s, 0.46 * s, 0.07 * s), STEEL_LIGHT, rot=(0.0, 0.0, -0.22), metallic=0.68)
        sc.add_box((tail_x1 - 0.18 * s, cy - 0.34 * s, cz), (0.44 * s, 0.34 * s, 0.07 * s), STEEL_MID, rot=(0.0, 0.0, 0.18), metallic=0.64)
        sc.add_box((tail_x1 - 0.16 * s, cy, cz), (0.40 * s, 0.07 * s, 1.00 * s), STEEL_DARK, metallic=0.66)

        # 2. Twin side-mounted shrouded electric thruster pods
        for sz in (-1, 1):
            tx = cx - half_len - 0.24 * s
            tz = cz + sz * (radius + 0.25 * s)
            sc.add_cylinder((tx + 0.24 * s, cy, tz), (tx - 0.26 * s, cy, tz), 0.16 * s, 0.14 * s, STEEL_DARK, segments=14, metallic=0.74)
            sc.add_cylinder((tx + 0.02 * s, cy, cz + sz * radius * 0.7), (tx + 0.02 * s, cy, tz), 0.052 * s, 0.052 * s, STEEL_MID, segments=8, metallic=0.72)
            sc.add_sphere((tx - 0.26 * s, cy, tz), 0.090 * s, CYAN, emissive=0.65, bloom=True)

        # 3. Tubular titanium landing skids tethered cleanly to buckled hull!
        skid_y = cy - mid_r - 0.24 * s
        for sz in (-1, 1):
            sk_z = cz + sz * (radius * 0.58)
            sc.add_cylinder((cx + half_len + 0.30 * s, skid_y, sk_z), (cx - half_len - 0.68 * s, skid_y, sk_z), 0.062 * s, 0.062 * s, STEEL_DARK, segments=10, metallic=0.76)
            for sx in (-0.65, 0.65):
                sc.add_cylinder((cx + sx * half_len, cy - mid_r * 0.85, cz + sz * radius * 0.38), (cx + sx * half_len, skid_y, sk_z), 0.046 * s, 0.046 * s, STEEL_MID, segments=8, metallic=0.72)

        # 4. Top dorsal conning hatch + sonar mast firmly attached to mid_r (NEVER floats during implosion!)
        sc.add_box((cx + 0.08 * s, cy + mid_r + 0.10 * s, cz), (0.64 * s, 0.22 * s, 0.42 * s), HULL_WHITE, metallic=0.64)
        sc.add_cylinder((cx - 0.08 * s, cy + mid_r + 0.20 * s, cz), (cx - 0.08 * s, cy + mid_r + 0.48 * s, cz), 0.040 * s, 0.040 * s, STEEL_LIGHT, segments=8, metallic=0.78)
        sc.add_sphere((cx - 0.08 * s, cy + mid_r + 0.50 * s, cz), 0.072 * s, DANGER if seam_stress > 0.6 else CYAN, emissive=0.80, bloom=True)

        # 5. Aft & bow titanium hemispherical end domes + bolted front viewport
        sc.add_sphere((cx - half_len, cy, cz), radius * 0.96, STEEL_MID, metallic=0.78)
        sc.add_sphere((cx + half_len, cy, cz), radius * 0.96, HULL_WHITE, metallic=0.74)
        vx = cx + half_len + radius * 0.80
        sc.add_cylinder((vx - 0.14 * s, cy, cz), (vx + 0.04 * s, cy, cz), radius * 0.44, radius * 0.38, STEEL_DARK, segments=16, metallic=0.80)
        sc.add_sphere((vx - 0.02 * s, cy, cz), radius * 0.34, GLASS_BLUE, metallic=0.78, rim_rgb=CYAN)
        sc.add_sphere((cx + half_len + 0.34 * s, cy - radius * 0.45, cz + 0.32 * s), 0.085 * s, (255, 245, 195), emissive=0.75, bloom=True)

        # 6. Bonded titanium-to-carbon end rings (pulsing crimson under seam stress)
        ring_col = lerp_color(BRASS, DANGER, clamp(seam_stress))
        for sx in (-1, 1):
            rx0 = cx + sx * (half_len - 0.14)
            rx1 = cx + sx * (half_len + 0.07)
            sc.add_cylinder(
                (rx0, cy, cz),
                (rx1, cy, cz),
                radius * 1.06,
                radius * 1.06,
                ring_col,
                segments=22,
                metallic=0.74,
                emissive=0.40 * clamp(seam_stress),
                bloom=(seam_stress > 0.45),
            )

        # 7. Segmented 3D carbon-fiber tube with fine carbon-weave PBR texture
        n_seg = 8
        body_col = lerp_color(CARBON_DARK, DANGER, buckling * 0.42)
        alpha = 0.40 if cutaway_dummy else 1.0
        for i in range(n_seg):
            u0 = i / n_seg
            u1 = (i + 1) / n_seg
            x0 = cx - half_len + 0.12 + u0 * (2.0 * (half_len - 0.12))
            x1 = cx - half_len + 0.12 + u1 * (2.0 * (half_len - 0.12))
            r0 = radius * (1.0 - buckling * 0.56 * (math.sin(u0 * math.pi) ** 1.4))
            r1 = radius * (1.0 - buckling * 0.56 * (math.sin(u1 * math.pi) ** 1.4))
            sc.add_cylinder(
                (x0, cy, cz),
                (x1, cy, cz),
                r0,
                r1,
                body_col,
                segments=22,
                metallic=0.52,
                caps=False,
                alpha=alpha,
                texture="carbon_weave" if not cutaway_dummy else None,
            )

        if cutaway_dummy:
            add_crash_test_dummy(sc, pos=(cx, cy - 0.14, cz + 0.05), scale=0.52 * s, yaw=-0.15, pose=dummy_pose, emotion=dummy_emotion, t=t, ground_shadow=False, show_legs=False)

    def _add_3d_radial_pressure_ring(
        self,
        sc: Scene3D,
        center: tuple[float, float, float],
        r_out: float,
        r_in: float,
        count: int,
        rgb: tuple[int, int, int],
        t: float,
    ) -> None:
        cx, cy, cz = center
        for i in range(count):
            ang = (2.0 * math.pi * i) / count
            pulse = 0.06 * math.sin(t * 7.0 + i * 0.6)
            p0 = (cx + math.cos(ang) * (r_out + pulse), cy + math.sin(ang) * (r_out * 0.85 + pulse), cz + 0.12 * math.sin(ang))
            p1 = (cx + math.cos(ang) * (r_in + pulse), cy + math.sin(ang) * (r_in * 0.85 + pulse), cz + 0.12 * math.sin(ang))
            sc.add_arrow_3d(p0, p1, rgb, shaft_r=0.050, head_r=0.125)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float, is_cover: bool = False) -> tuple[np.ndarray, list]:
        p = self.palette
        assert (
            p is not None
            and self.bg_ocean_bgr is not None
            and self.bg_alert_bgr is not None
            and self.bg_safe_bgr is not None
            and self.bg_surface_bgr is not None
        )
        overlays_2d: list = []

        if scene_key == "verdict_cta_card":
            bg = self.bg_surface_bgr
        elif scene_key in ("hull_pressure_peak", "ply_shear_fatigue", "dimple_instability", "implosion_wave_020ms", "air_compression_pulse"):
            bg = self.bg_alert_bgr
        elif scene_key == "sphere_uniform_stress":
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_ocean_bgr

        shake = math.sin(t * 60.0) * 0.055 if (scene_key in ("hull_pressure_peak", "implosion_wave_020ms", "air_compression_pulse") and not is_cover) else 0.0

        if scene_key == "hull_pressure_peak":
            # FRAME 0 HERO: All 12 crush arrows strictly INSIDE horizontal frame + cover framed cleanly below headline!
            if is_cover:
                cam = Camera3D(eye=(1.25, 0.78, 7.10), target=(0.0, 0.56, 0.0), fov_deg=41.0, cy_offset=45.0)
            else:
                cam = Camera3D(eye=(1.25 + math.sin(t * 1.2) * 0.26 + shake, 0.72, 6.65), target=(-0.05, -0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.35, span=7.0, step=1.0, rgb=(22, 48, 84), t=t, underwater=True)
            self._add_3d_composite_hull(
                sc,
                center=(0.08, -0.05, 0.0),
                half_len=0.98,
                radius=0.68,
                seam_stress=0.92,
                buckling=0.10 + 0.05 * math.sin(t * 14.0),
                cutaway_dummy=True,
                dummy_pose="panic_freefall",
                dummy_emotion="panic",
                t=t,
            )
            self._add_3d_radial_pressure_ring(sc, (0.04, -0.05, 0.0), 1.98, 1.26, 12, DANGER, t)
            if not is_cover:
                overlays_2d.append(lambda d: draw_sparks(d, 385, 1005, t, 10, 85, 85, p, seed=19))
                overlays_2d.append(lambda d: draw_sparks(d, 705, 1005, t, 10, 85, 85, p, seed=29))

        elif scene_key == "depth_3800m_scale":
            # UNIT-01 diving inside his ENCLOSED-CANOPY Yellow Submarine (ZERO Z-fighting, clear depth ruler!)
            cam = Camera3D(eye=(1.35, 0.58, 6.55), target=(0.0, -0.10, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.45, span=7.0, step=1.0, rgb=(20, 48, 84), t=t, underwater=True)
            sub_y = 0.85 - ease_out_cubic(prog) * 1.78
            self._add_3d_yellow_submarine(
                sc,
                center=(0.68, sub_y, 0.0),
                scale=0.84,
                yaw=-0.22,
                pitch=-0.18 + 0.05 * math.sin(t * 4.0),
                t=t,
                prop_speed=22.0,
                with_pilot=True,
                pilot_pose="pilot_sub",
                pilot_emotion="curious",
                enclosed_canopy=True,
            )
            sc.add_arrow_3d((0.78, sub_y + 2.02, 0.0), (0.78, sub_y + 1.38, 0.0), CYAN, shaft_r=0.068, head_r=0.16)

            def _depth_ruler(d: ImageDraw.ImageDraw) -> None:
                rx = 110
                d.line([(rx, 680), (rx, 1300)], fill=p.cyan, width=4)
                f = load_font(self.font_bold, 24)
                for idx, lbl in enumerate(("0 M", "1,000 M", "2,000 M", "3,000 M", "3,800 M")):
                    ry = 695 + idx * 148
                    col = p.text_highlight if idx == 4 else p.steel_light
                    d.line([(rx - 14, ry), (rx + 16, ry)], fill=col, width=3)
                    d.text((rx + 24, ry - 14), lbl, font=f, fill=col, stroke_width=3, stroke_fill=p.ink)

            overlays_2d.append(_depth_ruler)

        elif scene_key == "pressure_stack_arrows":
            # Enclosed Yellow Submarine + non-clipping pressure arrows + 380 ATM dial strictly matching badge inside safe zone!
            cam = Camera3D(eye=(-1.10, 0.62, 6.75), target=(0.20, -0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, rgb=(20, 48, 84), t=t, underwater=True)
            self._add_3d_yellow_submarine(
                sc,
                center=(-0.38, -0.18, 0.0),
                scale=0.68,
                yaw=0.18,
                pitch=-0.06 + math.sin(t * 10.0) * 0.03,
                t=t,
                prop_speed=24.0,
                with_pilot=True,
                pilot_pose="brace_impact",
                pilot_emotion="brace",
                enclosed_canopy=True,
            )
            self._add_3d_radial_pressure_ring(sc, (-0.38, -0.14, 0.0), 2.02, 1.38, 10, CYAN, t)
            # Reaches full 380 ATM cleanly by prog=0.45 so badge ("380 ATM") and dial NEVER contradict!
            atm = int(round(80 + ease_out_cubic(clamp(prog * 2.2)) * 300))
            overlays_2d.append(
                lambda d, _a=atm: draw_pressure_gauge(
                    d, 745, 1175, 108, clamp(_a / 380.0), "PRESSURE", f"{_a} ATM", p, self.font_black
                )
            )

        elif scene_key == "tonnage_per_sqft":
            # Realistically proportioned 1 SQ FT steel test plate + crisp dark pill readout (zero whiteout illegibility!)
            cam = Camera3D(eye=(2.1, 1.40, 5.95), target=(0.0, -0.1, 0.0), fov_deg=40.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.85, span=7.0, step=1.0, rgb=(22, 48, 84), t=t, underwater=True)
            sc.add_box((0.58, -1.28, 0.0), (1.52, 0.34, 1.52), STEEL_LIGHT, metallic=0.76)
            for ox in (-0.52, 0.0, 0.52):
                sc.add_arrow_3d((0.58 + ox, 1.65, 0.0), (0.58 + ox, -0.92, 0.0), DANGER if ox == 0.0 else AMBER, shaft_r=0.072, head_r=0.17)
            add_crash_test_dummy(sc, pos=(-1.45, -0.68, 0.55), scale=0.80, yaw=0.38, pose="point_right", emotion="shock", t=t)

            def _ton_lbl(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 36)
                lbl = "400 TONS / 1 SQ FT"
                bb = d.textbbox((0, 0), lbl, font=f)
                tw = bb[2] - bb[0]
                bx0 = 490 - tw // 2
                d.rounded_rectangle([bx0 - 22, 1255, bx0 + tw + 22, 1318], radius=14, fill=p.surface_panel, outline=p.danger, width=3)
                d.text((bx0, 1266), lbl, font=f, fill=p.text_highlight)

            overlays_2d.append(_ton_lbl)

        elif scene_key == "sphere_uniform_stress":
            # Machined titanium deep-sea bathysphere with bolted equatorial weld flange + recessed viewport (NOT a Pokéball!)
            cam = Camera3D(eye=(-1.38, 0.72, 6.25), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(22, 54, 82), t=t, underwater=True)
            sc.add_sphere((0.58, 0.25, 0.0), 0.92, STEEL_LIGHT, metallic=0.84, rim_rgb=EMERALD)
            # Bolted titanium equator weld collar + radial studs
            sc.add_cylinder((0.58, 0.19, 0.0), (0.58, 0.31, 0.0), 0.96, 0.96, STEEL_MID, segments=26, metallic=0.82)
            for bi in range(12):
                ba = bi * (2.0 * math.pi / 12.0)
                sc.add_sphere((0.58 + math.cos(ba) * 0.95, 0.25, math.sin(ba) * 0.95), 0.045, BRASS, metallic=0.80)
            # Small realistic thick acrylic viewport bezel (offset slightly up)
            sc.add_cylinder((0.58, 0.42, 0.72), (0.58, 0.42, 0.94), 0.28, 0.24, STEEL_DARK, segments=18, metallic=0.82)
            sc.add_sphere((0.58, 0.42, 0.88), 0.20, GLASS_BLUE, metallic=0.78, rim_rgb=CYAN)
            self._add_3d_radial_pressure_ring(sc, (0.58, 0.25, 0.0), 1.78, 1.12, 10, EMERALD, t)
            add_crash_test_dummy(sc, pos=(-1.46, -0.88, 0.65), scale=0.72, yaw=0.36, pose="point_right", emotion="relief", t=t)

            def _unif_lbl(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_bold, 28)
                lbl = "UNIFORM MEMBRANE STRESS"
                bb = d.textbbox((0, 0), lbl, font=f)
                tw = bb[2] - bb[0]
                bx0 = 490 - tw // 2
                d.rounded_rectangle([bx0 - 20, 1295, bx0 + tw + 20, 1348], radius=12, fill=p.surface_panel, outline=p.emerald, width=3)
                d.text((bx0, 1306), lbl, font=f, fill=p.emerald)

            overlays_2d.append(_unif_lbl)

        elif scene_key == "cylinder_joint_hotspot":
            # CRITICAL FIX: BOTH red hotspot arrows point DIRECTLY at the left & right titanium-to-carbon bonded end rings!
            cam = Camera3D(eye=(1.35, 0.82, 6.85), target=(0.0, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, rgb=(22, 48, 84), t=t, underwater=True)
            pulse = 0.55 + 0.45 * math.sin(t * 9.0)
            sub_cx, sub_hl = 0.45, 0.88
            self._add_3d_composite_hull(sc, center=(sub_cx, 0.14, 0.0), half_len=sub_hl, radius=0.58, seam_stress=pulse)
            # Left bonded ring = sub_cx - sub_hl = -0.43; Right bonded ring = sub_cx + sub_hl = +1.33!
            sc.add_arrow_3d((sub_cx - sub_hl, 1.58, 0.12), (sub_cx - sub_hl, 0.86, 0.12), DANGER, shaft_r=0.068, head_r=0.165)
            sc.add_arrow_3d((sub_cx + sub_hl, 1.58, 0.12), (sub_cx + sub_hl, 0.86, 0.12), DANGER, shaft_r=0.068, head_r=0.165)
            add_crash_test_dummy(sc, pos=(-1.55, -0.86, 0.65), scale=0.68, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "ply_shear_fatigue":
            # Compression arrows move dynamically OUTSIDE the expanding carbon plies (ZERO arrow piercing!)
            cam = Camera3D(eye=(2.05, 1.20, 6.20), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(24, 46, 78), t=t, underwater=True)
            n_plies = 7
            exp_p = ease_in_out_cubic(prog)
            max_y = 0.0
            for i in range(n_plies):
                sep = (i - 3.0) * exp_p * 0.14
                py = (i - 3.0) * 0.30 + sep
                max_y = max(max_y, abs(py))
                col = CARBON_DARK if i % 2 == 0 else STEEL_DARK
                sc.add_box((0.62, py, 0.0), (2.55, 0.19, 1.38), col, metallic=0.48, texture="carbon_weave")
                if i in (2, 4) and prog > 0.2:
                    crack_w = clamp((prog - 0.2) * 1.4) * 2.25
                    sc.add_box((0.62 - 1.12 + crack_w * 0.5, py + 0.12, 0.70), (crack_w, 0.045, 0.06), DANGER, emissive=0.65, bloom=True)
            arrow_tip_y = max_y + 0.22
            sc.add_arrow_3d((0.62, arrow_tip_y + 0.85, 0.2), (0.62, arrow_tip_y, 0.2), AMBER, shaft_r=0.075, head_r=0.18)
            sc.add_arrow_3d((0.62, -(arrow_tip_y + 0.85), 0.2), (0.62, -arrow_tip_y, 0.2), AMBER, shaft_r=0.075, head_r=0.18)
            add_crash_test_dummy(sc, pos=(-1.38, -0.82, 0.65), scale=0.68, yaw=0.38, pose="brace_impact", emotion="shock", t=t)

        elif scene_key == "dimple_instability":
            # Smooth continuous connected buckled carbon shell (28 seamless overlapping lofted segments, ZERO detached Lego bricks!)
            dimple = ease_out_cubic(clamp((prog - 0.25) / 0.62))
            cam = Camera3D(eye=(-1.45 + shake * dimple, 0.82, 5.95), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(24, 46, 78), t=t, underwater=True)

            def _wall_y(u: float) -> float:
                return 0.24 + math.sin(u * math.pi) * 0.42 - math.exp(-((u - 0.5) / 0.16) ** 2) * dimple * 0.96

            n_seg = 26
            for i in range(n_seg):
                u0 = i / n_seg
                u1 = (i + 1) / n_seg
                um = 0.5 * (u0 + u1)
                x0, x1 = -0.82 + u0 * 2.80, -0.82 + u1 * 2.80
                y0, y1 = _wall_y(u0), _wall_y(u1)
                seg_len = math.hypot(x1 - x0, y1 - y0) + 0.04
                slope = math.atan2(y1 - y0, x1 - x0)
                heat = math.exp(-((um - 0.5) / 0.16) ** 2) * dimple
                col = lerp_color(CARBON_DARK, DANGER, heat * 0.85)
                sc.add_box(
                    (0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.0),
                    (seg_len, 0.24, 1.32),
                    col,
                    rot=(0.0, 0.0, slope),
                    metallic=0.58,
                    emissive=0.35 * heat,
                    texture="carbon_weave",
                    bloom=(heat > 0.45),
                )
            sc.add_arrow_3d((0.58, 2.05 - dimple * 0.45, 0.15), (0.58, 0.95 - dimple * 0.82, 0.15), DANGER, shaft_r=0.082, head_r=0.19)
            add_crash_test_dummy(sc, pos=(-1.38, -0.88, 0.65), scale=0.68, yaw=0.36, pose="brace_impact", emotion="brace", t=t)

        elif scene_key == "implosion_wave_020ms":
            # Composite sub violently imploding with hatch & skids physically attached + strictly in-frame arrows!
            collapse = ease_in_out_cubic(clamp(prog * 1.15))
            cam = Camera3D(eye=(1.25 + shake, 0.65, 6.85), target=(0.05, 0.0, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, rgb=(24, 44, 76), t=t, underwater=True)
            self._add_3d_composite_hull(
                sc,
                center=(0.52, 0.24, 0.0),
                half_len=0.92 * (1.0 - 0.30 * collapse),
                radius=0.62 * (1.0 - 0.38 * collapse),
                seam_stress=1.0,
                buckling=clamp(0.18 + collapse * 0.82),
            )
            self._add_3d_radial_pressure_ring(sc, (0.48, 0.24, 0.0), 1.88 - 0.42 * collapse, 1.12 - 0.38 * collapse, 10, DANGER, t * 2.0)
            add_crash_test_dummy(sc, pos=(-1.52, -0.92, 0.65), scale=0.66, yaw=0.38, pose="panic_freefall", emotion="shock", t=t)
            ms = min(20.0, prog * 22.0)

            def _ms_badge(d: ImageDraw.ImageDraw) -> None:
                if collapse > 0.4:
                    draw_sparks(d, 600, 920, t, 20, 195, 145, p, seed=131)
                f = load_font(self.font_black, 40)
                label = f"T + {ms:04.1f} MS"
                bb = d.textbbox((0, 0), label, font=f)
                cx_b = 540
                d.rounded_rectangle([cx_b - 165, 1285, cx_b + 165, 1354], radius=14, fill=p.surface_panel, outline=p.danger, width=4)
                d.text((cx_b - (bb[2] - bb[0]) / 2, 1296), label, font=f, fill=p.text_highlight)

            overlays_2d.append(_ms_badge)

        elif scene_key == "air_compression_pulse":
            # Hydrodynamic water wall rushing inward into an adiabatic core (NO whiteout fried-egg blob!)
            squeeze = ease_out_cubic(prog)
            cam = Camera3D(eye=(shake, 0.55, 6.25), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, rgb=(24, 44, 76), t=t, underwater=True)
            core_r = max(0.24, 0.72 * (1.0 - 0.62 * squeeze))
            # Translucent collapsing deep-sea water torus wall rushing inward
            water_r = 1.48 - squeeze * 0.62
            for wi in range(16):
                wa = wi * (2.0 * math.pi / 16.0) + t * 0.8
                sc.add_sphere((0.42 + math.cos(wa) * water_r, 0.25 + math.sin(wa) * water_r * 0.85, 0.0), 0.20, GLASS_BLUE, metallic=0.45, rim_rgb=CYAN)
            # Compact adiabatic superheated air pocket (controlled emissive so 3D volume stays readable!)
            sc.add_sphere((0.42, 0.25, 0.0), core_r * 1.18, DANGER, metallic=0.15, emissive=0.52, rim_rgb=AMBER, bloom=True)
            sc.add_sphere((0.42, 0.25, 0.14), core_r * 0.68, AMBER, metallic=0.12, emissive=0.68, bloom=True)
            self._add_3d_radial_pressure_ring(sc, (0.42, 0.25, 0.0), 1.85, water_r + 0.18, 8, CYAN, t * 2.6)
            add_crash_test_dummy(sc, pos=(-1.45, -0.92, 0.65), scale=0.68, yaw=0.35, pose="brace_impact", emotion="shock", t=t)

            def _comp_lbl(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 32)
                lbl = "ADIABATIC COMPRESSION"
                bb = d.textbbox((0, 0), lbl, font=f)
                tw = bb[2] - bb[0]
                bx0 = 510 - tw // 2
                d.rounded_rectangle([bx0 - 18, 1288, bx0 + tw + 18, 1344], radius=12, fill=p.surface_panel, outline=p.amber, width=3)
                d.text((bx0, 1298), lbl, font=f, fill=p.text_highlight)

            overlays_2d.append(_comp_lbl)

        elif scene_key == "nerve_bar_comparison":
            # Unobstructed BOLT on left + mathematically exact 12.5X FASTER + safe-zone bars strictly inside x <= 860!
            cam = Camera3D(eye=(0.25, 0.35, 6.20), target=(0.0, -0.25, 0.0), fov_deg=41.0, cy_offset=95.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, rgb=(22, 48, 84), t=t, underwater=True)
            add_crash_test_dummy(sc, pos=(-1.62, -0.45, 0.48), scale=0.68, yaw=0.40, pose="point_right", emotion="curious", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=320,
                    y0=715,
                    width=540,
                    height=355,
                    items=[
                        ("HULL IMPLOSION", "20 MS", 20.0 / 250.0, p.danger),
                        ("HUMAN VISUAL NERVE", "250 MS", 1.0, p.cyan),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([320, 1105, 860, 1188], radius=16, fill=p.surface_panel, outline=p.text_highlight, width=4)
                f = load_font(self.font_black, 24)
                msg = "12.5X FASTER THAN HUMAN SIGHT"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((590 - (bb[2] - bb[0]) / 2, 1132), msg, font=f, fill=p.text_highlight)

            overlays_2d.append(_bars)

        else:  # verdict_cta_card — Clean ocean surface (ZERO black floor grid!), realistic BOLT standing dry on Yellow Sub top, waves below hull, safe-zone CTA buttons!
            cam = Camera3D(eye=(math.sin(t * 0.85) * 0.30, 0.45, 6.45), target=(0.0, 0.05, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            # NO sc.add_floor_grid in open ocean!

            def _surface_waves(d: ImageDraw.ImageDraw) -> None:
                # Waterline waves strictly at lower hull waterline (y ~ 1135, NEVER crossing BOLT's shins!)
                pts_back = []
                pts_front = []
                for x in range(0, 1081, 36):
                    yb = 1132 + int(math.sin(x * 0.014 + t * 3.8) * 10)
                    yf = 1152 + int(math.cos(x * 0.017 - t * 4.6) * 12)
                    pts_back.append((x, yb))
                    pts_front.append((x, yf))
                d.line(pts_back, fill=(72, 218, 245), width=6)
                d.line(pts_front, fill=(195, 248, 255), width=5)

                if 0.24 < prog < 0.60:
                    sp = (prog - 0.24) / 0.36
                    for si in range(16):
                        ang = -math.pi * (0.12 + 0.76 * (si / 15.0))
                        dist = (60 + (si % 4) * 28) * ease_out_cubic(sp)
                        sx = 540 + int(math.cos(ang) * dist * 1.40)
                        sy = 1136 + int(math.sin(ang) * dist + 110 * (sp ** 2))
                        sr = max(3, int((1.0 - sp) * 10))
                        d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(215, 250, 255))

            if prog < 0.40:
                rise = ease_out_cubic(prog / 0.40)
                sub_y = -2.15 + rise * 1.85
                sub_pitch = 0.72 * (1.0 - rise * 0.85)
                self._add_3d_yellow_submarine(
                    sc,
                    center=(-0.08 + rise * 0.08, sub_y, 0.0),
                    scale=0.86,
                    yaw=-0.12,
                    pitch=sub_pitch,
                    t=t,
                    prop_speed=38.0,
                    with_pilot=True,
                    pilot_pose="panic_freefall",
                    pilot_emotion="panic",
                    bubbles=True,
                    enclosed_canopy=True,
                )
            else:
                surf_t = (prog - 0.40) / 0.60
                bob = math.sin(t * 4.0) * 0.05
                self._add_3d_yellow_submarine(
                    sc,
                    center=(-0.10, -0.78 + bob, 0.0),
                    scale=0.92,
                    yaw=-0.12,
                    pitch=math.sin(t * 3.0) * 0.03,
                    t=t,
                    prop_speed=8.0,
                    with_pilot=False,
                    headlights=True,
                    bubbles=False,
                    enclosed_canopy=False,
                )
                # Realistically proportioned BOLT (scale=0.58) standing cleanly on top of the brass conning collar (y ~ +0.02, boots flush at -0.02 -> ZERO hull/periscope clipping!)
                if surf_t < 0.45:
                    hop = ease_out_cubic(surf_t / 0.45)
                    add_crash_test_dummy(
                        sc,
                        pos=(0.06, 0.56 + math.sin(hop * math.pi) * 0.30 + bob, 0.05),
                        scale=0.58,
                        yaw=0.18 * (1.0 - hop),
                        pose="sprint_escape",
                        emotion="relief",
                        t=t,
                        ground_shadow=False,
                    )
                else:
                    add_crash_test_dummy(
                        sc,
                        pos=(0.06, 0.66 + bob, 0.05),
                        scale=0.58,
                        yaw=math.sin(t * 2.0) * 0.14,
                        pose="cta_shrug",
                        emotion="cta",
                        t=t,
                        ground_shadow=False,
                    )

            overlays_2d.append(_surface_waves)
            overlays_2d.append(lambda d: draw_cta_buttons(d, t, p, self.font_black, by=1225))

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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "depth_3800m_scale"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("hull_pressure_peak", t=0.35, prog=0.45, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
