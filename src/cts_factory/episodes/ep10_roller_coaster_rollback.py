"""Episode 10: Why Roller Coasters NEVER Roll Backwards — True 3D Coaster Track, Anti-Rollback Dog, Magnetic Eddy Brakes & BOLT."""

from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette, build_stage_background, lerp_color
from cts_factory.engine.primitives import (
    draw_pressure_gauge,
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D, rot_matrix
from cts_factory.episodes.base import EpisodeScene, register_scene
from cts_factory.episodes.ep07_jet_engine_bird_strike import _build_sky_backdrop_bgr

RAIL_RED = (224, 58, 72)
STEEL_LIGHT = (194, 210, 230)
STEEL_MID = (118, 138, 166)
STEEL_DARK = (48, 62, 86)
CAR_YELLOW = (255, 206, 36)
CAR_YELLOW_DARK = (224, 152, 22)
CAR_NAVY = (24, 38, 60)
BRASS = (224, 174, 68)
COPPER = (226, 118, 64)
MAGNET_N = (255, 62, 82)
MAGNET_S = (38, 158, 245)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


@register_scene("ep10_roller_coaster_rollback")
class RollerCoasterRollbackScene(EpisodeScene):
    """Articulated 12-beat True 3D Roller Coaster Anti-Rollback, 3-Way Wheels & Magnetic Eddy Brakes."""

    slug = "ep10_roller_coaster_rollback"
    episode_id = "ep10"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_studio_bgr: np.ndarray | None = None
        self.bg_alert_bgr: np.ndarray | None = None
        self.bg_safe_bgr: np.ndarray | None = None
        self.bg_sky_bgr: np.ndarray | None = None
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
        self.bg_studio_bgr = cv2.cvtColor(
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
        self.bg_sky_bgr = _build_sky_backdrop_bgr(w, h, horizon_y=1260)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_coaster_track(
        self,
        sc: Scene3D,
        pitch: float = 0.45,
        length: float = 5.4,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        with_sawtooth: bool = True,
        with_chain: bool = False,
        chain_snapped: float = 0.0,
    ) -> None:
        """Tubular 3D steel coaster track (twin outer rails, central box spine, cross-ties & sawtooth rack)."""
        R = rot_matrix(0.0, 0.0, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x, y, z], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        half = length * 0.5
        # Twin crimson tubular running rails
        for sz in (-0.62, 0.62):
            sc.add_cylinder(_p(-half, 0.0, sz), _p(half, 0.0, sz), 0.085, 0.085, RAIL_RED, segments=10, metallic=0.72)
        # Central dark-steel box spine underneath
        sc.add_cylinder(_p(-half, -0.34, 0.0), _p(half, -0.34, 0.0), 0.14, 0.14, STEEL_DARK, segments=10, metallic=0.68)
        # Cross-tie ribs connecting rails to spine
        n_ties = 10
        for i in range(n_ties):
            tx = -half + (i + 0.5) * (length / n_ties)
            sc.add_cylinder(_p(tx, 0.0, -0.62), _p(tx, -0.34, 0.0), 0.045, 0.045, STEEL_MID, segments=6, metallic=0.68)
            sc.add_cylinder(_p(tx, 0.0, 0.62), _p(tx, -0.34, 0.0), 0.045, 0.045, STEEL_MID, segments=6, metallic=0.68)

        # Saw-toothed brass CNC anti-rollback rack running down the center!
        if with_sawtooth:
            sc.add_box(_p(0.0, -0.14, 0.0), (length, 0.10, 0.20), STEEL_DARK, rot=(0.0, 0.0, pitch), metallic=0.72)
            n_teeth = 12
            for ti in range(n_teeth):
                tx = -half + 0.25 + ti * ((length - 0.5) / n_teeth)
                sc.add_box(_p(tx, -0.02, 0.0), (0.22, 0.16, 0.16), BRASS, rot=(0.0, 0.0, pitch - 0.42), metallic=0.78)

        # Optional lift chain (intact or snapping wildly!)
        if with_chain:
            if chain_snapped < 0.05:
                sc.add_cylinder(_p(-half, 0.06, 0.0), _p(half, 0.06, 0.0), 0.045, 0.045, STEEL_LIGHT, segments=8, metallic=0.82)
            else:
                gap = chain_snapped * 0.72
                sc.add_cylinder(_p(-half, 0.06, 0.0), _p(-gap, 0.06 - gap * 0.45, 0.0), 0.045, 0.045, DANGER, segments=8, metallic=0.82, emissive=0.45)
                sc.add_cylinder(_p(gap, 0.06 + gap * 0.35, 0.0), _p(half, 0.06, 0.0), 0.045, 0.045, STEEL_LIGHT, segments=8, metallic=0.82)

    def _add_3d_yellow_coaster_car(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        t: float = 0.0,
        with_bolt: bool = True,
        bolt_pose: str = "pilot_sub",
        bolt_emotion: str = "curious",
        headlights: bool = True,
    ) -> None:
        """BOLT's 3D Yellow Roller Coaster Front Car (nose +X, tail -X, top +Y)."""
        R = rot_matrix(0.0, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Aerodynamic yellow nose + chassis tub + navy trim stripe
        sc.add_box(_p(0.0, 0.32, 0.0), (1.72 * scale, 0.46 * scale, 1.18 * scale), CAR_YELLOW, rot=(0.0, yaw, pitch), metallic=0.48)
        sc.add_sphere(_p(0.86, 0.30, 0.0), 0.46 * scale, CAR_YELLOW, metallic=0.52, squash_y=0.56)
        sc.add_box(_p(0.02, 0.16, 0.0), (1.76 * scale, 0.14 * scale, 1.22 * scale), CAR_NAVY, rot=(0.0, yaw, pitch), metallic=0.45)
        # Sleek metallic safety lap bar / shoulder harness arch
        sc.add_cylinder(_p(0.32, 0.52, -0.45), _p(0.32, 0.82, -0.45), 0.042 * scale, 0.042 * scale, STEEL_LIGHT, segments=8, metallic=0.82)
        sc.add_cylinder(_p(0.32, 0.52, 0.45), _p(0.32, 0.82, 0.45), 0.042 * scale, 0.042 * scale, STEEL_LIGHT, segments=8, metallic=0.82)
        sc.add_cylinder(_p(0.32, 0.82, -0.45), _p(0.32, 0.82, 0.45), 0.048 * scale, 0.048 * scale, AMBER, segments=8, metallic=0.65)
        # Rear contoured seat backrest
        sc.add_box(_p(-0.58, 0.66, 0.0), (0.24 * scale, 0.62 * scale, 1.02 * scale), CAR_NAVY, rot=(0.0, yaw, pitch - 0.15), metallic=0.42)

        # Twin front LED bumper headlights
        if headlights:
            for sz in (-0.34, 0.34):
                sc.add_sphere(_p(1.18, 0.32, sz), 0.095 * scale, (255, 248, 198), emissive=0.95, bloom=True)

        # 4 visible wheel assemblies hugging the rails
        for wx in (-0.52, 0.52):
            for wz in (-0.62, 0.62):
                sc.add_sphere(_p(wx, 0.02, wz), 0.14 * scale, STEEL_DARK, metallic=0.72)
                sc.add_sphere(_p(wx, 0.02, wz + (0.04 if wz > 0 else -0.04)), 0.075 * scale, AMBER, metallic=0.65)

        if with_bolt:
            add_crash_test_dummy(
                sc,
                pos=_p(-0.08, 0.62, 0.0),
                scale=0.68 * scale,
                yaw=yaw + 0.18,
                pose=bolt_pose,
                emotion=bolt_emotion,
                t=t,
                tilt_z=pitch * 0.45,
                ground_shadow=False,
            )

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

        bg = self.bg_studio_bgr
        if scene_key in ("coaster_chain_snap_hero", "train_70mph_blackout"):
            bg = self.bg_alert_bgr
        elif scene_key in ("dog_jams_tooth", "eddy_current_swirls", "spring_brakes_close"):
            bg = self.bg_safe_bgr
        elif scene_key in ("bolt_coaster_wave", "bolt_station_victory", "verdict_cta_card"):
            bg = self.bg_sky_bgr
        assert bg is not None

        cam = Camera3D(eye=(0.0, 0.8, 7.2), target=(0.0, 0.0, 0.0), fov_deg=41.0, width=w, height=h)
        sc = Scene3D(cam)

        if scene_key == "coaster_chain_snap_hero":
            shake = math.sin(t * 52.0) * 0.11 if prog > 0.35 else 0.0
            cam.eye = (0.25 + shake, 0.65, 6.7)
            cam.target = (0.0, 0.05, 0.0)
            snap_p = ease_out_cubic(clamp((prog - 0.30) / 0.70, 0.0, 1.0))
            self._add_3d_coaster_track(sc, pitch=0.48, length=6.2, center=(0.0, -0.35, 0.0), with_sawtooth=True, with_chain=True, chain_snapped=snap_p)
            self._add_3d_yellow_coaster_car(sc, center=(0.35, 0.05, 0.0), scale=1.02, yaw=0.0, pitch=0.48, t=t, with_bolt=True, bolt_pose="brace_impact", bolt_emotion="shock")
            if prog > 0.32:
                overlays_2d.append(lambda d, sp=snap_p: draw_sparks(d, 520, 995, sp, 20, 175, 145, p, seed=1001))

        elif scene_key == "bolt_coaster_wave":
            # Narrator: "Hey Bolt, wave down below — we are cutting power right now!"
            cam.eye = (0.35, 0.72, 6.5)
            cam.target = (0.0, 0.25, 0.0)
            self._add_3d_coaster_track(sc, pitch=0.42, length=6.0, center=(0.0, -0.58, 0.0), with_sawtooth=True, with_chain=True, chain_snapped=0.45 if prog > 0.55 else 0.0)
            # Tiny 1-inch rollback catch jitter at prog == 0.55, then locked rock-solid!
            catch_shift = -0.10 * math.sin(clamp((prog - 0.55) * 4.5, 0.0, 1.0) * math.pi) if prog > 0.55 else 0.0
            self._add_3d_yellow_coaster_car(sc, center=(catch_shift, -0.32 + catch_shift * 0.42, 0.0), scale=1.08, yaw=0.0, pitch=0.42, t=t, with_bolt=False)
            add_crash_test_dummy(
                sc,
                pos=(catch_shift - 0.04, 0.68 + catch_shift * 0.42, 0.0),
                scale=0.84,
                yaw=0.04 + math.sin(t * 2.4) * 0.10,
                pose="relief_wave",
                emotion="cta",
                t=t,
                ground_shadow=False,
            )

            def _wave_arc(d: ImageDraw.ImageDraw) -> None:
                pulse = (t * 2.2) % 1.0
                r = int(26 + pulse * 42)
                cx, cy = 625, 600
                d.arc([cx - r, cy - r, cx + r, cy + r], start=-55, end=25, fill=p.cyan, width=4)

            overlays_2d.append(_wave_arc)

        elif scene_key in ("anti_rollback_ratchet", "chain_dog_closeup", "dog_jams_tooth"):
            # Macro 3D cutaway of saw-toothed brass rack + hinged steel anti-rollback dog!
            cam.eye = (0.0, 0.35, 5.3)
            cam.target = (0.0, -0.10, 0.0)
            is_jam = scene_key == "dog_jams_tooth"
            # Heavy steel track spine + 6 giant crisp CNC brass sawtooth notches!
            sc.add_box((0.0, -1.05, 0.0), (5.2, 0.55, 1.05), STEEL_DARK, metallic=0.72)
            slide = 0.0
            if not is_jam:
                slide = (t * 1.45) % 0.85
            else:
                # Hop forward slightly, then slip backwards and SLAM into solid tooth!
                slide = 0.24 - ease_out_cubic(clamp((prog - 0.35) / 0.25, 0.0, 1.0)) * 0.32

            for ti in range(-3, 4):
                tx = ti * 0.85 - slide
                # Sloped ramp front + vertical dead-stop wall on the left side!
                sc.add_box((tx, -0.58, 0.0), (0.58, 0.42, 0.72), BRASS, rot=(0.0, 0.0, -0.45), metallic=0.80)
                sc.add_box((tx - 0.28, -0.56, 0.0), (0.14, 0.48, 0.76), STEEL_LIGHT, metallic=0.84)

            # Upper coaster car undercarriage bracket + hinged steel anti-rollback dog!
            sc.add_box((0.0, 0.92, 0.0), (2.4, 0.38, 0.92), CAR_YELLOW, metallic=0.52)
            sc.add_cylinder((0.45, 0.68, -0.52), (0.45, 0.68, 0.52), 0.14, 0.14, STEEL_LIGHT, segments=12, metallic=0.85)
            if not is_jam:
                # Dog hops rhythmically up and down over each passing tooth ("CLACK-CLACK-CLACK"!)
                hop_ang = 0.22 * abs(math.sin((slide / 0.85) * math.pi))
                dog_tip = (-0.34, -0.28 + hop_ang * 1.1, 0.0)
                dog_col = STEEL_LIGHT
            else:
                jammed = prog > 0.52
                dog_tip = (-0.30, -0.46 if jammed else -0.20, 0.0)
                dog_col = EMERALD if jammed else STEEL_LIGHT
            sc.add_cylinder((0.45, 0.68, 0.0), dog_tip, 0.14, 0.12, dog_col, metallic=0.84, emissive=0.45 if (is_jam and prog > 0.52) else 0.0, bloom=(is_jam and prog > 0.52), segments=10)

            if is_jam and prog > 0.50:
                sp = clamp((prog - 0.50) / 0.50, 0.0, 1.0)
                overlays_2d.append(lambda d, s=sp: draw_sparks(d, 465, 1065, s, 22, 180, 150, p, seed=1005))
                overlays_2d.append(lambda d: draw_pressure_gauge(d, 895, 1140, 96, 1.0, "LOCK STATE", "ZERO POWER", p, self.font_black))
            elif scene_key == "anti_rollback_ratchet":
                # Visual sound pulse rings on each CLACK!
                def _clack_waves(d: ImageDraw.ImageDraw) -> None:
                    ph = (t * 2.8) % 1.0
                    r = int(32 + ph * 95)
                    d.ellipse([480 - r, 1020 - r, 480 + r, 1020 + r], outline=p.cyan, width=4)

                overlays_2d.append(_clack_waves)

        elif scene_key == "upstop_wheels_clamp":
            # Exploded 3D blueprint of 3-way wheel bogie hugging tubular steel rail (Top, Bottom, Side)!
            cam.eye = (0.35, 0.40, 5.6)
            cam.target = (0.0, 0.0, 0.0)
            exp = 0.25 * (1.0 - ease_out_cubic(clamp(prog * 1.3, 0.0, 1.0)))
            # Central crimson tubular steel rail running into depth (Z axis)
            sc.add_cylinder((0.0, 0.0, -2.2), (0.0, 0.0, 2.2), 0.34, 0.34, RAIL_RED, segments=16, metallic=0.76)
            # 1) Road Wheel (TOP) — supports weight
            sc.add_cylinder((0.0, 0.78 + exp, -0.35), (0.0, 0.78 + exp, 0.35), 0.42, 0.42, CAR_YELLOW, segments=16, metallic=0.58)
            sc.add_cylinder((0.0, 0.78 + exp, -0.42), (0.0, 0.78 + exp, 0.42), 0.16, 0.16, STEEL_DARK, segments=12, metallic=0.78)
            # 2) Upstop Wheel (BOTTOM) — stops car lifting off upside down!
            sc.add_cylinder((0.0, -0.72 - exp, -0.30), (0.0, -0.72 - exp, 0.30), 0.36, 0.36, EMERALD, segments=16, metallic=0.58, emissive=0.25)
            # 3) Side Friction Guide Wheels (LEFT & RIGHT)
            for sx in (-1, 1):
                sc.add_cylinder((sx * (0.70 + exp), 0.0, -0.26), (sx * (0.70 + exp), 0.0, 0.26), 0.32, 0.32, CYAN, segments=14, metallic=0.58, emissive=0.25)
            # Structural C-yoke steel bogie bracket connecting all 3 wheel planes
            sc.add_box((-1.15, 0.0, 0.0), (0.20, 1.65, 0.48), STEEL_MID, metallic=0.76)
            sc.add_box((1.15, 0.0, 0.0), (0.20, 1.65, 0.48), STEEL_MID, metallic=0.76)
            sc.add_box((0.0, 1.25, 0.0), (2.45, 0.24, 0.56), STEEL_LIGHT, metallic=0.80)

            def _bogie_tags(d: ImageDraw.ImageDraw) -> None:
                f_b = load_font(self.font_black, 28)
                for txt, x, y, col in (
                    ("TOP: ROAD WHEEL", 355, 535, p.amber),
                    ("SIDE: GUIDE WHEELS", 650, 910, p.cyan),
                    ("BOTTOM: UPSTOP LOCK", 340, 1275, p.emerald),
                ):
                    d.rounded_rectangle([x - 16, y - 10, x + 365, y + 42], radius=12, fill=p.surface_panel, outline=col, width=3)
                    d.text((x, y), txt, font=f_b, fill=col)

            overlays_2d.append(_bogie_tags)

        elif scene_key == "train_70mph_blackout":
            shake = math.sin(t * 48.0) * 0.08
            cam.eye = (0.0 + shake, 0.65, 6.8)
            cam.target = (0.0, 0.0, 0.0)
            self._add_3d_coaster_track(sc, pitch=0.0, length=7.0, center=(0.0, -0.45, 0.0), with_sawtooth=False)
            car_x = -2.1 + ease_out_cubic(prog) * 2.55
            self._add_3d_yellow_coaster_car(sc, center=(car_x, -0.35, 0.0), scale=1.05, yaw=0.0, pitch=0.0, t=t, with_bolt=True, bolt_pose="brace_impact", bolt_emotion="panic")
            # High-speed red/amber velocity streaks
            for k in range(6):
                sy = -0.25 + k * 0.28
                sc.add_cylinder((car_x - 0.9 - k * 0.15, sy, 0.35), (car_x - 2.3 - k * 0.15, sy, 0.35), 0.025, 0.01, DANGER, segments=6, emissive=0.90, bloom=True)

        elif scene_key in ("copper_magnet_fins", "eddy_current_swirls"):
            # Macro 3D cutaway of gleaming copper brake fin slicing between permanent magnets!
            cam.eye = (0.45, 0.72, 6.1)
            cam.target = (0.0, -0.05, 0.0)
            is_eddy = scene_key == "eddy_current_swirls"
            # Thick gleaming vertical copper brake fin bolted under the yellow coaster car!
            fin_x = -0.85 + ease_out_cubic(prog) * 1.45 if is_eddy else 0.0
            sc.add_box((fin_x, 0.78, 0.0), (2.4, 0.34, 1.35), CAR_YELLOW, metallic=0.50)
            sc.add_box((fin_x, 0.0, 0.0), (2.2, 1.25, 0.16), COPPER, metallic=0.84)
            # Twin permanent magnet banks flanking the copper fin (ZERO contact, ZERO electricity!)
            for sz, col_m in ((-0.52, MAGNET_N), (0.52, MAGNET_S)):
                sc.add_box((0.0, -0.15, sz), (2.6, 0.92, 0.38), col_m, metallic=0.58)
                sc.add_box((0.0, -0.78, sz), (2.8, 0.34, 0.48), STEEL_DARK, metallic=0.72)

            if is_eddy:
                # Glowing swirling cyan eddy-current loops inside the copper fin pushing back smoothly!
                for k in range(3):
                    cx = fin_x - 0.65 + k * 0.65
                    for a_i in range(8):
                        ang = t * 7.0 + a_i * (math.pi * 0.25)
                        sc.add_sphere((cx + math.cos(ang) * 0.26, math.sin(ang) * 0.26, 0.14), 0.055, CYAN, emissive=0.95, bloom=True)
                # Narrator: "No power needed, Bolt!" -> BOLT celebrates calmly!
                add_crash_test_dummy(sc, pos=(-1.62, -0.25, 0.62), scale=0.84, yaw=0.35, pose="relief_wave", emotion="relief", t=t)

        elif scene_key == "spring_brakes_close":
            # Fail-closed mechanical pinch brakes slamming shut automatically when air pressure drops!
            cam.eye = (0.0, 0.55, 5.8)
            cam.target = (0.0, -0.05, 0.0)
            clamp_p = ease_out_cubic(clamp((prog - 0.28) / 0.38, 0.0, 1.0))
            gap = 0.62 * (1.0 - clamp_p) + 0.12
            # Central vertical steel brake fin
            sc.add_box((0.0, 0.15, 0.0), (0.18, 1.65, 2.2), STEEL_LIGHT, metallic=0.84)
            # Twin spring-loaded bronze pinch calipers closing inward from left & right!
            for sx in (-1, 1):
                sc.add_box((sx * (gap + 0.22), 0.0, 0.0), (0.36, 0.92, 1.55), AMBER if clamp_p < 0.8 else EMERALD, metallic=0.72, emissive=0.35 if clamp_p > 0.8 else 0.0)
                # Heavy steel coil spring rings pushing inward behind each caliper!
                for r_i in range(4):
                    rx = sx * (gap + 0.55 + r_i * 0.24)
                    sc.add_cylinder((rx, 0.0, -0.22), (rx, 0.0, 0.22), 0.22, 0.22, STEEL_MID, segments=10, metallic=0.78)
            if prog > 0.58:
                overlays_2d.append(lambda d: draw_sparks(d, 540, 960, (prog - 0.58) / 0.42, 16, 160, 140, p, seed=1010))
                overlays_2d.append(lambda d: draw_pressure_gauge(d, 165, 1140, 96, 0.0, "AIR PRESSURE", "0 PSI = LOCKED", p, self.font_black))

        elif scene_key == "bolt_station_victory":
            # Narrator: "Smooth stop, Bolt!" -> Open-sky sunset station dock finale!
            cam.eye = (0.0, 0.72, 7.1)
            cam.target = (0.0, 0.10, 0.0)
            arrive = ease_out_cubic(clamp(prog * 1.35, 0.0, 1.0))
            car_x = -0.85 + arrive * 0.85
            self._add_3d_coaster_track(sc, pitch=0.0, length=6.8, center=(0.0, -0.68, 0.0), with_sawtooth=False)
            self._add_3d_yellow_coaster_car(sc, center=(car_x, -0.58, 0.0), scale=1.10, yaw=-0.12, pitch=0.0, t=t, with_bolt=False)
            add_crash_test_dummy(
                sc,
                pos=(car_x, 0.45, 0.22),
                scale=0.88,
                yaw=0.08,
                pose="relief_wave",
                emotion="relief",
                t=t,
                ground_shadow=False,
            )

        else:  # verdict_cta_card
            cam.eye = (0.0, 0.72, 7.2)
            cam.target = (0.0, 0.12, 0.0)
            self._add_3d_coaster_track(sc, pitch=0.0, length=6.8, center=(0.0, -0.68, 0.0), with_sawtooth=False)
            self._add_3d_yellow_coaster_car(sc, center=(0.0, -0.58, 0.0), scale=1.08, yaw=-0.10, pitch=0.0, t=t, with_bolt=False)
            add_crash_test_dummy(
                sc,
                pos=(0.0, 0.46, 0.22),
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "coaster_chain_snap_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("coaster_chain_snap_hero", t=0.45, prog=0.62, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
