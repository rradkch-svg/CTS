"""Episode 04: Why Light Wind RIPPED This Steel Bridge Apart — True 3D Aeroelastic Flutter + UNIT-01."""

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

STEEL_LIGHT = (190, 208, 226)
STEEL_MID = (114, 136, 164)
STEEL_DARK = (48, 64, 88)
ROAD_DARK = (36, 46, 62)
CAR_YELLOW = (255, 204, 34)
CAR_NAVY = (26, 38, 58)
TIRE_DARK = (28, 32, 40)
BRASS = (220, 170, 72)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


def _add_3d_yellow_car(
    sc: Scene3D,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: float = 1.0,
    yaw: float = 0.0,
    pitch: float = 0.0,
    roll: float = 0.0,
    t: float = 0.0,
    wheel_speed: float = 10.0,
    with_driver: bool = True,
    driver_pose: str = "pilot_sub",
    driver_emotion: str = "curious",
) -> None:
    """Detailed 3D Yellow Crash-Test Convertible ridden by UNIT-01 (nose +X, top +Y, ZERO leg clipping)."""
    R = rot_matrix(roll, yaw, pitch)
    origin = np.array(center, dtype=np.float32)

    def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
        v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
        return tuple((origin + R @ v).tolist())

    # Seated BOLT inside cockpit tub (show_legs=False guarantees zero legs poking under chassis!)
    if with_driver:
        add_crash_test_dummy(
            sc,
            pos=_p(-0.10, 0.44, 0.0),
            scale=0.50 * scale,
            yaw=yaw + 0.45,
            tilt_z=pitch * 0.75,
            pose=driver_pose,
            emotion=driver_emotion,
            t=t,
            ground_shadow=False,
            show_legs=False,
        )

    # Lower chassis + contrasting navy rocker trim + sculpted hood & rear deck
    sc.add_box(_p(0.0, 0.24, 0.0), (1.78 * scale, 0.36 * scale, 0.90 * scale), CAR_YELLOW, rot=(roll, yaw, pitch), metallic=0.48, texture="painted_metal")
    sc.add_box(_p(0.0, 0.10, 0.0), (1.82 * scale, 0.11 * scale, 0.93 * scale), CAR_NAVY, rot=(roll, yaw, pitch), metallic=0.45, texture="painted_metal")
    # Hood panel + open dark interior cockpit well + rear seat backrest
    sc.add_box(_p(0.56, 0.39, 0.0), (0.64 * scale, 0.14 * scale, 0.84 * scale), CAR_NAVY, rot=(roll, yaw, pitch), metallic=0.48, texture="painted_metal")
    sc.add_box(_p(-0.08, 0.40, 0.0), (0.62 * scale, 0.08 * scale, 0.74 * scale), (18, 26, 40), rot=(roll, yaw, pitch), metallic=0.20, texture="matte")
    sc.add_box(_p(-0.48, 0.48, 0.0), (0.18 * scale, 0.28 * scale, 0.74 * scale), CAR_NAVY, rot=(roll, yaw, pitch - 0.15), metallic=0.32, texture="matte")
    # Slanted glass windshield frame
    sc.add_box(_p(0.28, 0.56, 0.0), (0.07 * scale, 0.34 * scale, 0.80 * scale), CYAN, rot=(roll, yaw, pitch + 0.45), metallic=0.72, alpha=0.56)
    # Rear sporty wing spoiler
    sc.add_box(_p(-0.82, 0.52, 0.0), (0.20 * scale, 0.06 * scale, 0.92 * scale), AMBER, rot=(roll, yaw, pitch), metallic=0.58, texture="painted_metal")
    # Headlights & crimson taillights (controlled glow, zero blowout)
    for sz in (-1, 1):
        sc.add_sphere(_p(0.90, 0.28, sz * 0.30), 0.082 * scale, (255, 246, 195), emissive=0.75)
        sc.add_sphere(_p(-0.90, 0.28, sz * 0.30), 0.072 * scale, DANGER, emissive=0.70)
    # 4 rubber tires + chrome rims
    for sx in (-0.54, 0.56):
        for sz in (-1, 1):
            w0 = _p(sx, 0.06, sz * 0.36)
            w1 = _p(sx, 0.06, sz * 0.54)
            sc.add_cylinder(w0, w1, 0.22 * scale, 0.22 * scale, TIRE_DARK, segments=16, metallic=0.22)
            sc.add_cylinder(_p(sx, 0.06, sz * 0.53), _p(sx, 0.06, sz * 0.56), 0.11 * scale, 0.11 * scale, STEEL_LIGHT, segments=14, metallic=0.84)


