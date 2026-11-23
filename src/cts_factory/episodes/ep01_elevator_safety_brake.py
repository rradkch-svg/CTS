"""Episode 01: How Elevators STOP When Every Cable Snaps — True 3D Phong + Crash-Test Dummy."""

from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette, build_stage_background, lerp_color
from cts_factory.engine.primitives import (
    draw_dotted_arc,
    draw_pressure_gauge,
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes.base import EpisodeScene, register_scene

STEEL_LIGHT = (188, 204, 224)
STEEL_MID = (112, 134, 162)
STEEL_DARK = (54, 70, 96)
CAB_INTERIOR = (28, 42, 66)
BRASS = (218, 168, 72)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


@register_scene("ep01_elevator_safety_brake")
class ElevatorSafetyBrakeScene(EpisodeScene):
    """Articulated 12-beat True 3D Phong CAD + Crash-Test Dummy ('UNIT-01') choreography."""

    slug = "ep01_elevator_safety_brake"
    episode_id = "ep01"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_default_bgr: np.ndarray | None = None
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
        self.bg_default_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.cyan)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_alert_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.amber)),
            cv2.COLOR_RGB2BGR,
        )
        self.bg_safe_bgr = cv2.cvtColor(
            np.array(build_stage_background(w, h, self.palette, spot_color=self.palette.emerald)),
            cv2.COLOR_RGB2BGR,
        )
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_shaft_rails(self, sc: Scene3D, y_offset: float = 0.0, rail_x: float = 1.62) -> None:
        """Twin 3D vertical machined steel T-guide rails with periodic wall brackets."""
        for sx in (-1, 1):
            rx = sx * rail_x
            sc.add_box((rx, 0.2, 0.0), (0.20, 7.2, 0.26), STEEL_LIGHT, metallic=0.72)
            sc.add_box((rx + sx * 0.16, 0.2, -0.05), (0.14, 7.2, 0.42), STEEL_DARK, metallic=0.55)
            for k in range(-3, 4):
                by = k * 1.1 + (y_offset % 1.1)
                sc.add_box((rx + sx * 0.34, by, -0.10), (0.28, 0.18, 0.30), STEEL_MID, metallic=0.5)

    def _add_3d_elevator_cab(
        self,
        sc: Scene3D,
        cy: float = 0.0,
        locked: bool = False,
        glow_col: tuple[int, int, int] = CYAN,
        dummy_pose: str = "explain",
        dummy_emotion: str = "engineer",
        t: float = 0.0,
        dummy_yaw: float = -0.18,
    ) -> None:
        """Open-front 3D steel elevator cab cutaway with Crash-Test Dummy standing inside."""
        # Rear interior wall & side walls with brushed metallic / architectural rib PBR textures
        sc.add_box((0.0, cy, -0.95), (2.42, 2.75, 0.14), CAB_INTERIOR, metallic=0.30, texture="cabin_wall")
        sc.add_box((-1.20, cy, 0.0), (0.14, 2.75, 1.92), STEEL_MID, metallic=0.58, texture="brushed_steel")
        sc.add_box((1.20, cy, 0.0), (0.14, 2.75, 1.92), STEEL_MID, metallic=0.58, texture="brushed_steel")
        # Overhead interior glowing LED light bar (with optical bloom!)
        sc.add_box((0.0, cy + 1.24, -0.20), (1.70, 0.08, 0.24), glow_col, emissive=0.82, metallic=0.1, bloom=True)
        # Floor deck & safety plank underneath
        sc.add_box((0.0, cy - 1.40, 0.0), (2.56, 0.24, 2.04), STEEL_MID, metallic=0.62, texture="brushed_steel")
        plank_col = EMERALD if locked else BRASS
        sc.add_box((0.0, cy - 1.66, 0.0), (2.78, 0.24, 1.55), plank_col, metallic=0.65, emissive=0.22 if locked else 0.0, texture="hazard_plate", bloom=locked)
        # Twin clamp jaws gripping the vertical T-rails
        for sx in (-1, 1):
            sc.add_box((sx * 1.48, cy - 1.66, 0.0), (0.36, 0.42, 0.56), EMERALD if locked else AMBER, metallic=0.60, emissive=0.30 if locked else 0.0, texture="machined_brass", bloom=locked)
        # Roof crosshead beam
        sc.add_box((0.0, cy + 1.46, 0.0), (2.58, 0.28, 2.04), STEEL_LIGHT, metallic=0.75, texture="brushed_steel")

        # Articulated 3D Crash-Test Dummy INSIDE the 3D cab!
        add_crash_test_dummy(
            sc,
            pos=(0.0, cy - 0.18, 0.08),
            scale=0.86,
            yaw=dummy_yaw,
            pose=dummy_pose,
            emotion=dummy_emotion,
            t=t,
        )

    def _add_3d_cables(
        self,
        sc: Scene3D,
        y_bot: float,
        y_top: float,
        count: int = 8,
        spread: float = 1.6,
        snapped: int = 0,
        snap_t: float = 0.0,
        highlight_idx: int = -1,
        single_active: bool = False,
    ) -> None:
        """Render 8 parallel 3D cylindrical steel hoist cables with animated recoil snap."""
        for i in range(count):
            frac = (i / max(1, count - 1)) - 0.5
            x = frac * spread
            z = 0.16 * math.sin(i * 1.3)
            if single_active and i != count // 2:
                sc.add_line_3d((x, y_bot, z), (x, y_top, z), (48, 66, 94), width=2)
                continue
            if i < snapped:
                mid = (y_bot + y_top) * 0.52 + 0.08 * math.sin(i * 2.1)
                recoil = 0.22 + 0.65 * clamp(snap_t)
                whip = math.sin(snap_t * 24.0 + i * 1.7) * 0.22
                sc.add_cylinder((x, y_bot, z), (x + whip, mid - recoil * 0.55, z + 0.12), 0.045, 0.042, DANGER, segments=8, metallic=0.6, emissive=0.2)
                sc.add_cylinder((x - whip * 0.8, mid + recoil * 0.65, z - 0.08), (x, y_top, z), 0.045, 0.042, AMBER, segments=8, metallic=0.6, emissive=0.15)
            else:
                col = CYAN if (single_active or i == highlight_idx) else STEEL_LIGHT
                rad = 0.055 if (single_active or i == highlight_idx) else 0.038
                sc.add_cylinder((x, y_bot, z), (x, y_top, z), rad, rad, col, segments=10, metallic=0.72, emissive=0.25 if col == CYAN else 0.0)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float) -> tuple[np.ndarray, list]:
        """Build and render the 3D scene for the active beat, plus optional 2D HUD overlays."""
        p = self.palette
        assert p is not None and self.bg_default_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("cables_snap_peak", "all_ropes_severed", "flyweights_flare_latch", "wedges_pinch_rails"):
            bg = self.bg_alert_bgr
        elif scene_key in ("cab_frozen_spark_fade", "verdict_cta_card"):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_default_bgr

        shake = math.sin(t * 58.0) * 0.06 if scene_key in ("cables_snap_peak", "all_ropes_severed", "wedges_pinch_rails") else 0.0

        if scene_key == "cables_snap_peak":
            # FRAME 0 HERO: Huge dramatic 3D close-up of UNIT-01 panicking inside falling 3D cab + snapping 3D cables!
            yaw_cam = math.sin(t * 1.4) * 0.35 + 1.55
            cam = Camera3D(eye=(yaw_cam + shake, 0.95, 5.45), target=(0.0, 0.15, 0.0), fov_deg=41.0, cy_offset=55.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, t=t)
            self._add_3d_shaft_rails(sc, y_offset=t * 2.8)
            self._add_3d_elevator_cab(sc, cy=-0.15, locked=False, glow_col=DANGER, dummy_pose="panic_freefall", dummy_emotion="panic", t=t, dummy_yaw=-0.22)
            self._add_3d_cables(sc, y_bot=1.45, y_top=2.95, count=8, spread=1.75, snapped=8, snap_t=clamp(0.32 + prog * 0.7))
            sc.add_arrow_3d((-2.22, 1.55, 0.25), (-2.22, -0.75, 0.25), DANGER, shaft_r=0.09, head_r=0.22)
            sc.add_arrow_3d((2.22, 1.55, 0.25), (2.22, -0.75, 0.25), DANGER, shaft_r=0.09, head_r=0.22)
            overlays_2d.append(lambda d: draw_sparks(d, 540, 740, t + 0.1, 22, 230, 140, p, seed=11))

        elif scene_key == "cab_halts_midshaft":
            locked = prog > 0.38
            drop = ease_out_cubic(min(1.0, prog / 0.38)) * 0.65
            cam = Camera3D(eye=(-2.1 + prog * 0.7, 0.6, 6.4), target=(0.0, -0.1, 0.0), fov_deg=41.0, cy_offset=55.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.3, span=7.0, step=1.0, t=t)
            self._add_3d_shaft_rails(sc, y_offset=0.0 if locked else prog * 1.8)
            self._add_3d_elevator_cab(
                sc,
                cy=0.35 - drop,
                locked=locked,
                glow_col=EMERALD if locked else AMBER,
                dummy_pose="relief_wave" if locked else "brace_impact",
                dummy_emotion="relief" if locked else "brace",
                t=t,
                dummy_yaw=0.20,
            )
            self._add_3d_cables(sc, y_bot=1.95 - drop, y_top=3.05, count=8, spread=1.5, snapped=8, snap_t=0.8)
            if locked:
                sc.add_arrow_3d((-2.25, -1.2, 0.2), (-2.25, 0.85, 0.2), EMERALD, shaft_r=0.085, head_r=0.20)
                sc.add_arrow_3d((2.25, -1.2, 0.2), (2.25, 0.85, 0.2), EMERALD, shaft_r=0.085, head_r=0.20)
                overlays_2d.append(lambda d: draw_sparks(d, 340, 1170, t, 10, 90, 60, p, seed=31))
                overlays_2d.append(lambda d: draw_sparks(d, 740, 1170, t, 10, 90, 60, p, seed=37))
            else:
                sc.add_arrow_3d((0.0, -1.8, 0.4), (0.0, -2.8, 0.4), DANGER, shaft_r=0.09, head_r=0.22)

        elif scene_key == "multi_cable_xray":
            cam = Camera3D(eye=(2.3, 1.25, 6.8), target=(0.0, 0.4, 0.0), fov_deg=41.0, cy_offset=50.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0, t=t)
            self._add_3d_shaft_rails(sc)
            sc.add_gear_3d((0.0, 2.55, 0.0), 0.92, 0.52, 18, t * 1.4, STEEL_MID, rot=(0.0, 0.0, 0.0), metallic=0.72)
            active_rope = int(prog * 8) % 8
            self._add_3d_cables(sc, y_bot=0.45, y_top=2.45, count=8, spread=1.65, highlight_idx=active_rope)
            self._add_3d_elevator_cab(sc, cy=-1.05, locked=False, glow_col=CYAN, dummy_pose="point_right", dummy_emotion="engineer", t=t, dummy_yaw=-0.25)
            sc.add_arrow_3d((-2.25, 0.2, 0.15), (-2.25, 2.2, 0.15), CYAN, shaft_r=0.08, head_r=0.19)
            sc.add_arrow_3d((2.25, 0.2, 0.15), (2.25, 2.2, 0.15), CYAN, shaft_r=0.08, head_r=0.19)

        elif scene_key == "single_cable_load_test":
            cam = Camera3D(eye=(-2.0, 0.9, 6.4), target=(0.0, 0.15, 0.0), fov_deg=40.0, cy_offset=50.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, t=t)
            bob = math.sin(t * 2.5) * 0.08
            self._add_3d_cables(sc, y_bot=1.05 + bob, y_top=3.05, count=8, spread=1.6, single_active=True)
            self._add_3d_elevator_cab(sc, cy=-0.45 + bob, locked=False, glow_col=EMERALD, dummy_pose="explain", dummy_emotion="relief", t=t, dummy_yaw=0.22)
            sc.add_arrow_3d((-2.15, 0.4, 0.2), (-2.15, 2.55, 0.2), EMERALD, shaft_r=0.09, head_r=0.21)
            sc.add_arrow_3d((2.15, 1.3, 0.2), (2.15, -0.95, 0.2), AMBER, shaft_r=0.09, head_r=0.21)

        elif scene_key == "governor_spinning":
            cam = Camera3D(eye=(1.9, 0.85, 5.6), target=(0.0, 0.1, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.95, span=7.0, step=1.0, t=t)
            # 3D rooftop steel governor housing + spinning brass flywheel
            sc.add_box((0.55, 0.2, -0.55), (2.6, 2.5, 0.24), STEEL_DARK, metallic=0.55)
            ang = t * 2.8
            sc.add_gear_3d((0.55, 0.2, 0.0), 1.08, 0.34, 18, ang, BRASS, metallic=0.72)
            for sx in (-1, 1):
                a = ang + (0 if sx == 1 else math.pi)
                fx = 0.55 + math.cos(a) * 0.56
                fy = 0.2 + math.sin(a) * 0.56
                sc.add_cylinder((0.55, 0.2, 0.34), (fx, fy, 0.34), 0.04, 0.04, CYAN, segments=10, emissive=0.35, bloom=True)
                sc.add_sphere((fx, fy, 0.38), 0.19, AMBER, metallic=0.55, depth_bias=-0.22)
            # Safety governor rope dropping down shaft
            sc.add_cylinder((-0.38, 0.2, 0.0), (-0.38, -2.5, 0.0), 0.045, 0.045, CYAN, segments=10, emissive=0.35, bloom=True)
            sc.add_cylinder((1.48, 0.2, 0.0), (1.48, -2.5, 0.0), 0.045, 0.045, CYAN, segments=10, emissive=0.35, bloom=True)
            # UNIT-01 standing on lab floor pointing up at governor
            add_crash_test_dummy(sc, pos=(-1.30, -0.78, 0.55), scale=0.84, yaw=0.35, pose="point_right", emotion="curious", t=t)

        elif scene_key == "all_ropes_severed":
            cam = Camera3D(eye=(-1.8 + shake, 0.8, 5.7), target=(-0.2, 0.1, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0)
            snapped = min(8, 2 + int(prog * 7.5))
            self._add_3d_cables(sc, y_bot=-1.2, y_top=2.4, count=8, spread=1.8, snapped=snapped, snap_t=prog)
            add_crash_test_dummy(sc, pos=(-1.45, -0.75, 0.55), scale=0.86, yaw=0.25, pose="brace_impact", emotion="panic", t=t)
            sc.add_arrow_3d((-0.2, 1.8, 0.45), (-0.2, -0.8, 0.45), DANGER, shaft_r=0.09, head_r=0.22)
            speed_v = clamp(0.45 + prog * 0.48)
            pct = int(round(prog * 18))
            overlays_2d.append(lambda d: draw_sparks(d, 480, 920, t, 20, 200, 140, p, seed=55))
            overlays_2d.append(
                lambda d, _sv=speed_v, _pct=pct: draw_pressure_gauge(
                    d, 825, 960, 138, _sv, "OVERSPEED", f"+{_pct}%", p, self.font_black
                )
            )

        elif scene_key == "flyweights_flare_latch":
            latched = prog > 0.62
            cam = Camera3D(eye=(1.7 + (shake if latched else 0.0), 0.75, 5.4), target=(0.15, 0.05, 0.0), fov_deg=40.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.0, span=7.0, step=1.0)
            # Outer notched 3D steel ratchet ring (12 teeth blocks arranged in circle)
            cx_g, cy_g = 0.55, 0.25
            for i in range(12):
                ra = i * (2 * math.pi / 12)
                sc.add_box(
                    (cx_g + math.cos(ra) * 1.48, cy_g + math.sin(ra) * 1.48, 0.0),
                    (0.28, 0.22, 0.36),
                    STEEL_LIGHT,
                    rot=(0.0, 0.0, ra),
                    metallic=0.72,
                )
            spin_ang = (prog * 14.0) if not latched else (0.62 * 14.0)
            sc.add_gear_3d((cx_g, cy_g, 0.0), 0.96, 0.30, 16, spin_ang, BRASS, metallic=0.72)
            flare = ease_out_cubic(min(1.0, prog / 0.62))
            fw_r = 0.52 + flare * 0.78
            for sx in (-1, 1):
                a = spin_ang + (0 if sx == 1 else math.pi)
                fx = cx_g + math.cos(a) * fw_r
                fy = cy_g + math.sin(a) * fw_r
                sc.add_cylinder((cx_g, cy_g, 0.24), (fx, fy, 0.24), 0.055, 0.055, DANGER if latched else AMBER, segments=10)
                sc.add_sphere((fx, fy, 0.26), 0.22, DANGER if latched else AMBER, metallic=0.45, emissive=0.25 if latched else 0.0)
                if not latched:
                    sc.add_arrow_3d((fx, fy, 0.30), (cx_g + math.cos(a) * (fw_r + 0.65), cy_g + math.sin(a) * (fw_r + 0.65), 0.30), AMBER, shaft_r=0.05, head_r=0.13)
            add_crash_test_dummy(sc, pos=(-1.22, -0.78, 0.55), scale=0.76, yaw=0.35, pose="point_right", emotion="shock" if latched else "curious", t=t)
            if latched:
                overlays_2d.append(lambda d: draw_sparks(d, 640, 860, t, 18, 160, 130, p, seed=71))

        elif scene_key == "linkage_rod_lift":
            cam = Camera3D(eye=(1.8, 0.95, 5.8), target=(0.0, -0.1, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0, t=t)
            lift = ease_in_out_cubic(prog) * 0.55
            # Under-cab 3D steel beams
            sc.add_box((0.35, 1.15, 0.0), (3.0, 0.38, 0.85), STEEL_MID, metallic=0.62)
            sc.add_box((0.35, -0.85, 0.0), (3.2, 0.38, 0.95), STEEL_DARK, metallic=0.58)
            # Stopped cyan rope pulling up on left activator
            sc.add_cylinder((-0.95, 2.5, 0.25), (-0.95, -0.15 + lift, 0.25), 0.05, 0.05, CYAN, segments=14, emissive=0.45, bloom=True)
            sc.add_arrow_3d((-1.30, -0.55, 0.35), (-1.30, 1.15, 0.35), CYAN, shaft_r=0.075, head_r=0.18)
            # Horizontal 3D brass bar & twin scissor linkages lifting wedges
            bar_y = -0.18 + lift
            sc.add_cylinder((-0.95, bar_y, 0.25), (1.65, bar_y, 0.25), 0.075, 0.075, BRASS, segments=16, metallic=0.75)
            for sx in (-1, 1):
                wx = 0.35 + sx * 1.15
                sc.add_cylinder((0.35 + sx * 0.50, -0.70, 0.25), (wx, bar_y, 0.25), 0.06, 0.06, STEEL_LIGHT, segments=14)
                sc.add_box((wx, bar_y + 0.05, 0.25), (0.36, 0.65, 0.42), AMBER, rot=(0.0, 0.0, sx * 0.14), metallic=0.62, texture="machined_brass")
                sc.add_arrow_3d((wx + sx * 0.40, bar_y - 0.35, 0.35), (wx + sx * 0.40, bar_y + 0.55, 0.35), AMBER, shaft_r=0.06, head_r=0.15)
            add_crash_test_dummy(sc, pos=(-1.28, -0.95, 0.75), scale=0.72, yaw=0.35, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "wedges_pinch_rails":
            # CLIMAX: Massive 3D steel T-rail + twin angled 3D amber hardened wedges jamming inward!
            bite = ease_out_cubic(min(1.0, prog * 1.35))
            cam = Camera3D(eye=(1.55 + shake, 0.65, 5.55), target=(0.0, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0, t=t)
            # Massive central 3D steel T-rail
            sc.add_box((0.45, 0.1, 0.0), (0.42, 4.8, 0.48), STEEL_LIGHT, metallic=0.80)
            sc.add_box((0.45, 0.1, -0.30), (0.92, 4.8, 0.20), STEEL_DARK, metallic=0.62)
            for sx in (-1, 1):
                gap = (1.0 - bite) * 0.38
                wy = -0.35 + bite * 0.52
                sc.add_box((0.45 + sx * 1.10, 0.0, 0.0), (0.42, 2.35, 0.72), STEEL_DARK, rot=(0.0, 0.0, -sx * 0.08), metallic=0.58)
                sc.add_box(
                    (0.45 + sx * (0.46 + gap), wy, 0.06),
                    (0.42, 1.42, 0.60),
                    lerp_color(BRASS, AMBER, bite),
                    rot=(0.0, 0.0, -sx * 0.12),
                    metallic=0.66,
                    emissive=0.22 * bite,
                    texture="machined_brass",
                )
                sc.add_arrow_3d((0.45 + sx * 2.05, 0.05, 0.25), (0.45 + sx * 0.85, 0.05, 0.25), DANGER if bite > 0.65 else AMBER, shaft_r=0.095, head_r=0.23)
            sc.add_arrow_3d((0.45, 2.1, 0.45), (0.45, 0.85, 0.45), CYAN, shaft_r=0.085, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.28, -0.92, 0.72), scale=0.72, yaw=0.38, pose="brace_impact", emotion="shock", t=t)
            if bite > 0.45:
                overlays_2d.append(lambda d: draw_sparks(d, 585, 940, t, 24, 190, 140, p, seed=91))

        elif scene_key == "cab_frozen_spark_fade":
            cam = Camera3D(eye=(-1.6 + math.sin(t * 0.8) * 0.4, 0.55, 5.8), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0)
            self._add_3d_shaft_rails(sc)
            self._add_3d_elevator_cab(sc, cy=0.0, locked=True, glow_col=EMERALD, dummy_pose="relief_wave", dummy_emotion="relief", t=t, dummy_yaw=0.15)
            overlays_2d.append(lambda d: draw_dotted_arc(d, 540, 990, 325, 0, 360, p.emerald, width=4, step_deg=10))

        elif scene_key == "hydraulic_buffer_cutaway":
            cam = Camera3D(eye=(2.0, 0.95, 6.0), target=(0.0, -0.15, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.95, span=7.0, step=1.0)
            compress = ease_in_out_cubic(math.sin(prog * math.pi)) * 0.65
            # Concrete pit floor + 3D cylindrical hydraulic oil buffer
            sc.add_box((0.35, -1.78, 0.0), (4.6, 0.36, 2.4), STEEL_DARK, metallic=0.35)
            sc.add_cylinder((0.45, -1.60, 0.0), (0.45, -0.15, 0.0), 0.72, 0.72, STEEL_MID, segments=20, metallic=0.65, alpha=0.55)
            sc.add_cylinder((0.45, -1.55, 0.0), (0.45, -0.35 - compress * 0.35, 0.0), 0.56, 0.56, CYAN, segments=18, metallic=0.25, emissive=0.35)
            rod_top = 1.15 - compress
            sc.add_cylinder((0.45, -0.45 - compress * 0.35, 0.0), (0.45, rod_top, 0.0), 0.24, 0.24, STEEL_LIGHT, segments=16, metallic=0.82)
            sc.add_cylinder((0.45, rod_top, 0.0), (0.45, rod_top + 0.26, 0.0), 0.85, 0.85, AMBER, segments=20, metallic=0.55)
            sc.add_arrow_3d((1.65, -1.4, 0.2), (1.65, 0.45, 0.2), EMERALD, shaft_r=0.085, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.40, -0.68, 0.65), scale=0.84, yaw=0.36, pose="point_right", emotion="engineer", t=t)

        else:  # verdict_cta_card
            cam = Camera3D(eye=(math.sin(t * 0.9) * 0.5, 0.55, 5.4), target=(0.0, 0.15, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0)
            # Locked 3D elevator frame behind hero dummy
            sc.add_box((-1.85, 0.4, -1.2), (0.20, 4.6, 0.24), STEEL_LIGHT, metallic=0.7)
            sc.add_box((1.85, 0.4, -1.2), (0.20, 4.6, 0.24), STEEL_LIGHT, metallic=0.7)
            sc.add_box((0.0, -0.95, -1.1), (3.1, 0.26, 1.2), EMERALD, metallic=0.5, emissive=0.2)
            # Hero 3D UNIT-01 centered facing viewer shrugging toward YES / NO!
            add_crash_test_dummy(sc, pos=(0.0, -0.15, 0.35), scale=1.05, yaw=math.sin(t * 1.8) * 0.12, pose="cta_shrug", emotion="cta", t=t)

            def _cta_buttons(d: ImageDraw.ImageDraw) -> None:
                pulse = 1.0 + 0.04 * math.sin(t * 7.0)
                for label, bx, col in (("YES", 330, p.amber), ("NO", 750, p.emerald)):
                    bw, bh = int(155 * pulse), int(88 * pulse)
                    d.rounded_rectangle([bx - bw, 1210, bx + bw, 1210 + bh], radius=18, fill=p.surface_panel, outline=col, width=5)
                    f = load_font(self.font_black, 48)
                    bb = d.textbbox((0, 0), label, font=f)
                    d.text((bx - (bb[2] - bb[0]) / 2, 1210 + (bh - (bb[3] - bb[1])) / 2 - 4), label, font=f, fill=col)

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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "cab_halts_midshaft"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("cables_snap_peak", t=0.35, prog=0.45, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
