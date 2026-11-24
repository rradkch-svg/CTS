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

    def _add_3d_hex_nut(
        self,
        sc: Scene3D,
        center: tuple[float, float, float],
        radius: float = 0.34,
        height: float = 0.24,
        rgb: tuple[int, int, int] = BRASS,
        emissive: float = 0.0,
        bloom: bool = False,
    ) -> None:
        """Crisp 6-sided 3D steel hexagonal nut + washer resting below box beam."""
        cx, cy, cz = center
        # Washer ring right above hex nut
        sc.add_cylinder((cx, cy + height * 0.50, cz), (cx, cy + height * 0.66, cz), radius * 1.24, radius * 1.24, STEEL_LIGHT, segments=14, metallic=0.82)
        # 6-segment cylinder = true sharp hexagonal nut!
        sc.add_cylinder((cx, cy - height * 0.50, cz), (cx, cy + height * 0.50, cz), radius, radius, rgb, segments=6, metallic=0.72, emissive=emissive, bloom=bloom)

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
        """Twin welded C-channel hollow box beam with visible center weld seam and optional bottom flange peel."""
        cx, cy, cz = center
        col = stress_col if stress_col is not None else STEEL_MID
        # Top flange
        sc.add_box((cx, cy + height * 0.42, cz), (width, 0.12, depth), STEEL_LIGHT, metallic=0.76)
        # Left & right vertical webs
        for sx in (-1, 1):
            sc.add_box((cx + sx * (width * 0.44), cy, cz), (0.14, height * 0.88, depth), col, metallic=0.70)
        # Bottom flange split in two halves (welded toe-to-toe) that can curl/peel downward under 2W load!
        for sx in (-1, 1):
            ang = sx * peel * 0.55
            fy = cy - height * 0.42 - peel * 0.24
            sc.add_box(
                (cx + sx * (width * 0.23 + peel * 0.08), fy, cz),
                (width * 0.46, 0.12, depth),
                lerp_color(STEEL_LIGHT, DANGER, peel),
                rot=(0.0, 0.0, ang),
                metallic=0.74,
                emissive=0.45 * peel,
                bloom=(peel > 0.35),
            )

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_steel_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("hex_nut_overload_hero", "load_path_trace", "fbd_overloaded_2w", "box_beam_flange_bend", "nut_pull_through_cad", "stress_ratio_bars"):
            bg = self.bg_alert_bgr
        elif scene_key in ("fbd_balanced_1w", "reinforced_plate_fix", "verdict_cta_card"):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_steel_bgr

        shake = math.sin(t * 58.0) * 0.055 if scene_key in ("hex_nut_overload_hero", "nut_pull_through_cad") else 0.0

        if scene_key == "hex_nut_overload_hero":
            # FRAME 0 HERO: Macro 3D hex nut + threaded rod concentrating 200% crimson load vectors onto a box-beam seam!
            cam = Camera3D(eye=(1.35 + math.sin(t * 1.1) * 0.30 + shake, 0.65, 5.95), target=(0.10, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_box_beam(sc, (0.45, 0.25, 0.0), width=2.25, height=0.82, depth=1.10, peel=0.22 + 0.08 * math.sin(t * 10.0))
            sc.add_cylinder((0.45, 2.05, 0.0), (0.45, -1.05, 0.0), 0.12, 0.12, STEEL_LIGHT, segments=12, metallic=0.84)
            self._add_3d_hex_nut(sc, (0.45, -0.45, 0.0), radius=0.38, height=0.28, rgb=DANGER, emissive=0.55, bloom=True)
            # Twin huge crimson 200% downward load arrows hammering the box beam onto the single nut!
            sc.add_arrow_3d((-0.25, 1.55, 0.45), (-0.25, 0.65, 0.45), DANGER, shaft_r=0.085, head_r=0.20)
            sc.add_arrow_3d((1.15, 1.55, 0.45), (1.15, 0.65, 0.45), DANGER, shaft_r=0.085, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.45, -0.88, 0.72), scale=0.72, yaw=0.38, pose="brace_impact", emotion="shock", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 600, 1020, t, 18, 170, 110, p, seed=61))

        elif scene_key in ("stacked_beams_blueprint", "continuous_rod_original"):
            # Clean elevation of two stacked suspended box beams hanging from ONE continuous ceiling rod!
            cam = Camera3D(eye=(1.35, 0.55, 6.45), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, t=t)
            # Ceiling anchor beam
            sc.add_box((0.62, 1.88, 0.0), (2.45, 0.22, 0.85), STEEL_DARK, metallic=0.68)
            # One continuous vertical hanger rod passing cleanly through BOTH box beams!
            sc.add_cylinder((0.62, 1.85, 0.0), (0.62, -1.65, 0.0), 0.085, 0.085, CYAN, segments=12, metallic=0.72, emissive=0.35)
            # Upper box beam + lower box beam
            self._add_3d_box_beam(sc, (0.62, 0.55, 0.0), width=2.05, height=0.52, depth=0.85)
            self._add_3d_box_beam(sc, (0.62, -0.88, 0.0), width=2.05, height=0.52, depth=0.85)
            self._add_3d_hex_nut(sc, (0.62, 0.14, 0.0), radius=0.26, height=0.20, rgb=EMERALD, emissive=0.35)
            self._add_3d_hex_nut(sc, (0.62, -1.30, 0.0), radius=0.26, height=0.20, rgb=EMERALD, emissive=0.35)
            add_crash_test_dummy(sc, pos=(-1.48, -0.92, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "fbd_balanced_1w":
            # Free-body diagram: emerald 1W on upper nut + emerald 1W on lower nut (SAFE!)
            cam = Camera3D(eye=(-1.15, 0.55, 6.45), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, t=t)
            sc.add_cylinder((0.55, 1.95, 0.0), (0.55, -1.65, 0.0), 0.085, 0.085, EMERALD, segments=12, emissive=0.45, bloom=True)
            self._add_3d_box_beam(sc, (0.55, 0.55, 0.0), width=1.95, height=0.50, depth=0.82)
            self._add_3d_box_beam(sc, (0.55, -0.88, 0.0), width=1.95, height=0.50, depth=0.82)
            self._add_3d_hex_nut(sc, (0.55, 0.16, 0.0), radius=0.26, height=0.20, rgb=EMERALD, emissive=0.55, bloom=True)
            self._add_3d_hex_nut(sc, (0.55, -1.28, 0.0), radius=0.26, height=0.20, rgb=EMERALD, emissive=0.55, bloom=True)
            # Balanced 1W downward arrows
            sc.add_arrow_3d((1.55, 0.95, 0.25), (1.55, 0.20, 0.25), EMERALD, shaft_r=0.068, head_r=0.16)
            sc.add_arrow_3d((1.55, -0.45, 0.25), (1.55, -1.20, 0.25), EMERALD, shaft_r=0.068, head_r=0.16)
            add_crash_test_dummy(sc, pos=(-1.48, -0.92, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="relief", t=t)

            def _lbl_1w(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 36)
                d.text((790, 815), "1W", font=f, fill=p.emerald, stroke_width=4, stroke_fill=p.ink)
                d.text((790, 1145), "1W", font=f, fill=p.emerald, stroke_width=4, stroke_fill=p.ink)

            overlays_2d.append(_lbl_1w)

        elif scene_key in ("offset_rod_swap", "load_path_trace"):
            # Animated swap from 1 continuous rod -> 2 shorter offset rods hanging lower beam from upper beam!
            shift = ease_in_out_cubic(prog) * 0.62 if scene_key == "offset_rod_swap" else 0.62
            cam = Camera3D(eye=(1.25, 0.55, 6.45), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, t=t)
            # Upper rod (ceiling -> upper beam)
            ux = 0.55 - shift * 0.45
            lx = 0.55 + shift * 0.55
            sc.add_cylinder((ux, 1.95, 0.0), (ux, 0.05, 0.0), 0.085, 0.085, AMBER if scene_key == "offset_rod_swap" else DANGER, segments=12, emissive=0.45)
            # Lower rod (upper beam -> lower beam)
            sc.add_cylinder((lx, 0.92, 0.0), (lx, -1.55, 0.0), 0.085, 0.085, CYAN if scene_key == "offset_rod_swap" else DANGER, segments=12, emissive=0.45)
            self._add_3d_box_beam(sc, (0.55, 0.55, 0.0), width=2.10, height=0.52, depth=0.85)
            self._add_3d_box_beam(sc, (0.55, -0.88, 0.0), width=2.10, height=0.52, depth=0.85)
            self._add_3d_hex_nut(sc, (ux, 0.14, 0.0), radius=0.28, height=0.22, rgb=DANGER, emissive=0.55, bloom=True)
            self._add_3d_hex_nut(sc, (lx, 0.96, 0.0), radius=0.25, height=0.18, rgb=BRASS)
            self._add_3d_hex_nut(sc, (lx, -1.28, 0.0), radius=0.25, height=0.18, rgb=BRASS)
            if scene_key == "load_path_trace":
                # Glowing crimson load-path arrows tracing lower beam -> upper beam -> single upper nut!
                sc.add_arrow_3d((lx + 0.35, -0.55, 0.35), (lx + 0.35, 0.45, 0.35), DANGER, shaft_r=0.068, head_r=0.16)
                sc.add_arrow_3d((lx, 0.55, 0.52), (ux, 0.55, 0.52), DANGER, shaft_r=0.068, head_r=0.16)
            add_crash_test_dummy(sc, pos=(-1.48, -0.92, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="shock" if scene_key == "load_path_trace" else "curious", t=t)

        elif scene_key == "fbd_overloaded_2w":
            # Free-body diagram explosion: BOTH 1W + 1W = 2W (200%) slamming onto the single upper nut!
            cam = Camera3D(eye=(-1.15, 0.55, 6.40), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, t=t)
            ux, lx = 0.25, 0.92
            sc.add_cylinder((ux, 1.95, 0.0), (ux, 0.02, 0.0), 0.09, 0.09, DANGER, segments=12, emissive=0.65, bloom=True)
            sc.add_cylinder((lx, 0.90, 0.0), (lx, -1.55, 0.0), 0.085, 0.085, AMBER, segments=12, emissive=0.45)
            self._add_3d_box_beam(sc, (0.58, 0.52, 0.0), width=2.15, height=0.54, depth=0.85, peel=0.18)
            self._add_3d_box_beam(sc, (0.58, -0.92, 0.0), width=2.15, height=0.52, depth=0.85)
            self._add_3d_hex_nut(sc, (ux, 0.08, 0.0), radius=0.32, height=0.24, rgb=DANGER, emissive=0.80, bloom=True)
            # Double huge crimson arrows hammering the upper nut!
            sc.add_arrow_3d((ux - 0.22, 1.48, 0.45), (ux - 0.22, 0.48, 0.45), DANGER, shaft_r=0.075, head_r=0.17)
            sc.add_arrow_3d((ux + 0.22, 1.48, 0.45), (ux + 0.22, 0.48, 0.45), DANGER, shaft_r=0.075, head_r=0.17)
            add_crash_test_dummy(sc, pos=(-1.48, -0.92, 0.72), scale=0.72, yaw=0.38, pose="brace_impact", emotion="panic", t=t)

            def _lbl_2w(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 40)
                d.text((780, 790), "2W!", font=f, fill=p.danger, stroke_width=5, stroke_fill=p.ink)

            overlays_2d.append(_lbl_2w)

        elif scene_key == "box_beam_flange_bend":
            # Macro cutaway of the twin C-channel toe-to-toe hollow weld seam bending above the washer!
            bend = ease_in_out_cubic(prog) * 0.55
            cam = Camera3D(eye=(0.45, 0.55, 5.75), target=(0.20, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_box_beam(sc, (0.55, 0.35, 0.0), width=2.35, height=0.92, depth=1.15, peel=bend)
            sc.add_cylinder((0.55, 1.95, 0.0), (0.55, -0.95, 0.0), 0.12, 0.12, STEEL_LIGHT, segments=12, metallic=0.84)
            self._add_3d_hex_nut(sc, (0.55, -0.35 - bend * 0.12, 0.0), radius=0.36, height=0.26, rgb=AMBER, emissive=0.45)
            sc.add_arrow_3d((0.55, 1.65, 0.55), (0.55, 0.65, 0.55), DANGER, shaft_r=0.088, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.48, -0.90, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="shock", t=t)

        elif scene_key == "nut_pull_through_cad":
            # CLIMAX: Abstract CAD cross-section as bottom flange curls downward and hex nut pulls cleanly through!
            peel = 0.25 + ease_out_cubic(clamp(prog * 1.25)) * 0.75
            cam = Camera3D(eye=(0.75 + shake, 0.55, 5.85), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            drop = ease_in_out_cubic(clamp((prog - 0.35) / 0.65)) * 0.85
            self._add_3d_box_beam(sc, (0.55, 0.42 - drop, 0.0), width=2.35, height=0.90, depth=1.15, peel=peel)
            sc.add_cylinder((0.55, 2.05, 0.0), (0.55, -0.75, 0.0), 0.12, 0.12, STEEL_LIGHT, segments=12, metallic=0.84)
            self._add_3d_hex_nut(sc, (0.55, -0.15, 0.0), radius=0.36, height=0.26, rgb=DANGER, emissive=0.78, bloom=True)
            add_crash_test_dummy(sc, pos=(-1.28, -0.90, 0.72), scale=0.68, yaw=0.38, pose="panic_freefall", emotion="panic", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 610, 990, t, 24, 210, 150, p, seed=69))

        elif scene_key == "stress_ratio_bars":
            # Clean split layout: UNIT-01 unobstructed on left pointing at 100% vs 200% nut stress bars!
            cam = Camera3D(eye=(0.25, 0.35, 5.95), target=(0.0, -0.25, 0.0), fov_deg=41.0, cy_offset=95.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, t=t)
            add_crash_test_dummy(sc, pos=(-1.42, -0.45, 0.55), scale=0.72, yaw=0.38, pose="point_right", emotion="shock", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=325,
                    y0=715,
                    width=680,
                    height=355,
                    items=[
                        ("ORIGINAL NUT (1W)", "100%", 0.50, p.emerald),
                        ("OFFSET NUT (2W)", "200%", 1.00, p.danger),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([325, 1105, 1005, 1188], radius=16, fill=p.surface_panel, outline=p.danger, width=4)
                f = load_font(self.font_black, 28)
                msg = "SAFETY FACTOR DROPPED < 1.0"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((665 - (bb[2] - bb[0]) / 2, 1130), msg, font=f, fill=p.danger)

            overlays_2d.append(_bars)

        elif scene_key == "reinforced_plate_fix":
            # Certified fix: continuous rod + thick emerald steel load-spreader bearing plate!
            cam = Camera3D(eye=(-1.15, 0.65, 6.15), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_box_beam(sc, (0.58, 0.35, 0.0), width=2.25, height=0.80, depth=1.05, peel=0.0, stress_col=STEEL_LIGHT)
            # Thick solid emerald reinforced load-spreader bearing plate underneath the box beam!
            sc.add_box((0.58, -0.18, 0.0), (2.40, 0.24, 1.18), EMERALD, metallic=0.68, emissive=0.35, bloom=True)
            sc.add_cylinder((0.58, 1.95, 0.0), (0.58, -1.35, 0.0), 0.12, 0.12, CYAN, segments=12, metallic=0.84)
            self._add_3d_hex_nut(sc, (0.58, -0.45, 0.0), radius=0.36, height=0.26, rgb=BRASS)
            add_crash_test_dummy(sc, pos=(-1.48, -0.88, 0.72), scale=0.72, yaw=0.38, pose="relief_wave", emotion="relief", t=t)

        else:  # verdict_cta_card
            cam = Camera3D(eye=(math.sin(t * 0.9) * 0.45, 0.55, 5.75), target=(0.0, 0.12, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.70, span=7.0, step=1.0, t=t)
            # Certified emerald reinforced box-beam & continuous rod behind UNIT-01
            self._add_3d_box_beam(sc, (0.0, 0.55, -1.25), width=2.45, height=0.68, depth=0.85, peel=0.0, stress_col=STEEL_LIGHT)
            sc.add_box((0.0, 0.10, -1.25), (2.55, 0.20, 0.95), EMERALD, metallic=0.65, emissive=0.30)
            sc.add_cylinder((0.0, 2.05, -1.25), (0.0, -1.25, -1.25), 0.10, 0.10, CYAN, segments=12)
            add_crash_test_dummy(sc, pos=(0.0, -0.02, 0.38), scale=0.96, yaw=math.sin(t * 1.8) * 0.14, pose="cta_shrug", emotion="cta", t=t)

            def _cta_buttons(d: ImageDraw.ImageDraw) -> None:
                pulse = 1.0 + 0.04 * math.sin(t * 7.0)
                for label, bx, col in (("YES", 205, p.cyan), ("NO", 875, p.amber)):
                    bw, bh = int(134 * pulse), int(84 * pulse)
                    by = 1125
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "hex_nut_overload_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("hex_nut_overload_hero", t=0.35, prog=0.45, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
