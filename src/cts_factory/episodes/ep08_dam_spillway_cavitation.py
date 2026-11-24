"""Episode 08: How Tiny Water Bubbles EAT Solid Concrete — Upgraded True 3D Concrete Mega-Dam, Fluid Sheet & Cavitation."""

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
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes.base import EpisodeScene, register_scene

CONCRETE_LIGHT = (176, 182, 188)
CONCRETE_MID = (128, 134, 142)
CONCRETE_DARK = (74, 80, 88)
REBAR_RUST = (196, 108, 56)
STEEL_LIGHT = (190, 206, 226)
STEEL_DARK = (54, 68, 92)
WATER_BRIGHT = (52, 208, 248)
WATER_DEEP = (24, 128, 192)
BUBBLE_ICE = (176, 238, 255)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


def _build_dam_valley_sky_bgr(w: int, h: int) -> np.ndarray:
    """Smooth twilight mountain-canyon backdrop behind the protected dam spillway (BGR)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    img = np.zeros((h, w, 3), dtype=np.float32)

    img[:, :, 2] = 10.0 + 36.0 * (ys ** 1.8)
    img[:, :, 1] = 24.0 + 76.0 * (ys ** 1.4) * (1.0 - 0.45 * ys)
    img[:, :, 0] = 54.0 + 98.0 * (ys ** 1.2) * (1.0 - 0.35 * ys)

    glow = np.exp(-((xs / 0.65) ** 2 + ((ys - 0.52) / 0.20) ** 2))
    img[:, :, 2] += 36.0 * glow
    img[:, :, 1] += 54.0 * glow
    img[:, :, 0] += 52.0 * glow
    return np.clip(img, 0, 255).astype(np.uint8)


@register_scene("ep08_dam_spillway_cavitation")
class DamSpillwayCavitationScene(EpisodeScene):
    """Articulated 12-beat True 3D Concrete Mega-Dam Spillway, Cavitation Micro-Jets & BOLT."""

    slug = "ep08_dam_spillway_cavitation"
    episode_id = "ep08"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_ocean_bgr: np.ndarray | None = None
        self.bg_alert_bgr: np.ndarray | None = None
        self.bg_safe_bgr: np.ndarray | None = None
        self.bg_valley_bgr: np.ndarray | None = None
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
        self.bg_valley_bgr = _build_dam_valley_sky_bgr(w, h)
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
        """Detailed 3D matte-concrete mega-dam wall, reservoir, gated crest, continuous chute & stilling basin."""
        # Upper turquoise reservoir water behind the dam crest
        sc.add_box((0.0, 1.55, -1.95), (6.8, 0.95, 1.35), WATER_DEEP, metallic=0.15, texture="matte")
        # Concrete canyon abutments + stilling basin floor so dam is grounded (never floating in void!)
        sc.add_box((-2.25, -0.10, -0.55), (1.45, 4.40, 1.85), CONCRETE_MID, metallic=0.10, texture="concrete")
        sc.add_box((2.25, -0.10, -0.55), (1.45, 4.40, 1.85), CONCRETE_MID, metallic=0.10, texture="concrete")
        sc.add_box((0.0, -2.10, 1.55), (6.2, 0.55, 2.40), CONCRETE_DARK, metallic=0.10, texture="concrete")
        sc.add_box((0.0, -1.78, 1.85), (4.8, 0.14, 1.80), WATER_DEEP, metallic=0.18, alpha=0.82, texture="matte")

        # Upper concrete crest + walkway + 3 steel radial floodgates
        sc.add_box((0.0, 1.48, -1.05), (3.60, 1.25, 1.05), CONCRETE_LIGHT, metallic=0.10, texture="concrete")
        for gx in (-0.95, 0.0, 0.95):
            gate_y = 1.48 + flood_open * 0.52
            sc.add_box((gx, gate_y, -0.48), (0.76, 0.72, 0.14), STEEL_DARK, metallic=0.72, texture="brushed_steel")
            sc.add_box((gx - 0.44, 1.72, -0.50), (0.16, 1.08, 0.42), CONCRETE_LIGHT, metallic=0.10, texture="concrete")
        sc.add_box((1.39, 1.72, -0.50), (0.16, 1.08, 0.42), CONCRETE_LIGHT, metallic=0.10, texture="concrete")

        # Continuous sloping concrete spillway chute (overlapping bevel-free concrete slabs, zero stair gaps!)
        for i in range(6):
            st = i / 5.0
            sy = 0.85 - st * 2.55
            sz = -0.35 + st * 2.15
            if crater_depth > 0.15 and i in (3, 4):
                sc.add_box((-1.10, sy, sz), (0.90, 0.42, 0.68), CONCRETE_MID, rot=(0.78, 0.0, 0.0), metallic=0.10, texture="concrete")
                sc.add_box((1.10, sy, sz), (0.90, 0.42, 0.68), CONCRETE_MID, rot=(0.78, 0.0, 0.0), metallic=0.10, texture="concrete")
                sc.add_box((0.0, sy - 0.42 * crater_depth, sz - 0.10), (1.35, 0.36, 0.64), (44, 24, 28), rot=(0.78, 0.0, 0.0), metallic=0.08, texture="concrete")
                for rx in (-0.42, -0.14, 0.14, 0.42):
                    sc.add_cylinder((rx, sy + 0.10, sz - 0.15), (rx + 0.04, sy - 0.36, sz + 0.28), 0.028, 0.028, REBAR_RUST, segments=6, metallic=0.72)
            else:
                sc.add_box((0.0, sy, sz), (2.96, 0.42, 0.72), CONCRETE_LIGHT if i % 2 == 0 else CONCRETE_MID, rot=(0.78, 0.0, 0.0), metallic=0.10, texture="concrete")

        # Steel aeration ramp + glowing cyan air slot mid-chute
        if aeration_ramp:
            sc.add_box((0.0, -0.14, 0.65), (2.86, 0.18, 0.46), AMBER, rot=(0.45, 0.0, 0.0), metallic=0.68, texture="brushed_steel")
            sc.add_cylinder((-1.40, -0.40, 0.90), (1.40, -0.40, 0.90), 0.085, 0.085, CYAN, segments=10, emissive=0.68, bloom=True)

        # Continuous smooth translucent water sheet + animated white-foam flow streaks (NOT Lego sticks!)
        if flood_open > 0.08:
            sheet_q = np.array(
                [
                    [-1.38, 1.18, 0.04],
                    [1.38, 1.18, 0.04],
                    [1.38, -1.62, 2.34],
                    [-1.38, -1.62, 2.34],
                ],
                dtype=np.float32,
            )
            sc.add_quad(sheet_q, rgb=WATER_DEEP, metallic=0.20, double_sided=True, alpha=0.62 * clamp(flood_open, 0.25, 1.0))
            for lane in range(7):
                lx = -1.12 + lane * 0.37
                for seg in range(3):
                    ph = (t * 2.4 + seg * 0.33 + lane * 0.09) % 1.0
                    y0 = 1.06 - ph * 2.55
                    z0 = -0.14 + ph * 2.04
                    lift = 0.20 * math.sin(clamp((ph - 0.42) * 3.2, 0.0, 1.0) * math.pi) if aeration_ramp else 0.0
                    col = BUBBLE_ICE if (aeration_ramp and ph > 0.44) else WATER_BRIGHT
                    sc.add_cylinder(
                        (lx, y0 + 0.18 + lift, z0 + 0.08),
                        (lx, y0 - 0.28 + lift, z0 + 0.46),
                        0.042,
                        0.022,
                        col,
                        emissive=0.32 if aeration_ramp and ph > 0.44 else 0.18,
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
        with_catwalk: bool = False,
    ) -> None:
        """Side-profile 3D cutaway of porous matte-concrete floor + continuous rushing water sheet."""
        # Matte concrete floor slabs along X (-2.4 to +2.4)
        for i in range(8):
            sx = -2.1 + i * 0.60
            if pit_depth > 0.08 and i in (5, 6):
                h_slab = max(0.32, 1.05 - pit_depth * 0.68)
                sy = -1.15 - (1.05 - h_slab) * 0.5
                sc.add_box((sx, sy, 0.0), (0.60, h_slab, 1.25), CONCRETE_DARK, metallic=0.08, texture="concrete")
                sc.add_box((sx, sy + h_slab * 0.5 + 0.03, 0.0), (0.56, 0.07, 1.15), DANGER, emissive=0.45 * pit_depth, texture="matte")
                # Anchored exposed rebar spanning across the pit walls
                sc.add_cylinder((sx - 0.32, -0.78, 0.28), (sx + 0.32, -0.82, 0.28), 0.028, 0.028, REBAR_RUST, segments=6, metallic=0.72)
            else:
                sc.add_box((sx, -1.15, 0.0), (0.60, 1.05, 1.25), CONCRETE_LIGHT if i % 2 == 0 else CONCRETE_MID, metallic=0.10, texture="concrete")

        # Steel inspection catwalk platform on the left so BOLT stands on real solid flooring!
        if with_catwalk:
            sc.add_box((-1.78, -0.58, 0.92), (1.05, 0.12, 0.62), STEEL_DARK, metallic=0.68, texture="brushed_steel")
            sc.add_cylinder((-2.25, -0.52, 1.18), (-1.30, -0.52, 1.18), 0.026, 0.026, AMBER, segments=6, metallic=0.65)
            sc.add_cylinder((-2.25, -0.58, 1.18), (-2.25, -0.18, 1.18), 0.024, 0.024, STEEL_LIGHT, segments=6, metallic=0.72)
            sc.add_cylinder((-1.30, -0.58, 1.18), (-1.30, -0.18, 1.18), 0.024, 0.024, STEEL_LIGHT, segments=6, metallic=0.72)

        # Tiny 1-inch concrete surface flaw bump at x = -0.55
        if bump and not aeration_ramp:
            sc.add_box((-0.55, -0.58, 0.0), (0.20, 0.11, 1.20), AMBER, rot=(0.0, 0.0, 0.22), metallic=0.25, texture="concrete")

        # Angled steel aeration ramp + recessed vertical air intake duct beneath the ramp!
        if aeration_ramp:
            sc.add_box((-0.68, -0.46, 0.0), (0.76, 0.24, 1.26), AMBER, rot=(0.0, 0.0, 0.34), metallic=0.70, texture="brushed_steel")
            sc.add_box((-0.24, -0.92, 0.0), (0.24, 0.62, 1.18), (18, 34, 52), metallic=0.15, texture="matte")
            sc.add_cylinder((-0.24, -0.62, -0.52), (-0.24, -0.62, 0.56), 0.095, 0.095, CYAN, segments=10, emissive=0.68, bloom=True)

        # Continuous curved translucent water stream sheet flying left -> right (+X)
        xs = np.linspace(-2.35, 2.35, 16)
        for i in range(len(xs) - 1):
            x0, x1 = float(xs[i]), float(xs[i + 1])

            def _lift(x: float) -> float:
                if aeration_ramp and x > -0.68:
                    d_r = clamp((x + 0.68) / 2.65, 0.0, 1.0)
                    return math.sin(d_r * math.pi) * 0.52
                if bump and x > -0.55:
                    d_b = clamp((x + 0.55) / 1.45, 0.0, 1.0)
                    return math.sin(d_b * math.pi) * 0.22
                return 0.0

            l0, l1 = _lift(x0), _lift(x1)
            q_front = np.array(
                [
                    [x0, -0.58 + l0, 0.58],
                    [x1, -0.58 + l1, 0.58],
                    [x1, 0.16 + l1, 0.58],
                    [x0, 0.16 + l0, 0.58],
                ],
                dtype=np.float32,
            )
            sc.add_quad(q_front, rgb=WATER_DEEP, metallic=0.18, double_sided=True, alpha=0.66)
            # Crisp dynamic surface foam streamline on top
            phase_off = math.sin(t * 9.0 + i * 0.9) * 0.03
            sc.add_cylinder((x0, 0.14 + l0 + phase_off, 0.52), (x1, 0.14 + l1 - phase_off, 0.52), 0.042, 0.042, WATER_BRIGHT, segments=6, emissive=0.22)

        # Cavitation vapor bubbles forming cleanly in low-pressure wake behind bump (controlled glow, zero whiteout!)
        if bubbles and not air_cushion:
            for bi in range(10):
                ph = (t * 2.0 + bi * 0.10) % 1.0
                bx = -0.38 + ph * 2.15
                by = -0.48 + math.sin(ph * math.pi) * 0.20 + (bi % 3 - 1) * 0.05
                bz = 0.62
                if ph > 0.78:
                    br = 0.04 + (1.0 - ph) * 0.26
                    sc.add_sphere((bx, -0.58, bz), br, DANGER, emissive=0.68, bloom=True)
                else:
                    br = 0.058 + 0.048 * math.sin(ph * math.pi)
                    sc.add_sphere((bx, by, bz), br, BUBBLE_ICE, metallic=0.18, emissive=0.28, rim_rgb=CYAN)

        # Protective entrained cyan air cushion nestled tightly directly beneath the lifted water sheet!
        if air_cushion:
            for ai in range(14):
                ph = (t * 2.1 + ai * 0.072) % 1.0
                ax = -0.18 + ph * 2.35
                d_r = clamp((ax + 0.68) / 2.65, 0.0, 1.0)
                ay = -0.54 + (ai % 2) * 0.14 + math.sin(d_r * math.pi) * 0.22
                sc.add_sphere((ax, ay, 0.64), 0.078, CYAN, metallic=0.18, emissive=0.45, rim_rgb=BUBBLE_ICE)

    def _render_scene_3d(
        self,
        scene_key: str,
        t: float,
        prog: float,
        rms: float,
        is_cover: bool = False,
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
            bg = self.bg_valley_bgr
        assert bg is not None

        cam = Camera3D(eye=(0.0, 0.9, 7.6), target=(0.0, -0.1, 0.0), fov_deg=41.0, width=w, height=h)
        sc = Scene3D(cam)

        if scene_key == "dam_cavitation_hero":
            cam.eye = (1.1, 1.05, 7.3)
            cam.target = (0.0, -0.15, 0.35)
            self._add_3d_mega_dam(sc, t=t, flood_open=1.0, crater_depth=0.45 + 0.55 * ease_out_cubic(prog))
            if prog > 0.35:
                overlays_2d.append(lambda d: draw_sparks(d, 540, 1080, prog, 16, 150, 130, p, seed=801))

        elif scene_key == "bolt_dam_wave_intro":
            # Narrator: "Hey Bolt, give us a wave before we open the floodgates!"
            # Phase 1 (prog < 0.42): Gates CLOSED, BOLT waves cheerfully on the crest!
            # Phase 2 (prog >= 0.42): Floodgates LIFT OPEN -> water rushes out -> BOLT slips & slides all the way down the dam spillway!
            gate_open = ease_out_cubic(clamp((prog - 0.40) / 0.24, 0.0, 1.0))
            slide = clamp((prog - 0.48) / 0.52, 0.0, 1.0)
            slide_eased = slide ** 1.35  # Accelerating gravity slide down the flooded chute!
            cam.eye = (0.28, 1.48 - slide_eased * 0.45, 7.25)
            cam.target = (0.0, 0.48 - slide_eased * 0.92, 0.15 + slide_eased * 0.45)
            self._add_3d_mega_dam(sc, t=t, flood_open=gate_open, crater_depth=0.0)

            if prog < 0.44:
                # Standing safely on the dry crest lip right in front of the closed center floodgate, waving!
                add_crash_test_dummy(
                    sc,
                    pos=(0.0, 1.98, -0.16),
                    scale=0.68,
                    yaw=0.05 + math.sin(t * 2.5) * 0.10,
                    pose="relief_wave",
                    emotion="cta",
                    t=t,
                )
            else:
                # Swept off balance and sliding hilariously down the 45° flooded concrete chute!
                bx = math.sin(slide_eased * 9.5) * 0.22 * (1.0 - 0.25 * slide_eased)
                # Follows the chute surface from (y=1.42, z=0.02) smoothly down to (y=-1.28, z=2.16)
                by = 1.98 - (slide_eased ** 0.95) * 3.18 + math.sin(clamp(slide * 3.2, 0.0, 1.0) * math.pi) * 0.22
                bz = -0.16 + slide_eased * 2.32
                add_crash_test_dummy(
                    sc,
                    pos=(bx, by, bz),
                    scale=0.68,
                    yaw=math.sin(t * 14.0) * 0.28,
                    tilt_z=math.sin(t * 11.0) * 0.34,
                    pose="panic_freefall",
                    emotion="panic" if slide > 0.12 else "shock",
                    t=t,
                    ground_shadow=False,
                )
                # Animated splash-foam spray kicking up around BOLT as he surfs/slides down the chute!
                for si in range(7):
                    sp_ph = (t * 4.2 + si * 0.145) % 1.0
                    sx = bx + ((si % 3) - 1) * (0.28 + sp_ph * 0.32)
                    sy = by - 0.45 + sp_ph * 0.52 - 0.18 * (sp_ph ** 2)
                    sz = bz + 0.18 + sp_ph * 0.25
                    sc.add_sphere((sx, sy, sz), 0.075 * (1.0 - sp_ph * 0.45), BUBBLE_ICE, emissive=0.35, rim_rgb=CYAN)

        elif scene_key == "spillway_bump_flow":
            cam.eye = (0.0, 0.45, 6.4)
            cam.target = (0.0, -0.35, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=True, bubbles=False)
            sc.add_arrow_3d((-0.55, 0.85, 0.65), (-0.55, -0.32, 0.65), AMBER, shaft_r=0.05, head_r=0.14)

        elif scene_key == "cold_water_boils":
            cam.eye = (0.35, 0.40, 6.2)
            cam.target = (0.10, -0.25, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=True, bubbles=True)
            overlays_2d.append(lambda d: draw_pressure_gauge(d, 165, 1205, 86, 0.08, "PRESSURE", "VAPOR BOIL", p, self.font_black))

        elif scene_key == "micro_bubble_implode":
            shake = math.sin(t * 50.0) * 0.08 if prog > 0.65 else 0.0
            cam.eye = (0.0 + shake, 0.38, 5.7)
            cam.target = (0.0, -0.15, 0.0)
            sc.add_box((0.0, -1.48, 0.0), (4.8, 0.95, 1.8), CONCRETE_MID, metallic=0.08, texture="concrete")
            col_p = ease_in_out_cubic(prog)
            r_bub = max(0.32, 1.12 * (1.0 - col_p * 0.68))
            bub_col = lerp_color(BUBBLE_ICE, CYAN, clamp(col_p, 0.0, 1.0))
            sc.add_sphere((0.0, 0.12 - col_p * 0.35, 0.0), r_bub, bub_col, metallic=0.22, emissive=0.25 + col_p * 0.18, rim_rgb=CYAN)
            for ang in np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False):
                # Skip bottom arrow so it never clips into the concrete floor!
                if math.sin(ang) < -0.75:
                    continue
                dist = r_bub + 0.88 * (1.0 - col_p * 0.50)
                sc.add_arrow_3d(
                    (math.cos(ang) * dist, 0.12 + math.sin(ang) * dist, 0.0),
                    (math.cos(ang) * (r_bub + 0.16), 0.12 + math.sin(ang) * (r_bub + 0.16), 0.0),
                    AMBER,
                    shaft_r=0.042,
                    head_r=0.11,
                )
            if prog > 0.62:
                overlays_2d.append(lambda d: draw_sparks(d, 540, 1040, (prog - 0.62) / 0.38, 18, 155, 130, p, seed=805))

        elif scene_key == "microjet_100k_psi":
            shake = math.sin(t * 54.0) * 0.09 if not is_cover else 0.0
            cam.eye = (0.0 + shake, 0.38, 6.2 if is_cover else 5.8)
            cam.target = (0.0, 0.05 if is_cover else -0.22, 0.0)
            # Cracked porous concrete blocks with ragged chipped crater center (matte concrete, NOT steel!)
            sc.add_box((-1.38, -1.35, 0.0), (2.05, 1.10, 1.6), CONCRETE_MID, metallic=0.08, texture="concrete")
            sc.add_box((1.38, -1.35, 0.0), (2.05, 1.10, 1.6), CONCRETE_MID, metallic=0.08, texture="concrete")
            sc.add_box((0.0, -1.62, 0.0), (0.92, 0.60, 1.45), CONCRETE_DARK, metallic=0.08, texture="concrete")
            # Chipped concrete debris flying upward from crater
            for ci, (cx_d, cy_d) in enumerate(((-0.42, -0.72), (0.45, -0.68), (-0.28, -0.52), (0.34, -0.55))):
                sc.add_box((cx_d, cy_d, 0.25), (0.16, 0.12, 0.14), CONCRETE_LIGHT, rot=(0.4 * ci, 0.6 * ci, 0.3), metallic=0.08, texture="concrete")
            # Realistic translucent blue-ice collapsing cavitation bubble + pressurized cyan-white water micro-jet!
            jet_p = ease_out_cubic(clamp(prog * 1.4, 0.0, 1.0)) if not is_cover else 0.92
            sc.add_sphere((0.0, 0.65, 0.0), 0.60, BUBBLE_ICE, metallic=0.22, emissive=0.28, rim_rgb=CYAN)
            sc.add_cylinder((0.0, 0.62, 0.0), (0.0, 0.62 - jet_p * 1.90, 0.0), 0.14, 0.042, WATER_BRIGHT, segments=12, emissive=0.72, bloom=True)
            sc.add_cylinder((0.0, 0.62, 0.0), (0.0, 0.62 - jet_p * 1.90, 0.0), 0.055, 0.018, (235, 250, 255), segments=8, emissive=0.88, bloom=True)
            if not is_cover:
                overlays_2d.append(lambda d, jp=jet_p: draw_sparks(d, 540, 1140, jp, 18, 160, 130, p, seed=806))
                overlays_2d.append(
                    lambda d, jp=jet_p: draw_pressure_gauge(d, 745, 1190, 86, 0.95, "JET SPIKE", "100K+ PSI", p, self.font_black)
                )

        elif scene_key == "concrete_pit_snowball":
            # Narrator: "Watch out, Bolt!" -> BOLT grounded firmly on steel inspection catwalk!
            cam.eye = (0.0, 0.55, 7.0)
            cam.target = (0.0, -0.25, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=True, bubbles=True, pit_depth=0.25 + 0.75 * ease_out_cubic(prog), with_catwalk=True)
            add_crash_test_dummy(sc, pos=(-1.78, 0.30, 0.92), scale=0.68, yaw=0.36, pose="brace_impact", emotion="panic", t=t)

        elif scene_key == "four_story_crater":
            shake = math.sin(t * 42.0) * 0.07
            cam.eye = (0.85 + shake, 0.72, 6.5)
            cam.target = (0.0, -0.45, 0.65)
            self._add_3d_mega_dam(sc, t=t, flood_open=1.0, crater_depth=1.0)
            overlays_2d.append(lambda d: draw_sparks(d, 540, 1080, prog, 16, 155, 130, p, seed=808))

        elif scene_key == "aeration_ramp_cutaway":
            cam.eye = (0.0, 0.45, 6.7)
            cam.target = (0.0, -0.30, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=False, bubbles=False, aeration_ramp=True, air_cushion=False, with_catwalk=True)
            add_crash_test_dummy(sc, pos=(-1.78, 0.30, 0.92), scale=0.68, yaw=0.36, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "air_cushion_shield":
            # Narrator: "Nice move, Bolt!" -> BOLT celebrates on the steel catwalk as cyan air cushion shields concrete!
            cam.eye = (0.0, 0.50, 6.8)
            cam.target = (0.0, -0.28, 0.0)
            self._add_spillway_cutaway_slab(sc, t=t, bump=False, bubbles=False, aeration_ramp=True, air_cushion=True, with_catwalk=True)
            add_crash_test_dummy(sc, pos=(-1.78, 0.30, 0.92), scale=0.70, yaw=0.28, pose="relief_wave", emotion="relief", t=t)

        elif scene_key == "cavitation_bars":
            # Frame dam higher up so the comparison bars sit cleanly BELOW the aeration zone (zero occlusion!)
            cam.eye = (0.0, 0.95, 8.2)
            cam.target = (0.0, -0.75, 0.0)
            self._add_3d_mega_dam(sc, t=t, flood_open=1.0, crater_depth=0.0, aeration_ramp=True)
            bar_p = ease_out_cubic(clamp(prog * 1.4, 0.0, 1.0))
            overlays_2d.append(
                lambda d, bp=bar_p: draw_comparison_bars(
                    d,
                    82,
                    1115,
                    774,
                    225,
                    [
                        ("0% AIR (RAW FLOW)", "40-FT CRATER", 0.96, p.danger),
                        ("8% AIR CUSHION", "0% EROSION", 0.0, p.emerald),
                    ],
                    bp,
                    p,
                    self.font_black,
                )
            )

        else:  # verdict_cta_card — Grounded observation deck directly below the protected mega-dam spillway!
            cam.eye = (0.0, 0.55, 7.6)
            cam.target = (0.0, -0.25, 0.0)
            self._add_3d_mega_dam(sc, t=t, flood_open=1.0, crater_depth=0.0, aeration_ramp=True)
            # Foreground dry concrete observation balcony where BOLT stands safely below the full spillway!
            sc.add_box((0.0, -1.65, 2.85), (2.4, 0.24, 1.25), CONCRETE_LIGHT, metallic=0.10, texture="concrete")
            add_crash_test_dummy(
                sc,
                pos=(0.0, -0.52, 2.85),
                scale=0.82,
                yaw=math.sin(t * 2.2) * 0.14,
                pose="cta_shrug",
                emotion="cta",
                t=t,
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "dam_cavitation_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("microjet_100k_psi", t=0.45, prog=0.72, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
