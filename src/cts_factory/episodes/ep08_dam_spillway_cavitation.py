"""Episode 08: How Tiny Water Bubbles EAT Solid Concrete — True 3D Mega-Dam Spillway + Cavitation Physics + BOLT."""

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
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes.base import EpisodeScene, register_scene
from cts_factory.episodes.ep02_submersible_implosion_physics import (
    SubmersibleImplosionScene,
    _build_surface_background_bgr,
)

CONCRETE_LIGHT = (176, 184, 194)
CONCRETE_MID = (124, 134, 148)
CONCRETE_DARK = (68, 76, 90)
REBAR_RUST = (196, 108, 56)
STEEL_LIGHT = (190, 206, 226)
STEEL_DARK = (54, 68, 92)
WATER_BRIGHT = (52, 208, 248)
WATER_DEEP = (22, 118, 178)
BUBBLE_ICE = (210, 248, 255)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


@register_scene("ep08_dam_spillway_cavitation")
class DamSpillwayCavitationScene(EpisodeScene):
    """Articulated 12-beat True 3D Mega-Dam Spillway, Cavitation Micro-Jets & BOLT."""

    slug = "ep08_dam_spillway_cavitation"
    episode_id = "ep08"

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
        self._sub_helper = SubmersibleImplosionScene()

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
        self.bg_surface_bgr = _build_surface_background_bgr(w, h, waterline_y=1120)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_mega_dam(
        self,
        sc: Scene3D,
        t: float,
        flood_open: float = 1.0,
        crater_depth: float = 0.0,
        aeration_ramp: bool = False,
    ) -> None:
        """Detailed 3D curved concrete mega-dam wall, gated crest, and steep spillway chute."""
        # Left & right towering concrete abutments
        sc.add_box((-2.25, 0.20, -0.55), (1.35, 3.85, 1.50), CONCRETE_MID, metallic=0.18)
        sc.add_box((2.25, 0.20, -0.55), (1.35, 3.85, 1.50), CONCRETE_MID, metallic=0.18)
        # Upper reservoir dam crest wall + steel floodgates
        sc.add_box((0.0, 1.48, -1.05), (3.60, 1.25, 1.05), CONCRETE_LIGHT, metallic=0.20)
        for gx in (-0.95, 0.0, 0.95):
            gate_y = 1.62 + flood_open * 0.42
            sc.add_box((gx, gate_y, -0.48), (0.76, 0.68, 0.14), STEEL_DARK, metallic=0.72)
            sc.add_box((gx - 0.44, 1.75, -0.50), (0.16, 1.05, 0.42), CONCRETE_LIGHT, metallic=0.22)
        sc.add_box((1.39, 1.75, -0.50), (0.16, 1.05, 0.42), CONCRETE_LIGHT, metallic=0.22)

        # Steep concrete spillway ramp sloping down toward foreground (+Z, -Y)
        for i in range(6):
            st = i / 5.0
            sy = 0.85 - st * 2.55
            sz = -0.35 + st * 2.15
            # If crater_depth > 0, carve out center chunks around i == 3, 4!
            if crater_depth > 0.15 and i in (3, 4):
                sc.add_box((-1.10, sy, sz), (0.85, 0.34, 0.56), CONCRETE_MID, rot=(0.78, 0.0, 0.0), metallic=0.18)
                sc.add_box((1.10, sy, sz), (0.85, 0.34, 0.56), CONCRETE_MID, rot=(0.78, 0.0, 0.0), metallic=0.18)
                # Dark glowing crater cavity + exposed orange rebar bars!
                sc.add_box((0.0, sy - 0.38 * crater_depth, sz - 0.10), (1.32, 0.36, 0.52), (48, 22, 28), rot=(0.78, 0.0, 0.0), emissive=0.45 * crater_depth)
                for rx in (-0.42, 0.0, 0.42):
                    sc.add_cylinder((rx, sy + 0.12, sz - 0.15), (rx + 0.06, sy - 0.35, sz + 0.25), 0.032, 0.032, REBAR_RUST, segments=6, metallic=0.75)
            else:
                sc.add_box((0.0, sy, sz), (2.95, 0.34, 0.56), CONCRETE_LIGHT if i % 2 == 0 else CONCRETE_MID, rot=(0.78, 0.0, 0.0), metallic=0.18)

        # Optional steel aeration ramp + glowing cyan air slot mid-chute!
        if aeration_ramp:
            sc.add_box((0.0, -0.18, 0.65), (2.85, 0.20, 0.46), AMBER, rot=(0.45, 0.0, 0.0), metallic=0.68)
            sc.add_cylinder((-1.42, -0.45, 0.92), (1.42, -0.45, 0.92), 0.10, 0.10, CYAN, segments=10, emissive=0.92, bloom=True)

        # Rushing 100 mph floodwater ribbons cascading down the chute!
        if flood_open > 0.05:
            for lane in range(7):
                lx = -1.05 + lane * 0.35
                for seg in range(4):
                    ph = (t * 2.8 + seg * 0.25 + lane * 0.07) % 1.0
                    y0 = 1.15 - ph * 2.85
                    z0 = -0.25 + ph * 2.25
                    lift = 0.26 * math.sin(clamp((ph - 0.42) * 3.5, 0.0, 1.0) * math.pi) if aeration_ramp else 0.0
                    col = BUBBLE_ICE if (aeration_ramp and ph > 0.45) else (WATER_BRIGHT if (lane + seg) % 2 == 0 else WATER_DEEP)
                    sc.add_cylinder(
                        (lx, y0 + 0.24 + lift, z0 + 0.16),
                        (lx, y0 - 0.16 + lift, z0 + 0.52),
                        0.095,
                        0.085,
                        col,
                        emissive=0.45 if aeration_ramp and ph > 0.45 else 0.22,
                        bloom=aeration_ramp and ph > 0.45,
                        segments=6,
                    )

    def _add_spillway_cutaway_slab(
        self,
        sc: Scene3D,
        t: float,
        bump: bool = True,
        bubbles: bool = True,
        pit_depth: float = 0.0,
        aeration_ramp: bool = False,
        air_cushion: bool = False,
    ) -> None:
        """Side-profile 3D cutaway of concrete spillway floor + 100 mph laminar flow sheet."""
        # Concrete floor slabs along X (-2.4 to +2.4)
        for i in range(8):
            sx = -2.1 + i * 0.60
            # Pit carved at i == 5, 6 when pit_depth > 0
            if pit_depth > 0.08 and i in (5, 6):
                h_slab = max(0.32, 1.05 - pit_depth * 0.68)
                sy = -1.15 - (1.05 - h_slab) * 0.5
                sc.add_box((sx, sy, 0.0), (0.58, h_slab, 1.25), CONCRETE_DARK, metallic=0.15)
                sc.add_box((sx, sy + h_slab * 0.5 + 0.04, 0.0), (0.52, 0.08, 1.10), DANGER, emissive=0.65 * pit_depth, bloom=True)
                # Exposed rebar in pit
                sc.add_cylinder((sx - 0.25, -0.78, 0.35), (sx + 0.25, -0.82, 0.35), 0.032, 0.032, REBAR_RUST, segments=6, metallic=0.75)
            else:
                sc.add_box((sx, -1.15, 0.0), (0.58, 1.05, 1.25), CONCRETE_LIGHT if i % 2 == 0 else CONCRETE_MID, metallic=0.18)

        # Tiny 1-inch concrete surface flaw bump at x = -0.65
        if bump and not aeration_ramp:
            sc.add_box((-0.65, -0.52, 0.0), (0.28, 0.22, 1.18), AMBER, rot=(0.0, 0.0, 0.28), metallic=0.35, emissive=0.25)

        # Intentional steel aeration ramp + air slot at x = -0.65
        if aeration_ramp:
            sc.add_box((-0.72, -0.46, 0.0), (0.72, 0.28, 1.26), AMBER, rot=(0.0, 0.0, 0.36), metallic=0.72)
            sc.add_cylinder((-0.26, -0.68, -0.58), (-0.26, -0.68, 0.62), 0.14, 0.14, CYAN, segments=10, emissive=0.92, bloom=True)

        # 100 mph rushing water stream flying left -> right (+X)
        for row in range(3):
            ry_base = -0.18 + row * 0.26
            for k in range(8):
                ph = (t * 2.5 + k * 0.125 + row * 0.04) % 1.0
                wx = -2.35 + ph * 4.70
                # Water lifts cleanly off bump or aeration ramp!
                lift = 0.0
                if aeration_ramp and wx > -0.70:
                    d_ramp = clamp((wx + 0.70) / 2.6, 0.0, 1.0)
                    lift = math.sin(d_ramp * math.pi) * 0.65
                elif bump and wx > -0.65:
                    d_bump = clamp((wx + 0.65) / 1.45, 0.0, 1.0)
                    lift = math.sin(d_bump * math.pi) * 0.28
                col = WATER_BRIGHT if row == 2 else WATER_DEEP
                sc.add_cylinder((wx - 0.20, ry_base + lift, -0.10 + row * 0.15), (wx + 0.20, ry_base + lift, -0.10 + row * 0.15), 0.085, 0.085, col, emissive=0.25, segments=6)

        # Cavitation vapor bubbles forming in low-pressure wake behind bump
        if bubbles and not air_cushion:
            for bi in range(11):
                ph = (t * 2.0 + bi * 0.09) % 1.0
                bx = -0.45 + ph * 2.25
                by = -0.46 + math.sin(ph * math.pi) * 0.26 + (bi % 3 - 1) * 0.07
                bz = ((bi % 4) - 1.5) * 0.22
                # Shrink violently into glowing red/amber implosion at ph > 0.78!
                if ph > 0.78:
                    br = 0.045 + (1.0 - ph) * 0.35
                    sc.add_sphere((bx, -0.58, bz), br, DANGER, emissive=0.95, bloom=True)
                else:
                    br = 0.07 + 0.08 * math.sin(ph * math.pi)
                    sc.add_sphere((bx, by, bz), br, BUBBLE_ICE, emissive=0.75, bloom=True, rim_rgb=CYAN)

        # Protective entrained air cushion underneath the lifted water sheet!
        if air_cushion:
            for ai in range(14):
                ph = (t * 2.2 + ai * 0.075) % 1.0
                ax = -0.25 + ph * 2.45
                ay = -0.52 + (ai % 3) * 0.11 + math.sin(t * 7.0 + ai) * 0.04
                az = ((ai % 4) - 1.5) * 0.24
                sc.add_sphere((ax, ay, az), 0.105, CYAN, emissive=0.88, bloom=True)

    def _render_scene_3d(
        self,
        scene_key: str,
        t: float,
        prog: float,
        rms: float,
    ) -> tuple[np.ndarray, list]:
        assert self.brand is not None and self.palette is not None
        p = self.palette
        w, h = self.brand.video_spec.width, self.brand.video_spec.height
        overlays_2d: list = []

        bg = self.bg_ocean_bgr
        if scene_key in ("dam_cavitation_hero", "micro_bubble_implode", "microjet_100k_psi", "four_story_crater"):
            bg = self.bg_alert_bgr
        elif scene_key in ("aeration_ramp_cutaway", "air_cushion_shield", "cavitation_bars"):
            bg = self.bg_safe_bgr
        elif scene_key == "verdict_cta_card":
            bg = self.bg_surface_bgr
        assert bg is not None

        cam = Camera3D(eye=(0.0, 0.9, 7.6), target=(0.0, -0.1, 0.0), fov_deg=41.0, width=w, height=h)
        sc = Scene3D(cam)

        if scene_key == "dam_cavitation_hero":
            cam.eye = (1.1, 1.05, 7.1)
            cam.target = (0.0, -0.15, 0.35)
            self._add_3d_mega_dam(sc, t=t, flood_open=1.0, crater_depth=0.45 + 0.55 * ease_out_cubic(prog))
            if prog > 0.35:
                overlays_2d.append(lambda d: draw_sparks(d, 540, 1080, prog, 16, 160, 140, p, seed=801))

        elif scene_key == "bolt_dam_wave_intro":
            # Narrator: "Hey Bolt, give us a wave before we open the floodgates!"
            cam.eye = (0.25, 1.45, 6.8)
            cam.target = (0.0, 0.35, 0.0)
            self._add_3d_mega_dam(sc, t=t, flood_open=0.15 + 0.35 * prog, crater_depth=0.0)
            # BOLT standing prominently on the sunlit concrete dam crest WAVING right at the camera!
            add_crash_test_dummy(
                sc,
                pos=(0.0, 2.28, -0.18),
                scale=0.95,
                yaw=0.05 + math.sin(t * 2.5) * 0.10,
                pose="relief_wave",
                emotion="cta",
                t=t,
            )

            def _wave_arc(d: ImageDraw.ImageDraw) -> None:
                pulse = (t * 2.2) % 1.0
                r = int(26 + pulse * 42)
                cx, cy = 645, 250
                d.arc([cx - r, cy - r, cx + r, cy + r], start=-55, end=25, fill=p.cyan, width=4)

            overlays_2d.append(_wave_arc)

        elif scene_key == "spillway_bump_flow":
            cam.eye = (0.0, 0.45, 6.3)
            cam.target = (0.0, -0.35, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=True, bubbles=False)
            # Arrow highlight pointing right at the tiny 1-inch bump
            sc.add_cylinder((-0.65, 0.72, 0.35), (-0.65, -0.22, 0.35), 0.05, 0.02, AMBER, segments=8, emissive=0.90, bloom=True)

        elif scene_key == "cold_water_boils":
            cam.eye = (0.35, 0.38, 5.7)
            cam.target = (0.15, -0.40, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=True, bubbles=True)
            overlays_2d.append(lambda d: draw_pressure_gauge(d, 165, 1140, 96, 0.08, "LOCAL PRESSURE", "VAPOR BOIL", p, self.font_black))

        elif scene_key == "micro_bubble_implode":
            # Macro 3D closeup of one giant vapor bubble collapsing asymmetrically!
            shake = math.sin(t * 50.0) * 0.10 if prog > 0.65 else 0.0
            cam.eye = (0.0 + shake, 0.35, 5.4)
            cam.target = (0.0, -0.15, 0.0)
            # Concrete floor beneath bubble
            sc.add_box((0.0, -1.45, 0.0), (4.6, 0.95, 1.8), CONCRETE_MID, metallic=0.18)
            col_p = ease_in_out_cubic(prog)
            # Outer high-pressure inward arrows crushing the bubble
            r_bub = max(0.28, 1.18 * (1.0 - col_p * 0.72))
            bub_col = lerp_color(BUBBLE_ICE, DANGER, clamp((col_p - 0.45) * 2.0, 0.0, 1.0))
            sc.add_sphere((0.0, 0.05 - col_p * 0.42, 0.0), r_bub, bub_col, metallic=0.25, emissive=0.72 + col_p * 0.25, bloom=True, rim_rgb=CYAN)
            for ang in np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False):
                dist = r_bub + 0.95 * (1.0 - col_p * 0.55)
                sc.add_cylinder(
                    (math.cos(ang) * dist, 0.05 + math.sin(ang) * dist, 0.0),
                    (math.cos(ang) * (r_bub + 0.18), 0.05 + math.sin(ang) * (r_bub + 0.18), 0.0),
                    0.055,
                    0.018,
                    AMBER,
                    segments=6,
                    emissive=0.88,
                    bloom=True,
                )
            if prog > 0.62:
                overlays_2d.append(lambda d: draw_sparks(d, 540, 1020, (prog - 0.62) / 0.38, 22, 180, 150, p, seed=805))

        elif scene_key == "microjet_100k_psi":
            shake = math.sin(t * 54.0) * 0.13
            cam.eye = (0.0 + shake, 0.35, 5.5)
            cam.target = (0.0, -0.25, 0.0)
            sc.add_box((-1.35, -1.35, 0.0), (2.1, 1.10, 1.6), CONCRETE_MID, metallic=0.18)
            sc.add_box((1.35, -1.35, 0.0), (2.1, 1.10, 1.6), CONCRETE_MID, metallic=0.18)
            sc.add_box((0.0, -1.62, 0.0), (0.85, 0.60, 1.4), CONCRETE_DARK, metallic=0.15)
            # Blazing needle-thin 100,000 PSI micro-jet piercing downward straight into concrete!
            jet_p = ease_out_cubic(clamp(prog * 1.4, 0.0, 1.0))
            sc.add_sphere((0.0, 0.65, 0.0), 0.58, BUBBLE_ICE, emissive=0.80, bloom=True, rim_rgb=CYAN)
            sc.add_cylinder((0.0, 0.72, 0.0), (0.0, 0.72 - jet_p * 1.98, 0.0), 0.15, 0.045, DANGER, segments=10, emissive=0.98, bloom=True)
            sc.add_cylinder((0.0, 0.72, 0.0), (0.0, 0.72 - jet_p * 1.98, 0.0), 0.065, 0.022, (255, 245, 195), segments=8, emissive=1.0, bloom=True)
            overlays_2d.append(lambda d, jp=jet_p: draw_sparks(d, 540, 1140, jp, 24, 190, 150, p, seed=806))
            overlays_2d.append(lambda d, jp=jet_p: draw_pressure_gauge(d, 895, 1140, 96, 0.25 + 0.75 * jp, "JET SPIKE", f"{int(25 + jp * 75)}K PSI", p, self.font_black))

        elif scene_key == "concrete_pit_snowball":
            # Narrator: "Watch out, Bolt!" -> BOLT reacts on the catwalk as pitting escalates!
            cam.eye = (0.0, 0.55, 6.8)
            cam.target = (0.0, -0.25, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=True, bubbles=True, pit_depth=0.25 + 0.75 * ease_out_cubic(prog))
            add_crash_test_dummy(sc, pos=(-1.68, -0.05, 0.65), scale=0.85, yaw=0.35, pose="brace_impact", emotion="panic", t=t)

        elif scene_key == "four_story_crater":
            shake = math.sin(t * 42.0) * 0.09
            cam.eye = (0.85 + shake, 0.72, 6.2)
            cam.target = (0.0, -0.45, 0.65)
            self._add_3d_mega_dam(sc, t=t, flood_open=1.0, crater_depth=1.0)
            overlays_2d.append(lambda d: draw_sparks(d, 540, 1080, prog, 18, 170, 140, p, seed=808))

        elif scene_key == "aeration_ramp_cutaway":
            cam.eye = (0.0, 0.42, 6.3)
            cam.target = (0.0, -0.35, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=False, bubbles=False, aeration_ramp=True, air_cushion=False)
            add_crash_test_dummy(sc, pos=(-1.72, -0.05, 0.65), scale=0.82, yaw=0.36, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "air_cushion_shield":
            # Narrator: "Nice move, Bolt!" -> BOLT celebrates as glowing cyan air cushion shields the concrete!
            cam.eye = (0.0, 0.48, 6.5)
            cam.target = (0.0, -0.30, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=False, bubbles=False, aeration_ramp=True, air_cushion=True)
            add_crash_test_dummy(sc, pos=(-1.68, -0.02, 0.68), scale=0.88, yaw=0.28, pose="relief_wave", emotion="relief", t=t)

        elif scene_key == "cavitation_bars":
            cam.eye = (0.0, 0.85, 7.6)
            cam.target = (0.0, 0.15, 0.0)
            self._add_3d_mega_dam(sc, t=t, flood_open=1.0, crater_depth=0.0, aeration_ramp=True)
            bar_p = ease_out_cubic(clamp(prog * 1.4, 0.0, 1.0))
            overlays_2d.append(
                lambda d, bp=bar_p: draw_comparison_bars(
                    d,
                    115,
                    1095,
                    850,
                    250,
                    [
                        ("0% AIR (RAW FLOW)", "40-FT CRATER", 0.96, p.danger),
                        ("8% AIR CUSHION", "0% EROSION", 0.08, p.emerald),
                    ],
                    bp,
                    p,
                    self.font_black,
                )
            )

        else:  # verdict_cta_card — Calm sunlit surface basin finale with BOLT's Yellow Submarine!
            cam.eye = (0.0, 0.72, 7.2)
            cam.target = (0.0, 0.12, 0.0)
            bob = math.sin(t * 3.1) * 0.07
            self._sub_helper._add_3d_yellow_submarine(
                sc,
                center=(0.0, -0.45 + bob, 0.15),
                scale=1.05,
                yaw=-0.18,
                pitch=math.sin(t * 2.5) * 0.04,
                t=t,
                prop_speed=10.0,
                with_pilot=False,
                headlights=True,
                bubbles=False,
            )
            add_crash_test_dummy(
                sc,
                pos=(0.0, 0.56 + bob, 0.35),
                scale=0.86,
                yaw=math.sin(t * 2.2) * 0.14,
                pose="cta_shrug",
                emotion="cta",
                t=t,
                ground_shadow=False,
            )

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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "dam_cavitation_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("microjet_100k_psi", t=0.45, prog=0.72, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
