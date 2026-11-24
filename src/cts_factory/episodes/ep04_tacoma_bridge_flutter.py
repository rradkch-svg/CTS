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
    """Detailed 3D Yellow Crash-Test Convertible ridden by UNIT-01 (nose +X, top +Y)."""
    R = rot_matrix(roll, yaw, pitch)
    origin = np.array(center, dtype=np.float32)

    def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
        v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
        return tuple((origin + R @ v).tolist())

    # Sleek lower chassis + sculpted nose & trunk
    sc.add_box(_p(0.0, 0.24, 0.0), (1.75 * scale, 0.34 * scale, 0.88 * scale), CAR_YELLOW, rot=(roll, yaw, pitch), metallic=0.52)
    sc.add_box(_p(0.52, 0.36, 0.0), (0.68 * scale, 0.16 * scale, 0.82 * scale), CAR_NAVY, rot=(roll, yaw, pitch), metallic=0.45)
    # Slanted glass windshield frame
    sc.add_box(_p(0.28, 0.56, 0.0), (0.08 * scale, 0.36 * scale, 0.78 * scale), CYAN, rot=(roll, yaw, pitch + 0.45), metallic=0.72, alpha=0.58)
    # Rear sporty wing spoiler
    sc.add_box(_p(-0.82, 0.52, 0.0), (0.20 * scale, 0.06 * scale, 0.90 * scale), AMBER, rot=(roll, yaw, pitch), metallic=0.58)
    # Twin glowing headlights & crimson taillights
    for sz in (-1, 1):
        sc.add_sphere(_p(0.88, 0.28, sz * 0.30), 0.085 * scale, (255, 248, 195), emissive=0.95, bloom=True)
        sc.add_sphere(_p(-0.88, 0.28, sz * 0.30), 0.075 * scale, DANGER, emissive=0.85, bloom=True)
    # 4 rubber tires + chrome rims
    for sx in (-0.54, 0.56):
        for sz in (-1, 1):
            w0 = _p(sx, 0.08, sz * 0.38)
            w1 = _p(sx, 0.08, sz * 0.56)
            sc.add_cylinder(w0, w1, 0.22 * scale, 0.22 * scale, TIRE_DARK, segments=14, metallic=0.25)
            sc.add_sphere(_p(sx, 0.08, sz * 0.56), 0.11 * scale, STEEL_LIGHT, metallic=0.82)

    if with_driver:
        add_crash_test_dummy(
            sc,
            pos=_p(-0.08, 0.64, 0.0),
            scale=0.52 * scale,
            yaw=yaw + 0.52,
            tilt_z=pitch * 0.8,
            pose=driver_pose,
            emotion=driver_emotion,
            t=t,
            ground_shadow=False,
        )


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
    ) -> None:
        """True 3D twin-tower suspension bridge with twisting deck, catenary cables & suspenders."""
        # Twin tall steel H-towers at x = -2.1 and +2.1
        tower_col = EMERALD if modern_safe else STEEL_LIGHT
        for tx in (-2.05, 2.05):
            for tz in (-0.52, 0.52):
                sc.add_box((tx, 0.35, tz), (0.18, 3.35, 0.18), STEEL_LIGHT, metallic=0.76)
            sc.add_box((tx, 1.80, 0.0), (0.16, 0.18, 1.18), tower_col, metallic=0.72, emissive=0.25 if modern_safe else 0.0)
            sc.add_box((tx, 0.72, 0.0), (0.14, 0.14, 1.10), STEEL_MID, metallic=0.70)

        # Sweeping catenary main cables (front & back)
        n_seg = 12
        for tz in (-0.52, 0.52):
            for i in range(n_seg):
                u0, u1 = i / n_seg, (i + 1) / n_seg
                x0 = -2.05 + u0 * 4.10
                x1 = -2.05 + u1 * 4.10
                y0 = 1.85 - 1.55 * (1.0 - (2.0 * u0 - 1.0) ** 2)
                y1 = 1.85 - 1.55 * (1.0 - (2.0 * u1 - 1.0) ** 2)
                sc.add_cylinder((x0, y0, tz), (x1, y1, tz), 0.042, 0.042, CYAN if modern_safe else AMBER, segments=8, emissive=0.35)

        # Twisting 12-segment road deck + vertical steel suspenders
        for i in range(n_seg):
            u = (i + 0.5) / n_seg
            x = -2.05 + u * 4.10
            env = math.sin(u * math.pi)
            roll = math.sin(t * 4.6 + u * 3.8) * twist_amp * env
            drop = 0.0
            is_snapped = (i < snapped_count)
            if is_snapped:
                drop = 0.85 * ((snapped_count - i) / max(1, snapped_count))
                roll += 0.55
            deck_y = -0.18 - drop + math.sin(t * 4.6 + u * 3.8) * 0.14 * twist_amp * env
            deck_col = EMERALD if modern_safe else lerp_color(STEEL_MID, DANGER, clamp(abs(roll) * 1.4))
            sc.add_box(
                (x, deck_y, 0.0),
                (0.36, 0.18 if modern_safe else 0.30, 1.08),
                deck_col,
                rot=(roll, 0.0, 0.0),
                metallic=0.62,
                emissive=0.25 if (modern_safe or abs(roll) > 0.35) else 0.0,
            )
            # Vertical suspenders
            if i % 2 == 1:
                cy_top = 1.85 - 1.55 * (1.0 - (2.0 * u - 1.0) ** 2)
                for tz in (-0.52, 0.52):
                    if not is_snapped:
                        edge_y = deck_y + math.sin(roll) * tz
                        sc.add_cylinder((x, cy_top, tz), (x, edge_y, tz), 0.022, 0.022, STEEL_LIGHT, segments=6)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_sky_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("bridge_twist_hero", "aeroelastic_flutter_loop", "torsion_45_degrees", "suspenders_stretching", "cables_unzip_collapse"):
            bg = self.bg_alert_bgr
        elif scene_key in ("modern_slotted_girder", "flutter_speed_comparison", "verdict_cta_card"):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_sky_bgr

        shake = math.sin(t * 55.0) * 0.06 if scene_key in ("bridge_twist_hero", "cables_unzip_collapse") else 0.0

        if scene_key == "bridge_twist_hero":
            # FRAME 0 HERO: Twisting steel suspension bridge + glowing wind arrows + UNIT-01 in Yellow Car panicking!
            cam = Camera3D(eye=(-0.85 + math.sin(t * 1.1) * 0.35 + shake, 0.95, 6.25), target=(0.0, 0.05, 0.0), fov_deg=42.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.95, span=7.0, step=1.0, rgb=(20, 56, 92), t=t, underwater=True)
            self._add_3d_suspension_bridge(sc, twist_amp=0.58, t=t)
            # UNIT-01 in his Yellow Crash-Test Car rocking wildly on the center deck!
            car_roll = math.sin(t * 4.6 + 1.9) * 0.55
            _add_3d_yellow_car(sc, center=(0.0, 0.05, 0.0), scale=0.68, yaw=-0.12, roll=car_roll, t=t, with_driver=True, driver_pose="panic_freefall", driver_emotion="panic")
            # Glowing wind arrows slamming across bridge
            for wy in (-0.35, 0.25, 0.85):
                sc.add_arrow_3d((-2.15, wy, 0.95), (-0.75, wy + math.sin(t * 6.0 + wy) * 0.18, 0.95), CYAN, shaft_r=0.055, head_r=0.14)
            overlays_2d.append(lambda d: draw_sparks(d, 540, 960, t, 14, 240, 140, p, seed=41))

        elif scene_key == "suspension_span_wave":
            cam = Camera3D(eye=(0.45, 0.82, 6.55), target=(0.0, 0.05, 0.0), fov_deg=42.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.0, span=7.0, step=1.0, rgb=(20, 56, 92), t=t, underwater=True)
            self._add_3d_suspension_bridge(sc, twist_amp=0.45, t=t)
            add_crash_test_dummy(sc, pos=(-1.55, -0.95, 1.15), scale=0.68, yaw=0.42, pose="point_right", emotion="curious", t=t)

        elif scene_key == "solid_h_girder_profile":
            # Exploded 3D cross-section of narrow road deck + towering solid 8-foot H-plate girders!
            cam = Camera3D(eye=(1.55, 0.78, 6.15), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Horizontal road slab + 2 tall solid vertical 8-ft steel H-girder walls
            sc.add_box((0.62, 0.05, 0.0), (1.95, 0.22, 1.85), ROAD_DARK, metallic=0.42)
            for sx in (-0.98, 0.98):
                sc.add_box((0.62 + sx, 0.05, 0.0), (0.20, 1.48, 1.90), STEEL_LIGHT, metallic=0.78)
                sc.add_box((0.62 + sx, 0.78, 0.0), (0.38, 0.12, 1.92), AMBER, metallic=0.68, texture="machined_brass")
                sc.add_box((0.62 + sx, -0.68, 0.0), (0.38, 0.12, 1.92), AMBER, metallic=0.68, texture="machined_brass")
            sc.add_arrow_3d((1.88, -0.68, 0.35), (1.88, 0.78, 0.35), CYAN, shaft_r=0.06, head_r=0.15)
            add_crash_test_dummy(sc, pos=(-1.48, -0.88, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "wind_tunnel_vortices":
            # Side-view wind tunnel: dense cyan wind slamming into flat H-girder wall & curling into crimson eddies!
            cam = Camera3D(eye=(0.0, 0.55, 6.25), target=(0.10, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # H-girder cross section centered right
            sc.add_box((0.45, 0.10, 0.0), (1.35, 0.18, 0.95), ROAD_DARK, metallic=0.45)
            for sx in (-0.68, 0.68):
                sc.add_box((0.45 + sx, 0.10, 0.0), (0.16, 1.25, 0.98), STEEL_LIGHT, metallic=0.76)
            # Incoming steady cyan wind streams from left -> blocked wall
            for wy in (-0.38, 0.10, 0.58):
                shift = ((t * 1.6 + wy) % 0.5) * 0.45
                sc.add_arrow_3d((-1.45 + shift, wy, 0.15), (-0.42 + shift * 0.3, wy, 0.15), CYAN, shaft_r=0.055, head_r=0.14)
            # Turbulent crimson vortices peeling off behind right side!
            for vi, vy in enumerate((0.62, -0.42)):
                va = t * 7.0 * (1 if vi == 0 else -1)
                vx = 1.55 + math.cos(va) * 0.18
                sc.add_sphere((vx, vy + math.sin(va) * 0.18, 0.15), 0.24, DANGER, emissive=0.72, rim_rgb=AMBER, bloom=True)
            add_crash_test_dummy(sc, pos=(-1.55, -0.92, 0.72), scale=0.70, yaw=0.38, pose="brace_impact", emotion="curious", t=t)

        elif scene_key == "alternating_vortex_twist":
            # Cross-section deck rocking as alternating upper/lower crimson vortices torque it!
            cam = Camera3D(eye=(0.25, 0.60, 6.25), target=(0.10, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            tilt = math.sin(t * 5.2) * 0.42
            sc.add_box((0.55, 0.12, 0.0), (1.75, 0.22, 1.10), STEEL_MID, rot=(0.0, 0.0, tilt), metallic=0.68)
            for sx in (-0.85, 0.85):
                gx = 0.55 + math.cos(tilt) * sx
                gy = 0.12 + math.sin(tilt) * sx
                sc.add_box((gx, gy, 0.0), (0.16, 1.08, 1.12), STEEL_LIGHT, rot=(0.0, 0.0, tilt), metallic=0.76)
            # Alternating torque arrows pushing ends up & down
            dir_s = 1.0 if math.cos(t * 5.2) > 0 else -1.0
            sc.add_arrow_3d((0.55 - 0.95, 0.12 - dir_s * 0.95, 0.25), (0.55 - 0.95, 0.12 + dir_s * 0.45, 0.25), DANGER, shaft_r=0.072, head_r=0.17)
            sc.add_arrow_3d((0.55 + 0.95, 0.12 + dir_s * 0.95, 0.25), (0.55 + 0.95, 0.12 - dir_s * 0.45, 0.25), CYAN, shaft_r=0.072, head_r=0.17)
            add_crash_test_dummy(sc, pos=(-1.48, -0.88, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "aeroelastic_flutter_loop":
            # Negative damping feedback loop: tilted deck amplifies wind torque!
            cam = Camera3D(eye=(-0.85, 0.65, 6.25), target=(0.15, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            amp = 0.25 + prog * 0.48
            tilt = math.sin(t * 6.5) * amp
            sc.add_box((0.55, 0.15, 0.0), (1.80, 0.24, 1.05), lerp_color(STEEL_MID, DANGER, prog * 0.65), rot=(0.0, 0.0, tilt), metallic=0.66)
            for sx in (-0.88, 0.88):
                sc.add_box((0.55 + math.cos(tilt) * sx, 0.15 + math.sin(tilt) * sx, 0.0), (0.16, 1.12, 1.08), STEEL_LIGHT, rot=(0.0, 0.0, tilt), metallic=0.76)
            # Huge self-reinforcing glowing crimson lift arrows!
            sc.add_arrow_3d((-0.65, 0.15, 0.25), (0.35, 0.95, 0.25), CYAN, shaft_r=0.068, head_r=0.165)
            sc.add_arrow_3d((0.95, -0.65, 0.25), (1.25, 1.15, 0.25), DANGER, shaft_r=0.085, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.46, -0.88, 0.72), scale=0.72, yaw=0.38, pose="brace_impact", emotion="shock", t=t)

        elif scene_key == "torsion_45_degrees":
            # Dramatic 45-degree twisting deck with live ROLL gauge + Yellow Car sliding on pitched road!
            cam = Camera3D(eye=(-1.15, 0.75, 6.45), target=(0.20, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(20, 50, 84), t=t, underwater=True)
            deg = 12.0 + ease_in_out_cubic(prog) * 33.0
            rad = math.radians(deg) * (1.0 if math.sin(t * 4.5) >= 0 else -1.0)
            sc.add_box((-0.25, 0.05, 0.0), (1.95, 0.22, 1.25), DANGER, rot=(0.0, 0.0, rad), metallic=0.58, emissive=0.25)
            _add_3d_yellow_car(sc, center=(-0.25, 0.26, 0.0), scale=0.62, yaw=0.15, pitch=rad, t=t, with_driver=True, driver_pose="panic_freefall", driver_emotion="panic")
            overlays_2d.append(
                lambda d, _deg=int(round(deg)), _p=prog: draw_pressure_gauge(
                    d, 855, 990, 128, clamp(0.25 + _p * 0.70), "DECK ROLL", f"{_deg} DEG", p, self.font_black
                )
            )

        elif scene_key == "suspenders_stretching":
            # Macro close-up of 5 vertical steel suspenders glowing crimson under extreme tensile stress!
            cam = Camera3D(eye=(1.45, 0.75, 6.05), target=(0.08, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            sc.add_box((0.55, 1.55, 0.0), (2.45, 0.24, 0.42), STEEL_MID, metallic=0.72)
            sc.add_box((0.55, -1.25, 0.0), (2.45, 0.28, 0.75), STEEL_DARK, metallic=0.66)
            for i in range(5):
                cx_s = -0.35 + i * 0.45
                heat = clamp(prog * 1.4 - i * 0.15)
                col = lerp_color(STEEL_LIGHT, DANGER, heat)
                sc.add_cylinder((cx_s, 1.45, 0.0), (cx_s, -1.12, 0.0), 0.055, 0.055, col, segments=10, emissive=0.55 * heat, bloom=(heat > 0.5))
            sc.add_arrow_3d((0.55, -0.35, 0.45), (0.55, -1.65, 0.45), DANGER, shaft_r=0.085, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.46, -0.88, 0.72), scale=0.72, yaw=0.38, pose="brace_impact", emotion="shock", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 610, 960, t, 18, 220, 160, p, seed=48))

        elif scene_key == "cables_unzip_collapse":
            # CLIMAX: Sequential zipper snap across the 3D suspension span + sparks!
            cam = Camera3D(eye=(-0.55 + shake, 0.85, 6.45), target=(0.05, 0.0, 0.0), fov_deg=42.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, rgb=(22, 48, 82), t=t, underwater=True)
            snapped = min(10, 1 + int(prog * 10.5))
            self._add_3d_suspension_bridge(sc, twist_amp=0.62, t=t, snapped_count=snapped)
            add_crash_test_dummy(sc, pos=(-1.55, -0.95, 1.15), scale=0.70, yaw=0.35, pose="panic_freefall", emotion="panic", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 560, 930, t, 26, 260, 170, p, seed=49))

        elif scene_key == "modern_slotted_girder":
            # Streamlined modern aerodynamic trapezoidal box girder with glowing emerald open wind slots!
            cam = Camera3D(eye=(1.35, 0.72, 6.15), target=(0.12, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Twin streamlined trapezoidal box decks with open air slot right down the center!
            for sx in (-0.68, 0.68):
                sc.add_box((0.55 + sx, 0.12, 0.0), (0.95, 0.34, 1.55), STEEL_LIGHT, metallic=0.78)
                sc.add_box((0.55 + sx, 0.32, 0.0), (0.98, 0.08, 1.58), EMERALD, metallic=0.55, emissive=0.35)
            # Smooth laminar cyan wind gliding horizontally + emerald equalizing flow right through the open center slot!
            sc.add_arrow_3d((0.55, -0.85, 0.25), (0.55, 1.15, 0.25), EMERALD, shaft_r=0.072, head_r=0.17)
            sc.add_arrow_3d((-0.95, 0.55, 0.25), (1.95, 0.55, 0.25), CYAN, shaft_r=0.06, head_r=0.15)
            add_crash_test_dummy(sc, pos=(-1.50, -0.88, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="relief", t=t)

        elif scene_key == "flutter_speed_comparison":
            # Clean split layout: UNIT-01 unobstructed on left pointing at 42 MPH vs 150+ MPH bars!
            cam = Camera3D(eye=(0.25, 0.35, 5.95), target=(0.0, -0.25, 0.0), fov_deg=41.0, cy_offset=95.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            add_crash_test_dummy(sc, pos=(-1.42, -0.45, 0.55), scale=0.72, yaw=0.38, pose="point_right", emotion="relief", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=325,
                    y0=715,
                    width=680,
                    height=355,
                    items=[
                        ("1940 H-GIRDER", "42 MPH", 42.0 / 160.0, p.danger),
                        ("MODERN SLOTTED DECK", "150+ MPH", 150.0 / 160.0, p.emerald),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([325, 1105, 1005, 1188], radius=16, fill=p.surface_panel, outline=p.emerald, width=4)
                f = load_font(self.font_black, 28)
                msg = "3.5X SAFER AERODYNAMICS"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((665 - (bb[2] - bb[0]) / 2, 1130), msg, font=f, fill=p.emerald)

            overlays_2d.append(_bars)

        else:  # verdict_cta_card — FUN FINALE: UNIT-01 zooms safely across the rock-solid emerald modern bridge in his Yellow Car!
            cam = Camera3D(eye=(math.sin(t * 0.8) * 0.40, 0.62, 6.05), target=(0.0, 0.10, 0.0), fov_deg=41.0, cy_offset=25.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.90, span=7.0, step=1.0, rgb=(20, 56, 86), t=t, underwater=True)
            self._add_3d_suspension_bridge(sc, twist_amp=0.0, t=t, modern_safe=True)
            car_x = -1.65 + ease_out_cubic(min(1.0, prog * 1.65)) * 1.65
            _add_3d_yellow_car(sc, center=(car_x, -0.02, 0.15), scale=0.82, yaw=-0.22, t=t, with_driver=False)
            add_crash_test_dummy(sc, pos=(car_x - 0.05, 1.06, 0.28), scale=0.78, yaw=math.sin(t * 1.8) * 0.14, pose="cta_shrug", emotion="cta", t=t, ground_shadow=False)

            def _cta_buttons(d: ImageDraw.ImageDraw) -> None:
                pulse = 1.0 + 0.04 * math.sin(t * 7.0)
                for label, bx, col in (("YES", 205, p.cyan), ("NO", 875, p.amber)):
                    bw, bh = int(134 * pulse), int(84 * pulse)
                    by = 1165
                    d.rounded_rectangle([bx - bw, by, bx + bw, by + bh], radius=18, fill=p.surface_panel, outline=col, width=5)
                    f = load_font(self.font_black, 46)
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "bridge_twist_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("bridge_twist_hero", t=0.35, prog=0.45, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
