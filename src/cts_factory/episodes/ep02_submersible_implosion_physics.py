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


def _build_surface_background_bgr(w: int, h: int, waterline_y: int = 1045) -> np.ndarray:
    """Build a crisp open-air twilight sky + sunlit turquoise horizon + deep ocean backdrop (BGR)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    wl = waterline_y / float(h)

    img = np.zeros((h, w, 3), dtype=np.float32)

    # Sky above waterline (deep midnight zenith -> twilight cobalt -> luminous teal horizon)
    sky_mask = (ys < wl).astype(np.float32)
    sky_t = np.clip(ys / max(0.01, wl), 0.0, 1.0)
    sky_r = 10.0 + 38.0 * (sky_t ** 2.2) + 32.0 * (sky_t ** 5.0)
    sky_g = 22.0 + 96.0 * (sky_t ** 1.8) + 46.0 * (sky_t ** 4.5)
    sky_b = 52.0 + 115.0 * (sky_t ** 1.4) + 32.0 * (sky_t ** 4.0)

    # Soft horizon moon/sun glow centered slightly above waterline
    glow = np.exp(-((xs / 0.58) ** 2 + ((ys - wl * 0.88) / 0.16) ** 2))
    sky_r = sky_r + 48.0 * glow
    sky_g = sky_g + 62.0 * glow
    sky_b = sky_b + 45.0 * glow

    # Ocean below waterline (bright turquoise surface -> deep abyssal navy)
    sea_mask = 1.0 - sky_mask
    sea_t = np.clip((ys - wl) / max(0.01, 1.0 - wl), 0.0, 1.0)
    sea_r = 22.0 * (1.0 - sea_t * 0.72) + 6.0 * sea_t
    sea_g = 112.0 * ((1.0 - sea_t) ** 1.35) + 18.0 * sea_t
    sea_b = 152.0 * ((1.0 - sea_t) ** 1.1) + 40.0 * sea_t

    img[:, :, 2] = sky_r * sky_mask + sea_r * sea_mask  # R
    img[:, :, 1] = sky_g * sky_mask + sea_g * sea_mask  # G
    img[:, :, 0] = sky_b * sky_mask + sea_b * sea_mask  # B
    bgr = np.clip(img, 0, 255).astype(np.uint8)

    # Subtle twinkling stars in upper sky
    rng = np.random.default_rng(42)
    for _ in range(42):
        sx = int(rng.integers(40, w - 40))
        sy = int(rng.integers(140, int(waterline_y * 0.72)))
        sr = int(rng.choice([1, 1, 2]))
        bright = int(rng.integers(165, 250))
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
        self.bg_surface_bgr = _build_surface_background_bgr(w, h, waterline_y=1045)
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
    ) -> None:
        """Detailed 3D Yellow Research Submarine ridden by UNIT-01 (nose +X, tail -X, top +Y)."""
        R = rot_matrix(0.0, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Streamlined teardrop yellow fuselage (4 tapered loft rings + rounded bow)
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
                segments=18,
                metallic=0.45,
                caps=False,
            )
        # Glossy rounded yellow bow nose + sapphire panoramic front viewport + brass bezel
        sc.add_sphere(_p(0.88, 0.0, 0.0), 0.56 * scale, SUB_YELLOW, metallic=0.48)
        sc.add_cylinder(
            _p(1.22, 0.02, 0.0),
            _p(1.34, 0.02, 0.0),
            0.35 * scale,
            0.31 * scale,
            BRASS,
            segments=16,
            metallic=0.75,
        )
        sc.add_sphere(_p(1.30, 0.02, 0.0), 0.28 * scale, GLASS_BLUE, metallic=0.75, rim_rgb=CYAN)

        # Dark navy technical racing trim stripe along mid-hull
        sc.add_cylinder(_p(0.45, -0.02, 0.0), _p(-0.55, -0.02, 0.0), 0.65 * scale, 0.58 * scale, SUB_NAVY, segments=18, metallic=0.42, caps=False)
        # Center yellow band leaving twin crisp navy pinstripes
        sc.add_cylinder(_p(0.40, 0.02, 0.0), _p(-0.50, 0.02, 0.0), 0.655 * scale, 0.585 * scale, SUB_YELLOW, segments=18, metallic=0.46, caps=False)

        # Side brass-rimmed glowing cyan portholes (camera-facing side)
        for px, pr in ((0.42, 0.16), (-0.18, 0.15)):
            sc.add_sphere(_p(px, 0.06, 0.57), pr * 1.18 * scale, BRASS, metallic=0.76)
            sc.add_sphere(_p(px, 0.06, 0.62), pr * 0.86 * scale, CYAN, metallic=0.35, emissive=0.55, bloom=True)

        # Raised yellow conning tower / open-top cockpit fairing + brass hatch rim
        sc.add_cylinder(
            _p(0.10, 0.42, 0.0),
            _p(0.06, 0.84, 0.0),
            0.40 * scale,
            0.35 * scale,
            SUB_YELLOW,
            segments=16,
            metallic=0.48,
        )
        sc.add_cylinder(
            _p(0.06, 0.80, 0.0),
            _p(0.06, 0.88, 0.0),
            0.39 * scale,
            0.39 * scale,
            BRASS,
            segments=16,
            metallic=0.78,
        )
        # Chrome periscope mast + glowing cyan sonar beacon behind pilot
        sc.add_cylinder(_p(-0.34, 0.54, 0.0), _p(-0.34, 1.32, 0.0), 0.052 * scale, 0.048 * scale, STEEL_LIGHT, segments=10, metallic=0.82)
        sc.add_cylinder(_p(-0.34, 1.30, 0.0), _p(-0.08, 1.30, 0.0), 0.056 * scale, 0.066 * scale, STEEL_LIGHT, segments=10, metallic=0.82)
        sc.add_sphere(_p(-0.06, 1.30, 0.0), 0.082 * scale, CYAN, emissive=0.90, bloom=True)

        # Side diving planes (hydroplanes)
        for sz in (-1, 1):
            sc.add_box(_p(0.20, 0.04, sz * 0.72), (0.38 * scale, 0.07 * scale, 0.36 * scale), SUB_YELLOW_DARK, rot=(0.0, yaw, pitch), metallic=0.52)

        # Tail rudder fins (top & bottom vertical + horizontal stabilizers)
        sc.add_box(_p(-1.46, 0.34, 0.0), (0.48 * scale, 0.46 * scale, 0.07 * scale), SUB_YELLOW_DARK, rot=(0.0, yaw, pitch - 0.18), metallic=0.52)
        sc.add_box(_p(-1.46, -0.30, 0.0), (0.44 * scale, 0.36 * scale, 0.07 * scale), SUB_YELLOW_DARK, rot=(0.0, yaw, pitch + 0.16), metallic=0.52)
        sc.add_box(_p(-1.48, 0.0, 0.0), (0.38 * scale, 0.07 * scale, 0.88 * scale), SUB_NAVY, rot=(0.0, yaw, pitch), metallic=0.58)

        # Shrouded rear prop nozzle + spinning 4-blade brass propeller!
        sc.add_cylinder(_p(-1.66, 0.0, 0.0), _p(-1.86, 0.0, 0.0), 0.28 * scale, 0.24 * scale, STEEL_DARK, segments=14, metallic=0.72, caps=False)
        sc.add_sphere(_p(-1.84, 0.0, 0.0), 0.11 * scale, BRASS, metallic=0.78)
        spin = t * prop_speed
        for b_idx in range(4):
            ba = spin + b_idx * (math.pi * 0.5)
            by = math.cos(ba) * 0.28
            bz = math.sin(ba) * 0.28
            sc.add_cylinder(_p(-1.85, 0.0, 0.0), _p(-1.90, by, bz), 0.036 * scale, 0.068 * scale, AMBER, segments=8, metallic=0.72)

        # Heavy dark-titanium landing skids beneath the belly
        for sz in (-1, 1):
            sc.add_cylinder(_p(0.66, -0.74, sz * 0.34), _p(-0.76, -0.74, sz * 0.34), 0.055 * scale, 0.055 * scale, STEEL_DARK, segments=10, metallic=0.74)
            sc.add_cylinder(_p(0.36, -0.52, sz * 0.26), _p(0.36, -0.74, sz * 0.34), 0.040 * scale, 0.040 * scale, STEEL_MID, segments=8, metallic=0.70)
            sc.add_cylinder(_p(-0.42, -0.48, sz * 0.26), _p(-0.42, -0.74, sz * 0.34), 0.040 * scale, 0.040 * scale, STEEL_MID, segments=8, metallic=0.70)

        # Twin glowing bow LED floodlights
        if headlights:
            for sz in (-1, 1):
                sc.add_sphere(_p(1.18, -0.26, sz * 0.34), 0.10 * scale, (255, 248, 195), emissive=0.95, bloom=True)

        # Animated rising bubble trail streaming off the spinning propeller
        if bubbles:
            for bi in range(6):
                phase = (t * 2.4 + bi * 0.17) % 1.0
                bx = -1.98 - phase * 1.15
                by = math.sin(t * 6.0 + bi * 1.9) * 0.16 + phase * 0.48
                bz = math.cos(t * 5.0 + bi * 1.4) * 0.14
                br = (0.095 - 0.045 * phase) * scale
                sc.add_sphere(_p(bx, by, bz), br, (185, 242, 255), metallic=0.20, emissive=0.45, rim_rgb=CYAN)

        # UNIT-01 riding right inside the yellow submarine's open conning cockpit!
        if with_pilot:
            pilot_pos = _p(0.08, 0.86, 0.02)
            add_crash_test_dummy(
                sc,
                pos=pilot_pos,
                scale=0.58 * scale,
                yaw=yaw + 0.55,
                tilt_z=pitch * 0.85,
                pose=pilot_pose,
                emotion=pilot_emotion,
                t=t,
                ground_shadow=False,
            )

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
        """Detailed 3D deep-sea Composite Submersible (tail fairing, fins, thrusters, skids, viewport & carbon tube)."""
        cx, cy, cz = center
        s = radius / 0.80  # proportional detail scale

        # 1. Sleek tapered white/titanium fiberglass tail fairing + tail stabilizer fins (left = aft -X)
        tail_x0 = cx - half_len - 0.12 * s
        tail_x1 = cx - half_len - 0.82 * s
        tail_x2 = cx - half_len - 1.38 * s
        sc.add_cylinder((tail_x0, cy, cz), (tail_x1, cy, cz), radius * 0.90, radius * 0.56, HULL_WHITE, segments=16, metallic=0.62, caps=False)
        sc.add_cylinder((tail_x1, cy, cz), (tail_x2, cy, cz), radius * 0.56, radius * 0.16, HULL_WHITE, segments=16, metallic=0.62)
        # Vertical & horizontal tail fins
        sc.add_box((tail_x1 - 0.22 * s, cy + 0.44 * s, cz), (0.52 * s, 0.48 * s, 0.07 * s), STEEL_LIGHT, rot=(0.0, 0.0, -0.22), metallic=0.68)
        sc.add_box((tail_x1 - 0.20 * s, cy - 0.36 * s, cz), (0.46 * s, 0.36 * s, 0.07 * s), STEEL_MID, rot=(0.0, 0.0, 0.18), metallic=0.64)
        sc.add_box((tail_x1 - 0.18 * s, cy, cz), (0.42 * s, 0.07 * s, 1.05 * s), STEEL_DARK, metallic=0.66)

        # 2. Twin side-mounted shrouded electric thruster pods with glowing cyan thruster cores
        for sz in (-1, 1):
            tx = cx - half_len - 0.25 * s
            tz = cz + sz * (radius + 0.26 * s)
            sc.add_cylinder((tx + 0.24 * s, cy, tz), (tx - 0.28 * s, cy, tz), 0.16 * s, 0.14 * s, STEEL_DARK, segments=12, metallic=0.74)
            sc.add_cylinder((tx + 0.02 * s, cy, cz + sz * radius * 0.7), (tx + 0.02 * s, cy, tz), 0.055 * s, 0.055 * s, STEEL_MID, segments=8, metallic=0.72)
            sc.add_sphere((tx - 0.28 * s, cy, tz), 0.095 * s, CYAN, emissive=0.75, bloom=True)

        # 3. Heavy tubular titanium landing skids / undercarriage sled beneath the pressure hull
        skid_y = cy - radius - 0.26 * s
        for sz in (-1, 1):
            sk_z = cz + sz * (radius * 0.62)
            sc.add_cylinder((cx + half_len + 0.35 * s, skid_y, sk_z), (cx - half_len - 0.72 * s, skid_y, sk_z), 0.068 * s, 0.068 * s, STEEL_DARK, segments=10, metallic=0.76)
            for sx in (-0.65, 0.65):
                sc.add_cylinder((cx + sx * half_len, cy - radius * 0.78, cz + sz * radius * 0.42), (cx + sx * half_len, skid_y, sk_z), 0.048 * s, 0.048 * s, STEEL_MID, segments=8, metallic=0.72)

        # 4. Top dorsal conning hatch + sonar transponder beacon
        sc.add_box((cx + 0.10 * s, cy + radius + 0.14 * s, cz), (0.68 * s, 0.24 * s, 0.44 * s), HULL_WHITE, metallic=0.64)
        sc.add_cylinder((cx - 0.08 * s, cy + radius + 0.24 * s, cz), (cx - 0.08 * s, cy + radius + 0.56 * s, cz), 0.042 * s, 0.042 * s, STEEL_LIGHT, segments=8, metallic=0.78)
        sc.add_sphere((cx - 0.08 * s, cy + radius + 0.58 * s, cz), 0.078 * s, DANGER if seam_stress > 0.6 else CYAN, emissive=0.92, bloom=True)

        # 5. Aft & bow glossy titanium hemispherical end domes + bolted bow viewport window (+X = front)
        sc.add_sphere((cx - half_len, cy, cz), radius * 0.96, STEEL_MID, metallic=0.78)
        sc.add_sphere((cx + half_len, cy, cz), radius * 0.96, HULL_WHITE, metallic=0.74)
        # Bolted acrylic front viewport on the bow dome (+X) + LED spotlight
        vx = cx + half_len + radius * 0.80
        sc.add_cylinder((vx - 0.14 * s, cy, cz), (vx + 0.04 * s, cy, cz), radius * 0.44, radius * 0.38, STEEL_DARK, segments=14, metallic=0.80)
        sc.add_sphere((vx - 0.02 * s, cy, cz), radius * 0.34, GLASS_BLUE, metallic=0.78, rim_rgb=CYAN)
        sc.add_sphere((cx + half_len + 0.36 * s, cy - radius * 0.46, cz + 0.34 * s), 0.09 * s, (255, 245, 195), emissive=0.90, bloom=True)

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
                segments=20,
                metallic=0.72,
                emissive=0.45 * clamp(seam_stress),
                bloom=(seam_stress > 0.4),
            )

        # 7. Segmented 3D carbon-fiber tube with realistic twill carbon-weave PBR texture!
        n_seg = 6
        body_col = lerp_color(CARBON_DARK, DANGER, buckling * 0.45)
        alpha = 0.42 if cutaway_dummy else 1.0
        for i in range(n_seg):
            u0 = i / n_seg
            u1 = (i + 1) / n_seg
            x0 = cx - half_len + 0.12 + u0 * (2.0 * (half_len - 0.12))
            x1 = cx - half_len + 0.12 + u1 * (2.0 * (half_len - 0.12))
            r0 = radius * (1.0 - buckling * 0.62 * (math.sin(u0 * math.pi) ** 1.4))
            r1 = radius * (1.0 - buckling * 0.62 * (math.sin(u1 * math.pi) ** 1.4))
            sc.add_cylinder(
                (x0, cy, cz),
                (x1, cy, cz),
                r0,
                r1,
                body_col,
                segments=20,
                metallic=0.52,
                caps=False,
                alpha=alpha,
                texture="carbon_weave" if not cutaway_dummy else None,
            )

        if cutaway_dummy:
            add_crash_test_dummy(sc, pos=(cx, cy - 0.16, cz + 0.05), scale=0.56 * s, yaw=-0.15, pose=dummy_pose, emotion=dummy_emotion, t=t, ground_shadow=False)

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
            pulse = 0.08 * math.sin(t * 7.0 + i * 0.6)
            p0 = (cx + math.cos(ang) * (r_out + pulse), cy + math.sin(ang) * (r_out * 0.85 + pulse), cz + 0.15 * math.sin(ang))
            p1 = (cx + math.cos(ang) * (r_in + pulse), cy + math.sin(ang) * (r_in * 0.85 + pulse), cz + 0.15 * math.sin(ang))
            sc.add_arrow_3d(p0, p1, rgb, shaft_r=0.056, head_r=0.140)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float) -> tuple[np.ndarray, list]:
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

        shake = math.sin(t * 60.0) * 0.065 if scene_key in ("hull_pressure_peak", "implosion_wave_020ms", "air_compression_pulse") else 0.0

        if scene_key == "hull_pressure_peak":
            # FRAME 0 HERO: Real 3D Deep-Sea Submersible (tail fairing, fins, thrusters, skids, viewport) + UNIT-01 + 12 crush arrows!
            cam = Camera3D(eye=(1.35 + math.sin(t * 1.2) * 0.30 + shake, 0.72, 6.25), target=(-0.10, -0.04, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.35, span=7.0, step=1.0, rgb=(22, 48, 84), t=t, underwater=True)
            self._add_3d_composite_hull(
                sc,
                center=(0.15, -0.05, 0.0),
                half_len=1.08,
                radius=0.72,
                seam_stress=0.92,
                buckling=0.10 + 0.05 * math.sin(t * 14.0),
                cutaway_dummy=True,
                dummy_pose="panic_freefall",
                dummy_emotion="panic",
                t=t,
            )
            self._add_3d_radial_pressure_ring(sc, (0.05, -0.05, 0.0), 2.28, 1.38, 12, DANGER, t)
            overlays_2d.append(lambda d: draw_sparks(d, 375, 1005, t, 10, 90, 90, p, seed=19))
            overlays_2d.append(lambda d: draw_sparks(d, 720, 1005, t, 10, 90, 90, p, seed=29))

        elif scene_key == "depth_3800m_scale":
            # FUN HERO BEAT: UNIT-01 riding his OWN YELLOW SUBMARINE diving down the 3,800m abyss!
            cam = Camera3D(eye=(1.35, 0.58, 6.45), target=(0.0, -0.10, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.45, span=7.0, step=1.0, rgb=(20, 48, 84), t=t, underwater=True)
            sub_y = 0.88 - ease_out_cubic(prog) * 1.82
            self._add_3d_yellow_submarine(
                sc,
                center=(0.55, sub_y, 0.0),
                scale=0.88,
                yaw=-0.22,
                pitch=-0.20 + 0.05 * math.sin(t * 4.0),
                t=t,
                prop_speed=22.0,
                with_pilot=True,
                pilot_pose="pilot_sub",
                pilot_emotion="curious",
            )
            sc.add_arrow_3d((0.68, sub_y + 2.05, 0.0), (0.68, sub_y + 1.35, 0.0), CYAN, shaft_r=0.072, head_r=0.17)

            def _depth_ruler(d: ImageDraw.ImageDraw) -> None:
                rx = 145
                d.line([(rx, 680), (rx, 1300)], fill=p.cyan, width=4)
                f = load_font(self.font_bold, 24)
                for idx, lbl in enumerate(("0 M", "1,000 M", "2,000 M", "3,000 M", "3,800 M")):
                    ry = 695 + idx * 148
                    col = p.text_highlight if idx == 4 else p.steel_light
                    d.line([(rx - 14, ry), (rx + 16, ry)], fill=col, width=3)
                    d.text((rx + 26, ry - 14), lbl, font=f, fill=col)

            overlays_2d.append(_depth_ruler)

        elif scene_key == "pressure_stack_arrows":
            # UNIT-01 piloting his Yellow Submarine as 380 ATM hydrostatic pressure closes in from all sides!
            cam = Camera3D(eye=(-1.15, 0.62, 6.65), target=(0.25, -0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, rgb=(20, 48, 84), t=t, underwater=True)
            self._add_3d_yellow_submarine(
                sc,
                center=(-0.38, -0.22, 0.0),
                scale=0.72,
                yaw=0.18,
                pitch=-0.06 + math.sin(t * 10.0) * 0.03,
                t=t,
                prop_speed=24.0,
                with_pilot=True,
                pilot_pose="brace_impact",
                pilot_emotion="brace",
            )
            self._add_3d_radial_pressure_ring(sc, (-0.42, -0.15, 0.0), 1.88, 1.18, 10, CYAN, t)
            atm = int(round(1 + prog * 379))
            overlays_2d.append(
                lambda d, _a=atm, _p=prog: draw_pressure_gauge(
                    d, 868, 1005, 126, clamp(_p * 0.92 + 0.08), "PRESSURE", f"{_a} ATM", p, self.font_black
                )
            )

        elif scene_key == "tonnage_per_sqft":
            cam = Camera3D(eye=(2.2, 1.45, 5.75), target=(0.0, -0.1, 0.0), fov_deg=40.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.85, span=7.0, step=1.0, rgb=(22, 48, 84), t=t, underwater=True)
            # True 3D 1 FT x 1 FT steel test plate under massive 3D load vectors
            sc.add_box((0.55, -1.20, 0.0), (2.25, 0.42, 2.25), STEEL_LIGHT, metallic=0.72)
            for ox in (-0.85, -0.42, 0.0, 0.42, 0.85):
                sc.add_arrow_3d((0.55 + ox, 1.75, 0.0), (0.55 + ox, -0.82, 0.0), DANGER if abs(ox) < 0.45 else AMBER, shaft_r=0.075, head_r=0.18)
            add_crash_test_dummy(sc, pos=(-1.55, -0.68, 0.55), scale=0.84, yaw=0.38, pose="point_right", emotion="shock", t=t)

            def _ton_lbl(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 40)
                lbl = "400 TONS / 1 SQ FT"
                bb = d.textbbox((0, 0), lbl, font=f)
                d.text((540 - (bb[2] - bb[0]) / 2, 1265), lbl, font=f, fill=p.text_highlight, stroke_width=5, stroke_fill=p.ink)

            overlays_2d.append(_ton_lbl)

        elif scene_key == "sphere_uniform_stress":
            cam = Camera3D(eye=(-1.42, 0.72, 6.25), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(22, 54, 82), t=t, underwater=True)
            # Glossy 3D Phong-shaded Titanium Bathysphere with bolted viewport flange & uniform stress arrows!
            sc.add_sphere((0.68, 0.30, 0.0), 0.94, STEEL_LIGHT, metallic=0.84, rim_rgb=EMERALD)
            sc.add_cylinder((0.68, 0.25, 0.0), (0.68, 0.35, 0.0), 0.98, 0.98, STEEL_MID, segments=22, metallic=0.82, caps=False)
            sc.add_sphere((0.68, 0.30, 0.58), 0.40, STEEL_DARK, metallic=0.78)
            sc.add_sphere((0.68, 0.30, 0.64), 0.33, GLASS_BLUE, metallic=0.75, rim_rgb=CYAN)
            self._add_3d_radial_pressure_ring(sc, (0.68, 0.30, 0.0), 1.80, 1.12, 10, EMERALD, t)
            add_crash_test_dummy(sc, pos=(-1.46, -0.88, 0.72), scale=0.74, yaw=0.36, pose="point_right", emotion="relief", t=t)

            def _unif_lbl(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_bold, 28)
                lbl = "UNIFORM MEMBRANE STRESS"
                bb = d.textbbox((0, 0), lbl, font=f)
                d.text((540 - (bb[2] - bb[0]) / 2, 1320), lbl, font=f, fill=p.emerald, stroke_width=4, stroke_fill=p.ink)

            overlays_2d.append(_unif_lbl)

        elif scene_key == "cylinder_joint_hotspot":
            # Upgraded detailed Composite Submersible showing the weak carbon-to-titanium seam!
            cam = Camera3D(eye=(1.55, 0.85, 6.70), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, rgb=(22, 48, 84), t=t, underwater=True)
            pulse = 0.55 + 0.45 * math.sin(t * 9.0)
            self._add_3d_composite_hull(sc, center=(0.82, 0.16, 0.0), half_len=0.92, radius=0.60, seam_stress=pulse)
            sc.add_arrow_3d((0.82, 1.68, 0.1), (0.82, 0.96, 0.1), DANGER, shaft_r=0.072, head_r=0.175)
            sc.add_arrow_3d((-0.10, 1.56, 0.1), (-0.10, 0.86, 0.1), DANGER, shaft_r=0.072, head_r=0.175)
            add_crash_test_dummy(sc, pos=(-1.55, -0.86, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "ply_shear_fatigue":
            cam = Camera3D(eye=(2.2, 1.25, 5.9), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(24, 46, 78), t=t, underwater=True)
            n_plies = 7
            for i in range(n_plies):
                sep = (i - 3.0) * ease_in_out_cubic(prog) * 0.16
                py = (i - 3.0) * 0.34 + sep
                col = CARBON_DARK if i % 2 == 0 else STEEL_DARK
                sc.add_box((0.62, py, 0.0), (2.65, 0.22, 1.45), col, metallic=0.52, texture="carbon_weave")
                if i in (2, 4) and prog > 0.2:
                    crack_w = clamp((prog - 0.2) * 1.4) * 2.35
                    sc.add_box((0.62 - 1.18 + crack_w * 0.5, py + 0.16, 0.74), (crack_w, 0.07, 0.08), DANGER, emissive=0.90, bloom=True)
            sc.add_arrow_3d((0.62, 2.25, 0.2), (0.62, 1.35, 0.2), AMBER, shaft_r=0.085, head_r=0.20)
            sc.add_arrow_3d((0.62, -2.15, 0.2), (0.62, -1.25, 0.2), AMBER, shaft_r=0.085, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.28, -0.82, 0.75), scale=0.74, yaw=0.38, pose="brace_impact", emotion="shock", t=t)

        elif scene_key == "dimple_instability":
            dimple = ease_out_cubic(clamp((prog - 0.32) / 0.55))
            cam = Camera3D(eye=(-1.55 + shake * dimple, 0.85, 5.75), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(24, 46, 78), t=t, underwater=True)

            def _wall_y(u: float) -> float:
                return 0.25 + math.sin(u * math.pi) * 0.45 - math.exp(-((u - 0.5) / 0.15) ** 2) * dimple * 1.05

            n_seg = 18
            for i in range(n_seg):
                u = (i + 0.5) / n_seg
                u_prev = max(0.0, u - 0.03)
                u_next = min(1.0, u + 0.03)
                x = -0.85 + u * 2.85
                y = _wall_y(u)
                dx = (u_next - u_prev) * 2.85
                dy = _wall_y(u_next) - _wall_y(u_prev)
                slope = math.atan2(dy, dx)
                heat = math.exp(-((u - 0.5) / 0.17) ** 2) * dimple
                col = lerp_color(STEEL_MID, DANGER, heat)
                sc.add_box(
                    (x, y, 0.0),
                    (0.22, 0.36, 1.35),
                    col,
                    rot=(0.0, 0.0, slope),
                    metallic=0.62,
                    emissive=0.45 * heat,
                    texture="carbon_weave",
                    bloom=(heat > 0.30),
                )
            sc.add_arrow_3d((0.58, 2.25 - dimple * 0.5, 0.15), (0.58, 0.95 - dimple * 0.85, 0.15), DANGER, shaft_r=0.095, head_r=0.23)
            add_crash_test_dummy(sc, pos=(-1.28, -0.88, 0.75), scale=0.74, yaw=0.36, pose="brace_impact", emotion="brace", t=t)

        elif scene_key == "implosion_wave_020ms":
            # Upgraded detailed Composite Submersible violently imploding in 20 MS!
            collapse = ease_in_out_cubic(clamp(prog * 1.15))
            cam = Camera3D(eye=(1.35 + shake, 0.65, 6.65), target=(0.05, 0.0, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, rgb=(24, 44, 76), t=t, underwater=True)
            self._add_3d_composite_hull(
                sc,
                center=(0.72, 0.24, 0.0),
                half_len=0.98 * (1.0 - 0.32 * collapse),
                radius=0.64 * (1.0 - 0.40 * collapse),
                seam_stress=1.0,
                buckling=clamp(0.18 + collapse * 0.82),
            )
            self._add_3d_radial_pressure_ring(sc, (0.65, 0.24, 0.0), 2.02 - 0.45 * collapse, 1.16 - 0.40 * collapse, 10, DANGER, t * 2.0)
            add_crash_test_dummy(sc, pos=(-1.55, -0.92, 0.72), scale=0.70, yaw=0.38, pose="panic_freefall", emotion="shock", t=t)
            ms = min(20.0, prog * 22.0)

            def _ms_badge(d: ImageDraw.ImageDraw) -> None:
                if collapse > 0.4:
                    draw_sparks(d, 650, 920, t, 22, 210, 155, p, seed=131)
                f = load_font(self.font_black, 42)
                label = f"T + {ms:04.1f} MS"
                bb = d.textbbox((0, 0), label, font=f)
                cx_b = 625
                d.rounded_rectangle([cx_b - 170, 1285, cx_b + 170, 1354], radius=14, fill=p.surface_panel, outline=p.danger, width=4)
                d.text((cx_b - (bb[2] - bb[0]) / 2, 1296), label, font=f, fill=p.text_highlight)

            overlays_2d.append(_ms_badge)

        elif scene_key == "air_compression_pulse":
            squeeze = ease_out_cubic(prog)
            cam = Camera3D(eye=(shake, 0.55, 5.95), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, rgb=(24, 44, 76), t=t, underwater=True)
            core_r = max(0.30, 0.92 * (1.0 - 0.65 * squeeze))
            sc.add_sphere((0.55, 0.30, 0.0), core_r * 1.42, DANGER, metallic=0.1, emissive=0.80, rim_rgb=AMBER, bloom=True)
            sc.add_sphere((0.55, 0.30, 0.15), core_r * 0.92, AMBER, metallic=0.1, emissive=0.92, rim_rgb=(255, 255, 220), bloom=True)
            sc.add_sphere((0.55, 0.30, 0.28), core_r * 0.50, (255, 252, 225), metallic=0.1, emissive=1.0, bloom=True)
            self._add_3d_radial_pressure_ring(sc, (0.55, 0.30, 0.0), 1.82, core_r + 0.36, 8, CYAN, t * 2.6)
            add_crash_test_dummy(sc, pos=(-1.42, -0.92, 0.72), scale=0.72, yaw=0.35, pose="brace_impact", emotion="shock", t=t)

            def _comp_lbl(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 34)
                lbl = "ADIABATIC COMPRESSION"
                bb = d.textbbox((0, 0), lbl, font=f)
                d.text((540 - (bb[2] - bb[0]) / 2, 1300), lbl, font=f, fill=p.text_highlight, stroke_width=4, stroke_fill=p.ink)

            overlays_2d.append(_comp_lbl)

        elif scene_key == "nerve_bar_comparison":
            # Clean split layout: UNIT-01 unobstructed on left pointing right at crisp comparison chart!
            cam = Camera3D(eye=(0.25, 0.35, 5.9), target=(0.0, -0.25, 0.0), fov_deg=41.0, cy_offset=95.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, rgb=(22, 48, 84), t=t, underwater=True)
            add_crash_test_dummy(sc, pos=(-1.42, -0.45, 0.55), scale=0.72, yaw=0.38, pose="point_right", emotion="curious", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=325,
                    y0=715,
                    width=680,
                    height=355,
                    items=[
                        ("HULL IMPLOSION", "20 MS", 20.0 / 250.0, p.danger),
                        ("HUMAN VISUAL NERVE", "250 MS", 1.0, p.cyan),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([325, 1105, 1005, 1188], radius=16, fill=p.surface_panel, outline=p.text_highlight, width=4)
                f = load_font(self.font_black, 28)
                msg = "10X FASTER THAN HUMAN SIGHT"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((665 - (bb[2] - bb[0]) / 2, 1130), msg, font=f, fill=p.text_highlight)

            overlays_2d.append(_bars)

        else:  # verdict_cta_card — FUN FINALE: UNIT-01 rockets his Yellow Sub UP & sprints out ABOVE the ocean surface!
            cam = Camera3D(eye=(math.sin(t * 0.85) * 0.35, 0.45, 6.25), target=(0.0, 0.15, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.35, span=7.0, step=1.0, rgb=(18, 62, 102), t=t, underwater=True)

            # Animated ocean surface wave ribbon right at waterline (y_world ~ -0.15 -> y_px ~ 1045)
            def _surface_waves(d: ImageDraw.ImageDraw) -> None:
                # Back wave crest
                pts_back = []
                pts_front = []
                for x in range(0, 1081, 36):
                    yb = 1038 + int(math.sin(x * 0.014 + t * 3.8) * 11)
                    yf = 1054 + int(math.cos(x * 0.017 - t * 4.6) * 13)
                    pts_back.append((x, yb))
                    pts_front.append((x, yf))
                d.line(pts_back, fill=(72, 218, 245), width=6)
                d.line(pts_front, fill=(195, 248, 255), width=5)

                # Big animated splash spray when Yellow Sub breaches the ocean surface!
                if 0.24 < prog < 0.62:
                    sp = (prog - 0.24) / 0.38
                    for si in range(18):
                        ang = -math.pi * (0.12 + 0.76 * (si / 17.0))
                        dist = (65 + (si % 4) * 32) * ease_out_cubic(sp)
                        sx = 540 + int(math.cos(ang) * dist * 1.45)
                        sy = 1042 + int(math.sin(ang) * dist + 115 * (sp ** 2))
                        sr = max(3, int((1.0 - sp) * 12))
                        d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(215, 250, 255))

            if prog < 0.42:
                # Phase 1: Emergency full-throttle ascent! Nose pitched skyward bursting up out of the deep!
                rise = ease_out_cubic(prog / 0.42)
                sub_y = -2.15 + rise * 2.25
                sub_pitch = 0.78 * (1.0 - rise * 0.85)
                self._add_3d_yellow_submarine(
                    sc,
                    center=(-0.10 + rise * 0.10, sub_y, 0.0),
                    scale=0.82,
                    yaw=-0.12,
                    pitch=sub_pitch,
                    t=t,
                    prop_speed=40.0,
                    with_pilot=True,
                    pilot_pose="panic_freefall",
                    pilot_emotion="panic",
                    bubbles=True,
                )
            else:
                # Phase 2: Yellow Sub floats bobbing on the ocean surface, while UNIT-01 runs/escapes ABOVE the surface!
                surf_t = (prog - 0.42) / 0.58
                bob = math.sin(t * 4.2) * 0.06
                self._add_3d_yellow_submarine(
                    sc,
                    center=(-0.15, -0.78 + bob, -0.35),
                    scale=0.78,
                    yaw=-0.16,
                    pitch=math.sin(t * 3.1) * 0.04,
                    t=t,
                    prop_speed=10.0,
                    with_pilot=False,
                    headlights=True,
                    bubbles=False,
                )
                if surf_t < 0.52:
                    # Frantic comical sprint straight up onto the dry open-air surface deck!
                    hop = ease_out_cubic(surf_t / 0.52)
                    dx_run = -0.35 + hop * 0.35
                    dy_run = 0.25 + math.sin(hop * math.pi) * 0.42 + hop * 0.40
                    add_crash_test_dummy(
                        sc,
                        pos=(dx_run, dy_run + bob, 0.38),
                        scale=0.82,
                        yaw=0.25 * (1.0 - hop),
                        pose="sprint_escape",
                        emotion="relief" if surf_t > 0.30 else "panic",
                        t=t,
                        ground_shadow=False,
                    )
                else:
                    # Safe & dry ABOVE the surface on top of his yellow sub, waving between YES / NO!
                    add_crash_test_dummy(
                        sc,
                        pos=(0.0, 0.65 + bob, 0.38),
                        scale=0.84,
                        yaw=math.sin(t * 2.0) * 0.14,
                        pose="cta_shrug",
                        emotion="cta",
                        t=t,
                        ground_shadow=False,
                    )

            overlays_2d.append(_surface_waves)

            def _cta_buttons(d: ImageDraw.ImageDraw) -> None:
                pulse = 1.0 + 0.04 * math.sin(t * 7.0)
                for label, bx, col in (("YES", 198, p.cyan), ("NO", 882, p.amber)):
                    bw, bh = int(130 * pulse), int(82 * pulse)
                    by = 875
                    d.rounded_rectangle([bx - bw, by, bx + bw, by + bh], radius=18, fill=p.surface_panel, outline=col, width=5)
                    f = load_font(self.font_black, 44)
                    bb = d.textbbox((0, 0), label, font=f)
                    d.text((bx - (bb[2] - bb[0]) / 2, by + (bh - (bb[3] - bb[1])) / 2 - 4), label, font=f, fill=col)

            overlays_2d.append(_cta_buttons)

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
        rendered_bgr, overlays_2d = self._render_scene_3d("hull_pressure_peak", t=0.35, prog=0.45, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
