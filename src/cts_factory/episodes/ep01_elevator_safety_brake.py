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
    draw_cta_buttons,
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
TIMBER_DARK = (112, 74, 42)
TIMBER_LIGHT = (162, 114, 68)
OIL_AMBER = (218, 146, 38)
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
        """Open-front 3D steel elevator cab cutaway with BOLT's boots grounded flush on the floor (ZERO roof hand clipping!)."""
        sc.add_box((0.0, cy, -0.95), (2.42, 2.75, 0.14), CAB_INTERIOR, metallic=0.30, texture="cabin_wall")
        sc.add_box((-1.20, cy, 0.0), (0.14, 2.75, 1.92), STEEL_MID, metallic=0.58, texture="brushed_steel")
        sc.add_box((1.20, cy, 0.0), (0.14, 2.75, 1.92), STEEL_MID, metallic=0.58, texture="brushed_steel")
        # Subtle interior LED strip (controlled glow, never blinding bloom!)
        sc.add_box((0.0, cy + 1.26, -0.20), (1.65, 0.07, 0.22), glow_col, emissive=0.58, metallic=0.1, bloom=True)
        # Floor deck (top face = cy - 1.28) & safety plank underneath
        sc.add_box((0.0, cy - 1.40, 0.0), (2.56, 0.24, 2.04), STEEL_MID, metallic=0.62, texture="brushed_steel")
        plank_col = EMERALD if locked else BRASS
        sc.add_box((0.0, cy - 1.66, 0.0), (2.78, 0.24, 1.55), plank_col, metallic=0.65, emissive=0.18 if locked else 0.0, texture="hazard_plate", bloom=locked)
        for sx in (-1, 1):
            sc.add_box((sx * 1.48, cy - 1.66, 0.0), (0.36, 0.42, 0.56), EMERALD if locked else AMBER, metallic=0.60, emissive=0.22 if locked else 0.0, texture="machined_brass", bloom=locked)
        # Roof crosshead beam
        sc.add_box((0.0, cy + 1.46, 0.0), (2.58, 0.28, 2.04), STEEL_LIGHT, metallic=0.75, texture="brushed_steel")

        # BOLT's boots reach local y=-1.20*scale; placing pos_y = cy - 0.34 at scale=0.76 puts boots FLUSH at cy - 1.25 and raised hands strictly below cy + 0.85!
        add_crash_test_dummy(
            sc,
            pos=(0.0, cy - 0.34, 0.08),
            scale=0.76,
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
            z = 0.14 * math.sin(i * 1.3)
            if single_active and i != count // 2:
                sc.add_line_3d((x, y_bot, z), (x, y_top, z), (48, 66, 94), width=2)
                continue
            if i < snapped:
                mid = (y_bot + y_top) * 0.52 + 0.06 * math.sin(i * 2.1)
                recoil = 0.20 + 0.58 * clamp(snap_t)
                whip = math.sin(snap_t * 24.0 + i * 1.7) * 0.18
                sc.add_cylinder((x, y_bot, z), (x + whip, mid - recoil * 0.50, z + 0.10), 0.042, 0.040, DANGER, segments=8, metallic=0.6, emissive=0.2)
                sc.add_cylinder((x - whip * 0.8, mid + recoil * 0.58, z - 0.06), (x, y_top, z), 0.042, 0.040, AMBER, segments=8, metallic=0.6, emissive=0.15)
            else:
                col = CYAN if (single_active or i == highlight_idx) else STEEL_LIGHT
                rad = 0.052 if (single_active or i == highlight_idx) else 0.036
                sc.add_cylinder((x, y_bot, z), (x, y_top, z), rad, rad, col, segments=10, metallic=0.74, emissive=0.22 if col == CYAN else 0.0)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float, is_cover: bool = False) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_default_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("cables_snap_peak", "all_ropes_severed", "flyweights_flare_latch", "wedges_pinch_rails"):
            bg = self.bg_alert_bgr
        elif scene_key in ("cab_frozen_spark_fade", "verdict_cta_card"):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_default_bgr

        shake = math.sin(t * 58.0) * 0.05 if (scene_key in ("cables_snap_peak", "all_ropes_severed", "wedges_pinch_rails") and not is_cover) else 0.0

        if scene_key == "cables_snap_peak":
            # FRAME 0 HERO: Grounded BOLT inside falling cab + cleanly framed cables + in-frame arrows (ZERO forehead sparks!)
            if is_cover:
                cam = Camera3D(eye=(1.45, 0.92, 7.85), target=(0.0, 0.42, 0.0), fov_deg=41.0, cy_offset=45.0)
            else:
                yaw_cam = math.sin(t * 1.4) * 0.30 + 1.45
                cam = Camera3D(eye=(yaw_cam + shake, 0.92, 5.85), target=(0.0, 0.12, 0.0), fov_deg=41.0, cy_offset=55.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, t=t)
            self._add_3d_shaft_rails(sc, y_offset=t * 2.8)
            self._add_3d_elevator_cab(sc, cy=-0.22, locked=False, glow_col=DANGER, dummy_pose="panic_freefall", dummy_emotion="panic", t=t, dummy_yaw=-0.22)
            self._add_3d_cables(sc, y_bot=1.38, y_top=2.85, count=8, spread=1.65, snapped=8, snap_t=clamp(0.32 + prog * 0.7))
            # Downward fall arrows strictly INSIDE the horizontal frame!
            sc.add_arrow_3d((-1.92, 1.35, 0.22), (-1.92, -0.65, 0.22), DANGER, shaft_r=0.075, head_r=0.18)
            sc.add_arrow_3d((1.92, 1.35, 0.22), (1.92, -0.65, 0.22), DANGER, shaft_r=0.075, head_r=0.18)
            if not is_cover:
                # Sparks strictly at the snapping cables ABOVE the cab roof (never on BOLT's forehead!)
                overlays_2d.append(lambda d: draw_sparks(d, 540, 625, t + 0.1, 18, 210, 100, p, seed=11))

        elif scene_key == "cab_halts_midshaft":
            locked = prog > 0.38
            drop = ease_out_cubic(min(1.0, prog / 0.38)) * 0.62
            cam = Camera3D(eye=(-1.95 + prog * 0.6, 0.6, 6.5), target=(0.0, -0.1, 0.0), fov_deg=41.0, cy_offset=55.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.3, span=7.0, step=1.0, t=t)
            self._add_3d_shaft_rails(sc, y_offset=0.0 if locked else prog * 1.8)
            self._add_3d_elevator_cab(
                sc,
                cy=0.32 - drop,
                locked=locked,
                glow_col=EMERALD if locked else AMBER,
                dummy_pose="relief_wave" if locked else "brace_impact",
                dummy_emotion="relief" if locked else "brace",
                t=t,
                dummy_yaw=0.20,
            )
            self._add_3d_cables(sc, y_bot=1.92 - drop, y_top=3.05, count=8, spread=1.5, snapped=8, snap_t=0.8)
            if locked:
                sc.add_arrow_3d((-1.95, -1.15, 0.2), (-1.95, 0.80, 0.2), EMERALD, shaft_r=0.075, head_r=0.18)
                sc.add_arrow_3d((1.95, -1.15, 0.2), (1.95, 0.80, 0.2), EMERALD, shaft_r=0.075, head_r=0.18)
                overlays_2d.append(lambda d: draw_sparks(d, 340, 1170, t, 10, 90, 60, p, seed=31))
                overlays_2d.append(lambda d: draw_sparks(d, 740, 1170, t, 10, 90, 60, p, seed=37))
            else:
                sc.add_arrow_3d((0.0, -1.8, 0.4), (0.0, -2.7, 0.4), DANGER, shaft_r=0.082, head_r=0.19)

        elif scene_key == "multi_cable_xray":
            # Real grooved hoist traction drum + steel motor shaft (NOT floating gear teeth stabbing cables!)
            cam = Camera3D(eye=(2.1, 1.15, 6.9), target=(0.0, 0.35, 0.0), fov_deg=41.0, cy_offset=50.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0, t=t)
            self._add_3d_shaft_rails(sc)
            # Overhead machine-room floor beam + traction motor + grooved cylindrical hoist drum!
            sc.add_box((0.0, 2.55, -0.58), (3.4, 0.35, 0.45), STEEL_DARK, metallic=0.68)
            sc.add_cylinder((-1.15, 2.55, 0.0), (1.15, 2.55, 0.0), 0.14, 0.14, STEEL_LIGHT, segments=14, metallic=0.84)
            sc.add_cylinder((-0.92, 2.55, 0.0), (0.92, 2.55, 0.0), 0.54, 0.54, STEEL_MID, segments=22, metallic=0.78)
            sc.add_box((1.35, 2.55, -0.05), (0.65, 0.72, 0.68), BRASS, metallic=0.72, texture="machined_brass")
            active_rope = int(prog * 8) % 8
            self._add_3d_cables(sc, y_bot=0.42, y_top=2.50, count=8, spread=1.56, highlight_idx=active_rope)
            self._add_3d_elevator_cab(sc, cy=-1.05, locked=False, glow_col=CYAN, dummy_pose="point_right", dummy_emotion="engineer", t=t, dummy_yaw=-0.22)
            sc.add_arrow_3d((-1.95, 0.2, 0.15), (-1.95, 2.1, 0.15), CYAN, shaft_r=0.072, head_r=0.17)
            sc.add_arrow_3d((1.95, 0.2, 0.15), (1.95, 2.1, 0.15), CYAN, shaft_r=0.072, head_r=0.17)

        elif scene_key == "single_cable_load_test":
            cam = Camera3D(eye=(-1.9, 0.88, 6.5), target=(0.0, 0.15, 0.0), fov_deg=40.0, cy_offset=50.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, t=t)
            self._add_3d_shaft_rails(sc)
            bob = math.sin(t * 2.5) * 0.08
            self._add_3d_cables(sc, y_bot=1.02 + bob, y_top=3.05, count=8, spread=1.55, single_active=True)
            self._add_3d_elevator_cab(sc, cy=-0.45 + bob, locked=False, glow_col=EMERALD, dummy_pose="explain", dummy_emotion="relief", t=t, dummy_yaw=0.22)
            sc.add_arrow_3d((-1.92, 0.4, 0.2), (-1.92, 2.35, 0.2), EMERALD, shaft_r=0.078, head_r=0.185)
            sc.add_arrow_3d((1.92, 1.25, 0.2), (1.92, -0.85, 0.2), AMBER, shaft_r=0.078, head_r=0.185)

        elif scene_key == "governor_spinning":
            # Anchored rooftop pedestal + grooved pulley sheave + helical coil springs + BOLT clearly separated on left!
            cam = Camera3D(eye=(1.55, 0.82, 6.25), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.95, span=7.0, step=1.0, t=t)
            cx_g, cy_g = 0.65, 0.22
            # Structural pedestal base anchored to floor + shaft
            sc.add_box((cx_g, -1.85, -0.35), (2.2, 0.24, 1.3), STEEL_DARK, metallic=0.65, texture="concrete")
            sc.add_box((cx_g, -0.80, -0.45), (0.65, 1.95, 0.45), STEEL_DARK, metallic=0.72)
            sc.add_cylinder((cx_g, cy_g, -0.45), (cx_g, cy_g, 0.36), 0.16, 0.16, STEEL_LIGHT, segments=16, metallic=0.84)
            # Smooth grooved brass governor sheave (rope sits in groove cleanly outside wheel radius!)
            ang = t * 2.8
            sc.add_cylinder((cx_g, cy_g, -0.18), (cx_g, cy_g, 0.18), 1.02, 1.02, BRASS, segments=26, metallic=0.78)
            sc.add_cylinder((cx_g, cy_g, -0.06), (cx_g, cy_g, 0.06), 0.90, 0.90, STEEL_DARK, segments=24, metallic=0.70)
            # Spring-loaded flyweights with REAL 3D helical tension springs!
            for sx in (-1, 1):
                a = ang + (0 if sx == 1 else math.pi)
                fx = cx_g + math.cos(a) * 0.62
                fy = cy_g + math.sin(a) * 0.62
                sc.add_coil_spring((cx_g + math.cos(a) * 0.18, cy_g + math.sin(a) * 0.18, 0.28), (fx, fy, 0.28), coil_radius=0.065, wire_radius=0.018, turns=4, rgb=STEEL_LIGHT)
                sc.add_sphere((fx, fy, 0.30), 0.18, AMBER, metallic=0.58, depth_bias=-0.18)
            # Cyan governor rope tangentially wrapping the outer groove (x = cx_g ± 1.02, ZERO piercing!)
            sc.add_cylinder((cx_g - 1.02, cy_g, 0.0), (cx_g - 1.02, -1.90, 0.0), 0.042, 0.042, CYAN, segments=10, emissive=0.35, bloom=True)
            sc.add_cylinder((cx_g + 1.02, cy_g, 0.0), (cx_g + 1.02, -1.90, 0.0), 0.042, 0.042, CYAN, segments=10, emissive=0.35, bloom=True)
            add_crash_test_dummy(sc, pos=(-1.55, -0.82, 0.55), scale=0.72, yaw=0.35, pose="point_right", emotion="curious", t=t)

        elif scene_key == "all_ropes_severed":
            # Full context: falling cab + rails + snapping cables + accurate safe-zone +15% TRIP gauge!
            cam = Camera3D(eye=(-1.40 + shake, 0.72, 6.45), target=(0.10, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, t=t)
            self._add_3d_shaft_rails(sc, y_offset=t * 3.2)
            self._add_3d_elevator_cab(sc, cy=-1.05 - prog * 0.35, locked=False, glow_col=DANGER, dummy_pose="brace_impact", dummy_emotion="panic", t=t, dummy_yaw=0.22)
            snapped = min(8, 2 + int(prog * 7.5))
            self._add_3d_cables(sc, y_bot=0.45 - prog * 0.35, y_top=2.35, count=8, spread=1.45, snapped=snapped, snap_t=prog)
            sc.add_arrow_3d((0.0, 1.85, 0.45), (0.0, 0.65, 0.45), DANGER, shaft_r=0.075, head_r=0.18)
            pct = int(round(6 + prog * 12))  # Climbs cleanly across the +15% trip threshold!
            speed_v = clamp(pct / 20.0)      # +14% is orange-amber, >= +15% crosses into red trip zone!
            overlays_2d.append(lambda d: draw_sparks(d, 510, 820, t, 18, 170, 120, p, seed=55))
            overlays_2d.append(
                lambda d, _sv=speed_v, _pct=pct: draw_pressure_gauge(
                    d, 745, 1175, 108, _sv, "OVERSPEED", f"+{_pct}% TRIP" if _pct >= 15 else f"+{_pct}%", p, self.font_black
                )
            )

        elif scene_key == "flyweights_flare_latch":
            # Spring-loaded flyweights with VISIBLE helical coil springs flaring outward to latch ratchet teeth (NO ring clipping, NO BOLT clipping!)
            latched = prog > 0.62
            cam = Camera3D(eye=(1.35 + (shake if latched else 0.0), 0.72, 6.65), target=(0.10, 0.0, 0.0), fov_deg=40.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, t=t)
            cx_g, cy_g = 0.68, 0.08
            ring_r = 1.36
            n_ring = 24
            seg_len = 2.0 * math.pi * ring_r / n_ring + 0.05
            for i in range(n_ring):
                ra = i * (2.0 * math.pi / n_ring)
                sc.add_box(
                    (cx_g + math.cos(ra) * ring_r, cy_g + math.sin(ra) * ring_r, -0.04),
                    (0.15, seg_len, 0.34),
                    STEEL_DARK,
                    rot=(0.0, 0.0, ra),
                    metallic=0.68,
                )
            for i in range(12):
                ra = i * (2.0 * math.pi / 12)
                sc.add_box(
                    (cx_g + math.cos(ra) * 1.18, cy_g + math.sin(ra) * 1.18, 0.0),
                    (0.18, 0.14, 0.32),
                    STEEL_LIGHT,
                    rot=(0.0, 0.0, ra),
                    metallic=0.76,
                )
            spin_ang = (prog * 12.0) if not latched else (0.62 * 12.0)
            sc.add_cylinder((cx_g, cy_g, -0.14), (cx_g, cy_g, 0.14), 0.72, 0.72, BRASS, segments=24, metallic=0.76)
            flare = ease_out_cubic(min(1.0, prog / 0.62))
            fw_r = 0.44 + flare * 0.46  # Strictly <= 0.90 so 0.17 radius ball stops flush on 1.18 teeth (NEVER clips ring!)
            for sx in (-1, 1):
                a = spin_ang + (0 if sx == 1 else math.pi)
                fx = cx_g + math.cos(a) * fw_r
                fy = cy_g + math.sin(a) * fw_r
                sc.add_coil_spring(
                    (cx_g + math.cos(a) * 0.14, cy_g + math.sin(a) * 0.14, 0.28),
                    (fx, fy, 0.28),
                    coil_radius=0.068,
                    wire_radius=0.018,
                    turns=4,
                    rgb=DANGER if latched else STEEL_LIGHT,
                )
                sc.add_sphere((fx, fy, 0.30), 0.17, DANGER if latched else AMBER, metallic=0.52, emissive=0.28 if latched else 0.0, depth_bias=-0.18)
                if not latched:
                    sc.add_arrow_3d(
                        (cx_g + math.cos(a) * (fw_r + 0.16), cy_g + math.sin(a) * (fw_r + 0.16), 0.38),
                        (cx_g + math.cos(a) * (fw_r + 0.44), cy_g + math.sin(a) * (fw_r + 0.44), 0.38),
                        CYAN,
                        shaft_r=0.036,
                        head_r=0.092,
                    )
            # Positioned cleanly left so BOLT's arm NEVER touches the governor ring or arrows!
            add_crash_test_dummy(sc, pos=(-1.62, -0.82, 0.55), scale=0.68, yaw=0.38, pose="point_right", emotion="shock" if latched else "curious", t=t)
            if latched:
                overlays_2d.append(lambda d: draw_sparks(d, 675, 910, t, 18, 160, 130, p, seed=71))

        elif scene_key == "linkage_rod_lift":
            # Connected under-cab safety plank + articulated pivot linkages + EXTERNAL activator rope (ZERO piercing solid steel!)
            cam = Camera3D(eye=(1.45, 0.85, 6.75), target=(0.10, -0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0, t=t)
            lift = ease_in_out_cubic(prog) * 0.48
            cx_l = 0.48
            # Recognizable cab floor bottom + side corner posts + lower safety plank frame
            sc.add_box((cx_l, 1.38, 0.0), (2.30, 0.28, 0.85), STEEL_LIGHT, metallic=0.72)
            for sx in (-1, 1):
                sc.add_box((cx_l + sx * 1.08, 0.25, -0.25), (0.16, 2.25, 0.24), STEEL_MID, metallic=0.68)
            sc.add_box((cx_l, -0.85, 0.0), (2.40, 0.30, 0.88), STEEL_DARK, metallic=0.62)
            # External cyan governor rope outside right edge of cab pulling up on an external clevis lever (ZERO steel piercing!)
            rope_x = cx_l + 1.40
            sc.add_cylinder((rope_x, 2.25, 0.22), (rope_x, -0.22 + lift, 0.22), 0.044, 0.044, CYAN, segments=12, emissive=0.40, bloom=True)
            sc.add_arrow_3d((rope_x + 0.30, -0.45, 0.30), (rope_x + 0.30, 0.98, 0.30), CYAN, shaft_r=0.058, head_r=0.14)
            # Horizontal actuator shaft + pivot joints + tapered brass safety wedges lifting inside steel guides!
            bar_y = -0.22 + lift
            sc.add_cylinder((cx_l - 0.85, bar_y, 0.22), (rope_x, bar_y, 0.22), 0.064, 0.064, BRASS, segments=14, metallic=0.78)
            sc.add_sphere((rope_x, bar_y, 0.22), 0.11, STEEL_LIGHT, metallic=0.84)
            for sx in (-1, 1):
                wx = cx_l + sx * 0.72
                sc.add_cylinder((cx_l + sx * 0.28, -0.70, 0.22), (wx, bar_y, 0.22), 0.050, 0.050, STEEL_LIGHT, segments=12)
                sc.add_sphere((cx_l + sx * 0.28, -0.70, 0.22), 0.09, BRASS, metallic=0.78)
                sc.add_sphere((wx, bar_y, 0.22), 0.09, BRASS, metallic=0.78)
                # Tapered wedge pair inside chamfered steel jaw!
                sc.add_cylinder((wx, bar_y - 0.18, 0.22), (wx, bar_y + 0.38, 0.22), 0.22, 0.08, AMBER, segments=4, metallic=0.68)
                sc.add_arrow_3d((wx, bar_y + 0.44, 0.32), (wx, bar_y + 0.90, 0.32), AMBER, shaft_r=0.048, head_r=0.125)
            add_crash_test_dummy(sc, pos=(-1.55, -0.95, 0.65), scale=0.68, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "wedges_pinch_rails":
            # CLIMAX: Massive T-rail + true tapered brass wedges jamming inward + left arrow strictly CLEAR of BOLT's head!
            bite = ease_out_cubic(min(1.0, prog * 1.35))
            cam = Camera3D(eye=(1.35 + shake, 0.65, 5.95), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0, t=t)
            sc.add_box((0.52, 0.1, 0.0), (0.40, 4.6, 0.46), STEEL_LIGHT, metallic=0.80)
            sc.add_box((0.52, 0.1, -0.28), (0.88, 4.6, 0.20), STEEL_DARK, metallic=0.62)
            for sx in (-1, 1):
                gap = (1.0 - bite) * 0.34
                wy = -0.35 + bite * 0.50
                # Angled outer steel jaw housing + true tapered wedge geometry!
                sc.add_box((0.52 + sx * 1.05, 0.0, 0.0), (0.36, 2.25, 0.68), STEEL_DARK, rot=(0.0, 0.0, -sx * 0.10), metallic=0.62)
                w_col = lerp_color(BRASS, AMBER, bite)
                sc.add_cylinder(
                    (0.52 + sx * (0.44 + gap), wy - 0.68, 0.05),
                    (0.52 + sx * (0.40 + gap), wy + 0.68, 0.05),
                    0.30,
                    0.12,
                    w_col,
                    segments=4,
                    metallic=0.70,
                    emissive=0.20 * bite,
                )
                # Clamping force arrows strictly in-frame and well CLEAR of BOLT on the left!
                sc.add_arrow_3d((0.52 + sx * 1.68, 0.05, 0.25), (0.52 + sx * 0.85, 0.05, 0.25), DANGER if bite > 0.65 else AMBER, shaft_r=0.075, head_r=0.18)
            sc.add_arrow_3d((0.52, 1.95, 0.42), (0.52, 0.85, 0.42), CYAN, shaft_r=0.075, head_r=0.18)
            add_crash_test_dummy(sc, pos=(-1.62, -0.92, 0.62), scale=0.66, yaw=0.38, pose="brace_impact", emotion="shock", t=t)
            if bite > 0.45:
                overlays_2d.append(lambda d: draw_sparks(d, 585, 940, t, 22, 180, 130, p, seed=91))

        elif scene_key == "cab_frozen_spark_fade":
            # Authentic 1853 ELISHA OTIS Crystal Palace Open Timber Hoist Platform + Cut Rope + Leaf-Spring Ratchet Pawls!
            cam = Camera3D(eye=(-1.25 + math.sin(t * 0.8) * 0.30, 0.60, 6.25), target=(0.0, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Twin 1853 notched vertical wooden & iron rack guide posts
            for sx in (-1, 1):
                rx = sx * 1.55
                sc.add_box((rx, 0.15, 0.0), (0.26, 5.4, 0.32), TIMBER_DARK, metallic=0.18, texture="matte")
                for k in range(-4, 5):
                    sc.add_box((rx - sx * 0.18, k * 0.52, 0.0), (0.16, 0.14, 0.24), STEEL_LIGHT, rot=(0.0, 0.0, sx * 0.25), metallic=0.76)
            # Open-air 1853 timber hoist platform + brass overhead crossbeam + cut hemp rope!
            sc.add_box((0.0, -1.18, 0.0), (2.75, 0.22, 1.75), TIMBER_LIGHT, metallic=0.15, texture="matte")
            for sx in (-1, 1):
                sc.add_box((sx * 1.24, 0.12, 0.0), (0.14, 2.55, 0.18), TIMBER_DARK, metallic=0.22, texture="matte")
            sc.add_box((0.0, 1.38, 0.0), (2.68, 0.22, 0.32), BRASS, metallic=0.72, texture="machined_brass")
            # Cut hemp rope whipping loose above the crossbeam!
            sc.add_cylinder((0.0, 2.85, 0.0), (0.18, 2.15, 0.08), 0.065, 0.060, AMBER, segments=10, metallic=0.15)
            sc.add_cylinder((-0.14, 1.72, 0.05), (0.0, 1.48, 0.0), 0.065, 0.060, DANGER, segments=10, metallic=0.15)
            # Twin emerald leaf-spring iron ratchet pawls locked tightly into the notched side posts!
            for sx in (-1, 1):
                sc.add_cylinder((0.0, 1.38, 0.18), (sx * 1.42, 1.12, 0.12), 0.075, 0.065, EMERALD, segments=10, metallic=0.76, emissive=0.30, bloom=True)
            # BOLT standing proudly on the frozen 1853 Otis hoist platform waving ("All safe, gentlemen!")
            add_crash_test_dummy(sc, pos=(0.0, -0.15, 0.05), scale=0.78, yaw=0.15, pose="relief_wave", emotion="relief", t=t)

        elif scene_key == "hydraulic_buffer_cutaway":
            # Smooth 28-segment cutaway steel hydraulic pit buffer + warm translucent amber oil + concrete pit + cab base above!
            cam = Camera3D(eye=(1.85, 0.90, 6.25), target=(0.05, -0.10, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.95, span=7.0, step=1.0, t=t)
            compress = ease_in_out_cubic(math.sin(prog * math.pi)) * 0.58
            # Matte concrete pit floor (NO metal rivets!)
            sc.add_box((0.35, -1.78, 0.0), (4.6, 0.36, 2.4), STEEL_DARK, metallic=0.12, texture="concrete")
            # Smooth cutaway outer steel housing + warm amber hydraulic oil column!
            sc.add_cylinder((0.52, -1.60, 0.0), (0.52, -0.10, 0.0), 0.72, 0.72, STEEL_MID, segments=28, metallic=0.70, alpha=0.45)
            sc.add_cylinder((0.52, -1.56, 0.0), (0.52, -0.32 - compress * 0.35, 0.0), 0.58, 0.58, OIL_AMBER, segments=24, metallic=0.35, emissive=0.18)
            rod_top = 1.05 - compress
            sc.add_cylinder((0.52, -0.45 - compress * 0.35, 0.0), (0.52, rod_top, 0.0), 0.22, 0.22, STEEL_LIGHT, segments=22, metallic=0.84)
            sc.add_cylinder((0.52, rod_top, 0.0), (0.52, rod_top + 0.22, 0.0), 0.76, 0.76, BRASS, segments=26, metallic=0.72)
            # Bottom of elevator cab resting on the buffer impact plate!
            sc.add_box((0.52, rod_top + 0.42, 0.0), (2.25, 0.22, 1.35), STEEL_MID, metallic=0.68, texture="brushed_steel")
            sc.add_arrow_3d((1.65, -1.35, 0.2), (1.65, 0.42, 0.2), EMERALD, shaft_r=0.075, head_r=0.18)
            add_crash_test_dummy(sc, pos=(-1.45, -0.68, 0.62), scale=0.78, yaw=0.36, pose="point_right", emotion="engineer", t=t)

        else:  # verdict_cta_card — Complete locked elevator cab backdrop + centered BOLT + safe-zone CTA buttons!
            cam = Camera3D(eye=(math.sin(t * 0.9) * 0.4, 0.55, 5.95), target=(0.0, 0.12, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            # Complete recognizable locked cab frame cleanly in background (z = -1.45, clear of buttons!)
            sc.add_box((-1.55, 0.35, -1.45), (0.18, 3.8, 0.24), STEEL_LIGHT, metallic=0.74)
            sc.add_box((1.55, 0.35, -1.45), (0.18, 3.8, 0.24), STEEL_LIGHT, metallic=0.74)
            sc.add_box((0.0, 1.82, -1.45), (3.1, 0.24, 0.55), STEEL_MID, metallic=0.70)
            sc.add_box((0.0, -0.95, -1.45), (3.1, 0.26, 0.75), EMERALD, metallic=0.58, emissive=0.22)
            add_crash_test_dummy(sc, pos=(0.0, -0.04, 0.40), scale=0.88, yaw=math.sin(t * 1.8) * 0.12, pose="cta_shrug", emotion="cta", t=t)
            overlays_2d.append(lambda d: draw_cta_buttons(d, t, p, self.font_black, by=1150, right_col=p.emerald))

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
        rendered_bgr, overlays_2d = self._render_scene_3d("cables_snap_peak", t=0.35, prog=0.45, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
