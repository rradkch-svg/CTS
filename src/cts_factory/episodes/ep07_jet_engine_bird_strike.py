"""Episode 07: How a Jet Engine SURVIVES Swallowing a Bird — True 3D Turbofan + BOLT's Yellow Mini-Jet."""

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

TITANIUM_LIGHT = (196, 212, 232)
TITANIUM_MID = (122, 142, 170)
TITANIUM_DARK = (54, 68, 92)
CARBON_DARK = (34, 44, 62)
JET_YELLOW = (255, 206, 36)
JET_YELLOW_DARK = (224, 152, 22)
JET_NAVY = (24, 38, 60)
GLASS_BLUE = (42, 168, 220)
KEVLAR_GOLD = (238, 186, 62)
CORE_ORANGE = (255, 118, 28)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


def _build_sky_backdrop_bgr(w: int, h: int, horizon_y: int = 1280) -> np.ndarray:
    """Crisp open-air aerospace twilight sky + warm golden horizon glow + distant cloud deck (BGR)."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    hy = horizon_y / float(h)

    img = np.zeros((h, w, 3), dtype=np.float32)
    sky_mask = (ys < hy).astype(np.float32)
    sky_t = np.clip(ys / max(0.01, hy), 0.0, 1.0)
    sky_r = 12.0 + 52.0 * (sky_t ** 2.4) + 65.0 * (sky_t ** 5.2)
    sky_g = 26.0 + 98.0 * (sky_t ** 1.7) + 48.0 * (sky_t ** 4.2)
    sky_b = 64.0 + 118.0 * (sky_t ** 1.3) + 18.0 * (sky_t ** 3.8)

    sun_glow = np.exp(-((xs / 0.56) ** 2 + ((ys - hy * 0.90) / 0.14) ** 2))
    sky_r = sky_r + 64.0 * sun_glow
    sky_g = sky_g + 54.0 * sun_glow
    sky_b = sky_b + 26.0 * sun_glow

    deck_mask = 1.0 - sky_mask
    deck_t = np.clip((ys - hy) / max(0.01, 1.0 - hy), 0.0, 1.0)
    deck_r = 38.0 * (1.0 - deck_t * 0.65) + 14.0 * deck_t
    deck_g = 56.0 * (1.0 - deck_t * 0.62) + 22.0 * deck_t
    deck_b = 88.0 * (1.0 - deck_t * 0.52) + 42.0 * deck_t

    img[:, :, 2] = sky_r * sky_mask + deck_r * deck_mask
    img[:, :, 1] = sky_g * sky_mask + deck_g * deck_mask
    img[:, :, 0] = sky_b * sky_mask + deck_b * deck_mask
    bgr = np.clip(img, 0, 255).astype(np.uint8)

    # Soft cloud wisps near horizon
    rng = np.random.default_rng(707)
    for _ in range(18):
        cx = int(rng.integers(40, w - 40))
        cy = int(rng.integers(horizon_y - 90, horizon_y + 220))
        rx = int(rng.integers(90, 220))
        ry = int(rng.integers(14, 34))
        overlay = bgr.copy()
        cv2.ellipse(overlay, (cx, cy), (rx, ry), 0, 0, 360, (148, 136, 128), -1, lineType=cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.16, bgr, 0.84, 0, bgr)
    return bgr


@register_scene("ep07_jet_engine_bird_strike")
class JetEngineBirdStrikeScene(EpisodeScene):
    """Articulated 12-beat True 3D High-Bypass Turbofan + BOLT's Yellow Mini-Jet."""

    slug = "ep07_jet_engine_bird_strike"
    episode_id = "ep07"

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
        self.bg_sky_bgr = _build_sky_backdrop_bgr(w, h, horizon_y=1240)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _add_3d_turbofan(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        spin: float = 0.0,
        cutaway: bool = False,
        kevlar_glow: float = 0.0,
        kevlar_bulge: float = 0.0,
        missing_blade_idx: int = -1,
        detached_blade_t: float = 0.0,
        show_core_fire: bool = True,
        bypass_highlight: float = 0.0,
    ) -> None:
        """Detailed 3D High-Bypass Turbofan (inlet +X, exhaust -X, vertical +Y)."""
        R = rot_matrix(0.0, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Outer nacelle cowling rings (intake lip -> mid fan cowl -> rear exhaust)
        if not cutaway:
            sc.add_cylinder(_p(1.38, 0.0, 0.0), _p(1.12, 0.0, 0.0), 1.38 * scale, 1.54 * scale, TITANIUM_LIGHT, segments=18, metallic=0.82, caps=False)
            sc.add_cylinder(_p(1.12, 0.0, 0.0), _p(-0.95, 0.0, 0.0), 1.54 * scale, 1.46 * scale, TITANIUM_MID, segments=18, metallic=0.62, caps=False)
            sc.add_cylinder(_p(-0.95, 0.0, 0.0), _p(-1.82, 0.0, 0.0), 1.46 * scale, 1.06 * scale, TITANIUM_DARK, segments=16, metallic=0.68, caps=False)
            # Yellow FailSafe racing stripe around nacelle
            sc.add_cylinder(_p(0.65, 0.0, 0.0), _p(0.32, 0.0, 0.0), 1.56 * scale, 1.56 * scale, JET_YELLOW, segments=18, metallic=0.45, caps=False)
        else:
            # Cutaway structural upper/lower arc rails so internal fan, bypass duct, and fiery core stay crystal clear!
            for ang in np.linspace(-math.pi * 0.85, math.pi * 0.25, 9):
                ry = math.sin(ang) * 1.46
                rz = math.cos(ang) * 1.46
                sc.add_cylinder(_p(1.22, ry, rz), _p(-1.55, ry * 0.82, rz * 0.82), 0.075 * scale, 0.065 * scale, TITANIUM_MID, segments=8, metallic=0.70)
            # Inlet silver intake hoop
            for i in range(16):
                a0 = i * (2.0 * math.pi / 16)
                a1 = (i + 1) * (2.0 * math.pi / 16)
                if math.cos(a0) > 0.35 and math.sin(a0) > -0.25:
                    continue
                sc.add_cylinder(
                    _p(1.25, math.sin(a0) * 1.42, math.cos(a0) * 1.42),
                    _p(1.25, math.sin(a1) * 1.42, math.cos(a1) * 1.42),
                    0.095 * scale,
                    0.095 * scale,
                    TITANIUM_LIGHT,
                    segments=8,
                    metallic=0.84,
                )

        # Golden Kevlar containment belt wrapping the fan plane!
        if kevlar_glow > 0.02 or cutaway:
            k_col = lerp_color(KEVLAR_GOLD, AMBER, clamp(kevlar_glow, 0.0, 1.0))
            k_segs = 18
            for i in range(k_segs):
                a0 = i * (2.0 * math.pi / k_segs)
                a1 = (i + 1) * (2.0 * math.pi / k_segs)
                if cutaway and math.cos(a0) > 0.45 and math.sin(a0) > -0.1:
                    continue
                b0 = kevlar_bulge * math.exp(-((a0 - 0.55) / 0.55) ** 2)
                b1 = kevlar_bulge * math.exp(-((a1 - 0.55) / 0.55) ** 2)
                r0 = 1.56 + b0
                r1 = 1.56 + b1
                sc.add_cylinder(
                    _p(0.68, math.sin(a0) * r0, math.cos(a0) * r0),
                    _p(0.68, math.sin(a1) * r1, math.cos(a1) * r1),
                    0.12 * scale,
                    0.12 * scale,
                    k_col,
                    segments=8,
                    metallic=0.35,
                    emissive=0.45 * kevlar_glow,
                    bloom=kevlar_glow > 0.35,
                )

        # Inner high-pressure compressor & combustor core (only ~20% diameter!)
        sc.add_cylinder(_p(0.32, 0.0, 0.0), _p(-1.45, 0.0, 0.0), 0.52 * scale, 0.44 * scale, TITANIUM_DARK, segments=14, metallic=0.75)
        if show_core_fire:
            sc.add_cylinder(_p(-0.35, 0.0, 0.0), _p(-1.12, 0.0, 0.0), 0.56 * scale, 0.48 * scale, CORE_ORANGE, segments=14, emissive=0.82, bloom=True)
            sc.add_cylinder(_p(-1.42, 0.0, 0.0), _p(-2.08, 0.0, 0.0), 0.38 * scale, 0.08 * scale, TITANIUM_MID, segments=12, metallic=0.72)

        # Glowing cyan bypass duct airflow ribbons (the 80% outer ring around the core!)
        if bypass_highlight > 0.05:
            for lane in range(6):
                la = lane * (math.pi / 3.0) + 0.3
                ly = math.sin(la) * 0.98
                lz = math.cos(la) * 0.98
                phase = (spin * 0.25 + lane * 0.19) % 1.0
                fx0 = 0.65 - phase * 1.95
                fx1 = fx0 - 0.45
                sc.add_cylinder(
                    _p(fx0, ly, lz),
                    _p(fx1, ly * 0.90, lz * 0.90),
                    0.055 * scale,
                    0.032 * scale,
                    CYAN,
                    segments=6,
                    emissive=0.85 * bypass_highlight,
                    bloom=True,
                )

        # Sharp painted spinner nose cone with spiral indicator band
        sc.add_cylinder(_p(0.84, 0.0, 0.0), _p(1.56, 0.0, 0.0), 0.44 * scale, 0.04 * scale, CARBON_DARK, segments=16, metallic=0.55)
        sc.add_sphere(_p(1.54, 0.0, 0.0), 0.055 * scale, TITANIUM_LIGHT, metallic=0.85)
        # White spiral swirl markers on the rotating spinner
        for k in range(5):
            kt = k / 4.0
            sx = 0.92 + kt * 0.52
            sr = (0.42 * (1.0 - kt) + 0.07)
            sa = spin + kt * 2.8
            sc.add_sphere(_p(sx, math.sin(sa) * sr, math.cos(sa) * sr), 0.052 * scale, (242, 248, 255), emissive=0.35)

        # 14 curved wide-chord hollow titanium fan blades
        n_blades = 14
        for bi in range(n_blades):
            ang = spin + bi * (2.0 * math.pi / n_blades)
            if bi == missing_blade_idx:
                # Flying detached blade hitting the Kevlar ring!
                rad_fly = 0.65 + detached_blade_t * 0.78
                fly_a = 0.55
                b_col = lerp_color(TITANIUM_LIGHT, DANGER, clamp(detached_blade_t * 1.2, 0.0, 1.0))
                sc.add_box(
                    _p(0.66, math.sin(fly_a) * rad_fly, math.cos(fly_a) * rad_fly),
                    (0.14 * scale, 0.62 * scale, 0.22 * scale),
                    b_col,
                    rot=(fly_a + detached_blade_t * 0.9, yaw + 0.35, pitch),
                    metallic=0.82,
                    emissive=0.30 if detached_blade_t > 0.3 else 0.0,
                )
                continue
            by = math.sin(ang) * 0.88
            bz = math.cos(ang) * 0.88
            # Blade root -> twisted wide-chord tip
            tip_a = ang + 0.16
            ty = math.sin(tip_a) * 1.32
            tz = math.cos(tip_a) * 1.32
            sc.add_cylinder(_p(0.76, math.sin(ang) * 0.38, math.cos(ang) * 0.38), _p(0.68, by, bz), 0.085 * scale, 0.11 * scale, TITANIUM_LIGHT, segments=6, metallic=0.84)
            sc.add_cylinder(_p(0.68, by, bz), _p(0.62, ty, tz), 0.11 * scale, 0.082 * scale, TITANIUM_MID, segments=6, metallic=0.86)

    def _add_3d_yellow_minijet(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        t: float = 0.0,
        with_pilot: bool = True,
        pilot_pose: str = "pilot_sub",
        pilot_emotion: str = "curious",
        afterburner: bool = True,
    ) -> None:
        """BOLT's Signature 3D Yellow Mini-Jet (nose +X, tail -X, top +Y)."""
        R = rot_matrix(roll, yaw, pitch)
        origin = np.array(center, dtype=np.float32)

        def _p(x: float, y: float, z: float) -> tuple[float, float, float]:
            v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
            return tuple((origin + R @ v).tolist())

        # Streamlined yellow fuselage loft (pointed nose -> cockpit mid -> tapered tail)
        loft = [(1.65, 0.08), (1.10, 0.34), (0.35, 0.48), (-0.65, 0.44), (-1.55, 0.24)]
        for (x0, r0), (x1, r1) in zip(loft[:-1], loft[1:]):
            sc.add_cylinder(_p(x0, 0.0, 0.0), _p(x1, 0.0, 0.0), r0 * scale, r1 * scale, JET_YELLOW, segments=16, metallic=0.48, caps=False)
        sc.add_sphere(_p(1.66, 0.0, 0.0), 0.095 * scale, TITANIUM_LIGHT, metallic=0.85)
        # Navy racing stripe along fuselage
        sc.add_cylinder(_p(0.75, -0.02, 0.0), _p(-0.85, -0.02, 0.0), 0.49 * scale, 0.44 * scale, JET_NAVY, segments=16, metallic=0.45, caps=False)
        sc.add_cylinder(_p(0.70, 0.02, 0.0), _p(-0.80, 0.02, 0.0), 0.495 * scale, 0.445 * scale, JET_YELLOW, segments=16, metallic=0.50, caps=False)

        # Open cockpit rim + front sapphire windscreen
        sc.add_cylinder(_p(0.28, 0.34, 0.0), _p(0.22, 0.56, 0.0), 0.36 * scale, 0.32 * scale, JET_NAVY, segments=14, metallic=0.55)
        sc.add_sphere(_p(0.58, 0.42, 0.0), 0.24 * scale, GLASS_BLUE, metallic=0.78, rim_rgb=CYAN)

        # Swept yellow main wings + cyan navigation wingtip LEDs + underwing mini-turbofans!
        for sz in (-1, 1):
            sc.add_box(_p(-0.18, -0.04, sz * 1.05), (0.68 * scale, 0.075 * scale, 1.38 * scale), JET_YELLOW_DARK, rot=(roll, yaw - sz * 0.26, pitch), metallic=0.54)
            # Wingtip glowing nav beacon
            tip_col = EMERALD if sz > 0 else DANGER
            sc.add_sphere(_p(-0.42, -0.02, sz * 1.72), 0.075 * scale, tip_col, emissive=0.92, bloom=True)
            # Underwing turbofan engine pod
            sc.add_cylinder(_p(0.22, -0.32, sz * 0.82), _p(-0.46, -0.32, sz * 0.82), 0.24 * scale, 0.20 * scale, TITANIUM_LIGHT, segments=12, metallic=0.78)
            sc.add_sphere(_p(0.24, -0.32, sz * 0.82), 0.14 * scale, CARBON_DARK, metallic=0.60)
            if afterburner:
                sc.add_cylinder(_p(-0.48, -0.32, sz * 0.82), _p(-0.82, -0.32, sz * 0.82), 0.13 * scale, 0.03 * scale, CYAN, segments=8, emissive=0.90, bloom=True)

        # Swept vertical tail fin + horizontal stabilizers
        sc.add_box(_p(-1.26, 0.46, 0.0), (0.58 * scale, 0.72 * scale, 0.07 * scale), JET_YELLOW_DARK, rot=(roll, yaw, pitch - 0.22), metallic=0.56)
        sc.add_box(_p(-1.32, 0.08, 0.0), (0.40 * scale, 0.06 * scale, 1.18 * scale), JET_NAVY, rot=(roll, yaw, pitch), metallic=0.58)

        # Rear exhaust nozzle
        sc.add_cylinder(_p(-1.52, 0.0, 0.0), _p(-1.74, 0.0, 0.0), 0.25 * scale, 0.20 * scale, TITANIUM_DARK, segments=12, metallic=0.78)
        if afterburner:
            flicker = 0.88 + 0.18 * math.sin(t * 28.0)
            sc.add_cylinder(_p(-1.74, 0.0, 0.0), _p(-1.74 - 0.58 * flicker, 0.0, 0.0), 0.17 * scale, 0.04 * scale, CORE_ORANGE, segments=10, emissive=0.95, bloom=True)

        if with_pilot:
            add_crash_test_dummy(
                sc,
                pos=_p(0.24, 0.46, 0.0),
                scale=0.56 * scale,
                yaw=yaw + 0.22,
                pose=pilot_pose,
                emotion=pilot_emotion,
                t=t,
                ground_shadow=False,
            )

    def _add_kinetic_bird_silhouette(
        self,
        sc: Scene3D,
        pos: tuple[float, float, float],
        scale: float = 0.34,
        wing_t: float = 0.0,
        glow: float = 0.5,
    ) -> None:
        """Clean geometric high-speed aerospace test-mass / bird silhouette (non-graphic, engineering style)."""
        x, y, z = pos
        flap = math.sin(wing_t * 16.0) * 0.22
        body_col = lerp_color((226, 236, 248), AMBER, glow * 0.45)
        sc.add_cylinder((x - 0.35 * scale, y, z), (x + 0.38 * scale, y + 0.04 * scale, z), 0.14 * scale, 0.18 * scale, body_col, metallic=0.30, emissive=0.35 * glow, segments=10)
        for sz in (-1, 1):
            sc.add_box((x - 0.04 * scale, y + flap * scale, z + sz * 0.42 * scale), (0.28 * scale, 0.05 * scale, 0.64 * scale), body_col, rot=(sz * flap, 0.0, 0.0), metallic=0.25, emissive=0.25 * glow)

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
        if scene_key in ("turbofan_impact_hero", "blade_off_snap"):
            bg = self.bg_alert_bgr
        elif scene_key in ("kevlar_catch_climax", "thrust_margin_bars"):
            bg = self.bg_safe_bgr
        elif scene_key in ("bolt_jet_safe_cruise", "verdict_cta_card"):
            bg = self.bg_sky_bgr
        assert bg is not None

        cam = Camera3D(eye=(0.0, 0.8, 7.6), target=(0.0, -0.05, 0.0), fov_deg=41.0, width=w, height=h)
        sc = Scene3D(cam)

        if scene_key == "turbofan_impact_hero":
            shake = math.sin(t * 48.0) * 0.12 if prog > 0.45 else 0.0
            cam.eye = (0.8 + shake, 0.65, 6.9)
            cam.target = (0.0, -0.05, 0.0)
            self._add_3d_turbofan(sc, center=(-0.35, 0.0, 0.0), scale=1.08, yaw=-0.42, spin=t * 14.0, kevlar_glow=0.35)
            # High-speed test bird silhouette approaching intake with glowing cyan/red velocity streaks
            bx = 2.65 - ease_out_cubic(min(1.0, prog * 1.45)) * 1.95
            self._add_kinetic_bird_silhouette(sc, (bx, 0.18, 0.65), scale=0.48, wing_t=t, glow=0.85)
            for k in range(4):
                sc.add_cylinder((bx + 0.35 + k * 0.12, 0.18 + (k - 1.5) * 0.12, 0.65), (bx + 1.05 + k * 0.12, 0.18 + (k - 1.5) * 0.12, 0.65), 0.025, 0.01, DANGER, segments=6, emissive=0.90, bloom=True)
            if prog > 0.48:
                impact_p = clamp((prog - 0.48) / 0.52, 0.0, 1.0)
                overlays_2d.append(lambda d, ip=impact_p: draw_sparks(d, 540, 880, ip, 16, 170, 140, p, seed=701))

        elif scene_key == "bolt_jet_wave_intro":
            # Narrator directly greets BOLT: "Hey Bolt, wave before we fire the test cannon!"
            cam.eye = (0.4, 0.72, 6.7)
            cam.target = (0.0, 0.10, 0.0)
            # Spinning test turbofan in rear right + BOLT waving happily from his 3D Yellow Mini-Jet!
            self._add_3d_turbofan(sc, center=(1.55, -0.15, -1.65), scale=0.72, yaw=-0.55, spin=t * 11.0, kevlar_glow=0.25)
            bob = math.sin(t * 3.0) * 0.06
            self._add_3d_yellow_minijet(
                sc,
                center=(-0.32, -0.35 + bob, 0.35),
                scale=1.08,
                yaw=0.24,
                pitch=0.05,
                t=t,
                with_pilot=False,
                afterburner=False,
            )
            # Large expressive BOLT standing right in the open cockpit WAVING directly at the viewer!
            add_crash_test_dummy(
                sc,
                pos=(-0.05, 0.42 + bob, 0.48),
                scale=0.92,
                yaw=0.05 + math.sin(t * 2.4) * 0.10,
                pose="relief_wave",
                emotion="cta",
                t=t,
                ground_shadow=False,
            )

            def _wave_tag(d: ImageDraw.ImageDraw) -> None:
                # Subtle friendly radar pulse arc near Bolt's waving hand
                pulse = (t * 2.2) % 1.0
                r = int(28 + pulse * 44)
                cx, cy = 620, 625
                d.arc([cx - r, cy - r, cx + r, cy + r], start=-55, end=25, fill=p.cyan, width=4)

            overlays_2d.append(_wave_tag)

        elif scene_key == "spinner_cone_deflect":
            cam.eye = (1.6, 0.55, 5.4)
            cam.target = (0.65, 0.0, 0.0)
            self._add_3d_turbofan(sc, center=(-0.45, 0.0, 0.0), scale=1.18, yaw=-0.35, spin=t * 12.0, cutaway=False)
            # Glowing outward deflection ribbons peeling off the sharp nose cone
            for ang in (-0.85, -0.35, 0.35, 0.85):
                ph = (t * 2.4 + abs(ang)) % 1.0
                x0 = 1.65 - ph * 1.15
                rad = 0.08 + (ph ** 1.3) * 1.05
                sc.add_sphere((x0, math.sin(ang) * rad, math.cos(ang) * rad * 0.6 + 0.2), 0.09, AMBER, emissive=0.92, bloom=True)
                sc.add_cylinder(
                    (1.55, 0.0, 0.25),
                    (0.55, math.sin(ang) * 1.05, math.cos(ang) * 0.65 + 0.25),
                    0.028,
                    0.045,
                    CYAN,
                    segments=6,
                    emissive=0.75,
                    bloom=True,
                )

        elif scene_key == "titanium_fan_blades":
            cam.eye = (0.2, 0.55, 6.2)
            cam.target = (0.0, 0.0, 0.0)
            # Exploded 3D close-up of curved wide-chord hollow titanium fan blade + truss core
            rot_y = -0.35 + math.sin(t * 1.6) * 0.28
            # Blade root dovetail
            sc.add_box((0.0, -1.55, 0.0), (0.65, 0.42, 0.34), TITANIUM_DARK, rot=(0.0, rot_y, 0.0), metallic=0.80)
            # Curved wide-chord titanium shell panels (cutaway showing internal truss ribs!)
            for seg in range(6):
                sy = -1.15 + seg * 0.44
                twist = rot_y + seg * 0.09
                w_seg = 0.85 + seg * 0.08
                sc.add_box((0.0, sy, -0.10), (w_seg, 0.40, 0.07), TITANIUM_LIGHT, rot=(0.0, twist, 0.05), metallic=0.86)
                # Glowing cyan internal hollow honeycomb/truss ribs!
                sc.add_cylinder((-w_seg * 0.38, sy - 0.16, 0.04), (w_seg * 0.38, sy + 0.16, 0.04), 0.032, 0.032, CYAN, segments=6, emissive=0.85, bloom=True)
                sc.add_cylinder((w_seg * 0.38, sy - 0.16, 0.04), (-w_seg * 0.38, sy + 0.16, 0.04), 0.032, 0.032, CYAN, segments=6, emissive=0.85, bloom=True)
            add_crash_test_dummy(sc, pos=(-1.62, -0.65, 0.45), scale=0.82, yaw=0.35, pose="point_right", emotion="curious", t=t)

        elif scene_key == "blade_radial_fling":
            cam.eye = (0.9, 0.6, 6.4)
            cam.target = (0.0, 0.0, 0.0)
            self._add_3d_turbofan(sc, center=(0.0, 0.0, 0.0), scale=1.08, yaw=-0.55, spin=t * 15.0, cutaway=True, bypass_highlight=0.75)
            # Centrifugal outward spiraling glowing amber debris streams
            for i in range(10):
                ph = (t * 2.2 + i * 0.11) % 1.0
                ang = i * 0.62 + ph * 2.2
                rad = 0.35 + ph * 1.05
                sc.add_sphere((0.55 - ph * 1.45, math.sin(ang) * rad, math.cos(ang) * rad), 0.085, AMBER, emissive=0.90, bloom=True)

        elif scene_key == "bypass_duct_xray":
            cam.eye = (0.0, 0.5, 7.2)
            cam.target = (0.0, 0.0, 0.0)
            self._add_3d_turbofan(sc, center=(0.0, 0.05, 0.0), scale=1.12, yaw=-0.12, spin=t * 12.0, cutaway=True, show_core_fire=True, bypass_highlight=1.0)
            # Highlight rings showing 80% outer bypass vs 20% inner core
            def _bypass_labels(d: ImageDraw.ImageDraw) -> None:
                f_b = load_font(self.font_black, 30)
                f_s = load_font(self.font_bold, 22)
                d.rounded_rectangle([72, 540, 412, 626], radius=14, fill=p.surface_panel, outline=p.cyan, width=3)
                d.text((92, 554), "80% BYPASS DUCT", font=f_b, fill=p.cyan)
                d.text((92, 592), "WIDE HOLLOW TUNNEL", font=f_s, fill=TITANIUM_LIGHT)
                d.rounded_rectangle([658, 1140, 1008, 1226], radius=14, fill=p.surface_panel, outline=p.amber, width=3)
                d.text((678, 1154), "20% INNER CORE", font=f_b, fill=p.amber)
                d.text((678, 1192), "STAYS UNTOUCHED", font=f_s, fill=TITANIUM_LIGHT)

            overlays_2d.append(_bypass_labels)

        elif scene_key == "debris_bypass_exit":
            # Narrator: "Hold tight, Bolt!" -> BOLT braces inside his cockpit as debris shoots cleanly out the bypass exit!
            cam.eye = (0.0, 0.65, 7.3)
            cam.target = (0.0, 0.0, 0.0)
            self._add_3d_turbofan(sc, center=(0.45, 0.20, -0.35), scale=0.98, yaw=-0.20, spin=t * 16.0, cutaway=True, show_core_fire=True, bypass_highlight=1.0)
            # Debris streaks exiting cleanly behind the engine far away from the inner core
            for i in range(12):
                ph = (t * 2.8 + i * 0.09) % 1.0
                ex = 0.95 - ph * 3.1
                ey = (0.98 if i % 2 == 0 else -0.92) + math.sin(ph * 6.0 + i) * 0.08
                sc.add_cylinder((ex + 0.24, ey + 0.20, -0.15), (ex, ey + 0.20, -0.15), 0.042, 0.025, AMBER, emissive=0.92, bloom=True, segments=6)
            # BOLT bracing tightly on the left foreground!
            add_crash_test_dummy(
                sc,
                pos=(-1.55, -0.68, 0.72),
                scale=0.88,
                yaw=0.35,
                pose="brace_impact",
                emotion="brace",
                t=t,
            )

        elif scene_key == "blade_off_snap":
            shake = math.sin(t * 54.0) * 0.14 * clamp((prog - 0.25) * 2.5, 0.0, 1.0)
            cam.eye = (0.85 + shake, 0.45, 5.7)
            cam.target = (0.15, 0.15, 0.0)
            snap_t = ease_out_cubic(clamp((prog - 0.22) / 0.78, 0.0, 1.0))
            self._add_3d_turbofan(
                sc,
                center=(-0.20, 0.0, 0.0),
                scale=1.15,
                yaw=-0.45,
                spin=t * 16.0,
                cutaway=True,
                kevlar_glow=0.35 + snap_t * 0.55,
                kevlar_bulge=snap_t * 0.18,
                missing_blade_idx=3 if prog > 0.22 else -1,
                detached_blade_t=snap_t,
            )
            if prog > 0.25:
                overlays_2d.append(lambda d, sp=snap_t: draw_sparks(d, 610, 740, sp, 20, 175, 145, p, seed=708))

        elif scene_key == "kevlar_catch_climax":
            cam.eye = (0.55, 0.52, 5.9)
            cam.target = (0.0, 0.12, 0.0)
            catch_p = ease_out_cubic(clamp(prog * 1.25, 0.0, 1.0))
            bulge = math.sin(catch_p * math.pi) * 0.34 + 0.12 * catch_p
            self._add_3d_turbofan(
                sc,
                center=(-0.15, 0.0, 0.0),
                scale=1.12,
                yaw=-0.42,
                spin=t * (10.0 * (1.0 - catch_p * 0.7)),
                cutaway=True,
                kevlar_glow=1.0,
                kevlar_bulge=bulge,
                missing_blade_idx=3,
                detached_blade_t=0.95,
            )
            overlays_2d.append(lambda d, cp=catch_p: draw_sparks(d, 625, 725, cp, 18, 170, 140, p, seed=709))
            overlays_2d.append(lambda d, cp=catch_p: draw_pressure_gauge(d, 165, 1140, 96, 0.25 + 0.70 * cp, "KEVLAR LOAD", f"{int(45 + cp * 55)}% CAUGHT", p, self.font_black))

        elif scene_key == "thrust_margin_bars":
            cam.eye = (0.0, 0.65, 7.6)
            cam.target = (0.0, 0.15, 0.0)
            self._add_3d_yellow_minijet(sc, center=(0.45, 0.68, -0.2), scale=0.86, yaw=-0.45, pitch=0.10, t=t, with_pilot=True, pilot_pose="pilot_sub", pilot_emotion="relief", afterburner=True)
            add_crash_test_dummy(sc, pos=(-1.55, -0.30, 0.55), scale=0.82, yaw=0.38, pose="point_right", emotion="engineer", t=t)
            bar_p = ease_out_cubic(clamp(prog * 1.4, 0.0, 1.0))
            overlays_2d.append(
                lambda d, bp=bar_p: draw_comparison_bars(
                    d,
                    115,
                    1100,
                    850,
                    245,
                    [
                        ("2 ENGINES NORMAL", "200% THRUST", 1.0, p.cyan),
                        ("1 ENGINE FAILED", "100% SAFE CLIMB", 0.58, p.emerald),
                    ],
                    bp,
                    p,
                    self.font_black,
                )
            )

        elif scene_key == "bolt_jet_safe_cruise":
            # Open-sky twilight finale! Narrator: "Nice landing, Bolt."
            cam.eye = (0.0, 0.68, 7.1)
            cam.target = (0.0, 0.05, 0.0)
            glide = ease_in_out_cubic(prog)
            bob = math.sin(t * 3.2) * 0.08
            self._add_3d_yellow_minijet(
                sc,
                center=(-0.35 + glide * 0.45, -0.08 + bob, 0.25),
                scale=1.18,
                yaw=-0.28 + glide * 0.22,
                pitch=0.06,
                roll=math.sin(t * 2.2) * 0.05,
                t=t,
                with_pilot=False,
                afterburner=True,
            )
            add_crash_test_dummy(
                sc,
                pos=(-0.08 + glide * 0.45, 0.72 + bob, 0.42),
                scale=0.86,
                yaw=0.08,
                pose="relief_wave",
                emotion="relief",
                t=t,
                ground_shadow=False,
            )

        else:  # verdict_cta_card
            cam.eye = (0.0, 0.72, 7.2)
            cam.target = (0.0, 0.10, 0.0)
            bob = math.sin(t * 3.0) * 0.06
            self._add_3d_yellow_minijet(
                sc,
                center=(0.0, -0.34 + bob, 0.15),
                scale=1.10,
                yaw=-0.22,
                pitch=0.04,
                t=t,
                with_pilot=False,
                afterburner=True,
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "turbofan_impact_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("turbofan_impact_hero", t=0.45, prog=0.52, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