@register_scene("ep04_tacoma_bridge_flutter")
class TacomaBridgeFlutterScene(EpisodeScene):
    """Articulated 12-beat True 3D Aeroelastic Bridge Flutter + UNIT-01 scene."""

    slug = "ep04_tacoma_bridge_flutter"
    episode_id = "ep04"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_sky_bgr: np.ndarray | None = None
        self.bg_alert_bgr: np.ndarray | None = None
        self.bg_safe_bgr: np.ndarray | None = None
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
        self.bg_sky_bgr = cv2.cvtColor(
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
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_suspension_bridge(
        self,
        sc: Scene3D,
        twist_amp: float = 0.45,
        t: float = 0.0,
        snapped_count: int = 0,
        modern_safe: bool = False,
        span_half: float = 1.85,
    ) -> None:
        """True 3D twin-tower suspension bridge with wide non-clipping cables & genuine slotted modern deck."""
        tower_col = EMERALD if modern_safe else STEEL_LIGHT
        cable_z = 0.78 if modern_safe else 0.72  # Wider than car so cables NEVER clip Yellow Car!
        for tx in (-span_half, span_half):
            for tz in (-cable_z, cable_z):
                sc.add_box((tx, 0.25, tz), (0.16, 3.10, 0.16), STEEL_LIGHT, metallic=0.76)
            sc.add_box((tx, 1.62, 0.0), (0.15, 0.16, cable_z * 2.15), tower_col, metallic=0.72, emissive=0.20 if modern_safe else 0.0)
            sc.add_box((tx, 0.65, 0.0), (0.13, 0.14, cable_z * 2.05), STEEL_MID, metallic=0.70)

        # Sweeping catenary main cables (front & back, safely clear of car lane!)
        n_seg = 14
        for tz in (-cable_z, cable_z):
            for i in range(n_seg):
                u0, u1 = i / n_seg, (i + 1) / n_seg
                x0 = -span_half + u0 * (2.0 * span_half)
                x1 = -span_half + u1 * (2.0 * span_half)
                y0 = 1.66 - 1.38 * (1.0 - (2.0 * u0 - 1.0) ** 2)
                y1 = 1.66 - 1.38 * (1.0 - (2.0 * u1 - 1.0) ** 2)
                sc.add_cylinder((x0, y0, tz), (x1, y1, tz), 0.038, 0.038, CYAN if modern_safe else AMBER, segments=8, emissive=0.28)

        # Twisting continuous road deck (or twin-lane modern slotted box girder!) + vertical steel suspenders
        seg_w = (2.0 * span_half) / n_seg + 0.04
        for i in range(n_seg):
            u = (i + 0.5) / n_seg
            x = -span_half + u * (2.0 * span_half)
            env = math.sin(u * math.pi)
            roll = math.sin(t * 4.4 + u * 3.8) * twist_amp * env
            drop = 0.0
            is_snapped = (i < snapped_count)
            if is_snapped:
                frac_drop = (snapped_count - i) / max(1, snapped_count)
                drop = 0.95 * (frac_drop ** 1.2)
                roll += 0.62 * frac_drop
            deck_y = -0.18 - drop + math.sin(t * 4.4 + u * 3.8) * 0.12 * twist_amp * env

            if modern_safe:
                # Genuine twin separated aerodynamic box lanes with visible glowing center air slot!
                for dz in (-0.42, 0.42):
                    sc.add_box((x, deck_y, dz), (seg_w, 0.16, 0.54), STEEL_LIGHT, metallic=0.74)
                    sc.add_box((x, deck_y + 0.09, dz), (seg_w, 0.04, 0.56), EMERALD, metallic=0.50, emissive=0.25)
                # Subtle structural cross-ties across the open air slot
                if i % 2 == 0:
                    sc.add_box((x, deck_y - 0.04, 0.0), (0.08, 0.08, 0.34), STEEL_MID, metallic=0.72)
            else:
                deck_col = lerp_color(ROAD_DARK, DANGER, clamp(abs(roll) * 1.15))
                sc.add_box((x, deck_y, 0.0), (seg_w, 0.24, 1.26), deck_col, rot=(roll, 0.0, 0.0), metallic=0.58, emissive=0.18 if abs(roll) > 0.32 else 0.0)
                # Twin side H-girder walls along the 1940 deck
                for sz in (-0.64, 0.64):
                    wy = deck_y + math.sin(roll) * sz
                    wz = math.cos(roll) * sz
                    sc.add_box((x, wy, wz), (seg_w, 0.38, 0.08), STEEL_LIGHT, rot=(roll, 0.0, 0.0), metallic=0.74)

            # Vertical steel suspenders + dangling snapped cables during zipper collapse!
            if i % 2 == 1:
                cy_top = 1.66 - 1.38 * (1.0 - (2.0 * u - 1.0) ** 2)
                for tz in (-cable_z, cable_z):
                    if not is_snapped:
                        edge_y = deck_y + math.sin(roll) * tz * 0.85
                        sc.add_cylinder((x, cy_top, tz), (x, edge_y, tz), 0.020, 0.020, STEEL_LIGHT, segments=6)
                    else:
                        # Whipping snapped suspender stubs hanging from the catenary cable!
                        whip = math.sin(t * 16.0 + i * 2.1) * 0.16
                        sc.add_cylinder((x, cy_top, tz), (x + whip, cy_top - 0.55, tz + 0.08), 0.020, 0.018, DANGER, segments=6, emissive=0.40)

    def _add_helical_vortex(
        self,
        sc: Scene3D,
        center: tuple[float, float, float],
        radius: float,
        sign: float,
        t: float,
        rgb: tuple[int, int, int] = DANGER,
    ) -> None:
        """Crisp swirling 3D aerodynamic vortex curl ring (replaces flat pink spheres!)."""
        cx, cy, cz = center
        pts = []
        n_seg = 14
        for k in range(n_seg + 1):
            frac = k / n_seg
            ang = sign * (t * 6.5 + frac * 1.85 * math.pi)
            r = radius * (0.35 + 0.68 * frac)
            pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r, cz + (frac - 0.5) * 0.25))
        for p0, p1 in zip(pts[:-1], pts[1:]):
            sc.add_cylinder(p0, p1, 0.036, 0.028, rgb, segments=6, emissive=0.65, bloom=True, caps=False)

    def _add_h_girder_section(
        self,
        sc: Scene3D,
        center: tuple[float, float, float],
        tilt: float = 0.0,
        road_col: tuple[int, int, int] = ROAD_DARK,
        width: float = 1.65,
        wall_h: float = 1.18,
        depth: float = 1.10,
    ) -> None:
        """Consistent 1940 solid H-girder cross-section with amber top/bottom flanges (never disappears!)."""
        cx, cy, cz = center
        sc.add_box((cx, cy, cz), (width, 0.20, depth), road_col, rot=(0.0, 0.0, tilt), metallic=0.45, texture="concrete")
        half_w = width * 0.49
        half_h = wall_h * 0.48
        ct, st = math.cos(tilt), math.sin(tilt)
        for sx in (-1, 1):
            wx = cx + ct * (sx * half_w)
            wy = cy + st * (sx * half_w)
            sc.add_box((wx, wy, cz), (0.16, wall_h, depth + 0.04), STEEL_LIGHT, rot=(0.0, 0.0, tilt), metallic=0.78)
            for sy in (-1, 1):
                fx = wx - st * (sy * half_h)
                fy = wy + ct * (sy * half_h)
                sc.add_box((fx, fy, cz), (0.34, 0.10, depth + 0.06), AMBER, rot=(0.0, 0.0, tilt), metallic=0.70, texture="machined_brass")

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float, is_cover: bool = False) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_sky_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("bridge_twist_hero", "aeroelastic_flutter_loop", "torsion_45_degrees", "suspenders_stretching", "cables_unzip_collapse"):
            bg = self.bg_alert_bgr
        elif scene_key in ("modern_slotted_girder", "flutter_speed_comparison", "verdict_cta_card"):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_sky_bgr

        shake = math.sin(t * 55.0) * 0.05 if (scene_key in ("bridge_twist_hero", "cables_unzip_collapse") and not is_cover) else 0.0

        if scene_key == "bridge_twist_hero":
            # FRAME 0 HERO: Twisting bridge + non-clipping wide cables + seated BOLT in Yellow Car!
            if is_cover:
                cam = Camera3D(eye=(-0.85, 0.95, 7.25), target=(0.0, 0.58, 0.0), fov_deg=41.0, cy_offset=45.0)
            else:
                cam = Camera3D(eye=(-0.85 + math.sin(t * 1.1) * 0.30 + shake, 0.92, 6.45), target=(0.0, 0.08, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.95, span=7.0, step=1.0, rgb=(20, 56, 92), t=t, underwater=True)
            self._add_3d_suspension_bridge(sc, twist_amp=0.52, t=t, span_half=1.80)
            car_roll = math.sin(t * 4.4 + 1.9) * 0.48
            _add_3d_yellow_car(sc, center=(0.0, -0.02, 0.0), scale=0.66, yaw=-0.08, roll=car_roll, t=t, with_driver=True, driver_pose="panic_freefall", driver_emotion="panic")
            # Wind arrows cleanly inside left margin, clear of tower!
            for wy in (-0.28, 0.25, 0.78):
                sc.add_arrow_3d((-1.52, wy, 1.05), (-0.65, wy + math.sin(t * 6.0 + wy) * 0.14, 1.05), CYAN, shaft_r=0.048, head_r=0.125)
            if not is_cover:
                overlays_2d.append(lambda d: draw_sparks(d, 540, 960, t, 14, 220, 130, p, seed=41))

        elif scene_key == "suspension_span_wave":
            cam = Camera3D(eye=(0.42, 0.82, 6.85), target=(0.0, 0.08, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.0, span=7.0, step=1.0, rgb=(20, 56, 92), t=t, underwater=True)
            self._add_3d_suspension_bridge(sc, twist_amp=0.45, t=t, span_half=1.78)
            add_crash_test_dummy(sc, pos=(-1.42, -0.95, 1.15), scale=0.66, yaw=0.40, pose="point_right", emotion="curious", t=t)

        elif scene_key == "solid_h_girder_profile":
            cam = Camera3D(eye=(1.45, 0.78, 6.25), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_h_girder_section(sc, (0.62, 0.05, 0.0), tilt=0.0, width=1.88, wall_h=1.42, depth=1.70)
            sc.add_arrow_3d((1.82, -0.65, 0.35), (1.82, 0.72, 0.35), CYAN, shaft_r=0.058, head_r=0.145)
            add_crash_test_dummy(sc, pos=(-1.42, -0.88, 0.68), scale=0.68, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "wind_tunnel_vortices":
            # Side-view wind tunnel: laminar cyan wind hitting H-girder + true swirling 3D helical vortices (NO flat spheres!)
            cam = Camera3D(eye=(0.0, 0.55, 6.45), target=(0.12, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_h_girder_section(sc, (0.42, 0.12, 0.0), tilt=0.0, width=1.28, wall_h=1.18, depth=0.95)
            # Steady wind streams clearly to the RIGHT of BOLT's head and stopping cleanly before H-girder wall!
            for wy in (-0.34, 0.12, 0.58):
                shift = ((t * 1.5 + wy) % 0.45) * 0.32
                sc.add_arrow_3d((-1.02 + shift, wy, 0.15), (-0.40 + shift * 0.25, wy, 0.15), CYAN, shaft_r=0.048, head_r=0.125)
            # Swirling helical red/amber aerodynamic vortex curls peeling off leeward side!
            self._add_helical_vortex(sc, (1.42, 0.58, 0.12), 0.32, +1.0, t, DANGER)
            self._add_helical_vortex(sc, (1.46, -0.36, 0.12), 0.32, -1.0, t, AMBER)
            add_crash_test_dummy(sc, pos=(-1.46, -0.92, 0.68), scale=0.66, yaw=0.38, pose="brace_impact", emotion="curious", t=t)

        elif scene_key == "alternating_vortex_twist":
            cam = Camera3D(eye=(0.25, 0.60, 6.45), target=(0.10, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            tilt = math.sin(t * 5.0) * 0.38
            self._add_h_girder_section(sc, (0.55, 0.12, 0.0), tilt=tilt, road_col=STEEL_MID, width=1.62, wall_h=1.08, depth=1.05)
            # Torque arrows strictly OUTSIDE the H-girder walls (zero impaling!)
            dir_s = 1.0 if math.cos(t * 5.0) > 0 else -1.0
            sc.add_arrow_3d((-0.56, 0.12 - dir_s * 0.82, 0.22), (-0.56, 0.12 + dir_s * 0.45, 0.22), DANGER, shaft_r=0.065, head_r=0.155)
            sc.add_arrow_3d((1.66, 0.12 + dir_s * 0.82, 0.22), (1.66, 0.12 - dir_s * 0.45, 0.22), CYAN, shaft_r=0.065, head_r=0.155)
            add_crash_test_dummy(sc, pos=(-1.46, -0.88, 0.68), scale=0.66, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "aeroelastic_flutter_loop":
            cam = Camera3D(eye=(-0.85, 0.65, 6.45), target=(0.15, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            amp = 0.22 + prog * 0.44
            tilt = math.sin(t * 6.0) * amp
            self._add_h_girder_section(sc, (0.55, 0.15, 0.0), tilt=tilt, road_col=lerp_color(STEEL_MID, DANGER, prog * 0.60), width=1.65, wall_h=1.08, depth=1.02)
            # Clear external wind & lift arrows (never stabbing through the H-girder!)
            sc.add_arrow_3d((-0.82, 0.15, 0.22), (-0.32, 0.82, 0.22), CYAN, shaft_r=0.060, head_r=0.145)
            sc.add_arrow_3d((1.62, -0.58, 0.22), (1.78, 1.05, 0.22), DANGER, shaft_r=0.078, head_r=0.18)
            add_crash_test_dummy(sc, pos=(-1.44, -0.88, 0.68), scale=0.66, yaw=0.38, pose="brace_impact", emotion="shock", t=t)

        elif scene_key == "torsion_45_degrees":
            # Smooth continuous 45° twisting H-girder bridge deck + attached suspenders + safe-zone 45° gauge!
            cam = Camera3D(eye=(-1.05, 0.72, 6.55), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(20, 50, 84), t=t, underwater=True)
            peak_deg = 22.0 + ease_in_out_cubic(prog) * 23.0  # Smoothly escalates to full 45°!
            osc = math.sin(t * 3.8)
            rad = math.radians(peak_deg) * osc
            live_deg = int(round(peak_deg))
            self._add_h_girder_section(sc, (-0.20, 0.05, 0.0), tilt=rad, road_col=lerp_color(ROAD_DARK, DANGER, 0.55), width=1.82, wall_h=0.95, depth=1.22)
            # Attached steel suspender cables connecting the tilting deck edges upward!
            ct, st = math.cos(rad), math.sin(rad)
            for sx in (-0.90, 0.90):
                ex = -0.20 + ct * sx
                ey = 0.05 + st * sx
                sc.add_cylinder((ex, ey, 0.0), (-0.20 + sx, 2.35, 0.0), 0.032, 0.032, STEEL_LIGHT, segments=8)
            _add_3d_yellow_car(sc, center=(-0.20 - st * 0.16, 0.05 + ct * 0.16, 0.0), scale=0.60, yaw=0.12, pitch=rad, t=t, with_driver=True, driver_pose="panic_freefall", driver_emotion="panic")
            overlays_2d.append(
                lambda d, _deg=live_deg: draw_pressure_gauge(
                    d, 745, 1175, 108, clamp(_deg / 45.0), "DECK ROLL", f"{_deg}°", p, self.font_black
                )
            )

        elif scene_key == "suspenders_stretching":
            cam = Camera3D(eye=(1.38, 0.72, 6.20), target=(0.08, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            sc.add_box((0.55, 1.55, 0.0), (2.35, 0.24, 0.42), STEEL_MID, metallic=0.72)
            sc.add_box((0.55, -1.25, 0.0), (2.35, 0.28, 0.75), STEEL_DARK, metallic=0.66)
            for i in range(5):
                cx_s = -0.30 + i * 0.42
                heat = clamp(prog * 1.4 - i * 0.15)
                col = lerp_color(STEEL_LIGHT, DANGER, heat)
                # Subtle tensile vibration + realistic metallic cable glow (no flat pink sabers)
                vib = math.sin(t * 42.0 + i * 1.3) * 0.025 * heat
                sc.add_cylinder((cx_s, 1.45, 0.0), (cx_s + vib, -1.12, 0.0), 0.050, 0.050, col, segments=10, metallic=0.72, emissive=0.32 * heat, bloom=(heat > 0.65))
            sc.add_arrow_3d((0.55, -0.35, 0.45), (0.55, -1.65, 0.45), DANGER, shaft_r=0.078, head_r=0.185)
            add_crash_test_dummy(sc, pos=(-1.42, -0.88, 0.68), scale=0.68, yaw=0.38, pose="brace_impact", emotion="shock", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 610, 960, t, 18, 210, 150, p, seed=48))

        elif scene_key == "cables_unzip_collapse":
            cam = Camera3D(eye=(-0.55 + shake, 0.85, 6.75), target=(0.05, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, rgb=(22, 48, 82), t=t, underwater=True)
            snapped = min(12, 1 + int(prog * 12.0))
            self._add_3d_suspension_bridge(sc, twist_amp=0.62, t=t, snapped_count=snapped, span_half=1.78)
            add_crash_test_dummy(sc, pos=(-1.42, -0.95, 1.15), scale=0.66, yaw=0.35, pose="panic_freefall", emotion="panic", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 560, 930, t, 24, 240, 160, p, seed=49))

        elif scene_key == "modern_slotted_girder":
            # True streamlined aerodynamic trapezoidal twin-box deck with open center wind slot + non-crossing arrows!
            cam = Camera3D(eye=(1.25, 0.72, 6.35), target=(0.12, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Twin streamlined trapezoidal box decks separated by open center pressure-equalizing air slot!
            for sx in (-0.72, 0.72):
                bx = 0.52 + sx
                sc.add_box((bx, 0.12, 0.0), (0.86, 0.30, 1.50), STEEL_LIGHT, metallic=0.78)
                sc.add_box((bx, 0.30, 0.0), (0.88, 0.07, 1.52), EMERALD, metallic=0.52, emissive=0.25)
                # Angled aerodynamic wedge nose/tail fairings on outer edges!
                edge_x = bx + (0.56 if sx > 0 else -0.56)
                sc.add_box((edge_x, 0.12, 0.0), (0.34, 0.22, 1.48), STEEL_MID, rot=(0.0, 0.0, -0.45 if sx > 0 else 0.45), metallic=0.76)
            # Non-crossing flow arrows: laminar cyan gliding ABOVE deck, emerald equalizing cleanly UP through center slot!
            sc.add_arrow_3d((-0.82, 0.72, 0.22), (1.85, 0.72, 0.22), CYAN, shaft_r=0.055, head_r=0.14)
            sc.add_arrow_3d((0.52, -0.88, 0.22), (0.52, 0.42, 0.22), EMERALD, shaft_r=0.068, head_r=0.16)
            add_crash_test_dummy(sc, pos=(-1.44, -0.88, 0.68), scale=0.68, yaw=0.38, pose="point_right", emotion="relief", t=t)

        elif scene_key == "flutter_speed_comparison":
            # Unobstructed BOLT on left pointing at crisp safe-zone comparison bars (strictly x <= 860!)
            cam = Camera3D(eye=(0.25, 0.35, 6.20), target=(0.0, -0.25, 0.0), fov_deg=41.0, cy_offset=95.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            add_crash_test_dummy(sc, pos=(-1.62, -0.45, 0.48), scale=0.68, yaw=0.40, pose="point_right", emotion="relief", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=320,
                    y0=715,
                    width=540,
                    height=355,
                    items=[
                        ("1940 H-GIRDER", "42 MPH", 42.0 / 160.0, p.danger),
                        ("MODERN SLOTTED DECK", "150+ MPH", 150.0 / 160.0, p.emerald),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([320, 1105, 860, 1188], radius=16, fill=p.surface_panel, outline=p.emerald, width=4)
                f = load_font(self.font_black, 26)
                msg = "3.5X SAFER AERODYNAMICS"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((590 - (bb[2] - bb[0]) / 2, 1130), msg, font=f, fill=p.emerald)

            overlays_2d.append(_bars)

        else:  # verdict_cta_card — UNIT-01 seated cleanly inside his Yellow Car on the modern slotted emerald bridge!
            cam = Camera3D(eye=(math.sin(t * 0.8) * 0.35, 0.65, 6.85), target=(0.0, 0.08, 0.0), fov_deg=41.0, cy_offset=25.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.90, span=7.0, step=1.0, rgb=(20, 56, 86), t=t, underwater=True)
            self._add_3d_suspension_bridge(sc, twist_amp=0.0, t=t, modern_safe=True, span_half=1.76)
            car_x = -0.75 + ease_out_cubic(min(1.0, prog * 1.45)) * 0.75
            _add_3d_yellow_car(
                sc,
                center=(car_x, -0.02, 0.05),
                scale=0.88,
                yaw=-0.16,
                t=t,
                with_driver=True,
                driver_pose="cta_shrug",
                driver_emotion="cta",
            )
            overlays_2d.append(lambda d: draw_cta_buttons(d, t, p, self.font_black, by=1160))

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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "bridge_twist_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("bridge_twist_hero", t=0.35, prog=0.45, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
