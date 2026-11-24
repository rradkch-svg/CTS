"""Episode 05: The Genius Gear That Lets Cars TURN Smoothly — True 3D Bevel Differential + UNIT-01."""

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
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes.base import EpisodeScene, register_scene
from cts_factory.episodes.ep04_tacoma_bridge_flutter import _add_3d_yellow_car

STEEL_LIGHT = (192, 210, 228)
STEEL_MID = (118, 138, 166)
STEEL_DARK = (50, 66, 92)
TIRE_DARK = (28, 32, 42)
ICE_CYAN = (120, 238, 255)
BRASS = (224, 174, 72)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


@register_scene("ep05_car_differential_gear")
class CarDifferentialGearScene(EpisodeScene):
    """Articulated 12-beat True 3D Automotive Differential + Yellow Test-Car + UNIT-01 scene."""

    slug = "ep05_car_differential_gear"
    episode_id = "ep05"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_steel_bgr: np.ndarray | None = None
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
        self.bg_steel_bgr = cv2.cvtColor(
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
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_differential(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.35, 0.15, 0.0),
        scale: float = 1.0,
        t: float = 0.0,
        rpm_left: float = 1.0,
        rpm_right: float = 1.0,
        explode: float = 0.0,
        show_tires: bool = True,
        lsd_clamp: float = 0.0,
    ) -> None:
        """Articulated 3D bevel-gear differential with pinion, ring gear, carrier, spider gears & tires."""
        cx, cy, cz = center
        s = scale
        avg = 0.5 * (rpm_left + rpm_right)
        diff = 0.5 * (rpm_right - rpm_left)

        # Driveshaft + input bevel pinion entering from rear (-Z)
        pin_z = cz - (1.05 + explode * 0.65) * s
        sc.add_cylinder((cx, cy, pin_z - 0.85 * s), (cx, cy, pin_z), 0.11 * s, 0.11 * s, STEEL_MID, segments=12, metallic=0.76)
        sc.add_cylinder((cx, cy, pin_z), (cx, cy, pin_z + 0.28 * s), 0.24 * s, 0.15 * s, CYAN, segments=12, metallic=0.65, emissive=0.35)

        # Giant vertical brass ring gear mounted on left side of rotating carrier cage
        ring_x = cx - (0.48 + explode * 0.35) * s
        sc.add_cylinder((ring_x - 0.12 * s, cy, cz), (ring_x + 0.10 * s, cy, cz), 0.88 * s, 0.88 * s, BRASS, segments=22, metallic=0.78)
        # Ring gear teeth notches rotating with avg carrier speed
        c_ang = t * 2.2 * avg
        for i in range(12):
            a = c_ang + i * (2.0 * math.pi / 12.0)
            sc.add_box(
                (ring_x + 0.02 * s, cy + math.cos(a) * 0.90 * s, cz + math.sin(a) * 0.90 * s),
                (0.18 * s, 0.14 * s, 0.14 * s),
                AMBER,
                metallic=0.74,
            )

        # Open rotating differential carrier frame bars
        for sa in (c_ang, c_ang + math.pi):
            by = cy + math.cos(sa) * 0.58 * s
            bz = cz + math.sin(sa) * 0.58 * s
            sc.add_cylinder((cx - 0.44 * s, by, bz), (cx + 0.44 * s, by, bz), 0.065 * s, 0.065 * s, STEEL_DARK, segments=8, metallic=0.72)

        # Spider gear cross-pin + twin orbiting amber spider bevel gears!
        sp_ang = t * 4.5 * diff
        for sign in (-1, 1):
            sy = cy + sign * math.cos(c_ang) * (0.34 + explode * 0.22) * s
            sz = cz + sign * math.sin(c_ang) * (0.34 + explode * 0.22) * s
            sc.add_sphere((cx, sy, sz), 0.21 * s, AMBER if abs(diff) > 0.1 else BRASS, metallic=0.72, emissive=0.35 if abs(diff) > 0.1 else 0.0, bloom=(abs(diff) > 0.25))
            # Spinning spider tooth marker dot so viewer literally sees spider gears rotating!
            mk = sp_ang * sign
            sc.add_sphere(
                (cx + math.cos(mk) * 0.14 * s, sy, sz + math.sin(mk) * 0.14 * s),
                0.062 * s,
                CYAN if abs(diff) > 0.1 else STEEL_LIGHT,
                emissive=0.75,
            )

        # Left & right axle side gears + half-shafts + tires!
        for sx, rpm, col_ax in ((-1, rpm_left, CYAN), (1, rpm_right, AMBER)):
            gx = cx + sx * (0.38 + explode * 0.35) * s
            sc.add_cylinder((gx - sx * 0.08 * s, cy, cz), (gx + sx * 0.10 * s, cy, cz), 0.28 * s, 0.22 * s, col_ax, segments=14, metallic=0.72, emissive=0.25)
            ax_end = cx + sx * (1.42 + explode * 0.35) * s
            sc.add_cylinder((gx + sx * 0.10 * s, cy, cz), (ax_end, cy, cz), 0.095 * s, 0.095 * s, STEEL_LIGHT, segments=12, metallic=0.82)

            # Optional limited-slip clutch plates clamping tightly on axle!
            if lsd_clamp > 0.05:
                for pi in range(3):
                    px = cx + sx * (0.58 + pi * 0.11 - lsd_clamp * 0.05) * s
                    sc.add_cylinder((px, cy, cz), (px + sx * 0.05 * s, cy, cz), 0.36 * s, 0.36 * s, EMERALD, segments=14, metallic=0.72, emissive=0.45 * lsd_clamp, bloom=True)

            if show_tires:
                tx = ax_end + sx * 0.18 * s
                sc.add_cylinder((tx - sx * 0.22 * s, cy, cz), (tx + sx * 0.22 * s, cy, cz), 0.62 * s, 0.62 * s, TIRE_DARK, segments=18, metallic=0.22)
                sc.add_cylinder((tx - sx * 0.24 * s, cy, cz), (tx + sx * 0.24 * s, cy, cz), 0.34 * s, 0.34 * s, STEEL_LIGHT, segments=14, metallic=0.80)
                # Rotating spoke markers on the tire so speed difference is INSTANTLY visible!
                w_ang = t * 4.2 * rpm
                for sp in range(3):
                    wa = w_ang + sp * (2.0 * math.pi / 3.0)
                    sc.add_sphere(
                        (tx + sx * 0.25 * s, cy + math.cos(wa) * 0.44 * s, cz + math.sin(wa) * 0.44 * s),
                        0.08 * s,
                        EMERALD if lsd_clamp > 0.5 else (DANGER if rpm > 1.8 else col_ax),
                        emissive=0.75,
                        bloom=True,
                    )

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_steel_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("cornering_arc_skid", "ice_patch_wheel_spin", "dry_tire_frozen_ice"):
            bg = self.bg_alert_bgr
        elif scene_key in ("lsd_clutch_clamp", "verdict_cta_card"):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_steel_bgr

        if scene_key == "diff_gear_hero":
            # FRAME 0 HERO: Gleaming 3D brass & steel bevel differential splitting speed between two tires!
            cam = Camera3D(eye=(0.45 + math.sin(t * 1.1) * 0.45, 0.92, 6.15), target=(0.0, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.05, 0.15, 0.0), scale=0.92, t=t, rpm_left=0.6, rpm_right=1.7)
            sc.add_arrow_3d((-1.45, 1.15, 0.2), (-0.75, 1.15, 0.2), CYAN, shaft_r=0.065, head_r=0.155)
            sc.add_arrow_3d((0.65, 1.15, 0.2), (1.75, 1.15, 0.2), AMBER, shaft_r=0.085, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.42, -0.95, 0.95), scale=0.68, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "cornering_arc_skid":
            # Solid axle problem: Yellow Car skidding with red tire drag sparks!
            cam = Camera3D(eye=(1.15, 1.35, 6.20), target=(0.0, -0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            # Curved road corner tiles
            for i in range(9):
                a = -0.7 + i * 0.18
                sc.add_box((math.sin(a) * 1.8, -1.45, -1.2 + math.cos(a) * 1.6), (0.65, 0.12, 1.25), STEEL_DARK, rot=(0.0, -a, 0.0), metallic=0.35)
            _add_3d_yellow_car(sc, center=(0.20, -0.95, 0.25), scale=0.95, yaw=-0.35 + math.sin(t * 22.0) * 0.04, t=t, with_driver=True, driver_pose="panic_freefall", driver_emotion="panic")
            overlays_2d.append(lambda d: draw_sparks(d, 560, 1140, t, 22, 240, 120, p, seed=52))

        elif scene_key == "overhead_arc_rpm":
            # Overhead cornering arc telemetry comparing inner 60 RPM vs outer 100 RPM!
            cam = Camera3D(eye=(0.0, 4.65, 3.85), target=(0.0, -0.35, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.45, span=7.0, step=1.0, t=t)
            # Inner cyan arc & outer amber arc rails
            for i in range(10):
                a = -0.85 + i * 0.19
                sc.add_box((math.sin(a) * 1.05, -1.30, -0.9 + math.cos(a) * 1.05), (0.25, 0.08, 0.16), CYAN, rot=(0.0, -a, 0.0), emissive=0.55)
                sc.add_box((math.sin(a) * 2.15, -1.30, -0.9 + math.cos(a) * 2.15), (0.42, 0.08, 0.18), AMBER, rot=(0.0, -a, 0.0), emissive=0.65)
            car_a = -0.65 + ease_in_out_cubic(prog) * 1.30
            _add_3d_yellow_car(sc, center=(math.sin(car_a) * 1.60, -1.10, -0.9 + math.cos(car_a) * 1.60), scale=0.72, yaw=-car_a, t=t, with_driver=True, driver_pose="pilot_sub", driver_emotion="curious")

            def _arc_labels(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 32)
                d.text((155, 1150), "INNER: 60 RPM", font=f, fill=p.cyan, stroke_width=4, stroke_fill=p.ink)
                d.text((625, 1215), "OUTER: 100 RPM", font=f, fill=p.amber, stroke_width=4, stroke_fill=p.ink)

            overlays_2d.append(_arc_labels)

        elif scene_key == "diff_exploded_parts":
            cam = Camera3D(eye=(0.85, 0.95, 6.65), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            exp = ease_out_cubic(prog) * 0.95
            self._add_3d_differential(sc, center=(0.45, 0.18, 0.0), scale=0.80, t=t, rpm_left=1.0, rpm_right=1.0, explode=exp, show_tires=False)
            add_crash_test_dummy(sc, pos=(-1.52, -0.88, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "pinion_drives_ring":
            cam = Camera3D(eye=(1.75, 0.88, 5.95), target=(0.15, 0.10, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.45, 0.15, 0.0), scale=0.92, t=t, rpm_left=1.2, rpm_right=1.2, show_tires=False)
            sc.add_arrow_3d((0.45, 0.15, -2.05), (0.45, 0.15, -1.15), CYAN, shaft_r=0.072, head_r=0.17)
            add_crash_test_dummy(sc, pos=(-1.48, -0.88, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "straight_drive_orbit":
            cam = Camera3D(eye=(-0.45, 0.85, 6.20), target=(0.05, 0.10, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.25, 0.15, 0.0), scale=0.88, t=t, rpm_left=1.0, rpm_right=1.0, show_tires=True)
            sc.add_arrow_3d((-0.95, 1.15, 0.2), (-0.95, 1.75, 0.2), EMERALD, shaft_r=0.065, head_r=0.155)
            sc.add_arrow_3d((1.45, 1.15, 0.2), (1.45, 1.75, 0.2), EMERALD, shaft_r=0.065, head_r=0.155)
            add_crash_test_dummy(sc, pos=(-1.50, -0.92, 0.92), scale=0.68, yaw=0.38, pose="point_right", emotion="relief", t=t)

        elif scene_key == "corner_spider_rotation":
            # Cornering close-up: spider gears visibly rotating to split RPM!
            cam = Camera3D(eye=(0.45, 0.82, 5.75), target=(0.15, 0.12, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.45, 0.15, 0.0), scale=0.90, t=t, rpm_left=0.45, rpm_right=1.85, show_tires=True)
            add_crash_test_dummy(sc, pos=(-1.50, -0.90, 0.85), scale=0.68, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "rpm_split_bars":
            # Clean split layout: UNIT-01 unobstructed on left pointing at 60 RPM vs 100 RPM bars!
            cam = Camera3D(eye=(0.25, 0.35, 5.95), target=(0.0, -0.25, 0.0), fov_deg=41.0, cy_offset=95.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            add_crash_test_dummy(sc, pos=(-1.42, -0.45, 0.55), scale=0.72, yaw=0.38, pose="point_right", emotion="engineer", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=325,
                    y0=715,
                    width=680,
                    height=355,
                    items=[
                        ("INNER TIRE (-20)", "60 RPM", 60.0 / 110.0, p.cyan),
                        ("OUTER TIRE (+20)", "100 RPM", 100.0 / 110.0, p.amber),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([325, 1105, 1005, 1188], radius=16, fill=p.surface_panel, outline=p.text_highlight, width=4)
                f = load_font(self.font_black, 28)
                msg = "AVERAGE ALWAYS = 80 RPM"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((665 - (bb[2] - bb[0]) / 2, 1130), msg, font=f, fill=p.text_highlight)

            overlays_2d.append(_bars)

        elif scene_key in ("ice_patch_wheel_spin", "dry_tire_frozen_ice"):
            # Hilarious ice-slip trap: right tire on glowing cyan ice spinning at 200 RPM, left dry tire FROZEN at 0 RPM!
            cam = Camera3D(eye=(0.25, 0.85, 6.25), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, t=t)
            # Dry asphalt slab on left, glossy glowing cyan ice slab on right!
            sc.add_box((-1.10, -0.82, 0.0), (1.45, 0.16, 1.85), STEEL_DARK, metallic=0.25)
            sc.add_box((1.35, -0.82, 0.0), (1.55, 0.16, 1.85), ICE_CYAN, metallic=0.82, emissive=0.45, bloom=True)
            self._add_3d_differential(sc, center=(0.15, 0.02, 0.0), scale=0.88, t=t, rpm_left=0.0, rpm_right=2.6, show_tires=True)
            # Red spin warning arrow above ice tire
            sc.add_arrow_3d((1.55, 1.45, 0.25), (1.55, 0.78, 0.25), DANGER, shaft_r=0.075, head_r=0.18)
            add_crash_test_dummy(sc, pos=(-1.32, -0.92, 0.92), scale=0.64, yaw=0.38, pose="panic_freefall", emotion="shock", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 785, 1020, t, 18, 160, 120, p, seed=59))

        elif scene_key == "lsd_clutch_clamp":
            # Limited-slip clutch packs clamp BOTH axles together with glowing emerald lock!
            clamp_p = ease_out_cubic(clamp(prog * 1.35))
            cam = Camera3D(eye=(0.35, 0.85, 6.15), target=(0.08, 0.08, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.25, 0.12, 0.0), scale=0.90, t=t, rpm_left=1.25 * clamp_p + 0.1, rpm_right=1.25, show_tires=True, lsd_clamp=clamp_p)
            sc.add_arrow_3d((-0.65, 1.25, 0.2), (-0.05, 0.65, 0.2), EMERALD, shaft_r=0.072, head_r=0.17)
            sc.add_arrow_3d((1.15, 1.25, 0.2), (0.55, 0.65, 0.2), EMERALD, shaft_r=0.072, head_r=0.17)
            add_crash_test_dummy(sc, pos=(-1.38, -0.90, 0.88), scale=0.66, yaw=0.38, pose="relief_wave", emotion="relief", t=t)

        else:  # verdict_cta_card — FUN FINALE: UNIT-01 happily cruising in his Yellow Test-Car with emerald traction!
            cam = Camera3D(eye=(math.sin(t * 0.85) * 0.40, 0.65, 6.05), target=(0.0, 0.05, 0.0), fov_deg=41.0, cy_offset=25.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.75, span=7.0, step=1.0, t=t)
            _add_3d_yellow_car(sc, center=(0.0, -0.82, -0.55), scale=0.98, yaw=-0.22 + math.sin(t * 1.4) * 0.10, t=t, with_driver=False)
            add_crash_test_dummy(sc, pos=(0.0, 0.08, 0.55), scale=0.86, yaw=math.sin(t * 1.8) * 0.14, pose="cta_shrug", emotion="cta", t=t, ground_shadow=True)

            def _cta_buttons(d: ImageDraw.ImageDraw) -> None:
                pulse = 1.0 + 0.04 * math.sin(t * 7.0)
                for label, bx, col in (("YES", 200, p.cyan), ("NO", 880, p.amber)):
                    bw, bh = int(132 * pulse), int(82 * pulse)
                    by = 920
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "diff_gear_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("diff_gear_hero", t=0.35, prog=0.45, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
