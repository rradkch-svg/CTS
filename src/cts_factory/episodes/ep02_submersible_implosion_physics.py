"""Episode 02: Why Deep-Sea Hulls IMPLODE in Milliseconds — True 3D Phong + Crash-Test Dummy."""

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
    draw_dotted_arc,
    draw_pressure_gauge,
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes.base import EpisodeScene, register_scene

STEEL_LIGHT = (188, 206, 226)
STEEL_MID = (112, 134, 162)
STEEL_DARK = (50, 66, 92)
CARBON_DARK = (38, 48, 66)
BRASS = (218, 168, 72)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


@register_scene("ep02_submersible_implosion_physics")
class SubmersibleImplosionScene(EpisodeScene):
    """Articulated 12-beat True 3D Phong Materials-Science + Crash-Test Dummy ('UNIT-01') scene."""

    slug = "ep02_submersible_implosion_physics"
    episode_id = "ep02"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_ocean_bgr: np.ndarray | None = None
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
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_composite_hull(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        half_len: float = 1.45,
        radius: float = 0.85,
        seam_stress: float = 0.5,
        buckling: float = 0.0,
        cutaway_dummy: bool = False,
        dummy_pose: str = "panic_freefall",
        dummy_emotion: str = "panic",
        t: float = 0.0,
    ) -> None:
        """True 3D cylindrical carbon-fiber pressure hull with Phong titanium domes & end-rings."""
        cx, cy, cz = center
        # Left & right glossy 3D titanium hemispherical end domes
        sc.add_sphere((cx - half_len, cy, cz), radius * 0.98, STEEL_MID, metallic=0.78)
        sc.add_sphere((cx + half_len, cy, cz), radius * 0.98, STEEL_MID, metallic=0.78)
        # Bonded titanium-to-carbon end rings (pulsing crimson under seam stress)
        ring_col = lerp_color(BRASS, DANGER, clamp(seam_stress))
        for sx in (-1, 1):
            rx0 = cx + sx * (half_len - 0.16)
            rx1 = cx + sx * (half_len + 0.06)
            sc.add_cylinder((rx0, cy, cz), (rx1, cy, cz), radius * 1.07, radius * 1.07, ring_col, segments=20, metallic=0.65, emissive=0.35 * clamp(seam_stress))

        # Segmented 3D carbon-fiber tube showing true inward buckling pinch!
        n_seg = 6
        body_col = lerp_color(CARBON_DARK, DANGER, buckling * 0.45)
        alpha = 0.48 if cutaway_dummy else 1.0
        for i in range(n_seg):
            u0 = i / n_seg
            u1 = (i + 1) / n_seg
            x0 = cx - half_len + 0.14 + u0 * (2.0 * (half_len - 0.14))
            x1 = cx - half_len + 0.14 + u1 * (2.0 * (half_len - 0.14))
            r0 = radius * (1.0 - buckling * 0.62 * (math.sin(u0 * math.pi) ** 1.4))
            r1 = radius * (1.0 - buckling * 0.62 * (math.sin(u1 * math.pi) ** 1.4))
            sc.add_cylinder((x0, cy, cz), (x1, cy, cz), r0, r1, body_col, segments=20, metallic=0.45, caps=False, alpha=alpha)

        if cutaway_dummy:
            # Crash-Test Dummy visible inside translucent 3D pressure cutaway!
            add_crash_test_dummy(sc, pos=(cx, cy - 0.18, cz + 0.05), scale=0.62, yaw=-0.18, pose=dummy_pose, emotion=dummy_emotion, t=t)

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
            sc.add_arrow_3d(p0, p1, rgb, shaft_r=0.058, head_r=0.145)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_ocean_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("hull_pressure_peak", "ply_shear_fatigue", "dimple_instability", "implosion_wave_020ms", "air_compression_pulse"):
            bg = self.bg_alert_bgr
        elif scene_key in ("sphere_uniform_stress", "verdict_cta_card"):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_ocean_bgr

        shake = math.sin(t * 60.0) * 0.065 if scene_key in ("hull_pressure_peak", "implosion_wave_020ms", "air_compression_pulse") else 0.0

        if scene_key == "hull_pressure_peak":
            # FRAME 0 HERO: Huge 3D cutaway pressure hull + wide-eyed UNIT-01 inside + 12 3D crimson radial arrows!
            cam = Camera3D(eye=(1.4 + math.sin(t * 1.2) * 0.35 + shake, 0.75, 5.5), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.25, span=7.0, step=1.0, rgb=(22, 48, 84))
            self._add_3d_composite_hull(
                sc,
                center=(0.0, 0.05, 0.0),
                half_len=1.40,
                radius=0.92,
                seam_stress=0.92,
                buckling=0.10 + 0.05 * math.sin(t * 14.0),
                cutaway_dummy=True,
                dummy_pose="panic_freefall",
                dummy_emotion="panic",
                t=t,
            )
            self._add_3d_radial_pressure_ring(sc, (0.0, 0.05, 0.0), 2.55, 1.38, 12, DANGER, t)
            overlays_2d.append(lambda d: draw_sparks(d, 350, 995, t, 10, 90, 90, p, seed=19))
            overlays_2d.append(lambda d: draw_sparks(d, 730, 995, t, 10, 90, 90, p, seed=29))

        elif scene_key == "depth_3800m_scale":
            cam = Camera3D(eye=(1.6, 0.55, 6.1), target=(0.0, -0.1, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.4, span=7.0, step=1.0, rgb=(20, 48, 84))
            sub_y = 1.15 - ease_out_cubic(prog) * 2.15
            self._add_3d_composite_hull(
                sc,
                center=(0.45, sub_y, 0.0),
                half_len=1.12,
                radius=0.68,
                seam_stress=prog * 0.65,
                cutaway_dummy=True,
                dummy_pose="brace_impact",
                dummy_emotion="curious",
                t=t,
            )
            sc.add_arrow_3d((0.45, sub_y + 1.55, 0.0), (0.45, sub_y + 0.80, 0.0), CYAN, shaft_r=0.075, head_r=0.18)

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
            cam = Camera3D(eye=(-1.5, 0.7, 6.2), target=(0.35, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, rgb=(20, 48, 84))
            self._add_3d_composite_hull(
                sc,
                center=(-0.45, 0.0, 0.0),
                half_len=1.05,
                radius=0.68,
                seam_stress=0.5,
                cutaway_dummy=True,
                dummy_pose="brace_impact",
                dummy_emotion="brace",
                t=t,
            )
            self._add_3d_radial_pressure_ring(sc, (-0.45, 0.0, 0.0), 2.15, 1.15, 10, CYAN, t)
            atm = int(round(1 + prog * 379))
            overlays_2d.append(
                lambda d, _a=atm, _p=prog: draw_pressure_gauge(
                    d, 825, 990, 136, clamp(_p * 0.92 + 0.08), "PRESSURE", f"{_a} ATM", p, self.font_black
                )
            )

        elif scene_key == "tonnage_per_sqft":
            cam = Camera3D(eye=(2.2, 1.45, 5.7), target=(0.0, -0.1, 0.0), fov_deg=40.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.85, span=7.0, step=1.0, rgb=(22, 48, 84))
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
            cam = Camera3D(eye=(-1.5, 0.75, 5.9), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(22, 54, 82))
            # Glossy 3D Phong-shaded Titanium Pressure Sphere!
            sc.add_sphere((0.52, 0.15, 0.0), 1.05, STEEL_LIGHT, metallic=0.84, rim_rgb=EMERALD)
            sc.add_sphere((0.52, 0.15, 0.65), 0.42, (20, 95, 130), metallic=0.65, rim_rgb=CYAN)
            self._add_3d_radial_pressure_ring(sc, (0.52, 0.15, 0.0), 2.15, 1.24, 10, EMERALD, t)
            add_crash_test_dummy(sc, pos=(-1.55, -0.85, 0.72), scale=0.84, yaw=0.36, pose="point_right", emotion="relief", t=t)

            def _unif_lbl(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_bold, 28)
                lbl = "UNIFORM MEMBRANE STRESS"
                bb = d.textbbox((0, 0), lbl, font=f)
                d.text((540 - (bb[2] - bb[0]) / 2, 1305), lbl, font=f, fill=p.emerald)

            overlays_2d.append(_unif_lbl)

        elif scene_key == "cylinder_joint_hotspot":
            cam = Camera3D(eye=(1.8, 0.9, 5.9), target=(0.0, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.1, span=7.0, step=1.0, rgb=(22, 48, 84))
            pulse = 0.55 + 0.45 * math.sin(t * 9.0)
            self._add_3d_composite_hull(sc, center=(0.45, 0.25, 0.0), half_len=1.32, radius=0.80, seam_stress=pulse)
            sc.add_arrow_3d((0.45, 2.05, 0.1), (0.45, 1.15, 0.1), DANGER, shaft_r=0.08, head_r=0.19)
            sc.add_arrow_3d((-0.78, 1.95, 0.1), (-0.78, 1.05, 0.1), DANGER, shaft_r=0.08, head_r=0.19)
            add_crash_test_dummy(sc, pos=(-1.60, -0.82, 0.85), scale=0.82, yaw=0.36, pose="point_right", emotion="curious", t=t)

        elif scene_key == "ply_shear_fatigue":
            cam = Camera3D(eye=(2.2, 1.25, 5.6), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(24, 46, 78))
            # 7 true 3D extruded carbon-fiber laminate plies shearing apart with crimson cracks
            n_plies = 7
            for i in range(n_plies):
                sep = (i - 3.0) * ease_in_out_cubic(prog) * 0.16
                py = (i - 3.0) * 0.34 + sep
                col = CARBON_DARK if i % 2 == 0 else STEEL_DARK
                sc.add_box((0.55, py, 0.0), (2.75, 0.22, 1.45), col, metallic=0.45)
                if i in (2, 4) and prog > 0.2:
                    crack_w = clamp((prog - 0.2) * 1.4) * 2.4
                    sc.add_box((0.55 - 1.2 + crack_w * 0.5, py + 0.16, 0.74), (crack_w, 0.07, 0.08), DANGER, emissive=0.75)
            sc.add_arrow_3d((0.55, 2.25, 0.2), (0.55, 1.35, 0.2), AMBER, shaft_r=0.085, head_r=0.20)
            sc.add_arrow_3d((0.55, -2.15, 0.2), (0.55, -1.25, 0.2), AMBER, shaft_r=0.085, head_r=0.20)
            add_crash_test_dummy(sc, pos=(-1.60, -0.82, 0.90), scale=0.80, yaw=0.38, pose="brace_impact", emotion="shock", t=t)

        elif scene_key == "dimple_instability":
            dimple = ease_out_cubic(clamp((prog - 0.32) / 0.55))
            cam = Camera3D(eye=(-1.55 + shake * dimple, 0.85, 5.4), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, rgb=(24, 46, 78))
            # Curved segmented 3D hull wall snapping an inward buckling dimple!
            for i in range(11):
                u = i / 10.0
                x = -0.95 + u * 2.95
                arch = math.sin(u * math.pi) * 0.45
                dent = math.exp(-((u - 0.5) / 0.15) ** 2) * dimple * 1.05
                y = 0.25 + arch - dent
                col = lerp_color(STEEL_MID, DANGER, math.exp(-((u - 0.5) / 0.18) ** 2) * dimple)
                sc.add_box((x, y, 0.0), (0.30, 0.42, 1.35), col, metallic=0.58, emissive=0.25 * dimple if abs(u - 0.5) < 0.16 else 0.0)
            sc.add_arrow_3d((0.52, 2.25 - dimple * 0.5, 0.15), (0.52, 0.95 - dimple * 0.85, 0.15), DANGER, shaft_r=0.095, head_r=0.23)
            add_crash_test_dummy(sc, pos=(-1.60, -0.88, 0.92), scale=0.80, yaw=0.36, pose="brace_impact", emotion="brace", t=t)

        elif scene_key == "implosion_wave_020ms":
            collapse = ease_in_out_cubic(clamp(prog * 1.15))
            cam = Camera3D(eye=(1.35 + shake, 0.65, 5.3), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=35.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, rgb=(24, 44, 76))
            self._add_3d_composite_hull(
                sc,
                center=(0.15, 0.15, 0.0),
                half_len=1.42 * (1.0 - 0.34 * collapse),
                radius=0.88 * (1.0 - 0.42 * collapse),
                seam_stress=1.0,
                buckling=clamp(0.18 + collapse * 0.82),
            )
            self._add_3d_radial_pressure_ring(sc, (0.15, 0.15, 0.0), 2.55 - 0.65 * collapse, 1.35 - 0.55 * collapse, 12, DANGER, t * 2.0)
            add_crash_test_dummy(sc, pos=(-1.62, -0.95, 0.95), scale=0.76, yaw=0.38, pose="panic_freefall", emotion="shock", t=t)
            ms = min(20.0, prog * 22.0)

            def _ms_badge(d: ImageDraw.ImageDraw) -> None:
                if collapse > 0.4:
                    draw_sparks(d, 555, 960, t, 22, 230, 165, p, seed=131)
                f = load_font(self.font_black, 44)
                label = f"T + {ms:04.1f} MS"
                bb = d.textbbox((0, 0), label, font=f)
                d.rounded_rectangle([365, 1235, 715, 1308], radius=14, fill=p.surface_panel, outline=p.danger, width=4)
                d.text((540 - (bb[2] - bb[0]) / 2, 1246), label, font=f, fill=p.text_highlight)

            overlays_2d.append(_ms_badge)

        elif scene_key == "air_compression_pulse":
            squeeze = ease_out_cubic(prog)
            cam = Camera3D(eye=(shake, 0.55, 5.4), target=(0.0, 0.0, 0.0), fov_deg=41.0, cy_offset=30.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.2, span=7.0, step=1.0, rgb=(24, 44, 76))
            core_r = max(0.32, 1.05 * (1.0 - 0.68 * squeeze))
            sc.add_sphere((0.25, 0.15, 0.0), core_r * 1.45, DANGER, metallic=0.1, emissive=0.75, rim_rgb=AMBER)
            sc.add_sphere((0.25, 0.15, 0.15), core_r * 0.95, AMBER, metallic=0.1, emissive=0.90, rim_rgb=(255, 255, 220))
            sc.add_sphere((0.25, 0.15, 0.28), core_r * 0.52, (255, 252, 225), metallic=0.1, emissive=1.0)
            self._add_3d_radial_pressure_ring(sc, (0.25, 0.15, 0.0), 2.35, core_r + 0.42, 8, CYAN, t * 2.6)
            add_crash_test_dummy(sc, pos=(-1.62, -0.92, 0.92), scale=0.76, yaw=0.35, pose="brace_impact", emotion="shock", t=t)

            def _comp_lbl(d: ImageDraw.ImageDraw) -> None:
                f = load_font(self.font_black, 34)
                lbl = "ADIABATIC COMPRESSION"
                bb = d.textbbox((0, 0), lbl, font=f)
                d.text((540 - (bb[2] - bb[0]) / 2, 1285), lbl, font=f, fill=p.text_highlight, stroke_width=4, stroke_fill=p.ink)

            overlays_2d.append(_comp_lbl)

        elif scene_key == "nerve_bar_comparison":
            cam = Camera3D(eye=(0.4, 0.3, 5.8), target=(0.0, -0.3, 0.0), fov_deg=41.0, cy_offset=110.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.6, span=7.0, step=1.0, rgb=(22, 48, 84))
            add_crash_test_dummy(sc, pos=(-1.55, -0.50, 0.65), scale=0.72, yaw=0.35, pose="point_right", emotion="curious", t=t)

            def _bars(d: ImageDraw.ImageDraw) -> None:
                draw_comparison_bars(
                    d,
                    x0=105,
                    y0=700,
                    width=870,
                    height=370,
                    items=[
                        ("HULL IMPLOSION COLLAPSE", "20 MS", 20.0 / 250.0, p.danger),
                        ("HUMAN VISUAL NERVE SIGNAL", "250 MS", 1.0, p.cyan),
                    ],
                    progress=ease_out_cubic(min(1.0, prog * 1.45)),
                    palette=p,
                    font_path=self.font_black,
                )
                d.rounded_rectangle([245, 1105, 955, 1188], radius=16, fill=p.surface_panel, outline=p.text_highlight, width=4)
                f = load_font(self.font_black, 32)
                msg = "10X FASTER THAN HUMAN SIGHT"
                bb = d.textbbox((0, 0), msg, font=f)
                d.text((600 - (bb[2] - bb[0]) / 2, 1128), msg, font=f, fill=p.text_highlight)

            overlays_2d.append(_bars)

        else:  # verdict_cta_card
            cam = Camera3D(eye=(math.sin(t * 0.9) * 0.45, 0.55, 5.4), target=(0.0, 0.15, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.65, span=7.0, step=1.0, rgb=(20, 50, 82))
            # Certified 3D Titanium Sphere behind UNIT-01
            sc.add_sphere((0.0, 0.45, -1.25), 1.12, STEEL_LIGHT, metallic=0.82, rim_rgb=EMERALD)
            add_crash_test_dummy(sc, pos=(0.0, -0.15, 0.38), scale=1.05, yaw=math.sin(t * 1.8) * 0.12, pose="cta_shrug", emotion="cta", t=t)

            def _cta_buttons(d: ImageDraw.ImageDraw) -> None:
                pulse = 1.0 + 0.04 * math.sin(t * 7.0)
                for label, bx, col in (("YES", 330, p.cyan), ("NO", 750, p.amber)):
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
