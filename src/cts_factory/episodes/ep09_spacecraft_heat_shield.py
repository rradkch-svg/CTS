"""Episode 09: How a 3-Inch Shield Survives 5,000°F Reentry — True 3D Space Capsule, Bow Shock & Triple-Chute Splashdown."""

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
from cts_factory.engine.renderer3d import Camera3D, Scene3D, rot_matrix
from cts_factory.episodes.base import EpisodeScene, register_scene
from cts_factory.episodes.ep02_submersible_implosion_physics import _build_surface_background_bgr

HULL_WHITE = (224, 232, 242)
HULL_DARK = (42, 50, 64)
TITANIUM_LIGHT = (192, 208, 228)
CAPSULE_YELLOW = (255, 206, 36)
CAPSULE_NAVY = (24, 38, 60)
SHIELD_RESIN = (188, 128, 66)
SHIELD_CHAR = (38, 34, 38)
PLASMA_HOT = (255, 118, 26)
PLASMA_WHITE = (255, 242, 198)
CHUTE_ORANGE = (255, 108, 34)
GLASS_BLUE = (42, 168, 224)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


def _build_orbit_backdrop_bgr(w: int, h: int) -> np.ndarray:
    """Deep starry orbit + curved glowing cobalt-cyan Earth limb at bottom (BGR)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    img = np.zeros((h, w, 3), dtype=np.float32)

    # Space zenith
    img[:, :, 2] = 6.0 + 10.0 * ys
    img[:, :, 1] = 10.0 + 18.0 * ys
    img[:, :, 0] = 22.0 + 34.0 * ys

    # Curved Earth limb glow near bottom
    r_earth = np.sqrt((xs * 1.15) ** 2 + ((ys - 1.52) * 1.65) ** 2)
    limb = np.exp(-((r_earth - 0.96) / 0.065) ** 2)
    earth_body = (r_earth < 0.94).astype(np.float32)
    img[:, :, 2] += 42.0 * limb + 14.0 * earth_body
    img[:, :, 1] += 148.0 * limb + 58.0 * earth_body
    img[:, :, 0] += 235.0 * limb + 132.0 * earth_body
    bgr = np.clip(img, 0, 255).astype(np.uint8)

    rng = np.random.default_rng(909)
    for _ in range(85):
        sx = int(rng.integers(24, w - 24))
        sy = int(rng.integers(100, int(h * 0.68)))
        sr = int(rng.choice([1, 1, 2]))
        bright = int(rng.integers(170, 255))
        cv2.circle(bgr, (sx, sy), sr, (bright, bright, min(255, bright + 8)), -1, lineType=cv2.LINE_AA)
    return bgr


@register_scene("ep09_spacecraft_heat_shield")
class SpacecraftHeatShieldScene(EpisodeScene):
    """Articulated 12-beat True 3D Spacecraft Reentry, Detached Bow Shock & Triple-Chute Splashdown."""

    slug = "ep09_spacecraft_heat_shield"
    episode_id = "ep09"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_orbit_bgr: np.ndarray | None = None
        self.bg_studio_bgr: np.ndarray | None = None
        self.bg_alert_bgr: np.ndarray | None = None
        self.bg_safe_bgr: np.ndarray | None = None
        self.bg_surface_bgr: np.ndarray | None = None
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
        self.bg_orbit_bgr = _build_orbit_backdrop_bgr(w, h)
        self.bg_studio_bgr = cv2.cvtColor(
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
        self.bg_surface_bgr = _build_surface_background_bgr(w, h, waterline_y=1140)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_space_capsule(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        t: float = 0.0,
        plasma: float = 0.0,
        bow_shock_gap: float = 0.0,
        charred: float = 0.0,
        cutaway_cabin: bool = False,
        flotation_collar: bool = False,
    ) -> None:
        """Detailed 3D Gumdrop Reentry Capsule (heat shield at -Y, docking collar at +Y)."""
        R = rot_matrix(roll, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Blunt curved 3-inch ablative heat shield base (-Y)
        shield_col = lerp_color(SHIELD_RESIN, SHIELD_CHAR, clamp(charred, 0.0, 1.0))
        if plasma > 0.2:
            shield_col = lerp_color(shield_col, PLASMA_HOT, plasma * 0.45)
        sc.add_cylinder(_p(0.0, -0.78, 0.0), _p(0.0, -0.52, 0.0), 1.06 * scale, 1.24 * scale, shield_col, segments=18, metallic=0.25, emissive=0.35 * plasma)
        sc.add_sphere(_p(0.0, -0.78, 0.0), 1.05 * scale, shield_col, metallic=0.25, squash_y=0.28, emissive=0.42 * plasma)

        # Optional bright yellow ocean flotation collar ring!
        if flotation_collar:
            for i in range(16):
                a0 = i * (2.0 * math.pi / 16)
                a1 = (i + 1) * (2.0 * math.pi / 16)
                sc.add_cylinder(
                    _p(math.cos(a0) * 1.28, -0.42, math.sin(a0) * 1.28),
                    _p(math.cos(a1) * 1.28, -0.42, math.sin(a1) * 1.28),
                    0.18 * scale,
                    0.18 * scale,
                    CAPSULE_YELLOW,
                    segments=8,
                    metallic=0.32,
                )

        # Main conical pressurized crew module hull
        if not cutaway_cabin:
            sc.add_cylinder(_p(0.0, -0.52, 0.0), _p(0.0, 0.72, 0.0), 1.22 * scale, 0.62 * scale, HULL_WHITE, segments=18, metallic=0.45)
            # FailSafe yellow & navy band around mid-capsule
            sc.add_cylinder(_p(0.0, -0.18, 0.0), _p(0.0, -0.02, 0.0), 1.08 * scale, 1.00 * scale, CAPSULE_YELLOW, segments=18, metallic=0.48, caps=False)
            sc.add_cylinder(_p(0.0, -0.26, 0.0), _p(0.0, -0.18, 0.0), 1.12 * scale, 1.08 * scale, CAPSULE_NAVY, segments=18, metallic=0.45, caps=False)
            # Camera-facing circular sapphire crew window + titanium frame
            sc.add_sphere(_p(0.0, 0.22, 0.78), 0.28 * scale, TITANIUM_LIGHT, metallic=0.80)
            sc.add_sphere(_p(0.0, 0.22, 0.85), 0.22 * scale, GLASS_BLUE, metallic=0.78, emissive=0.35, rim_rgb=CYAN)
        else:
            # Cutaway back shell revealing cool emerald-lit cabin inside!
            sc.add_cylinder(_p(0.0, -0.52, -0.22), _p(0.0, 0.72, -0.22), 1.12 * scale, 0.56 * scale, HULL_DARK, segments=14, metallic=0.52)
            sc.add_cylinder(_p(0.0, -0.45, 0.0), _p(0.0, -0.35, 0.0), 1.08 * scale, 1.08 * scale, EMERALD, segments=14, emissive=0.45)

        # Top titanium docking ring & chute bay
        sc.add_cylinder(_p(0.0, 0.72, 0.0), _p(0.0, 1.02, 0.0), 0.62 * scale, 0.52 * scale, HULL_DARK, segments=16, metallic=0.68)
        sc.add_cylinder(_p(0.0, 0.98, 0.0), _p(0.0, 1.10, 0.0), 0.56 * scale, 0.56 * scale, TITANIUM_LIGHT, segments=16, metallic=0.82)

        # RCS thruster pods on flanks
        for sx in (-1, 1):
            sc.add_box(_p(sx * 0.96, -0.12, 0.0), (0.20 * scale, 0.28 * scale, 0.20 * scale), HULL_DARK, rot=(roll, yaw, pitch), metallic=0.72)

        # Glowing incandescent detached bow shock + plasma wake!
        if plasma > 0.05:
            gap = 0.28 + bow_shock_gap * 0.36
            # Glowing detached bow shock arc right beneath the blunt belly!
            for i in range(11):
                u = (i / 10.0) * 2.0 - 1.0
                sx = u * 1.58
                sy = -0.96 - gap + (u * u) * 0.68
                col = PLASMA_WHITE if abs(u) < 0.35 else PLASMA_HOT
                r_p = (0.16 - abs(u) * 0.05) * scale
                sc.add_sphere(_p(sx, sy, 0.12), r_p, col, emissive=0.96 * plasma, bloom=True)
            # Sweeping plasma streamers curling past the capsule flanks
            for side in (-1, 1):
                for k in range(5):
                    ph = (t * 3.4 + k * 0.20 + (0.1 if side > 0 else 0.0)) % 1.0
                    px = side * (1.28 + ph * 0.65)
                    py = -0.82 - gap * 0.5 + ph * 2.55
                    col = PLASMA_HOT if ph < 0.55 else DANGER
                    sc.add_cylinder(_p(px, py, 0.0), _p(px + side * 0.10, py + 0.32, 0.0), 0.08 * scale, 0.025 * scale, col, emissive=0.92 * plasma, bloom=True, segments=6)

        # Cyan cool dead-air buffer indicator inside the bow shock standoff gap!
        if bow_shock_gap > 0.35:
            for j in range(5):
                u = (j / 4.0) * 2.0 - 1.0
                sc.add_sphere(_p(u * 0.85, -1.04 + (u * u) * 0.16, 0.16), 0.095 * scale, CYAN, emissive=0.88, bloom=True)

    def _add_3d_parachutes(
        self,
        sc: Scene3D,
        capsule_top: tuple[float, float, float],
        bloom_p: float,
        t: float,
    ) -> None:
        """Three giant orange-and-white striped 3D main parachutes blooming above the capsule."""
        cx, cy, cz = capsule_top
        open_s = max(0.15, ease_out_cubic(bloom_p))
        offsets = [(-1.35, 2.35, -0.25), (0.0, 2.65, 0.20), (1.35, 2.35, -0.25)]
        for idx, (ox, oy, oz) in enumerate(offsets):
            sway = math.sin(t * 2.4 + idx * 1.4) * 0.08
            px = cx + ox * open_s + sway
            py = cy + oy * (0.45 + 0.55 * open_s)
            pz = cz + oz * open_s
            rad = 0.78 * open_s
            # Striped orange & white parachute canopy dome (segmented panels)
            sc.add_sphere((px, py, pz), rad, CHUTE_ORANGE, metallic=0.15, squash_y=0.62)
            sc.add_cylinder((px, py + rad * 0.10, pz), (px, py + rad * 0.36, pz), rad * 0.92, rad * 0.65, HULL_WHITE, segments=14, metallic=0.12, caps=False)
            # 4 crisp shroud cords linking canopy rim to capsule apex
            for a_idx in range(4):
                ang = a_idx * (math.pi * 0.5) + 0.4
                rx = px + math.cos(ang) * rad * 0.82
                rz = pz + math.sin(ang) * rad * 0.82
                sc.add_cylinder((cx, cy, cz), (rx, py - rad * 0.12, rz), 0.018, 0.014, TITANIUM_LIGHT, segments=5, metallic=0.55)

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

        bg = self.bg_orbit_bgr
        if scene_key in ("sharp_vs_blunt_nose", "ablative_layers_cutaway", "temp_gradient_bars"):
            bg = self.bg_studio_bgr
        elif scene_key in ("ablative_gas_shedding",):
            bg = self.bg_alert_bgr
        elif scene_key in ("triple_chute_descent", "bolt_ocean_splashdown", "verdict_cta_card"):
            bg = self.bg_surface_bgr
        assert bg is not None

        cam = Camera3D(eye=(0.0, 0.4, 7.2), target=(0.0, -0.05, 0.0), fov_deg=41.0, width=w, height=h)
        sc = Scene3D(cam)

        if scene_key == "capsule_plasma_hero":
            shake = math.sin(t * 48.0) * 0.09
            cam.eye = (0.45 + shake, 0.35, 6.4)
            cam.target = (0.0, -0.15, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.08, 0.0), scale=1.12, yaw=0.18, pitch=-0.28, t=t, plasma=1.0, bow_shock_gap=0.4, charred=0.6)
            overlays_2d.append(lambda d: draw_sparks(d, 540, 1140, prog, 18, 175, 140, p, seed=901))

        elif scene_key == "bolt_capsule_wave":
            # Narrator: "Buckle up, Bolt — wave goodbye to space!"
            cam.eye = (0.0, 0.62, 6.7)
            cam.target = (0.0, 0.20, 0.0)
            bob = math.sin(t * 2.6) * 0.06
            self._add_3d_space_capsule(sc, center=(0.0, -0.58 + bob, 0.0), scale=1.06, yaw=0.12, pitch=-0.06, t=t, plasma=0.12)
            # BOLT waving goodbye to space right from the open top docking ring!
            add_crash_test_dummy(
                sc,
                pos=(0.0, 0.65 + bob, 0.16),
                scale=0.92,
                yaw=0.04 + math.sin(t * 2.2) * 0.10,
                pose="relief_wave",
                emotion="cta",
                t=t,
                ground_shadow=False,
            )

            def _wave_arc(d: ImageDraw.ImageDraw) -> None:
                pulse = (t * 2.2) % 1.0
                r = int(28 + pulse * 44)
                cx, cy = 640, 560
                d.arc([cx - r, cy - r, cx + r, cy + r], start=-55, end=25, fill=p.cyan, width=4)

            overlays_2d.append(_wave_arc)

        elif scene_key == "air_compression_shock":
            cam.eye = (0.0, 0.25, 6.3)
            cam.target = (0.0, -0.25, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.42, 0.0), scale=1.05, yaw=0.10, pitch=0.0, t=t, plasma=0.85, bow_shock_gap=0.25)
            # Rising compressed air molecule spheres piling up and turning glowing orange under the belly!
            for i in range(16):
                ph = (t * 2.2 + i * 0.065) % 1.0
                mx = ((i % 5) - 2.0) * 0.56
                my = -2.35 + ph * 1.42
                col = lerp_color(CYAN, PLASMA_HOT, clamp((ph - 0.45) * 2.2, 0.0, 1.0))
                sc.add_sphere((mx, my, 0.20), 0.095, col, emissive=0.75 + ph * 0.25, bloom=True)

        elif scene_key == "sharp_vs_blunt_nose":
            cam.eye = (0.0, 0.35, 7.3)
            cam.target = (0.0, -0.05, 0.0)
            # LEFT: Sharp needle nose cone melting inside attached red shockwave!
            sc.add_cylinder((-1.48, 0.65, 0.0), (-1.48, -0.95, 0.0), 0.72, 0.05, TITANIUM_LIGHT, segments=14, metallic=0.78)
            sc.add_sphere((-1.48, -0.92, 0.0), 0.32, DANGER, emissive=0.98, bloom=True)
            for s in (-1, 1):
                sc.add_cylinder((-1.48, -1.02, 0.05), (-1.48 + s * 0.92, 0.55, 0.05), 0.045, 0.045, DANGER, segments=6, emissive=0.92, bloom=True)
            # RIGHT: Blunt capsule deflecting bow shock cleanly away!
            self._add_3d_space_capsule(sc, center=(1.42, 0.15, 0.0), scale=0.78, yaw=0.0, pitch=0.0, t=t, plasma=0.92, bow_shock_gap=0.85)
            overlays_2d.append(lambda d: draw_sparks(d, 295, 1085, prog, 14, 150, 130, p, seed=904))

            def _vs_tags(d: ImageDraw.ImageDraw) -> None:
                f_b = load_font(self.font_black, 30)
                d.rounded_rectangle([84, 540, 444, 608], radius=14, fill=p.surface_panel, outline=p.danger, width=3)
                d.text((112, 556), "POINTY = MELTS", font=f_b, fill=p.danger)
                d.rounded_rectangle([620, 540, 996, 608], radius=14, fill=p.surface_panel, outline=p.emerald, width=3)
                d.text((648, 556), "BLUNT = DEFLECTS", font=f_b, fill=p.emerald)

            overlays_2d.append(_vs_tags)

        elif scene_key == "detached_bow_shock":
            cam.eye = (0.0, 0.25, 6.2)
            cam.target = (0.0, -0.25, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.32, 0.0), scale=1.08, yaw=0.08, pitch=0.0, t=t, plasma=1.0, bow_shock_gap=1.0)
            overlays_2d.append(lambda d: draw_pressure_gauge(d, 165, 1140, 96, 0.98, "HEAT DEFLECTED", "98% PUSHED", p, self.font_black))

        elif scene_key == "bolt_bow_shock_gap":
            # Narrator: "Relax, Bolt — that curve traps a dead-air buffer ahead of you!"
            cam.eye = (0.0, 0.32, 6.2)
            cam.target = (0.0, -0.15, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.20, 0.0), scale=1.18, yaw=0.0, pitch=0.0, t=t, plasma=0.95, bow_shock_gap=1.0, cutaway_cabin=True)
            # BOLT chilling calmly inside the cool 72°F cutaway cabin!
            add_crash_test_dummy(sc, pos=(0.0, 0.28, 0.12), scale=0.66, yaw=0.05, pose="explain", emotion="relief", t=t, ground_shadow=False)

        elif scene_key == "ablative_layers_cutaway":
            cam.eye = (0.35, 0.48, 6.4)
            cam.target = (0.0, 0.0, 0.0)
            # Exploded 3-inch ablative shield cross-section stack (horizontal 3D slabs separating smoothly!)
            sep = 0.22 + 0.45 * ease_out_cubic(prog)
            # Top layer: Cool Titanium Cabin Floor (72°F)
            sc.add_box((0.0, 0.95 + sep * 0.5, 0.0), (2.75, 0.26, 1.55), TITANIUM_LIGHT, metallic=0.82)
            # Mid layer: 3-inch Virgin Phenolic Resin Honeycomb Core
            sc.add_box((0.0, 0.20, 0.0), (2.75, 0.58, 1.55), SHIELD_RESIN, metallic=0.22)
            for hx in (-0.95, -0.32, 0.32, 0.95):
                sc.add_cylinder((hx, 0.46, 0.78), (hx, -0.06, 0.78), 0.12, 0.12, AMBER, segments=6, metallic=0.35)
            # Bottom layer: Glowing Black Carbon Char Layer (burning on purpose!)
            sc.add_box((0.0, -0.68 - sep * 0.5, 0.0), (2.75, 0.30, 1.55), SHIELD_CHAR, metallic=0.18, emissive=0.35)
            sc.add_box((0.0, -0.88 - sep * 0.5, 0.0), (2.68, 0.12, 1.48), PLASMA_HOT, emissive=0.92, bloom=True)
            add_crash_test_dummy(sc, pos=(-1.72, -0.35, 0.55), scale=0.82, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "ablative_gas_shedding":
            cam.eye = (0.0, 0.25, 5.8)
            cam.target = (0.0, -0.25, 0.0)
            self._add_3d_space_capsule(sc, center=(0.0, 0.42, 0.0), scale=1.12, yaw=0.06, pitch=0.0, t=t, plasma=1.0, bow_shock_gap=0.75, charred=1.0)
            # Sacrificial glowing char-vapor particles shedding cleanly away from the shield surface!
            for i in range(14):
                ph = (t * 2.6 + i * 0.075) % 1.0
                side = -1 if i % 2 == 0 else 1
                gx = side * (0.35 + ph * 1.95)
                gy = -0.62 - (1.0 - ph) * 0.28 + ph * 1.45
                sc.add_sphere((gx, gy, 0.28), 0.095 * (1.0 - ph * 0.4), PLASMA_WHITE if ph < 0.4 else AMBER, emissive=0.95, bloom=True)

        elif scene_key == "temp_gradient_bars":
            cam.eye = (0.0, 0.65, 7.6)
            cam.target = (0.0, 0.15, 0.0)
            self._add_3d_space_capsule(sc, center=(0.55, 0.72, -0.25), scale=0.84, yaw=0.15, pitch=-0.16, t=t, plasma=0.88, bow_shock_gap=0.7, charred=0.9)
            add_crash_test_dummy(sc, pos=(-1.55, -0.28, 0.55), scale=0.84, yaw=0.36, pose="point_right", emotion="engineer", t=t)
            bar_p = ease_out_cubic(clamp(prog * 1.4, 0.0, 1.0))
            overlays_2d.append(
                lambda d, bp=bar_p: draw_comparison_bars(
                    d,
                    115,
                    1100,
                    850,
                    245,
                    [
                        ("OUTSIDE PLASMA", "5,000 DEG F", 1.0, p.danger),
                        ("BOLT'S CABIN (3 IN IN)", "72 DEG F", 0.14, p.emerald),
                    ],
                    bp,
                    p,
                    self.font_black,
                )
            )

        elif scene_key == "triple_chute_descent":
            # Three huge orange-and-white 3D parachutes bloom open above the twilight ocean!
            cam.eye = (0.0, 0.55, 8.2)
            cam.target = (0.0, 0.55, 0.0)
            chute_p = clamp(prog * 1.35, 0.0, 1.0)
            cap_y = 0.25 - prog * 0.85
            sway = math.sin(t * 2.2) * 0.09
            self._add_3d_space_capsule(sc, center=(sway, cap_y, 0.0), scale=0.86, yaw=0.10, roll=sway * 0.4, t=t, plasma=0.0, charred=1.0)
            self._add_3d_parachutes(sc, (sway, cap_y + 0.92, 0.0), bloom_p=chute_p, t=t)

        elif scene_key == "bolt_ocean_splashdown":
            # Narrator: "Welcome home, Bolt!" -> Capsule splashes gently in turquoise ocean, BOLT waves triumphantly!
            cam.eye = (0.0, 0.72, 7.2)
            cam.target = (0.0, 0.12, 0.0)
            bob = math.sin(t * 3.0) * 0.07
            self._add_3d_space_capsule(sc, center=(0.0, -0.58 + bob, 0.12), scale=1.04, yaw=0.08, roll=math.sin(t * 2.2) * 0.05, t=t, plasma=0.0, charred=1.0, flotation_collar=True)
            add_crash_test_dummy(
                sc,
                pos=(0.0, 0.62 + bob, 0.25),
                scale=0.88,
                yaw=0.06,
                pose="relief_wave",
                emotion="relief",
                t=t,
                ground_shadow=False,
            )

        else:  # verdict_cta_card
            cam.eye = (0.0, 0.72, 7.2)
            cam.target = (0.0, 0.12, 0.0)
            bob = math.sin(t * 3.0) * 0.06
            self._add_3d_space_capsule(sc, center=(0.0, -0.60 + bob, 0.12), scale=1.02, yaw=0.08, roll=math.sin(t * 2.0) * 0.04, t=t, plasma=0.0, charred=1.0, flotation_collar=True)
            add_crash_test_dummy(
                sc,
                pos=(0.0, 0.58 + bob, 0.25),
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "capsule_plasma_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("capsule_plasma_hero", t=0.45, prog=0.55, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
