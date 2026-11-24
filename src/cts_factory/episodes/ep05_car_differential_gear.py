"""Episode 05: The Genius Gear That Lets Cars TURN Smoothly — True 3D Bevel Differential + UNIT-01."""

from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette, build_stage_background
from cts_factory.engine.primitives import (
    draw_comparison_bars,
    draw_cta_buttons,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes.base import EpisodeScene, register_scene
from cts_factory.episodes.ep04_tacoma_bridge_flutter import _add_3d_yellow_car

STEEL_LIGHT = (192, 210, 228)
STEEL_MID = (118, 138, 166)
STEEL_DARK = (50, 66, 92)
ASPHALT_DARK = (38, 44, 56)
TIRE_DARK = (28, 32, 42)
ICE_BLUE = (118, 214, 245)
ICE_FROST = (210, 242, 255)
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
        """Mechanically accurate 3D bevel-gear differential: visible meshing pinion, radially toothed ring gear, cross-pin, toothed bevel spider & side gears."""
        cx, cy, cz = center
        s = scale
        avg = 0.5 * (rpm_left + rpm_right)
        diff = 0.5 * (rpm_right - rpm_left)
        c_ang = t * 2.2 * avg

        # 1. Giant vertical brass ring gear mounted on left side of rotating carrier cage (with radially rotated bevel teeth!)
        ring_x = cx - (0.50 + explode * 0.34) * s
        sc.add_cylinder((ring_x - 0.11 * s, cy, cz), (ring_x + 0.09 * s, cy, cz), 0.88 * s, 0.88 * s, BRASS, segments=26, metallic=0.80)
        sc.add_cylinder((ring_x - 0.13 * s, cy, cz), (ring_x + 0.11 * s, cy, cz), 0.56 * s, 0.56 * s, STEEL_DARK, segments=22, metallic=0.72)
        n_ring_teeth = 18
        for i in range(n_ring_teeth):
            a = c_ang + i * (2.0 * math.pi / n_ring_teeth)
            # True radial orientation around X-axis (rot=(a, 0, 0))!
            sc.add_box(
                (ring_x + 0.04 * s, cy + math.cos(a) * 0.88 * s, cz + math.sin(a) * 0.88 * s),
                (0.16 * s, 0.13 * s, 0.09 * s),
                AMBER,
                rot=(a, 0.0, 0.0),
                metallic=0.76,
            )

        # 2. Input driveshaft + toothed cyan bevel pinion visibly meshing on the FRONT-LOWER rim of the ring gear (+Z)!
        pin_x = ring_x + 0.14 * s
        pin_z = cz + (0.86 + explode * 0.52) * s
        pin_ang = -c_ang * 3.0
        sc.add_cylinder((pin_x, cy, pin_z + 0.92 * s), (pin_x, cy, pin_z + 0.18 * s), 0.105 * s, 0.105 * s, STEEL_MID, segments=14, metallic=0.78)
        sc.add_cylinder((pin_x, cy, pin_z + 0.22 * s), (pin_x, cy, pin_z - 0.08 * s), 0.23 * s, 0.15 * s, CYAN, segments=16, metallic=0.70, emissive=0.25)
        for pt_i in range(8):
            pa = pin_ang + pt_i * (2.0 * math.pi / 8.0)
            sc.add_box(
                (pin_x + math.cos(pa) * 0.21 * s, cy + math.sin(pa) * 0.21 * s, pin_z + 0.06 * s),
                (0.08 * s, 0.06 * s, 0.20 * s),
                STEEL_LIGHT,
                rot=(0.0, 0.0, pa),
                metallic=0.80,
            )

        # 3. Open rotating differential carrier cage bars (radius 0.72*s — strictly CLEAR of spider gears, ZERO clipping!)
        for sa in (c_ang + math.pi * 0.5, c_ang + math.pi * 1.5):
            by = cy + math.cos(sa) * 0.72 * s
            bz = cz + math.sin(sa) * 0.72 * s
            sc.add_cylinder((cx - 0.46 * s, by, bz), (cx + 0.46 * s, by, bz), 0.058 * s, 0.058 * s, STEEL_DARK, segments=10, metallic=0.74)
        # Right carrier end flange connecting bars cleanly
        sc.add_cylinder((cx + 0.42 * s, cy, cz), (cx + 0.50 * s, cy, cz), 0.74 * s, 0.74 * s, STEEL_DARK, segments=20, metallic=0.70, alpha=0.45)

        # 4. Solid steel spider cross-pin shaft + twin TOOTHED BEVEL spider gears meshing with side gears!
        pin_r = 0.58 * s
        sc.add_cylinder(
            (cx, cy - math.cos(c_ang) * pin_r, cz - math.sin(c_ang) * pin_r),
            (cx, cy + math.cos(c_ang) * pin_r, cz + math.sin(c_ang) * pin_r),
            0.055 * s,
            0.055 * s,
            STEEL_LIGHT,
            segments=10,
            metallic=0.84,
        )
        sp_ang = t * 4.5 * diff
        for sign in (-1, 1):
            sp_dist = (0.31 + explode * 0.20) * s
            sy = cy + sign * math.cos(c_ang) * sp_dist
            sz = cz + sign * math.sin(c_ang) * sp_dist
            # Bevel spider gear body (tapered cone pointing inward toward differential center)
            in_y = cy + sign * math.cos(c_ang) * (sp_dist - 0.14 * s)
            in_z = cz + sign * math.sin(c_ang) * (sp_dist - 0.14 * s)
            out_y = cy + sign * math.cos(c_ang) * (sp_dist + 0.10 * s)
            out_z = cz + sign * math.sin(c_ang) * (sp_dist + 0.10 * s)
            sp_col = AMBER if abs(diff) > 0.1 else BRASS
            sc.add_cylinder((cx, out_y, out_z), (cx, in_y, in_z), 0.23 * s, 0.15 * s, sp_col, segments=14, metallic=0.76, emissive=0.22 if abs(diff) > 0.1 else 0.0)
            # 8 real protruding bevel gear teeth around each spider gear so spin is unmistakably mechanical!
            # Local tangent basis around cross-pin axis (0, cos(c_ang), sin(c_ang)):
            # u_vec = (1, 0, 0), v_vec = (0, -sin(c_ang), cos(c_ang))
            n_sp_t = 8
            for ti in range(n_sp_t):
                ta = sp_ang * sign + ti * (2.0 * math.pi / n_sp_t)
                tx = cx + math.cos(ta) * 0.21 * s
                ty = sy - math.sin(ta) * math.sin(c_ang) * 0.21 * s
                tz = sz + math.sin(ta) * math.cos(c_ang) * 0.21 * s
                t_col = CYAN if (ti == 0 and abs(diff) > 0.1) else (STEEL_LIGHT if ti % 2 == 0 else sp_col)
                sc.add_box((tx, ty, tz), (0.07 * s, 0.07 * s, 0.07 * s), t_col, metallic=0.78, emissive=0.55 if (ti == 0 and abs(diff) > 0.1) else 0.0)

        # 5. Left & right TOOTHED BEVEL side gears + half-shafts + tires!
        for sx, rpm, col_ax in ((-1, rpm_left, CYAN), (1, rpm_right, AMBER)):
            gx = cx + sx * (0.29 + explode * 0.34) * s
            w_ang = t * 4.2 * rpm
            # Bevel side gear body meshing tightly with spider gears!
            sc.add_cylinder((gx + sx * 0.12 * s, cy, cz), (gx - sx * 0.10 * s, cy, cz), 0.29 * s, 0.20 * s, col_ax, segments=16, metallic=0.74, emissive=0.18)
            # 10 radial bevel teeth around each side gear!
            for si in range(10):
                sa = w_ang + si * (2.0 * math.pi / 10.0)
                sc.add_box(
                    (gx - sx * 0.02 * s, cy + math.cos(sa) * 0.26 * s, cz + math.sin(sa) * 0.26 * s),
                    (0.11 * s, 0.075 * s, 0.065 * s),
                    STEEL_LIGHT,
                    rot=(sa, 0.0, 0.0),
                    metallic=0.80,
                )
            ax_end = cx + sx * (1.38 + explode * 0.34) * s
            sc.add_cylinder((gx + sx * 0.11 * s, cy, cz), (ax_end, cy, cz), 0.095 * s, 0.095 * s, STEEL_LIGHT, segments=14, metallic=0.84)

            # Precision limited-slip friction clutch stack (clean alternating steel & emerald plates, NO radioactive glow!)
            if lsd_clamp > 0.05:
                for pi in range(4):
                    px = cx + sx * (0.56 + pi * 0.095 - lsd_clamp * 0.04) * s
                    p_col = EMERALD if pi % 2 == 0 else STEEL_LIGHT
                    sc.add_cylinder((px, cy, cz), (px + sx * 0.045 * s, cy, cz), 0.34 * s, 0.34 * s, p_col, segments=18, metallic=0.74, emissive=0.22 * lsd_clamp if pi % 2 == 0 else 0.0)

            if show_tires:
                tx = ax_end + sx * 0.18 * s
                sc.add_cylinder((tx - sx * 0.22 * s, cy, cz), (tx + sx * 0.22 * s, cy, cz), 0.62 * s, 0.62 * s, TIRE_DARK, segments=22, metallic=0.20)
                sc.add_cylinder((tx - sx * 0.24 * s, cy, cz), (tx + sx * 0.24 * s, cy, cz), 0.34 * s, 0.34 * s, STEEL_LIGHT, segments=18, metallic=0.82)
                for sp in range(3):
                    wa = w_ang + sp * (2.0 * math.pi / 3.0)
                    sc.add_sphere(
                        (tx + sx * 0.25 * s, cy + math.cos(wa) * 0.44 * s, cz + math.sin(wa) * 0.44 * s),
                        0.075 * s,
                        EMERALD if lsd_clamp > 0.5 else (DANGER if rpm > 1.8 else col_ax),
                        emissive=0.65,
                        bloom=True,
                    )

    def _add_curved_road(self, sc: Scene3D, r_mid: float = 1.65, z_center: float = -1.05, y_level: float = -1.35, highlight_arcs: bool = False) -> None:
        """Smooth continuous curved asphalt road using tangent-aligned rot=(0, +a, 0) (ZERO domino twisting!)."""
        n_tiles = 18
        a0, a1 = -0.88, 0.88
        for i in range(n_tiles):
            a = a0 + (a1 - a0) * (i / max(1, n_tiles - 1))
            # Tangent to (R*sin(a), y, z_center + R*cos(a)) is (cos(a), 0, -sin(a)) = Ry(+a) @ [1, 0, 0]!
            sc.add_box(
                (math.sin(a) * r_mid, y_level, z_center + math.cos(a) * r_mid),
                (0.28, 0.12, 1.32),
                ASPHALT_DARK,
                rot=(0.0, a, 0.0),
                metallic=0.12,
                texture="concrete",
            )
            if highlight_arcs:
                # Inner cyan curve rail (R_in = r_mid - 0.56) & Outer amber curve rail (R_out = r_mid + 0.56)
                r_in = r_mid - 0.58
                r_out = r_mid + 0.58
                sc.add_box((math.sin(a) * r_in, y_level + 0.08, z_center + math.cos(a) * r_in), (0.22, 0.06, 0.14), CYAN, rot=(0.0, a, 0.0), emissive=0.48)
                sc.add_box((math.sin(a) * r_out, y_level + 0.08, z_center + math.cos(a) * r_out), (0.34, 0.06, 0.16), AMBER, rot=(0.0, a, 0.0), emissive=0.52)
            elif i % 2 == 0:
                # Crisp dashed center yellow lane stripe following curve tangent (+a)
                sc.add_box((math.sin(a) * r_mid, y_level + 0.07, z_center + math.cos(a) * r_mid), (0.16, 0.02, 0.08), AMBER, rot=(0.0, a, 0.0), emissive=0.30)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float, is_cover: bool = False) -> tuple[np.ndarray, list]:
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
            # FRAME 0 HERO: Gleaming mechanically accurate 3D bevel differential + visible driveshaft pinion + tires!
            if is_cover:
                cam = Camera3D(eye=(0.55, 1.05, 6.75), target=(0.0, 0.45, 0.0), fov_deg=41.0, cy_offset=45.0)
            else:
                cam = Camera3D(eye=(0.55 + math.sin(t * 1.1) * 0.40, 0.96, 6.25), target=(0.0, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.08, 0.12, 0.0), scale=0.88, t=t, rpm_left=0.6, rpm_right=1.7)
            sc.add_arrow_3d((-1.45, 1.18, 0.2), (-0.75, 1.18, 0.2), CYAN, shaft_r=0.060, head_r=0.145)
            sc.add_arrow_3d((0.68, 1.18, 0.2), (1.72, 1.18, 0.2), AMBER, shaft_r=0.078, head_r=0.185)
            if not is_cover:
                add_crash_test_dummy(sc, pos=(-1.42, -0.95, 0.88), scale=0.66, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "cornering_arc_skid":
            # Solid axle problem: Yellow Car steering IN THE EXACT DIRECTION OF THE CURVE (yaw = +car_a!) with rear tire smoke!
            cam = Camera3D(eye=(0.95, 1.55, 6.15), target=(0.0, -0.35, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            r_mid, z_c = 1.68, -1.10
            self._add_curved_road(sc, r_mid=r_mid, z_center=z_c, y_level=-1.35, highlight_arcs=False)
            car_a = -0.38 + ease_in_out_cubic(prog) * 0.72
            cx_c = math.sin(car_a) * r_mid
            cz_c = z_c + math.cos(car_a) * r_mid
            # POSITIVE +car_a aligns car nose (+X) strictly tangent to curve (cos(a), 0, -sin(a))!
            skid_wobble = math.sin(t * 22.0) * 0.045
            _add_3d_yellow_car(
                sc,
                center=(cx_c, -1.06, cz_c),
                scale=0.84,
                yaw=car_a + skid_wobble,
                t=t,
                with_driver=True,
                driver_pose="panic_freefall",
                driver_emotion="panic",
            )
            # Realistic tire-contact grey smoke puffs trailing behind the skidding rear tires (NO sparks on windshield!)
            tx_dir, tz_dir = math.cos(car_a), -math.sin(car_a)
            for si in range(5):
                ph = (t * 2.8 + si * 0.20) % 1.0
                sx = cx_c - tx_dir * (0.62 + ph * 0.75)
                sy = -1.16 + ph * 0.34
                sz = cz_c - tz_dir * (0.62 + ph * 0.75) + (0.28 if si % 2 == 0 else -0.28)
                sc.add_sphere((sx, sy, sz), 0.11 + ph * 0.12, (165, 174, 188), metallic=0.05)

        elif scene_key == "overhead_arc_rpm":
            # Overhead cornering arc telemetry: car turning strictly TANGENT (+car_a) with INNER=60 RPM & OUTER=100 RPM labels on their TRUE arcs!
            cam = Camera3D(eye=(0.0, 4.75, 3.80), target=(0.0, -0.45, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.45, span=7.0, step=1.0, t=t)
            r_mid, z_c = 1.62, -0.95
            self._add_curved_road(sc, r_mid=r_mid, z_center=z_c, y_level=-1.32, highlight_arcs=True)
            car_a = -0.62 + ease_in_out_cubic(prog) * 1.24
            # POSITIVE +car_a: car drives LEFT-to-RIGHT curving cleanly into the LEFT turn!
            # Inner wheel (-Z) rides the INNER CYAN arc (60 RPM), Outer wheel (+Z) rides the OUTER AMBER arc (100 RPM)!
            _add_3d_yellow_car(
                sc,
                center=(math.sin(car_a) * r_mid, -1.06, z_c + math.cos(car_a) * r_mid),
                scale=0.70,
                yaw=car_a,
                t=t,
                with_driver=True,
                driver_pose="pilot_sub",
                driver_emotion="curious",
            )

            def _arc_labels(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 28)
                # INNER cyan pill positioned cleanly ABOVE/INSIDE the cyan inner arc (away from outer amber arc!)
                for txt, bx, by, col in (
                    ("INNER: 60 RPM", 335, 840, p.cyan),
                    ("OUTER: 100 RPM", 460, 1265, p.amber),
                ):
                    bb = d.textbbox((0, 0), txt, font=f)
                    tw = bb[2] - bb[0]
                    bx0 = min(bx, 850 - tw - 28)
                    d.rounded_rectangle([bx0, by, bx0 + tw + 28, by + 46], radius=12, fill=p.surface_panel, outline=col, width=3)
                    d.text((bx0 + 14, by + 7), txt, font=f, fill=col)

            overlays_2d.append(_arc_labels)

        elif scene_key == "diff_exploded_parts":
            cam = Camera3D(eye=(0.95, 0.98, 6.75), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            exp = ease_out_cubic(prog) * 0.85
            self._add_3d_differential(sc, center=(0.45, 0.18, 0.0), scale=0.78, t=t, rpm_left=1.0, rpm_right=1.0, explode=exp, show_tires=False)
            add_crash_test_dummy(sc, pos=(-1.48, -0.88, 0.72), scale=0.68, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "pinion_drives_ring":
            # Elevated 3/4 view showing driveshaft + cyan bevel pinion DIRECTLY meshing with the front brass ring gear teeth!
            cam = Camera3D(eye=(1.85, 1.08, 5.75), target=(0.12, 0.10, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.45, 0.15, 0.0), scale=0.88, t=t, rpm_left=1.2, rpm_right=1.2, show_tires=False)
            # Clear cyan torque arrow pointing right along the visible front driveshaft into the pinion!
            sc.add_arrow_3d((0.12, 0.45, 1.85), (0.12, 0.45, 0.95), CYAN, shaft_r=0.068, head_r=0.16)
            add_crash_test_dummy(sc, pos=(-1.46, -0.88, 0.68), scale=0.68, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "straight_drive_orbit":
            cam = Camera3D(eye=(-0.38, 0.88, 6.25), target=(0.05, 0.10, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.25, 0.15, 0.0), scale=0.86, t=t, rpm_left=1.0, rpm_right=1.0, show_tires=True)
            sc.add_arrow_3d((-0.95, 1.15, 0.2), (-0.95, 1.72, 0.2), EMERALD, shaft_r=0.062, head_r=0.15)
            sc.add_arrow_3d((1.42, 1.15, 0.2), (1.42, 1.72, 0.2), EMERALD, shaft_r=0.062, head_r=0.15)
            add_crash_test_dummy(sc, pos=(-1.46, -0.92, 0.88), scale=0.66, yaw=0.38, pose="point_right", emotion="relief", t=t)

        elif scene_key == "corner_spider_rotation":
            # Cornering close-up: toothed bevel spider gears visibly spinning on the cross-pin to split RPM!
            cam = Camera3D(eye=(0.45, 0.86, 5.75), target=(0.15, 0.12, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.42, 0.15, 0.0), scale=0.88, t=t, rpm_left=0.45, rpm_right=1.85, show_tires=True)
            add_crash_test_dummy(sc, pos=(-1.46, -0.90, 0.82), scale=0.66, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "rpm_split_bars":
            # Clean split layout: BOLT unobstructed on left pointing at safe-zone bars (x0=320, width=540 -> x1=860!)
            cam = Camera3D(eye=(0.25, 0.35, 6.20), target=(0.0, -0.25, 0.0), fov_deg=41.0, cy_offset=95.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            add_crash_test_dummy(sc, pos=(-1.62, -0.45, 0.48), scale=0.68, yaw=0.40, pose="point_right", emotion="engineer", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=320,
                    y0=715,
                    width=540,
                    height=355,
                    items=[
                        ("INNER TIRE (-20)", "60 RPM", 60.0 / 110.0, p.cyan),
                        ("OUTER TIRE (+20)", "100 RPM", 100.0 / 110.0, p.amber),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([320, 1105, 860, 1188], radius=16, fill=p.surface_panel, outline=p.text_highlight, width=4)
                f = load_font(self.font_black, 26)
                msg = "AVERAGE ALWAYS = 80 RPM"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((590 - (bb[2] - bb[0]) / 2, 1130), msg, font=f, fill=p.text_highlight)

            overlays_2d.append(_bars)

        elif scene_key in ("ice_patch_wheel_spin", "dry_tire_frozen_ice"):
            # Ice-slip trap: in-frame frosted blue ice slab (no blown-out white neon!), cool ice spray pellets (no orange welding sparks!)
            cam = Camera3D(eye=(0.25, 0.88, 6.45), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, t=t)
            # Dry asphalt slab on left, crisp translucent frosted ice slab strictly in-frame on right!
            sc.add_box((-1.05, -0.82, 0.0), (1.38, 0.16, 1.75), ASPHALT_DARK, metallic=0.14, texture="concrete")
            sc.add_box((1.18, -0.82, 0.0), (1.36, 0.16, 1.75), ICE_BLUE, metallic=0.65, emissive=0.12, texture="matte")
            self._add_3d_differential(sc, center=(0.08, 0.02, 0.0), scale=0.84, t=t, rpm_left=0.0, rpm_right=2.6, show_tires=True)
            # Red spin warning arrow above ice tire
            sc.add_arrow_3d((1.42, 1.42, 0.25), (1.42, 0.78, 0.25), DANGER, shaft_r=0.070, head_r=0.165)
            # Cool white/cyan ice crystals spraying backward from spinning tire contact patch (ZERO welding sparks!)
            for ki in range(7):
                ph = (t * 3.4 + ki * 0.145) % 1.0
                ix = 1.42 + (ki % 3 - 1) * 0.12
                iy = -0.68 + ph * 0.55 - 0.25 * (ph ** 2)
                iz = -0.25 - ph * 1.10
                sc.add_sphere((ix, iy, iz), 0.055 * (1.0 - ph * 0.5), ICE_FROST, emissive=0.35)
            add_crash_test_dummy(sc, pos=(-1.35, -0.92, 0.85), scale=0.62, yaw=0.38, pose="panic_freefall", emotion="shock", t=t)

        elif scene_key == "lsd_clutch_clamp":
            clamp_p = ease_out_cubic(clamp(prog * 1.35))
            cam = Camera3D(eye=(0.35, 0.88, 6.25), target=(0.08, 0.08, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.05, span=7.0, step=1.0, t=t)
            self._add_3d_differential(sc, center=(0.25, 0.12, 0.0), scale=0.88, t=t, rpm_left=1.25 * clamp_p + 0.1, rpm_right=1.25, show_tires=True, lsd_clamp=clamp_p)
            sc.add_arrow_3d((-0.65, 1.25, 0.2), (-0.05, 0.65, 0.2), EMERALD, shaft_r=0.068, head_r=0.16)
            sc.add_arrow_3d((1.15, 1.25, 0.2), (0.55, 0.65, 0.2), EMERALD, shaft_r=0.068, head_r=0.16)
            add_crash_test_dummy(sc, pos=(-1.42, -0.90, 0.82), scale=0.66, yaw=0.38, pose="relief_wave", emotion="relief", t=t)

        else:  # verdict_cta_card — UNIT-01 seated cleanly inside his Yellow Test-Car + safe-zone CTA buttons (NO shadow on car door!)
            cam = Camera3D(eye=(math.sin(t * 0.85) * 0.35, 0.72, 6.15), target=(0.0, 0.02, 0.0), fov_deg=41.0, cy_offset=25.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.55, span=7.0, step=1.0, t=t)
            _add_3d_yellow_car(
                sc,
                center=(0.0, -1.08, 0.0),
                scale=1.08,
                yaw=0.16 + math.sin(t * 1.4) * 0.08,
                t=t,
                with_driver=True,
                driver_pose="cta_shrug",
                driver_emotion="cta",
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "diff_gear_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("diff_gear_hero", t=0.35, prog=0.45, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
