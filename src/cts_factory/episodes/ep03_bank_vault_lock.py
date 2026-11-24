"""Episode 03: Inside a Bank Vault Door Built to NEVER Open — True 3D PBR + UNIT-01."""

from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette, build_stage_background, lerp_color
from cts_factory.engine.primitives import (
    draw_dotted_arc,
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes.base import EpisodeScene, register_scene

STEEL_LIGHT = (192, 210, 228)
STEEL_MID = (118, 138, 166)
STEEL_DARK = (52, 68, 92)
COPPER = (224, 118, 56)
BRASS = (224, 174, 72)
AMBER = (255, 146, 28)
CYAN = (0, 212, 255)
GLASS_CYAN = (90, 232, 255)
DANGER = (255, 46, 76)
EMERALD = (46, 229, 139)


@register_scene("ep03_bank_vault_lock")
class BankVaultLockScene(EpisodeScene):
    """Articulated 12-beat True 3D Bank Vault Mechanism + Crash-Test Dummy ('UNIT-01') scene."""

    slug = "ep03_bank_vault_lock"
    episode_id = "ep03"

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

    def _add_3d_vault_door(
        self,
        sc: Scene3D,
        center: tuple[float, float, float] = (0.35, 0.08, 0.0),
        radius: float = 1.25,
        bolt_ext: float = 1.0,
        wheel_ang: float = 0.0,
        deadbolts_fired: bool = False,
        xray_mode: bool = False,
    ) -> None:
        """Massive 20-ton circular 3D steel bank vault door with radial locking bolts & brass wheel."""
        cx, cy, cz = center
        # Heavy surrounding steel vault wall frame ring (16 segments)
        ring_r = radius * 1.24
        n_ring = 16
        seg_len = 2.0 * math.pi * ring_r / n_ring + 0.05
        for i in range(n_ring):
            a = i * (2.0 * math.pi / n_ring)
            sc.add_box(
                (cx + math.cos(a) * ring_r, cy + math.sin(a) * ring_r, cz - 0.14),
                (0.24, seg_len, 0.42),
                STEEL_DARK,
                rot=(0.0, 0.0, a),
                metallic=0.72,
            )

        # Main circular 20-ton vault door disc
        door_alpha = 0.42 if xray_mode else 1.0
        sc.add_cylinder(
            (cx, cy, cz - 0.18),
            (cx, cy, cz + 0.14),
            radius,
            radius * 0.98,
            STEEL_MID if not xray_mode else STEEL_DARK,
            segments=24,
            metallic=0.78,
            alpha=door_alpha,
        )
        # Stepped brushed-steel bevel rim
        sc.add_cylinder(
            (cx, cy, cz + 0.12),
            (cx, cy, cz + 0.22),
            radius * 0.88,
            radius * 0.84,
            STEEL_LIGHT,
            segments=24,
            metallic=0.82,
            alpha=door_alpha,
        )

        # 12 massive radial 4-inch solid chrome locking bolts driven outward by cam ring
        n_bolts = 12
        for i in range(n_bolts):
            a = i * (2.0 * math.pi / n_bolts)
            r0 = radius * 0.46
            r1 = radius * (0.86 + 0.34 * bolt_ext)
            p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0, cz + 0.06)
            p1 = (cx + math.cos(a) * r1, cy + math.sin(a) * r1, cz + 0.06)
            bolt_col = DANGER if deadbolts_fired and (i % 3 == 0) else STEEL_LIGHT
            sc.add_cylinder(
                p0,
                p1,
                0.088,
                0.088,
                bolt_col,
                segments=10,
                metallic=0.84,
                emissive=0.45 if (deadbolts_fired and i % 3 == 0) else 0.0,
                bloom=(deadbolts_fired and i % 3 == 0),
            )

        # Central geared brass cam ring
        sc.add_gear_3d((cx, cy, cz + 0.20), radius * 0.42, 0.14, 14, wheel_ang, BRASS, metallic=0.78)

        # Front 4-spoke brass vault handwheel
        wz = cz + 0.44
        sc.add_cylinder((cx, cy, cz + 0.22), (cx, cy, wz), 0.11, 0.11, STEEL_DARK, segments=12, metallic=0.80)
        for sp in range(4):
            sa = wheel_ang + sp * (math.pi * 0.5)
            sc.add_cylinder(
                (cx, cy, wz),
                (cx + math.cos(sa) * radius * 0.42, cy + math.sin(sa) * radius * 0.42, wz),
                0.048,
                0.048,
                BRASS,
                segments=8,
                metallic=0.80,
            )
            sc.add_sphere(
                (cx + math.cos(sa) * radius * 0.44, cy + math.sin(sa) * radius * 0.44, wz),
                0.085,
                AMBER,
                metallic=0.65,
            )
        sc.add_sphere((cx, cy, wz + 0.02), 0.14, BRASS, metallic=0.82)

        # If relocker deadbolts fired, add 4 glowing crimson perpendicular jam bars across the face!
        if deadbolts_fired:
            for a_deg in (45, 135, 225, 315):
                ar = math.radians(a_deg)
                p0 = (cx + math.cos(ar) * radius * 0.28, cy + math.sin(ar) * radius * 0.28, cz + 0.34)
                p1 = (cx + math.cos(ar) * radius * 1.15, cy + math.sin(ar) * radius * 1.15, cz + 0.34)
                sc.add_cylinder(p0, p1, 0.078, 0.078, DANGER, segments=10, emissive=0.75, bloom=True)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_steel_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("carbide_drill_approach", "glass_relocker_plate", "deadbolts_fire_jam", "vault_permanently_sealed"):
            bg = self.bg_alert_bgr
        elif scene_key in ("verdict_cta_card",):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_steel_bgr

        shake = math.sin(t * 58.0) * 0.06 if scene_key in ("carbide_drill_approach", "deadbolts_fire_jam") else 0.0

        if scene_key == "vault_door_hero":
            # FRAME 0 HERO: Massive 20-ton circular vault door + 12 radial bolts + UNIT-01 straining to open it!
            cam = Camera3D(eye=(-1.2 + math.sin(t * 1.1) * 0.35, 0.65, 6.25), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_vault_door(
                sc,
                center=(0.48, 0.02, 0.0),
                radius=1.22,
                bolt_ext=0.88 + 0.12 * math.sin(t * 6.0),
                wheel_ang=math.sin(t * 5.0) * 0.14,
            )
            add_crash_test_dummy(sc, pos=(-1.42, -0.82, 0.72), scale=0.78, yaw=0.45, pose="brace_impact", emotion="panic", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 640, 960, t, 14, 210, 180, p, seed=31))

        elif scene_key == "armor_layers_exploded":
            # Exploded 3D stacked armor plates floating cleanly apart!
            cam = Camera3D(eye=(2.35, 0.95, 6.35), target=(0.10, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            sep = 0.28 + ease_out_cubic(prog) * 0.42
            layers = [
                (-sep * 1.5, STEEL_LIGHT, None, 0.80),
                (-sep * 0.5, STEEL_DARK, "carbon_weave", 0.65),
                (sep * 0.5, COPPER, "machined_brass", 0.78),
                (sep * 1.5, BRASS, "machined_brass", 0.74),
            ]
            for ox, col, tex, met in layers:
                sc.add_box((0.65 + ox, 0.12, 0.0), (0.16, 2.25, 1.85), col, metallic=met, texture=tex)
            sc.add_arrow_3d((0.65 - sep * 2.1, 1.55, 0.2), (0.65 + sep * 2.1, 1.55, 0.2), CYAN, shaft_r=0.065, head_r=0.16)
            add_crash_test_dummy(sc, pos=(-1.48, -0.86, 0.72), scale=0.74, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "copper_heat_shield":
            # Oxy-acetylene torch hitting outer steel while copper sheet wicks heat sideways!
            cam = Camera3D(eye=(-1.45, 0.78, 6.15), target=(0.15, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Outer manganese steel plate + thick copper thermal spreader behind it
            sc.add_box((0.45, 0.15, 0.35), (2.20, 1.95, 0.22), STEEL_DARK, metallic=0.68)
            sc.add_box((0.45, 0.15, -0.05), (2.30, 2.05, 0.34), COPPER, metallic=0.78, texture="machined_brass")
            # Glowing plasma torch jet hitting center-front
            sc.add_cylinder((0.45, 0.15, 1.45), (0.45, 0.15, 0.55), 0.11, 0.07, STEEL_LIGHT, segments=12, metallic=0.80)
            sc.add_sphere((0.45, 0.15, 0.48), 0.24 + 0.04 * math.sin(t * 28.0), AMBER, emissive=0.95, rim_rgb=DANGER, bloom=True)
            sc.add_sphere((0.45, 0.15, 0.52), 0.13, (255, 252, 225), emissive=1.0, bloom=True)
            # Heat dispersion arrows wicking outward sideways through copper plate!
            for dx, dy in ((1.0, 0.0), (-1.0, 0.0), (0.0, 0.95), (0.0, -0.95)):
                sc.add_arrow_3d((0.45 + dx * 0.35, 0.15 + dy * 0.35, 0.0), (0.45 + dx * 1.35, 0.15 + dy * 1.25, 0.0), CYAN, shaft_r=0.06, head_r=0.145)
            add_crash_test_dummy(sc, pos=(-1.46, -0.88, 0.72), scale=0.74, yaw=0.38, pose="brace_impact", emotion="curious", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 635, 920, t, 20, 180, 150, p, seed=33))

        elif scene_key == "radial_bolts_cam":
            # X-ray geared cam ring driving all radial steel bolts outward simultaneously!
            cam = Camera3D(eye=(1.35, 0.70, 6.25), target=(0.05, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            ext = ease_in_out_cubic(clamp(prog * 1.2))
            self._add_3d_vault_door(
                sc,
                center=(0.55, 0.08, 0.0),
                radius=1.18,
                bolt_ext=ext,
                wheel_ang=prog * 2.4,
                xray_mode=True,
            )
            add_crash_test_dummy(sc, pos=(-1.46, -0.86, 0.72), scale=0.74, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "dual_combination_wheels":
            # Dual 3-wheel CNC brass combination lock stacks aligning their tiny notched gates!
            cam = Camera3D(eye=(-1.45, 0.85, 6.25), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            align = ease_in_out_cubic(clamp((prog - 0.15) / 0.70))
            for lock_idx, ly in enumerate((0.72, -0.68)):
                for w_idx in range(3):
                    wz = -0.35 + w_idx * 0.36
                    ang = (1.0 - align) * (2.6 + w_idx * 1.5 + lock_idx * 1.1)
                    sc.add_gear_3d((0.62, ly, wz), 0.52, 0.14, 14, ang, BRASS, metallic=0.78)
                    # Glowing cyan notch indicator aligning at top (angle = pi/2)
                    na = math.pi * 0.5 + ang
                    sc.add_sphere(
                        (0.62 + math.cos(na) * 0.44, ly + math.sin(na) * 0.44, wz + 0.09),
                        0.08,
                        EMERALD if align > 0.85 else CYAN,
                        emissive=0.85,
                        bloom=True,
                    )
                # Steel locking fence bar dropping into aligned gates!
                fence_y = ly + 0.72 - (0.20 if align > 0.85 else 0.0)
                sc.add_box((0.62, fence_y, 0.0), (0.14, 0.18, 1.15), EMERALD if align > 0.85 else STEEL_LIGHT, metallic=0.72, emissive=0.35 if align > 0.85 else 0.0)
            add_crash_test_dummy(sc, pos=(-1.45, -0.86, 0.72), scale=0.74, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "triple_time_lock":
            # Triple-redundant wind-up mechanical time-lock clocks ticking in unison!
            cam = Camera3D(eye=(0.45, 0.55, 6.20), target=(0.05, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Machined brass time-lock housing box holding 3 mechanical movements
            sc.add_box((0.55, 0.20, -0.22), (2.75, 1.38, 0.36), STEEL_DARK, metallic=0.72)
            for idx, ox in enumerate((-0.82, 0.0, 0.82)):
                cx_c = 0.55 + ox
                sc.add_cylinder((cx_c, 0.22, -0.02), (cx_c, 0.22, 0.14), 0.38, 0.38, BRASS, segments=18, metallic=0.80)
                sc.add_cylinder((cx_c, 0.22, 0.14), (cx_c, 0.22, 0.18), 0.31, 0.31, (18, 28, 44), segments=18, metallic=0.35)
                # Ticking brass & cyan clock hands
                ha = -math.pi * 0.5 + math.floor(t * 2.0) * 0.32
                sc.add_cylinder((cx_c, 0.22, 0.22), (cx_c + math.cos(ha) * 0.25, 0.22 + math.sin(ha) * 0.25, 0.22), 0.028, 0.022, CYAN, segments=8, emissive=0.75, bloom=True)
                sc.add_sphere((cx_c, 0.22, 0.24), 0.055, AMBER, metallic=0.78)
            # Heavy horizontal steel dogging blocker bar below clocks
            sc.add_box((0.55, -0.82, 0.05), (2.55, 0.26, 0.32), AMBER, metallic=0.68, texture="machined_brass")
            add_crash_test_dummy(sc, pos=(-1.52, -0.88, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "time_lock_bar_block":
            # Exploded diagram: 1 clock stopped (red), 2 backup clocks still running (emerald) keeping bar locked!
            cam = Camera3D(eye=(-1.30, 0.72, 6.25), target=(0.10, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            sc.add_box((0.60, 0.35, -0.20), (2.65, 1.18, 0.32), STEEL_DARK, metallic=0.70)
            for idx, ox in enumerate((-0.80, 0.0, 0.80)):
                cx_c = 0.60 + ox
                dead = (idx == 0)
                rim_col = DANGER if dead else EMERALD
                sc.add_cylinder((cx_c, 0.35, 0.0), (cx_c, 0.35, 0.16), 0.36, 0.36, rim_col, segments=16, metallic=0.62, emissive=0.45, bloom=True)
                sc.add_cylinder((cx_c, 0.35, 0.16), (cx_c, 0.35, 0.20), 0.28, 0.28, (18, 28, 44), segments=16, metallic=0.3)
                ha = 0.5 if dead else (-math.pi * 0.5 + t * 2.2)
                sc.add_cylinder((cx_c, 0.35, 0.23), (cx_c + math.cos(ha) * 0.22, 0.35 + math.sin(ha) * 0.22, 0.23), 0.026, 0.020, rim_col, segments=8, emissive=0.8)
            # Horizontal blocking bar + red NO-PASS arrow pushing against it
            sc.add_box((0.60, -0.68, 0.08), (2.55, 0.30, 0.36), STEEL_LIGHT, metallic=0.78)
            sc.add_arrow_3d((0.60, -1.65, 0.18), (0.60, -0.92, 0.18), DANGER, shaft_r=0.08, head_r=0.19)
            add_crash_test_dummy(sc, pos=(-1.48, -0.88, 0.72), scale=0.72, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "carbide_drill_approach":
            # Spinning carbide drill boring right-to-left straight toward the hidden armor wall!
            cam = Camera3D(eye=(1.45 + shake, 0.72, 6.05), target=(0.05, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Vault steel wall slab
            sc.add_box((-0.05, 0.12, 0.0), (0.45, 2.35, 1.85), STEEL_MID, metallic=0.74)
            # Spinning carbide drill advancing inward
            dx = 1.65 - ease_in_out_cubic(prog) * 0.85
            sc.add_cylinder((dx + 0.95, 0.12, 0.0), (dx + 0.12, 0.12, 0.0), 0.32, 0.28, AMBER, segments=14, metallic=0.62)
            sc.add_cylinder((dx + 0.12, 0.12, 0.0), (dx - 0.62, 0.12, 0.0), 0.12, 0.03, STEEL_LIGHT, segments=12, metallic=0.88)
            # Spinning fluted drill collars
            for fi in range(4):
                fx = dx - 0.02 - fi * 0.14
                sc.add_cylinder((fx, 0.12, 0.0), (fx - 0.05, 0.12, 0.0), 0.135, 0.11, CYAN, segments=10, emissive=0.35)
            sc.add_arrow_3d((dx + 1.15, 0.85, 0.2), (dx - 0.15, 0.85, 0.2), DANGER, shaft_r=0.072, head_r=0.175)
            add_crash_test_dummy(sc, pos=(-1.45, -0.88, 0.72), scale=0.72, yaw=0.38, pose="brace_impact", emotion="shock", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 560, 930, t, 22, 160, 140, p, seed=81))

        elif scene_key == "glass_relocker_plate":
            # Macro cutaway of the glowing tempered-glass sheet holding taut spring-loaded deadbolt cables!
            cam = Camera3D(eye=(-1.35, 0.75, 6.15), target=(0.12, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Glowing translucent cyan tempered glass sheet in a dark steel frame
            sc.add_box((0.62, 0.15, 0.0), (1.95, 1.85, 0.12), GLASS_CYAN, metallic=0.45, emissive=0.42, alpha=0.58, bloom=True)
            # Frame edges around glass pane
            for sy in (-0.94, 0.94):
                sc.add_box((0.62, 0.15 + sy, 0.0), (2.05, 0.12, 0.22), STEEL_DARK, metallic=0.72)
            # Tensioned trigger cables running from glass center to spring-loaded crimson deadbolts!
            for sx in (-1, 1):
                sc.add_cylinder((0.62, 0.15, 0.12), (0.62 + sx * 1.25, 0.15 + sx * 0.45, 0.12), 0.036, 0.036, AMBER, segments=8, emissive=0.55)
                sc.add_box((0.62 + sx * 1.42, 0.15 + sx * 0.45, 0.12), (0.34, 0.32, 0.34), DANGER, metallic=0.62, emissive=0.55, bloom=True)
            # Drill tip approaching the glass pane
            drill_x = 1.95 - prog * 0.85
            sc.add_cylinder((drill_x + 0.65, 0.15, 0.35), (drill_x, 0.15, 0.08), 0.10, 0.025, STEEL_LIGHT, segments=10, metallic=0.88)
            add_crash_test_dummy(sc, pos=(-1.50, -0.88, 0.72), scale=0.70, yaw=0.38, pose="brace_impact", emotion="shock", t=t)

        elif scene_key == "deadbolts_fire_jam":
            # CLIMAX: Tempered glass shatters into flying cyan shards + 4 crimson spring deadbolts slam shut!
            fire = ease_out_cubic(clamp(prog * 1.35))
            cam = Camera3D(eye=(1.35 + shake, 0.68, 6.20), target=(0.08, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Exploding cyan glass shards scattering outward
            for si in range(14):
                ang = (2.0 * math.pi * si) / 14.0 + 0.2
                dist = 0.25 + fire * (1.25 + (si % 3) * 0.28)
                sc.add_box(
                    (0.58 + math.cos(ang) * dist, 0.18 + math.sin(ang) * dist * 0.85, 0.20 + fire * 0.35),
                    (0.18, 0.14, 0.06),
                    GLASS_CYAN,
                    rot=(fire * si, fire * 1.7, ang),
                    emissive=0.65,
                    bloom=True,
                )
            # Central vault steel bar being permanently jammed by 4 incoming crimson spring deadbolts!
            sc.add_box((0.58, 0.18, -0.05), (0.48, 2.35, 0.42), STEEL_MID, metallic=0.76)
            for sx, sy in ((-1, 0.65), (1, 0.65), (-1, -0.45), (1, -0.45)):
                bx = 0.58 + sx * (1.55 - fire * 0.98)
                sc.add_cylinder((bx + sx * 0.45, 0.18 + sy, 0.05), (bx - sx * 0.25, 0.18 + sy, 0.05), 0.12, 0.12, DANGER, segments=12, metallic=0.55, emissive=0.72, bloom=True)
                sc.add_arrow_3d((0.58 + sx * 1.95, 0.18 + sy, 0.25), (0.58 + sx * 0.88, 0.18 + sy, 0.25), DANGER, shaft_r=0.065, head_r=0.16)
            add_crash_test_dummy(sc, pos=(-1.46, -0.90, 0.72), scale=0.72, yaw=0.38, pose="panic_freefall", emotion="panic", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 635, 920, t, 26, 220, 180, p, seed=101))

        elif scene_key == "vault_permanently_sealed":
            # Vault door permanently jammed with glowing red relocker bars; UNIT-01 shaking head!
            cam = Camera3D(eye=(-1.45 + math.sin(t * 0.9) * 0.35, 0.65, 6.35), target=(0.05, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_vault_door(sc, center=(0.55, 0.06, 0.0), radius=1.18, bolt_ext=1.0, wheel_ang=0.0, deadbolts_fired=True)
            add_crash_test_dummy(sc, pos=(-1.48, -0.86, 0.72), scale=0.74, yaw=0.38, pose="cta_shrug", emotion="shock", t=t)
            overlays_2d.append(lambda d: draw_dotted_arc(d, 615, 950, 310, 0, 360, p.danger, width=4, step_deg=12))

        else:  # verdict_cta_card
            cam = Camera3D(eye=(math.sin(t * 0.9) * 0.45, 0.55, 5.85), target=(0.0, 0.12, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.75, span=7.0, step=1.0, t=t)
            # Giant gleaming vault door locked behind UNIT-01!
            self._add_3d_vault_door(sc, center=(0.0, 0.32, -1.35), radius=1.28, bolt_ext=1.0, wheel_ang=0.2, deadbolts_fired=True)
            add_crash_test_dummy(sc, pos=(0.0, -0.05, 0.38), scale=0.95, yaw=math.sin(t * 1.8) * 0.14, pose="cta_shrug", emotion="cta", t=t)

            def _cta_buttons(d: ImageDraw.ImageDraw) -> None:
                pulse = 1.0 + 0.04 * math.sin(t * 7.0)
                for label, bx, col in (("YES", 205, p.amber), ("NO", 875, p.emerald)):
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
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "vault_door_hero"))
        rendered_bgr, overlays_2d = self._render_scene_3d(scene_key, t, beat_progress, rms)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        rendered_bgr, overlays_2d = self._render_scene_3d("vault_door_hero", t=0.35, prog=0.45, rms=0.4)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
