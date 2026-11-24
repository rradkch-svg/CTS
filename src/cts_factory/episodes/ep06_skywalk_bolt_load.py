"""Episode 06: How One Tiny Bolt Change DOUBLED Steel Stress — True 3D Statics CAD + UNIT-01."""

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
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes.base import EpisodeScene, register_scene

STEEL_LIGHT = (192, 210, 228)
STEEL_MID = (116, 138, 166)
STEEL_DARK = (50, 66, 92)
BRASS = (224, 174, 72)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


@register_scene("ep06_skywalk_bolt_load")
class SkywalkBoltLoadScene(EpisodeScene):
    """Articulated 12-beat True 3D Statics & Free-Body Diagram Cutaway + UNIT-01 scene."""

    slug = "ep06_skywalk_bolt_load"
    episode_id = "ep06"

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

    def _add_ceiling_anchor(self, sc: Scene3D, cx: float = 0.58, y: float = 1.94, width: float = 2.65) -> None:
        """Persistent overhead structural ceiling anchor beam so hanger rods NEVER float in empty air."""
        sc.add_box((cx, y, 0.0), (width, 0.24, 0.92), STEEL_DARK, metallic=0.68, texture="concrete")
        sc.add_box((cx, y - 0.14, 0.0), (width + 0.10, 0.06, 0.96), STEEL_MID, metallic=0.76)

    def _add_3d_hex_nut(
        self,
        sc: Scene3D,
        center: tuple[float, float, float],
        radius: float = 0.34,
        height: float = 0.24,
        rgb: tuple[int, int, int] = BRASS,
        emissive: float = 0.0,
        bloom: bool = False,
        washer_below: bool = False,
    ) -> None:
        """Crisp 6-sided 3D steel hexagonal nut + washer seated flush against the bearing face (never floating/inverted!)."""
        cx, cy, cz = center
        if washer_below:
            # Nut sits ON TOP of upper beam flange -> washer goes BELOW nut, flush on beam!
            sc.add_cylinder((cx, cy - height * 0.64, cz), (cx, cy - height * 0.50, cz), radius * 1.24, radius * 1.24, STEEL_LIGHT, segments=16, metallic=0.84)
        else:
            # Nut rests BELOW lower beam flange -> washer goes ABOVE nut, flush on beam!
            sc.add_cylinder((cx, cy + height * 0.50, cz), (cx, cy + height * 0.64, cz), radius * 1.24, radius * 1.24, STEEL_LIGHT, segments=16, metallic=0.84)
        sc.add_cylinder((cx, cy - height * 0.50, cz), (cx, cy + height * 0.50, cz), radius, radius, rgb, segments=6, metallic=0.74, emissive=emissive, bloom=bloom)

    def _add_3d_box_beam(
        self,
        sc: Scene3D,
        center: tuple[float, float, float],
        width: float = 2.0,
        height: float = 0.62,
        depth: float = 0.85,
        peel: float = 0.0,
        stress_col: tuple[int, int, int] | None = None,
    ) -> None:
        """Twin welded C-channel hollow box beam with visible top/bottom weld seams and true hinged bottom-flange peel."""
        cx, cy, cz = center
        col = stress_col if stress_col is not None else STEEL_MID
        half_w = width * 0.44
        half_h = height * 0.42

        # Top flange split into twin welded C-channel flanges with crisp center weld seam bead!
        sc.add_box((cx - width * 0.25, cy + half_h, cz), (width * 0.48, 0.12, depth), STEEL_LIGHT, metallic=0.76)
        sc.add_box((cx + width * 0.25, cy + half_h, cz), (width * 0.48, 0.12, depth), STEEL_LIGHT, metallic=0.76)
        sc.add_box((cx, cy + half_h, cz), (0.06, 0.13, depth + 0.02), AMBER if peel > 0.1 else STEEL_DARK, metallic=0.65)

        # Left & right vertical C-channel webs
        for sx in (-1, 1):
            sc.add_box((cx + sx * half_w, cy, cz), (0.14, height * 0.88, depth), col, metallic=0.72)

        # Bottom flange halves HINGED at the outer web corners (cx ± half_w, cy - half_h) so they curl downward cleanly!
        flange_len = width * 0.44
        for sx in (-1, 1):
            ang = sx * peel * 0.82  # Right bends down-right, left bends down-left opening the center weld seam!
            hinge_x = cx + sx * half_w
            hinge_y = cy - half_h
            # Vector from hinge inward toward center is (-sx * flange_len/2, 0), rotated by ang:
            dx_in = -sx * (flange_len * 0.5)
            fx = hinge_x + math.cos(ang) * dx_in
            fy = hinge_y + math.sin(ang) * dx_in
            sc.add_box(
                (fx, fy, cz),
                (flange_len, 0.12, depth),
                lerp_color(STEEL_LIGHT, DANGER, peel),
                rot=(0.0, 0.0, ang),
                metallic=0.74,
                emissive=0.35 * peel,
                bloom=(peel > 0.45),
            )
        if peel < 0.08:
            sc.add_box((cx, cy - half_h, cz), (0.06, 0.13, depth + 0.02), STEEL_DARK, metallic=0.65)

    def _draw_force_pill(self, d: ImageDraw.ImageDraw, text: str, x: int, y: int, col: tuple[int, int, int], font_size: int = 32) -> None:
        """High-contrast dark pill label so 1W / 2W! never wash out over bright bloom."""
        p = self.palette
        assert p is not None
        f = load_font(self.font_black, font_size)
        bb = d.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        bx0 = min(x, 852 - tw - 26)
        d.rounded_rectangle([bx0, y, bx0 + tw + 26, y + th + 18], radius=12, fill=p.surface_panel, outline=col, width=3)
        d.text((bx0 + 13, y + 9 - bb[1]), text, font=f, fill=col)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float, is_cover: bool = False) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_steel_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("hex_nut_overload_hero", "load_path_trace", "fbd_overloaded_2w", "box_beam_flange_bend", "nut_pull_through_cad", "stress_ratio_bars"):
            bg = self.bg_alert_bgr
        elif scene_key in ("fbd_balanced_1w", "reinforced_plate_fix", "verdict_cta_card"):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_steel_bgr

        shake = math.sin(t * 58.0) * 0.05 if (scene_key in ("hex_nut_overload_hero", "nut_pull_through_cad") and not is_cover) else 0.0

        if scene_key == "hex_nut_overload_hero":
            # FRAME 0 HERO: Macro 3D hex nut + threaded rod + overhead anchor concentrating 200% load onto twin-channel seam!
            if is_cover:
                cam = Camera3D(eye=(1.30, 0.72, 6.75), target=(0.15, 0.55, 0.0), fov_deg=41.0, cy_offset=45.0)
            else:
                cam = Camera3D(eye=(1.30 + math.sin(t * 1.1) * 0.25 + shake, 0.65, 6.15), target=(0.10, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.45, y=1.96, width=2.45)
            self._add_3d_box_beam(sc, (0.45, 0.22, 0.0), width=2.20, height=0.80, depth=1.06, peel=0.22 + 0.07 * math.sin(t * 10.0))
            sc.add_cylinder((0.45, 1.92, 0.0), (0.45, -1.05, 0.0), 0.115, 0.115, STEEL_LIGHT, segments=14, metallic=0.84)
            self._add_3d_hex_nut(sc, (0.45, -0.45, 0.0), radius=0.36, height=0.26, rgb=DANGER, emissive=0.45, bloom=True)
            sc.add_arrow_3d((-0.25, 1.48, 0.45), (-0.25, 0.65, 0.45), DANGER, shaft_r=0.078, head_r=0.185)
            sc.add_arrow_3d((1.15, 1.48, 0.45), (1.15, 0.65, 0.45), DANGER, shaft_r=0.078, head_r=0.185)
            if not is_cover:
                add_crash_test_dummy(sc, pos=(-1.36, -0.88, 0.58), scale=0.66, yaw=0.38, pose="brace_impact", emotion="shock", t=t)
                overlays_2d.append(lambda d: draw_sparks(d, 600, 1020, t, 18, 165, 105, p, seed=61))

        elif scene_key in ("stacked_beams_blueprint", "continuous_rod_original"):
            cam = Camera3D(eye=(1.30, 0.55, 6.55), target=(0.12, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.62, y=1.92, width=2.45)
            sc.add_cylinder((0.62, 1.88, 0.0), (0.62, -1.62, 0.0), 0.085, 0.085, CYAN, segments=12, metallic=0.76, emissive=0.25)
            self._add_3d_box_beam(sc, (0.62, 0.55, 0.0), width=2.05, height=0.52, depth=0.85)
            self._add_3d_box_beam(sc, (0.62, -0.88, 0.0), width=2.05, height=0.52, depth=0.85)
            self._add_3d_hex_nut(sc, (0.62, 0.14, 0.0), radius=0.26, height=0.20, rgb=EMERALD, emissive=0.28)
            self._add_3d_hex_nut(sc, (0.62, -1.30, 0.0), radius=0.26, height=0.20, rgb=EMERALD, emissive=0.28)
            add_crash_test_dummy(sc, pos=(-1.38, -0.92, 0.58), scale=0.66, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "fbd_balanced_1w":
            # Free-body diagram: emerald 1W on upper nut + emerald 1W on lower nut (with crisp pill labels!)
            cam = Camera3D(eye=(-1.10, 0.55, 6.55), target=(0.12, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.55, y=1.92, width=2.40)
            sc.add_cylinder((0.55, 1.88, 0.0), (0.55, -1.62, 0.0), 0.085, 0.085, CYAN, segments=12, metallic=0.76, emissive=0.25)
            self._add_3d_box_beam(sc, (0.55, 0.55, 0.0), width=1.95, height=0.50, depth=0.82)
            self._add_3d_box_beam(sc, (0.55, -0.88, 0.0), width=1.95, height=0.50, depth=0.82)
            self._add_3d_hex_nut(sc, (0.55, 0.16, 0.0), radius=0.26, height=0.20, rgb=EMERALD, emissive=0.38, bloom=True)
            self._add_3d_hex_nut(sc, (0.55, -1.28, 0.0), radius=0.26, height=0.20, rgb=EMERALD, emissive=0.38, bloom=True)
            sc.add_arrow_3d((1.58, 0.92, 0.25), (1.58, 0.22, 0.25), EMERALD, shaft_r=0.064, head_r=0.15)
            sc.add_arrow_3d((1.58, -0.48, 0.25), (1.58, -1.18, 0.25), EMERALD, shaft_r=0.064, head_r=0.15)
            add_crash_test_dummy(sc, pos=(-1.38, -0.92, 0.58), scale=0.66, yaw=0.38, pose="point_right", emotion="relief", t=t)

            def _lbl_1w(d: ImageDraw.ImageDraw) -> None:
                self._draw_force_pill(d, "1W", 745, 795, p.emerald, font_size=34)
                self._draw_force_pill(d, "1W", 745, 1115, p.emerald, font_size=34)

            overlays_2d.append(_lbl_1w)

        elif scene_key in ("offset_rod_swap", "load_path_trace"):
            # Clean animated swap from 1 continuous rod -> 2 offset rods with properly oriented washers (washer_below=True on top nut!)
            shift = ease_in_out_cubic(prog) * 0.65 if scene_key == "offset_rod_swap" else 0.65
            cam = Camera3D(eye=(1.15, 0.55, 6.55), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.55, y=1.92, width=2.45)
            ux = 0.55 - shift * 0.45
            lx = 0.55 + shift * 0.55
            rod_u_col = DANGER if scene_key == "load_path_trace" else CYAN
            sc.add_cylinder((ux, 1.88, 0.0), (ux, -0.05, 0.0), 0.085, 0.085, rod_u_col, segments=12, metallic=0.74, emissive=0.30)
            sc.add_cylinder((lx, 1.08, 0.0), (lx, -1.55, 0.0), 0.085, 0.085, AMBER if scene_key == "load_path_trace" else STEEL_LIGHT, segments=12, metallic=0.74, emissive=0.25)
            self._add_3d_box_beam(sc, (0.55, 0.55, 0.0), width=2.10, height=0.52, depth=0.85)
            self._add_3d_box_beam(sc, (0.55, -0.88, 0.0), width=2.10, height=0.52, depth=0.85)
            # Upper nut under upper beam (washer ABOVE nut -> flush under bottom flange!)
            self._add_3d_hex_nut(sc, (ux, 0.14, 0.0), radius=0.28, height=0.22, rgb=DANGER, emissive=0.45, bloom=True, washer_below=False)
            # Lower rod's upper nut ON TOP of upper beam (washer BELOW nut -> flush on top flange! ZERO floating washer!)
            if shift > 0.18:
                self._add_3d_hex_nut(sc, (lx, 0.96, 0.0), radius=0.25, height=0.18, rgb=BRASS, washer_below=True)
            self._add_3d_hex_nut(sc, (lx, -1.28, 0.0), radius=0.25, height=0.18, rgb=BRASS, washer_below=False)
            if scene_key == "load_path_trace":
                # Glowing crimson load-path arrows tracing lower beam -> upper beam -> single left upper nut!
                sc.add_arrow_3d((lx + 0.36, -0.58, 0.38), (lx + 0.36, 0.48, 0.38), DANGER, shaft_r=0.064, head_r=0.15)
                sc.add_arrow_3d((lx, 0.55, 0.54), (ux, 0.55, 0.54), DANGER, shaft_r=0.064, head_r=0.15)
            add_crash_test_dummy(sc, pos=(-1.38, -0.92, 0.58), scale=0.66, yaw=0.38, pose="point_right", emotion="shock" if scene_key == "load_path_trace" else "curious", t=t)

        elif scene_key == "fbd_overloaded_2w":
            # Free-body diagram: ALL 3 nuts present (including BOTH nuts on lower offset rod!) + "2W!" strictly on LEFT red nut!
            cam = Camera3D(eye=(-1.05, 0.55, 6.55), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.58, y=1.92, width=2.45)
            ux, lx = 0.22, 0.96
            sc.add_cylinder((ux, 1.88, 0.0), (ux, -0.05, 0.0), 0.09, 0.09, DANGER, segments=12, emissive=0.45, bloom=True)
            sc.add_cylinder((lx, 1.08, 0.0), (lx, -1.55, 0.0), 0.085, 0.085, AMBER, segments=12, metallic=0.72, emissive=0.25)
            self._add_3d_box_beam(sc, (0.58, 0.52, 0.0), width=2.15, height=0.54, depth=0.85, peel=0.18)
            self._add_3d_box_beam(sc, (0.58, -0.92, 0.0), width=2.15, height=0.52, depth=0.85)
            # Overloaded LEFT red nut (2W!) + BOTH brass nuts on RIGHT lower rod (1W)!
            self._add_3d_hex_nut(sc, (ux, 0.08, 0.0), radius=0.32, height=0.24, rgb=DANGER, emissive=0.65, bloom=True, washer_below=False)
            self._add_3d_hex_nut(sc, (lx, 0.94, 0.0), radius=0.25, height=0.18, rgb=BRASS, washer_below=True)
            self._add_3d_hex_nut(sc, (lx, -1.32, 0.0), radius=0.25, height=0.18, rgb=BRASS, washer_below=False)
            # Double crimson 1W + 1W arrows slamming down onto LEFT overloaded nut!
            sc.add_arrow_3d((ux - 0.22, 1.48, 0.45), (ux - 0.22, 0.48, 0.45), DANGER, shaft_r=0.070, head_r=0.16)
            sc.add_arrow_3d((ux + 0.22, 1.48, 0.45), (ux + 0.22, 0.48, 0.45), DANGER, shaft_r=0.070, head_r=0.16)
            add_crash_test_dummy(sc, pos=(-1.38, -0.92, 0.58), scale=0.66, yaw=0.38, pose="brace_impact", emotion="panic", t=t)

            def _lbl_2w(d: ImageDraw.ImageDraw) -> None:
                # 2W! badge strictly right beside the LEFT red overloaded nut, and 1W on the lower RIGHT rod!
                self._draw_force_pill(d, "2W!", 395, 790, p.danger, font_size=36)
                self._draw_force_pill(d, "1W", 745, 1140, p.amber, font_size=30)

            overlays_2d.append(_lbl_2w)

        elif scene_key == "box_beam_flange_bend":
            # Macro cutaway of the twin C-channel toe-to-toe hollow weld seam bending smoothly above the nut!
            bend = ease_in_out_cubic(prog) * 0.48
            cam = Camera3D(eye=(0.45, 0.55, 6.05), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.55, y=1.96, width=2.50)
            self._add_3d_box_beam(sc, (0.55, 0.35, 0.0), width=2.30, height=0.88, depth=1.10, peel=bend)
            sc.add_cylinder((0.55, 1.92, 0.0), (0.55, -1.05, 0.0), 0.115, 0.115, STEEL_LIGHT, segments=14, metallic=0.84)
            # Nut stays cleanly below the bending bottom seam!
            self._add_3d_hex_nut(sc, (0.55, -0.34 - bend * 0.25, 0.0), radius=0.35, height=0.26, rgb=AMBER, emissive=0.35)
            sc.add_arrow_3d((0.55, 1.55, 0.55), (0.55, 0.72, 0.55), DANGER, shaft_r=0.080, head_r=0.185)
            add_crash_test_dummy(sc, pos=(-1.38, -0.90, 0.58), scale=0.66, yaw=0.38, pose="point_right", emotion="shock", t=t)

        elif scene_key == "nut_pull_through_cad":
            # CLIMAX: Bottom flanges hinge wide downward as the box beam slides PAST the stationary red nut!
            peel = 0.28 + ease_out_cubic(clamp(prog * 1.15)) * 0.72
            drop = ease_in_out_cubic(clamp((prog - 0.28) / 0.72)) * 1.05
            cam = Camera3D(eye=(0.72 + shake, 0.55, 6.15), target=(0.12, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.55, y=1.96, width=2.50)
            # Box beam drops downward while hinged bottom flanges peel open around the red nut!
            self._add_3d_box_beam(sc, (0.55, 0.35 - drop, 0.0), width=2.30, height=0.86, depth=1.10, peel=peel)
            sc.add_cylinder((0.55, 1.92, 0.0), (0.55, -0.68, 0.0), 0.115, 0.115, STEEL_LIGHT, segments=14, metallic=0.84)
            # Stationary red hex nut stays anchored at y = -0.22 as the beam drops past it -> TRUE pull-through!
            self._add_3d_hex_nut(sc, (0.55, -0.22, 0.0), radius=0.34, height=0.25, rgb=DANGER, emissive=0.68, bloom=True)
            add_crash_test_dummy(sc, pos=(-1.35, -0.90, 0.58), scale=0.64, yaw=0.38, pose="panic_freefall", emotion="panic", t=t)
            # Sparks strictly at the curled bottom seam tearing past the nut!
            spark_y = int(1045 + drop * 110)
            overlays_2d.append(lambda d, sy=spark_y: draw_sparks(d, 615, sy, t, 22, 185, 130, p, seed=69))

        elif scene_key == "stress_ratio_bars":
            # Unobstructed BOLT on left pointing at safe-zone bars (x0=320, width=540 -> x1=860!)
            cam = Camera3D(eye=(0.25, 0.35, 6.20), target=(0.0, -0.25, 0.0), fov_deg=41.0, cy_offset=95.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            add_crash_test_dummy(sc, pos=(-1.62, -0.45, 0.48), scale=0.68, yaw=0.40, pose="point_right", emotion="shock", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=320,
                    y0=715,
                    width=540,
                    height=355,
                    items=[
                        ("ORIGINAL NUT (1W)", "100%", 0.50, p.emerald),
                        ("OFFSET NUT (2W)", "200%", 1.00, p.danger),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([320, 1105, 860, 1188], radius=16, fill=p.surface_panel, outline=p.danger, width=4)
                f = load_font(self.font_black, 25)
                msg = "SAFETY FACTOR DROPPED < 1.0"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((590 - (bb[2] - bb[0]) / 2, 1130), msg, font=f, fill=p.danger)

            overlays_2d.append(_bars)

        elif scene_key == "reinforced_plate_fix":
            # Certified fix: ceiling anchor + continuous rod + thick emerald steel load-spreader bearing plate!
            cam = Camera3D(eye=(-1.10, 0.62, 6.35), target=(0.12, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.58, y=1.92, width=2.45)
            self._add_3d_box_beam(sc, (0.58, 0.35, 0.0), width=2.20, height=0.78, depth=1.02, peel=0.0, stress_col=STEEL_LIGHT)
            sc.add_box((0.58, -0.18, 0.0), (2.36, 0.24, 1.15), EMERALD, metallic=0.68, emissive=0.25, bloom=True)
            sc.add_cylinder((0.58, 1.88, 0.0), (0.58, -1.30, 0.0), 0.115, 0.115, CYAN, segments=14, metallic=0.84)
            self._add_3d_hex_nut(sc, (0.58, -0.45, 0.0), radius=0.34, height=0.25, rgb=BRASS)
            add_crash_test_dummy(sc, pos=(-1.38, -0.88, 0.58), scale=0.66, yaw=0.38, pose="relief_wave", emotion="relief", t=t)

        else:  # verdict_cta_card — Certified emerald beam offset cleanly right behind BOLT (ZERO rod spearing torso!) + safe-zone CTA buttons!
            cam = Camera3D(eye=(math.sin(t * 0.9) * 0.35, 0.55, 6.05), target=(0.0, 0.10, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.70, span=7.0, step=1.0, t=t)
            self._add_ceiling_anchor(sc, cx=0.92, y=1.96, width=2.20)
            self._add_3d_box_beam(sc, (0.92, 0.52, -1.15), width=2.15, height=0.64, depth=0.82, peel=0.0, stress_col=STEEL_LIGHT)
            sc.add_box((0.92, 0.08, -1.15), (2.28, 0.20, 0.92), EMERALD, metallic=0.65, emissive=0.22)
            sc.add_cylinder((0.92, 1.92, -1.15), (0.92, -1.15, -1.15), 0.095, 0.095, CYAN, segments=12, metallic=0.82)
            self._add_3d_hex_nut(sc, (0.92, -0.18, -1.15), radius=0.28, height=0.22, rgb=BRASS)
            add_crash_test_dummy(sc, pos=(-0.58, -0.08, 0.45), scale=0.86, yaw=0.18 + math.sin(t * 1.8) * 0.12, pose="cta_shrug", emotion="cta", t=t)
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "hex_nut_overload_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("hex_nut_overload_hero", t=0.35, prog=0.45, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
