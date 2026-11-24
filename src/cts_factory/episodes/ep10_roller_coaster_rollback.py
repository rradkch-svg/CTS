"""Episode 10: Why Roller Coasters NEVER Roll Backwards — Upgraded True 3D Coaster Track, Anti-Rollback Dog, Cutaway Magnetic Eddy Brakes & Helical Spring Brakes."""

from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette, build_stage_background
from cts_factory.engine.primitives import (
    draw_cta_buttons,
    draw_pressure_gauge,
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D, rot_matrix
from cts_factory.episodes.base import EpisodeScene, register_scene

RAIL_RED = (224, 58, 72)
STEEL_LIGHT = (194, 210, 230)
STEEL_MID = (118, 138, 166)
STEEL_DARK = (48, 62, 86)
CAR_YELLOW = (255, 206, 36)
CAR_NAVY = (24, 38, 60)
BRASS = (224, 174, 68)
COPPER = (226, 118, 64)
MAGNET_N = (255, 62, 82)
MAGNET_S = (38, 158, 245)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


def _build_theme_park_sunset_bgr(w: int, h: int) -> np.ndarray:
    """Clean dusk theme-park twilight sky with soft sunset horizon glow (zero flat ocean ellipses!)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    img = np.zeros((h, w, 3), dtype=np.float32)

    img[:, :, 2] = 14.0 + 68.0 * (ys ** 1.9) * (1.0 - 0.42 * ys)
    img[:, :, 1] = 22.0 + 74.0 * (ys ** 1.6) * (1.0 - 0.48 * ys)
    img[:, :, 0] = 56.0 + 96.0 * (ys ** 1.2) * (1.0 - 0.45 * ys)

    glow = np.exp(-((xs / 0.70) ** 2 + ((ys - 0.62) / 0.18) ** 2))
    img[:, :, 2] += 54.0 * glow
    img[:, :, 1] += 36.0 * glow
    img[:, :, 0] += 18.0 * glow
    return np.clip(img, 0, 255).astype(np.uint8)


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
        self.bg_park_bgr: np.ndarray | None = None
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
        self.bg_park_bgr = _build_theme_park_sunset_bgr(w, h)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_coaster_track(
        self,
        sc: Scene3D,
        pitch: float = 0.45,
        length: float = 5.6,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        with_sawtooth: bool = True,
        with_chain: bool = False,
        chain_snapped: float = 0.0,
        with_supports: bool = True,
        with_station: bool = False,
    ) -> None:
        """Tubular 3D steel coaster track with real vertical support columns and optional station platform."""
        R = rot_matrix(0.0, 0.0, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x, y, z], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        half = length * 0.5
        # Steel structural support columns anchoring the track (never floating in void!)
        if with_supports:
            for sx in (-1.9, 0.0, 1.9):
                top_pt = _p(sx, -0.34, 0.0)
                sc.add_cylinder(top_pt, (top_pt[0], -3.4, top_pt[2]), 0.14, 0.16, STEEL_MID, segments=12, metallic=0.68)

        # Station boarding deck + safety gate rail
        if with_station:
            sc.add_box((0.0, -0.58, -1.25), (6.4, 0.24, 1.20), (112, 120, 134), metallic=0.12, texture="concrete")
            sc.add_cylinder((-3.0, -0.02, -0.78), (3.0, -0.02, -0.78), 0.032, 0.032, AMBER, segments=6, metallic=0.65)
            for gx in (-2.4, -0.8, 0.8, 2.4):
                sc.add_cylinder((gx, -0.46, -0.78), (gx, -0.02, -0.78), 0.028, 0.028, STEEL_LIGHT, segments=6, metallic=0.72)

        # Twin crimson tubular running rails
        for sz in (-0.62, 0.62):
            sc.add_cylinder(_p(-half, 0.0, sz), _p(half, 0.0, sz), 0.085, 0.085, RAIL_RED, segments=14, metallic=0.72)
        sc.add_cylinder(_p(-half, -0.34, 0.0), _p(half, -0.34, 0.0), 0.14, 0.14, STEEL_DARK, segments=14, metallic=0.68)

        n_ties = 10
        for i in range(n_ties):
            tx = -half + (i + 0.5) * (length / n_ties)
            sc.add_cylinder(_p(tx, 0.0, -0.62), _p(tx, -0.34, 0.0), 0.045, 0.045, STEEL_MID, segments=8, metallic=0.68)
            sc.add_cylinder(_p(tx, 0.0, 0.62), _p(tx, -0.34, 0.0), 0.045, 0.045, STEEL_MID, segments=8, metallic=0.68)

        if with_sawtooth:
            sc.add_box(_p(0.0, -0.14, 0.0), (length, 0.10, 0.20), STEEL_DARK, rot=(0.0, 0.0, pitch), metallic=0.72)
            n_teeth = 12
            for ti in range(n_teeth):
                tx = -half + 0.25 + ti * ((length - 0.5) / n_teeth)
                sc.add_box(_p(tx, -0.02, 0.0), (0.20, 0.15, 0.16), BRASS, rot=(0.0, 0.0, pitch - 0.42), metallic=0.78, texture="machined_brass")

        # Visible segmented lift chain ABOVE the spine so snap is unmistakable!
        if with_chain:
            if chain_snapped < 0.05:
                sc.add_cylinder(_p(-half, 0.12, 0.0), _p(half, 0.12, 0.0), 0.055, 0.055, STEEL_LIGHT, segments=10, metallic=0.82)
            else:
                gap = 0.20 + chain_snapped * 0.72
                sc.add_cylinder(_p(-half, 0.12, 0.0), _p(-gap, 0.12 - gap * 0.35, 0.10), 0.055, 0.055, DANGER, segments=10, metallic=0.82, emissive=0.45, bloom=True)
                sc.add_cylinder(_p(gap, 0.12 + gap * 0.25, 0.10), _p(half, 0.12, 0.0), 0.055, 0.055, STEEL_LIGHT, segments=10, metallic=0.82)

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
        """BOLT's 3D Yellow Roller Coaster Car with cylindrical wheels & seated BOLT (ZERO legs poking under floor!)."""
        R = rot_matrix(0.0, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Seated BOLT rendered inside the yellow coaster cockpit (show_legs=False guarantees zero floor clipping!)
        if with_bolt:
            add_crash_test_dummy(
                sc,
                pos=_p(-0.08, 0.72, -0.02),
                scale=0.66 * scale,
                yaw=yaw + 0.16,
                pose=bolt_pose,
                emotion=bolt_emotion,
                t=t,
                tilt_z=pitch * 0.45,
                ground_shadow=False,
                show_legs=False,
            )

        # Deep sleek yellow coaster hull + tapered nose + dark navy bumper
        sc.add_box(_p(0.0, 0.36, 0.0), (1.76 * scale, 0.56 * scale, 1.18 * scale), CAR_YELLOW, rot=(0.0, yaw, pitch), metallic=0.45, texture="painted_metal")
        sc.add_sphere(_p(0.88, 0.34, 0.0), 0.48 * scale, CAR_YELLOW, metallic=0.48, squash_y=0.60)
        sc.add_box(_p(0.02, 0.14, 0.0), (1.80 * scale, 0.14 * scale, 1.22 * scale), CAR_NAVY, rot=(0.0, yaw, pitch), metallic=0.45, texture="painted_metal")
        # Front padded lap-bar arch clear of BOLT's torso (never clipping crotch!)
        sc.add_cylinder(_p(0.42, 0.60, -0.46), _p(0.42, 0.86, -0.46), 0.038 * scale, 0.038 * scale, STEEL_LIGHT, segments=8, metallic=0.82)
        sc.add_cylinder(_p(0.42, 0.60, 0.46), _p(0.42, 0.86, 0.46), 0.038 * scale, 0.038 * scale, STEEL_LIGHT, segments=8, metallic=0.82)
        sc.add_cylinder(_p(0.42, 0.86, -0.46), _p(0.42, 0.86, 0.46), 0.044 * scale, 0.044 * scale, AMBER, segments=8, metallic=0.62)
        # Contoured rear seat backrest
        sc.add_box(_p(-0.62, 0.72, 0.0), (0.24 * scale, 0.62 * scale, 1.02 * scale), CAR_NAVY, rot=(0.0, yaw, pitch - 0.15), metallic=0.38, texture="matte")

        # Subtle warm headlights (controlled glow, no whiteout orb!)
        if headlights:
            for sz in (-0.34, 0.34):
                sc.add_sphere(_p(1.20, 0.34, sz), 0.085 * scale, (255, 242, 185), emissive=0.58)

        # True 3D cylindrical polyurethane coaster wheels hugging the rails (NOT spheres!)
        for wx in (-0.54, 0.54):
            for wz in (-0.62, 0.62):
                s_out = 0.09 if wz > 0 else -0.09
                sc.add_cylinder(_p(wx, 0.02, wz - s_out), _p(wx, 0.02, wz + s_out), 0.15 * scale, 0.15 * scale, STEEL_DARK, segments=16, metallic=0.65)
                sc.add_cylinder(_p(wx, 0.02, wz - s_out * 1.15), _p(wx, 0.02, wz + s_out * 1.15), 0.075 * scale, 0.075 * scale, AMBER, segments=12, metallic=0.72)

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

        bg = self.bg_studio_bgr
        if scene_key in ("coaster_chain_snap_hero", "train_70mph_blackout"):
            bg = self.bg_alert_bgr
        elif scene_key in ("dog_jams_tooth", "eddy_current_swirls", "spring_brakes_close"):
            bg = self.bg_safe_bgr
        elif scene_key in ("bolt_coaster_wave", "bolt_station_victory", "verdict_cta_card"):
            bg = self.bg_park_bgr
        assert bg is not None

        cam = Camera3D(eye=(0.0, 0.8, 7.2), target=(0.0, 0.0, 0.0), fov_deg=41.0, width=w, height=h)
        sc = Scene3D(cam)

        if scene_key == "coaster_chain_snap_hero":
            shake = math.sin(t * 52.0) * 0.08 if (prog > 0.35 and not is_cover) else 0.0
            if is_cover:
                cam = Camera3D(eye=(0.25, 0.70, 7.6), target=(0.0, 0.78, 0.0), fov_deg=41.0, width=w, height=h)
                sc = Scene3D(cam)
            else:
                cam = Camera3D(eye=(0.25 + shake, 0.62, 6.8), target=(0.0, 0.05, 0.0), fov_deg=41.0, width=w, height=h)
                sc = Scene3D(cam)
            snap_p = ease_out_cubic(clamp((prog - 0.25) / 0.75, 0.0, 1.0)) if not is_cover else 0.72
            self._add_3d_coaster_track(sc, pitch=0.45, length=6.4, center=(0.0, -0.45, 0.0), with_sawtooth=True, with_chain=True, chain_snapped=snap_p)
            self._add_3d_yellow_coaster_car(sc, center=(0.32, -0.06, 0.0), scale=0.98, yaw=0.0, pitch=0.45, t=t, with_bolt=True, bolt_pose="brace_impact", bolt_emotion="shock")
            if prog > 0.30 and not is_cover:
                overlays_2d.append(lambda d, sp=snap_p: draw_sparks(d, 520, 995, sp, 18, 160, 135, p, seed=1001))

        elif scene_key == "bolt_coaster_wave":
            # Narrator: "Hey Bolt, wave down below — we are cutting power right now!"
            cam.eye = (0.28, 0.72, 6.8)
            cam.target = (0.0, 0.20, 0.0)
            snapped = 0.45 if prog > 0.55 else 0.0
            self._add_3d_coaster_track(sc, pitch=0.42, length=6.2, center=(0.0, -0.58, 0.0), with_sawtooth=True, with_chain=True, chain_snapped=snapped)
            catch_shift = -0.08 * math.sin(clamp((prog - 0.55) * 4.5, 0.0, 1.0) * math.pi) if prog > 0.55 else 0.0
            self._add_3d_yellow_coaster_car(
                sc,
                center=(catch_shift, -0.28 + catch_shift * 0.42, 0.0),
                scale=1.06,
                yaw=0.0,
                pitch=0.42,
                t=t,
                with_bolt=True,
                bolt_pose="relief_wave" if prog < 0.62 else "explain",
                bolt_emotion="cta" if prog < 0.62 else "relief",
            )

        elif scene_key in ("anti_rollback_ratchet", "chain_dog_closeup", "dog_jams_tooth"):
            # Macro 3D cutaway of CNC sawtooth rack + spring-loaded steel anti-rollback dog!
            cam.eye = (0.25 if scene_key == "chain_dog_closeup" else 0.0, 0.38, 5.5)
            cam.target = (0.0, -0.10, 0.0)
            is_jam = scene_key == "dog_jams_tooth"
            sc.add_box((0.0, -1.05, 0.0), (5.4, 0.55, 1.05), STEEL_DARK, metallic=0.72, texture="brushed_steel")
            if not is_jam:
                slide = (t * 1.45) % 0.85
            else:
                slide = 0.24 - ease_out_cubic(clamp((prog - 0.35) / 0.25, 0.0, 1.0)) * 0.32

            # Clean triangular sawtooth ratchet teeth built from tapered wedges!
            for ti in range(-3, 4):
                tx = ti * 0.85 - slide
                # Back vertical stop wall + inclined brass ramp
                q_front = np.array(
                    [
                        [tx - 0.32, -0.78, 0.36],
                        [tx + 0.44, -0.78, 0.36],
                        [tx - 0.22, -0.32, 0.36],
                        [tx - 0.32, -0.32, 0.36],
                    ],
                    dtype=np.float32,
                )
                sc.add_quad(q_front, rgb=BRASS, metallic=0.78, double_sided=True, texture="machined_brass")
                sc.add_box((tx - 0.27, -0.55, 0.0), (0.10, 0.46, 0.72), STEEL_LIGHT, metallic=0.84, texture="brushed_steel")
                sc.add_box((tx + 0.06, -0.58, 0.0), (0.62, 0.16, 0.70), BRASS, rot=(0.0, 0.0, -0.56), metallic=0.78, texture="machined_brass")

            # Coaster chassis bracket + steel pivot clevis + real helical spring + hinged steel dog!
            sc.add_box((0.0, 0.96, 0.0), (2.5, 0.38, 0.96), CAR_YELLOW, metallic=0.48, texture="painted_metal")
            sc.add_box((0.45, 0.72, 0.0), (0.36, 0.32, 0.62), STEEL_MID, metallic=0.76, texture="brushed_steel")
            sc.add_cylinder((0.45, 0.68, -0.44), (0.45, 0.68, 0.44), 0.11, 0.11, STEEL_LIGHT, segments=14, metallic=0.85)
            if not is_jam:
                hop_ang = 0.22 * abs(math.sin((slide / 0.85) * math.pi))
                dog_tip = (-0.28, -0.32 + hop_ang * 0.95, 0.0)
                dog_col = STEEL_LIGHT
            else:
                jammed = prog > 0.52
                dog_tip = (-0.25, -0.48 if jammed else -0.22, 0.0)
                dog_col = EMERALD if jammed else STEEL_LIGHT
            sc.add_cylinder((0.45, 0.68, 0.0), dog_tip, 0.13, 0.11, dog_col, metallic=0.84, emissive=0.22 if (is_jam and prog > 0.52) else 0.0, segments=14)
            # Real helical return spring pushing the dog downward onto the teeth!
            sc.add_coil_spring((0.02, 0.76, 0.0), (0.04, 0.16, 0.0), coil_radius=0.11, wire_radius=0.024, turns=4, rgb=AMBER)

            if is_jam and prog > 0.50:
                sp = clamp((prog - 0.50) / 0.50, 0.0, 1.0)
                overlays_2d.append(lambda d, s=sp: draw_sparks(d, 480, 1065, s, 16, 150, 120, p, seed=1005))
                overlays_2d.append(lambda d: draw_pressure_gauge(d, 740, 1185, 86, 1.0, "LOCK STATE", "ZERO POWER", p, self.font_black, invert_scale=True))
            elif scene_key == "anti_rollback_ratchet":
                def _clack_waves(d: ImageDraw.ImageDraw) -> None:
                    for ring_i in range(2):
                        ph = (t * 2.6 + ring_i * 0.5) % 1.0
                        r = int(28 + ph * 85)
                        d.arc([480 - r, 1020 - r, 480 + r, 1020 + r], start=195, end=345, fill=p.cyan, width=4)

                overlays_2d.append(_clack_waves)

        elif scene_key == "upstop_wheels_clamp":
            # Connected C-yoke 3-way coaster wheel bogie with true axles + ZERO overlapping/clipped tags!
            cam.eye = (0.38, 0.35, 6.0)
            cam.target = (0.0, -0.05, 0.0)
            exp = 0.22 * (1.0 - ease_out_cubic(clamp(prog * 1.3, 0.0, 1.0)))
            sc.add_cylinder((0.0, 0.0, -2.2), (0.0, 0.0, 2.2), 0.34, 0.34, RAIL_RED, segments=22, metallic=0.76)
            # 1) Road Wheel (TOP) + horizontal steel axle linking both C-yoke legs
            sc.add_cylinder((-1.15, 0.78 + exp, 0.0), (1.15, 0.78 + exp, 0.0), 0.08, 0.08, STEEL_LIGHT, segments=12, metallic=0.82)
            sc.add_cylinder((0.0, 0.78 + exp, -0.34), (0.0, 0.78 + exp, 0.34), 0.42, 0.42, CAR_YELLOW, segments=22, metallic=0.58)
            sc.add_cylinder((0.0, 0.78 + exp, -0.40), (0.0, 0.78 + exp, 0.40), 0.16, 0.16, STEEL_DARK, segments=16, metallic=0.78)
            # 2) Upstop Wheel (BOTTOM) + lower steel axle connecting yoke legs!
            sc.add_cylinder((-1.15, -0.72 - exp, 0.0), (1.15, -0.72 - exp, 0.0), 0.075, 0.075, STEEL_LIGHT, segments=12, metallic=0.82)
            sc.add_cylinder((0.0, -0.72 - exp, -0.28), (0.0, -0.72 - exp, 0.28), 0.36, 0.36, EMERALD, segments=22, metallic=0.55)
            # 3) Side Friction Guide Wheels + vertical pivot shafts anchored to C-yoke!
            for sx in (-1, 1):
                sc.add_cylinder((sx * (0.70 + exp), -0.72, 0.0), (sx * (0.70 + exp), 0.78, 0.0), 0.065, 0.065, STEEL_LIGHT, segments=10, metallic=0.82)
                sc.add_cylinder((sx * (0.70 + exp), 0.0, -0.24), (sx * (0.70 + exp), 0.0, 0.24), 0.32, 0.32, CYAN, segments=20, metallic=0.55)
            # Fully connected structural C-yoke frame (zero floating gaps!)
            sc.add_box((-1.15, 0.22, 0.0), (0.22, 2.20, 0.48), STEEL_MID, metallic=0.76, texture="brushed_steel")
            sc.add_box((1.15, 0.22, 0.0), (0.22, 2.20, 0.48), STEEL_MID, metallic=0.76, texture="brushed_steel")
            sc.add_box((0.0, 1.24, 0.0), (2.52, 0.24, 0.56), STEEL_LIGHT, metallic=0.80, texture="brushed_steel")

            def _bogie_tags(d: ImageDraw.ImageDraw) -> None:
                f_b = load_font(self.font_black, 24)
                # Auto-sized boxes positioned cleanly clear of HUD badge AND strictly inside x <= 852!
                for txt, x, y, col in (
                    ("TOP: ROAD WHEEL", 486, 536, p.amber),
                    ("SIDE: GUIDE WHEELS", 476, 1218, p.cyan),
                    ("BOTTOM: UPSTOP LOCK", 96, 1278, p.emerald),
                ):
                    bb = d.textbbox((0, 0), txt, font=f_b)
                    tw = bb[2] - bb[0]
                    bx0 = min(x, 850 - tw - 28)
                    d.rounded_rectangle([bx0, y, bx0 + tw + 28, y + 44], radius=12, fill=p.surface_panel, outline=col, width=3)
                    d.text((bx0 + 14, y + 8), txt, font=f_b, fill=col)

            overlays_2d.append(_bogie_tags)

        elif scene_key == "train_70mph_blackout":
            shake = math.sin(t * 48.0) * 0.07
            cam.eye = (0.0 + shake, 0.65, 7.0)
            cam.target = (0.0, 0.0, 0.0)
            self._add_3d_coaster_track(sc, pitch=0.0, length=7.0, center=(0.0, -0.45, 0.0), with_sawtooth=False, with_station=True)
            car_x = -1.9 + ease_out_cubic(prog) * 2.35
            # Headlights OFF during power blackout!
            self._add_3d_yellow_coaster_car(sc, center=(car_x, -0.35, 0.0), scale=1.02, yaw=0.0, pitch=0.0, t=t, with_bolt=True, bolt_pose="brace_impact", bolt_emotion="panic", headlights=False)
            # Tapered organic aerodynamic speed wisps (not uniform neon stair bars!)
            for k in range(4):
                sy = -0.10 + k * 0.34
                wlen = 1.2 + (k % 2) * 0.65
                sc.add_cylinder((car_x - 0.95 - k * 0.12, sy, 0.25), (car_x - 0.95 - wlen, sy, 0.25), 0.018, 0.005, CYAN, segments=6, emissive=0.55)

        elif scene_key in ("copper_magnet_fins", "eddy_current_swirls"):
            # Elevated 3/4 TOP-SIDE view with translucent front magnet so the COPPER FIN + EDDY SWIRLS are 100% VISIBLE!
            cam.eye = (1.65, 1.55, 5.4)
            cam.target = (0.0, -0.05, 0.0)
            is_eddy = scene_key == "eddy_current_swirls"
            fin_x = -0.75 + ease_out_cubic(prog) * 1.25 if is_eddy else 0.0
            # Yellow coaster undercarriage + gleaming vertical copper brake fin right down the center!
            sc.add_box((fin_x, 0.92, 0.0), (2.3, 0.28, 1.15), CAR_YELLOW, metallic=0.48, texture="painted_metal")
            sc.add_box((fin_x, 0.08, 0.0), (2.25, 1.32, 0.18), COPPER, metallic=0.84, texture="machined_brass")
            # Rear Red North Magnet Bank (solid) + Front Blue South Magnet Bank (translucent cutaway so copper & swirls shine through!)
            sc.add_box((0.0, -0.14, -0.58), (2.6, 0.92, 0.34), MAGNET_N, metallic=0.55, texture="painted_metal")
            sc.add_box((0.0, -0.76, -0.58), (2.8, 0.32, 0.44), STEEL_DARK, metallic=0.72, texture="brushed_steel")
            sc.add_box((0.0, -0.14, 0.58), (2.6, 0.92, 0.34), MAGNET_S, metallic=0.55, alpha=0.32, texture=None)
            sc.add_box((0.0, -0.76, 0.58), (2.8, 0.32, 0.44), STEEL_DARK, metallic=0.72, texture="brushed_steel")

            if is_eddy:
                # Crisp glowing cyan eddy-current rings spinning right ON the copper fin surface (100% unobstructed!)
                for k in range(3):
                    cx = fin_x - 0.62 + k * 0.62
                    pts_loop = []
                    for a_i in range(11):
                        ang = t * 7.0 + a_i * (2.0 * math.pi / 10.0)
                        pts_loop.append((cx + math.cos(ang) * 0.24, 0.08 + math.sin(ang) * 0.24, 0.14))
                    for q0, q1 in zip(pts_loop[:-1], pts_loop[1:]):
                        sc.add_cylinder(q0, q1, 0.032, 0.032, CYAN, segments=6, emissive=0.85, bloom=True, caps=False)

        elif scene_key == "spring_brakes_close":
            # TRUE 3D HELICAL COIL SPRINGS clamping twin calipers tightly onto the steel fin (ZERO floating coin stacks, ZERO air gap!)
            cam.eye = (0.0, 0.55, 6.0)
            cam.target = (0.0, -0.05, 0.0)
            clamp_p = ease_out_cubic(clamp((prog - 0.25) / 0.38, 0.0, 1.0))
            gap = 0.52 * (1.0 - clamp_p) + 0.095  # Closes flush against 0.18-thick fin (half=0.09)!
            # Central vertical steel brake fin attached to yellow car chassis above
            sc.add_box((0.0, 1.15, 0.0), (2.6, 0.32, 1.45), CAR_YELLOW, metallic=0.48, texture="painted_metal")
            sc.add_box((0.0, 0.15, 0.0), (0.18, 1.65, 2.0), STEEL_LIGHT, metallic=0.84, texture="brushed_steel")
            # Fixed outer brake housing walls + true 3D helical steel coil springs + bronze calipers!
            for sx in (-1, 1):
                sc.add_box((sx * 1.62, 0.0, 0.0), (0.28, 1.25, 1.55), STEEL_DARK, metallic=0.72, texture="brushed_steel")
                cal_col = AMBER if clamp_p < 0.85 else EMERALD
                sc.add_box((sx * (gap + 0.18), 0.0, 0.0), (0.34, 0.92, 1.48), cal_col, metallic=0.68, texture="brushed_steel")
                sc.add_coil_spring((sx * 1.48, 0.24, 0.0), (sx * (gap + 0.35), 0.24, 0.0), coil_radius=0.14, wire_radius=0.032, turns=5, rgb=STEEL_LIGHT)
                sc.add_coil_spring((sx * 1.48, -0.24, 0.0), (sx * (gap + 0.35), -0.24, 0.0), coil_radius=0.14, wire_radius=0.032, turns=5, rgb=STEEL_LIGHT)
            if prog > 0.56:
                overlays_2d.append(
                    lambda d: draw_pressure_gauge(d, 165, 1185, 86, 0.0, "AIR LINE", "0 PSI = LOCKED", p, self.font_black, invert_scale=False)
                )

        elif scene_key == "bolt_station_victory":
            # Narrator: "Smooth stop, Bolt!" -> Real theme-park sunset station dock finale!
            cam.eye = (0.0, 0.72, 7.2)
            cam.target = (0.0, 0.05, 0.0)
            arrive = ease_out_cubic(clamp(prog * 1.35, 0.0, 1.0))
            car_x = -0.82 + arrive * 0.82
            self._add_3d_coaster_track(sc, pitch=0.0, length=6.8, center=(0.0, -0.68, 0.0), with_sawtooth=False, with_station=True)
            self._add_3d_yellow_coaster_car(
                sc,
                center=(car_x, -0.58, 0.0),
                scale=1.08,
                yaw=-0.10,
                pitch=0.0,
                t=t,
                with_bolt=True,
                bolt_pose="relief_wave",
                bolt_emotion="relief",
            )

        else:  # verdict_cta_card
            cam.eye = (0.0, 0.72, 7.4)
            cam.target = (0.0, 0.05, 0.0)
            self._add_3d_coaster_track(sc, pitch=0.0, length=6.8, center=(0.0, -0.68, 0.0), with_sawtooth=False, with_station=True)
            self._add_3d_yellow_coaster_car(
                sc,
                center=(0.0, -0.58, 0.0),
                scale=1.06,
                yaw=-0.08,
                pitch=0.0,
                t=t,
                with_bolt=True,
                bolt_pose="cta_shrug",
                bolt_emotion="cta",
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "coaster_chain_snap_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("coaster_chain_snap_hero", t=0.45, prog=0.62, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
