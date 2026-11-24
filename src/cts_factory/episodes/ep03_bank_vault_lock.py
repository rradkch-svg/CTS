"""Episode 03: Inside a Bank Vault Door Built to NEVER Open — True 3D PBR + UNIT-01."""

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
    draw_sparks,
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
GLASS_CYAN = (108, 226, 250)
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
        radius: float = 1.22,
        bolt_ext: float = 1.0,
        wheel_ang: float = 0.0,
        deadbolts_fired: bool = False,
        xray_mode: bool = False,
    ) -> None:
        """Massive 20-ton circular 3D steel bank vault door with TRUE 24 radial locking bolts, cam linkages & smooth 32-seg rim."""
        cx, cy, cz = center
        # Smooth 28-segment circular surrounding vault wall frame ring (NO 16-sided wagon wheel!)
        ring_r = radius * 1.24
        n_ring = 28
        seg_len = 2.0 * math.pi * ring_r / n_ring + 0.04
        for i in range(n_ring):
            a = i * (2.0 * math.pi / n_ring)
            sc.add_box(
                (cx + math.cos(a) * ring_r, cy + math.sin(a) * ring_r, cz - 0.14),
                (0.24, seg_len, 0.44),
                STEEL_DARK,
                rot=(0.0, 0.0, a),
                metallic=0.72,
            )

        # Main circular 20-ton vault door disc
        door_alpha = 0.36 if xray_mode else 1.0
        sc.add_cylinder((cx, cy, cz - 0.18), (cx, cy, cz + 0.14), radius, radius * 0.98, STEEL_MID if not xray_mode else STEEL_DARK, segments=32, metallic=0.80, alpha=door_alpha)
        sc.add_cylinder((cx, cy, cz + 0.12), (cx, cy, cz + 0.22), radius * 0.88, radius * 0.84, STEEL_LIGHT, segments=32, metallic=0.84, alpha=door_alpha)

        # EXACTLY 24 massive radial 4-inch solid chrome locking bolts (matches "24 solid steel bolts" / "24 X 4-INCH"!)
        n_bolts = 24
        for i in range(n_bolts):
            a = i * (2.0 * math.pi / n_bolts)
            r0 = radius * 0.42
            r1 = radius * (0.86 + 0.32 * bolt_ext)
            p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0, cz + 0.06)
            p1 = (cx + math.cos(a) * r1, cy + math.sin(a) * r1, cz + 0.06)
            is_dead = deadbolts_fired and (i % 6 == 0)
            bolt_col = DANGER if is_dead else STEEL_LIGHT
            sc.add_cylinder(
                p0,
                p1,
                0.056,
                0.056,
                bolt_col,
                segments=10,
                metallic=0.84,
                emissive=0.40 if is_dead else 0.0,
                bloom=is_dead,
            )
            # Visible brass cam linkage collar connecting every bolt to the central cam ring!
            sc.add_sphere((cx + math.cos(a) * r0, cy + math.sin(a) * r0, cz + 0.10), 0.048, BRASS, metallic=0.80)

        # Central geared brass cam ring + steel ring collar
        sc.add_gear_3d((cx, cy, cz + 0.20), radius * 0.44, 0.14, 24, wheel_ang, BRASS, metallic=0.78)
        sc.add_cylinder((cx, cy, cz + 0.20), (cx, cy, cz + 0.26), radius * 0.32, radius * 0.32, STEEL_DARK, segments=22, metallic=0.78)

        # Heavy 5-spoke machined chrome & brass vault handwheel with outer wheel rim ring!
        wz = cz + 0.44
        sc.add_cylinder((cx, cy, cz + 0.22), (cx, cy, wz), 0.11, 0.11, STEEL_DARK, segments=14, metallic=0.82)
        wheel_r = radius * 0.44
        n_rim = 18
        rim_seg = 2.0 * math.pi * wheel_r / n_rim + 0.03
        for ri in range(n_rim):
            ra = wheel_ang + ri * (2.0 * math.pi / n_rim)
            sc.add_box(
                (cx + math.cos(ra) * wheel_r, cy + math.sin(ra) * wheel_r, wz),
                (0.065, rim_seg, 0.065),
                BRASS,
                rot=(0.0, 0.0, ra),
                metallic=0.82,
            )
        for sp in range(5):
            sa = wheel_ang + sp * (2.0 * math.pi / 5.0)
            sc.add_cylinder((cx, cy, wz), (cx + math.cos(sa) * wheel_r, cy + math.sin(sa) * wheel_r, wz), 0.042, 0.042, STEEL_LIGHT, segments=8, metallic=0.84)
        sc.add_sphere((cx, cy, wz + 0.02), 0.13, BRASS, metallic=0.84)

        # Compact crimson relocker jam latches on the rim (no giant neon lightsaber tubes!)
        if deadbolts_fired:
            for a_deg in (45, 135, 225, 315):
                ar = math.radians(a_deg)
                p0 = (cx + math.cos(ar) * radius * 0.72, cy + math.sin(ar) * radius * 0.72, cz + 0.28)
                p1 = (cx + math.cos(ar) * radius * 1.18, cy + math.sin(ar) * radius * 1.18, cz + 0.28)
                sc.add_cylinder(p0, p1, 0.068, 0.068, DANGER, segments=12, metallic=0.65, emissive=0.55, bloom=True)

    def _add_industrial_drill(self, sc: Scene3D, tip_pos: tuple[float, float, float], t: float) -> None:
        """Consistent industrial carbide drill motor + chuck + fluted helical bit used across beats 8 & 9."""
        tx, ty, tz = tip_pos
        # Heavy brushed-steel & amber drill housing
        sc.add_cylinder((tx + 1.48, ty, tz), (tx + 0.78, ty, tz), 0.30, 0.26, AMBER, segments=16, metallic=0.62)
        sc.add_cylinder((tx + 0.78, ty, tz), (tx + 0.56, ty, tz), 0.20, 0.15, STEEL_DARK, segments=14, metallic=0.82)
        # Fluted carbide drill bit with rotating cyan-silver helical flute ribs
        sc.add_cylinder((tx + 0.56, ty, tz), (tx, ty, tz), 0.105, 0.028, STEEL_LIGHT, segments=14, metallic=0.88)
        sc.add_coil_spring((tx + 0.52, ty, tz), (tx + 0.06, ty, tz), coil_radius=0.075, wire_radius=0.018, turns=4, rgb=CYAN, metallic=0.85)

    def _add_timelock_housing(self, sc: Scene3D, cx: float, cy: float, t: float, fail_first: bool = False) -> None:
        """Consistent precision 3-movement mechanical Swiss time-lock housing with crisp clock faces & dual hands."""
        sc.add_box((cx, cy, -0.22), (2.68, 1.24, 0.34), STEEL_DARK, metallic=0.72)
        sc.add_box((cx, cy, -0.04), (2.74, 1.30, 0.05), BRASS, metallic=0.78)
        for idx, ox in enumerate((-0.80, 0.0, 0.80)):
            cx_c = cx + ox
            dead = fail_first and (idx == 0)
            bezel_col = DANGER if dead else (EMERALD if fail_first else BRASS)
            sc.add_cylinder((cx_c, cy, -0.01), (cx_c, cy, 0.15), 0.37, 0.37, bezel_col, segments=22, metallic=0.78, emissive=0.25 if fail_first else 0.0)
            # Crisp dark slate clock dial + 4 cardinal brass hour markers
            sc.add_cylinder((cx_c, cy, 0.15), (cx_c, cy, 0.19), 0.30, 0.30, (18, 28, 44), segments=22, metallic=0.25)
            for h_i in range(4):
                ha_m = h_i * (math.pi * 0.5)
                sc.add_sphere((cx_c + math.cos(ha_m) * 0.24, cy + math.sin(ha_m) * 0.24, 0.21), 0.024, STEEL_LIGHT, metallic=0.80)
            # Dual clock hands (minute + hour)
            ha = 0.5 if dead else (-math.pi * 0.5 + math.floor(t * 2.0) * 0.35)
            ha_hr = -0.8 if dead else (-math.pi * 0.5 + t * 0.25)
            hand_col = DANGER if dead else (EMERALD if fail_first else CYAN)
            sc.add_cylinder((cx_c, cy, 0.22), (cx_c + math.cos(ha) * 0.23, cy + math.sin(ha) * 0.23, 0.22), 0.024, 0.018, hand_col, segments=8, emissive=0.55)
            sc.add_cylinder((cx_c, cy, 0.23), (cx_c + math.cos(ha_hr) * 0.14, cy + math.sin(ha_hr) * 0.14, 0.23), 0.028, 0.022, AMBER, segments=8)
            sc.add_sphere((cx_c, cy, 0.25), 0.048, BRASS, metallic=0.82)

    def _render_scene_3d(self, scene_key: str, t: float, prog: float, rms: float, is_cover: bool = False) -> tuple[np.ndarray, list]:
        p = self.palette
        assert p is not None and self.bg_steel_bgr is not None and self.bg_alert_bgr is not None and self.bg_safe_bgr is not None
        overlays_2d: list = []

        if scene_key in ("carbide_drill_approach", "glass_relocker_plate", "deadbolts_fire_jam", "vault_permanently_sealed"):
            bg = self.bg_alert_bgr
        elif scene_key in ("verdict_cta_card",):
            bg = self.bg_safe_bgr
        else:
            bg = self.bg_steel_bgr

        shake = math.sin(t * 58.0) * 0.05 if (scene_key in ("carbide_drill_approach", "deadbolts_fire_jam") and not is_cover) else 0.0

        if scene_key == "vault_door_hero":
            # FRAME 0 HERO: Massive 24-bolt circular vault door + BOLT cleanly clear on left + clean 1:1 cover framing!
            if is_cover:
                cam = Camera3D(eye=(-1.15, 0.72, 6.90), target=(0.12, 0.52, 0.0), fov_deg=41.0, cy_offset=45.0)
            else:
                cam = Camera3D(eye=(-1.15 + math.sin(t * 1.1) * 0.30, 0.65, 6.45), target=(0.05, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_vault_door(
                sc,
                center=(0.48, 0.02, 0.0),
                radius=1.16,
                bolt_ext=0.88 + 0.12 * math.sin(t * 6.0),
                wheel_ang=math.sin(t * 5.0) * 0.14,
            )
            if not is_cover:
                add_crash_test_dummy(sc, pos=(-1.55, -0.82, 0.65), scale=0.72, yaw=0.45, pose="brace_impact", emotion="panic", t=t)
                overlays_2d.append(lambda d: draw_sparks(d, 640, 960, t, 14, 200, 170, p, seed=31))

        elif scene_key == "armor_layers_exploded":
            cam = Camera3D(eye=(2.25, 0.92, 6.45), target=(0.10, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            sep = 0.28 + ease_out_cubic(prog) * 0.40
            layers = [
                (-sep * 1.5, STEEL_LIGHT, "brushed_steel", 0.80),
                (-sep * 0.5, STEEL_DARK, "carbon_weave", 0.62),
                (sep * 0.5, COPPER, "machined_brass", 0.82),
                (sep * 1.5, BRASS, "machined_brass", 0.76),
            ]
            for ox, col, tex, met in layers:
                sc.add_box((0.65 + ox, 0.12, 0.0), (0.16, 2.20, 1.80), col, metallic=met, texture=tex)
            sc.add_arrow_3d((0.65 - sep * 2.0, 1.50, 0.2), (0.65 + sep * 2.0, 1.50, 0.2), CYAN, shaft_r=0.060, head_r=0.15)
            add_crash_test_dummy(sc, pos=(-1.55, -0.86, 0.65), scale=0.70, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "copper_heat_shield":
            # Stepped cutaway: gleaming COPPER thermal spreader CLEARLY EXPOSED in front with heat-wicking arrows ON ITS FRONT SURFACE!
            cam = Camera3D(eye=(-1.25, 0.72, 6.25), target=(0.12, 0.05, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Rear manganese steel armor backing + large exposed front COPPER alloy heat-spreader slab + cutaway outer steel rim!
            sc.add_box((0.52, 0.15, -0.25), (2.25, 2.05, 0.24), STEEL_DARK, metallic=0.68)
            sc.add_box((0.52, 0.15, 0.10), (2.10, 1.90, 0.34), COPPER, metallic=0.82, texture="machined_brass")
            # Left cutaway lip of outer steel shell so viewer sees steel -> copper sandwich!
            sc.add_box((-0.38, 0.15, 0.34), (0.34, 1.98, 0.16), STEEL_MID, metallic=0.76)
            # Industrial oxy-acetylene cutting torch handle + brass nozzle + tapered blue-amber flame cone!
            sc.add_cylinder((0.52, 0.15, 1.55), (0.52, 0.15, 0.88), 0.12, 0.09, BRASS, segments=14, metallic=0.82)
            sc.add_cylinder((0.52, 0.15, 0.88), (0.52, 0.15, 0.72), 0.075, 0.045, STEEL_LIGHT, segments=12, metallic=0.86)
            sc.add_cylinder((0.52, 0.15, 0.72), (0.52, 0.15, 0.30), 0.045, 0.16 + 0.03 * math.sin(t * 28.0), AMBER, segments=14, emissive=0.82, bloom=True)
            sc.add_cylinder((0.52, 0.15, 0.70), (0.52, 0.15, 0.42), 0.028, 0.07, CYAN, segments=10, emissive=0.90, bloom=True)
            # Heat dispersion arrows clearly ON THE FRONT FACE of the copper plate (z = +0.34, NEVER buried behind steel!)
            for dx, dy in ((1.0, 0.0), (-0.75, 0.0), (0.0, 0.88), (0.0, -0.88)):
                sc.add_arrow_3d((0.52 + dx * 0.28, 0.15 + dy * 0.28, 0.36), (0.52 + dx * 1.12, 0.15 + dy * 1.05, 0.36), CYAN, shaft_r=0.052, head_r=0.13)
            add_crash_test_dummy(sc, pos=(-1.55, -0.88, 0.65), scale=0.70, yaw=0.38, pose="brace_impact", emotion="curious", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 635, 920, t, 18, 165, 135, p, seed=33))

        elif scene_key == "radial_bolts_cam":
            # X-ray geared cam ring driving ALL 24 radial steel bolts outward simultaneously!
            cam = Camera3D(eye=(1.30, 0.68, 6.45), target=(0.05, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            ext = ease_in_out_cubic(clamp(prog * 1.2))
            self._add_3d_vault_door(sc, center=(0.55, 0.08, 0.0), radius=1.16, bolt_ext=ext, wheel_ang=prog * 2.4, xray_mode=True)
            add_crash_test_dummy(sc, pos=(-1.55, -0.86, 0.65), scale=0.70, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "dual_combination_wheels":
            # True smooth machined brass combination wheel discs with recessed NOTCH GATES mounted on a steel spindle (ZERO clipped gear teeth!)
            cam = Camera3D(eye=(-1.35, 0.82, 6.40), target=(0.15, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            align = ease_in_out_cubic(clamp((prog - 0.15) / 0.70))
            for lock_idx, ly in enumerate((0.72, -0.68)):
                # Solid horizontal steel spindle shaft supporting all 3 combination discs!
                sc.add_cylinder((0.62, ly, -0.62), (0.62, ly, 0.62), 0.12, 0.12, STEEL_LIGHT, segments=14, metallic=0.84)
                for w_idx in range(3):
                    wz = -0.36 + w_idx * 0.36
                    ang = (1.0 - align) * (2.4 + w_idx * 1.4 + lock_idx * 1.0)
                    # Smooth CNC brass disc built with an actual open notch gate cutout at angle (pi/2 + ang)!
                    gate_a = math.pi * 0.5 + ang
                    n_arc = 18
                    for ai in range(n_arc):
                        a0 = gate_a + 0.24 + ai * ((2.0 * math.pi - 0.48) / n_arc)
                        sc.add_box(
                            (0.62 + math.cos(a0) * 0.42, ly + math.sin(a0) * 0.42, wz),
                            (0.22, 0.16, 0.12),
                            BRASS,
                            rot=(0.0, 0.0, a0),
                            metallic=0.80,
                        )
                    # Glowing gate slot marker right inside the open notch!
                    sc.add_box(
                        (0.62 + math.cos(gate_a) * 0.34, ly + math.sin(gate_a) * 0.34, wz),
                        (0.14, 0.14, 0.13),
                        EMERALD if align > 0.85 else CYAN,
                        rot=(0.0, 0.0, gate_a),
                        emissive=0.72,
                        bloom=True,
                    )
                # Steel locking fence bar dropping cleanly INTO the aligned top gate notches!
                fence_y = ly + 0.68 - (0.24 if align > 0.85 else 0.0)
                sc.add_box((0.62, fence_y, 0.0), (0.12, 0.16, 1.10), EMERALD if align > 0.85 else STEEL_LIGHT, metallic=0.76, emissive=0.30 if align > 0.85 else 0.0)
            add_crash_test_dummy(sc, pos=(-1.55, -0.86, 0.65), scale=0.70, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "triple_time_lock":
            cam = Camera3D(eye=(0.42, 0.55, 6.35), target=(0.05, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_timelock_housing(sc, cx=0.58, cy=0.22, t=t, fail_first=False)
            sc.add_box((0.58, -0.82, 0.05), (2.52, 0.26, 0.32), AMBER, metallic=0.68, texture="machined_brass")
            add_crash_test_dummy(sc, pos=(-1.58, -0.88, 0.65), scale=0.68, yaw=0.38, pose="point_right", emotion="engineer", t=t)

        elif scene_key == "time_lock_bar_block":
            cam = Camera3D(eye=(-1.25, 0.70, 6.40), target=(0.10, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_timelock_housing(sc, cx=0.62, cy=0.34, t=t, fail_first=True)
            sc.add_box((0.62, -0.68, 0.08), (2.52, 0.28, 0.34), STEEL_LIGHT, metallic=0.78)
            sc.add_arrow_3d((0.62, -1.62, 0.18), (0.62, -0.92, 0.18), DANGER, shaft_r=0.075, head_r=0.18)
            add_crash_test_dummy(sc, pos=(-1.58, -0.88, 0.65), scale=0.68, yaw=0.38, pose="point_right", emotion="curious", t=t)

        elif scene_key == "carbide_drill_approach":
            cam = Camera3D(eye=(1.38 + shake, 0.72, 6.25), target=(0.05, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            sc.add_box((-0.05, 0.12, 0.0), (0.44, 2.30, 1.80), STEEL_MID, metallic=0.76)
            dx = 0.88 - ease_in_out_cubic(prog) * 0.65
            self._add_industrial_drill(sc, (dx, 0.12, 0.0), t)
            sc.add_arrow_3d((dx + 1.35, 0.85, 0.2), (dx + 0.15, 0.85, 0.2), DANGER, shaft_r=0.068, head_r=0.165)
            add_crash_test_dummy(sc, pos=(-1.55, -0.88, 0.65), scale=0.68, yaw=0.38, pose="brace_impact", emotion="shock", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 560, 930, t, 20, 155, 130, p, seed=81))

        elif scene_key == "glass_relocker_plate":
            # Translucent tempered glass pane + steel tension wires + TRUE 3D helical coil springs holding 4 steel deadbolts!
            cam = Camera3D(eye=(-1.25, 0.72, 6.45), target=(0.12, 0.0, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Steel outer frame + crisp translucent tempered glass sheet (subtle gloss, NOT baby-blue LED!)
            sc.add_box((0.55, 0.15, 0.0), (1.78, 1.72, 0.08), GLASS_CYAN, metallic=0.65, emissive=0.15, alpha=0.44)
            for sy in (-0.88, 0.88):
                sc.add_box((0.55, 0.15 + sy, 0.0), (1.92, 0.12, 0.22), STEEL_DARK, metallic=0.74)
            for sx in (-0.90, 0.90):
                sc.add_box((0.55 + sx, 0.15, 0.0), (0.12, 1.84, 0.22), STEEL_DARK, metallic=0.74)
            # Taut steel trigger cables + REAL 3D helical coil springs holding back the crimson spring-loaded deadbolts!
            for sx, sy in ((-1, 0.52), (1, 0.52), (-1, -0.38), (1, -0.38)):
                sc.add_cylinder((0.55, 0.15, 0.10), (0.55 + sx * 0.95, 0.15 + sy, 0.10), 0.024, 0.024, AMBER, segments=8, metallic=0.78)
                sc.add_coil_spring((0.55 + sx * 1.48, 0.15 + sy, 0.10), (0.55 + sx * 1.08, 0.15 + sy, 0.10), coil_radius=0.095, wire_radius=0.022, turns=4, rgb=STEEL_LIGHT)
                sc.add_cylinder((0.55 + sx * 1.12, 0.15 + sy, 0.10), (0.55 + sx * 0.82, 0.15 + sy, 0.10), 0.088, 0.088, DANGER, segments=12, metallic=0.65, emissive=0.35)
            # Same consistent industrial carbide drill tip approaching the tempered glass!
            drill_x = 1.45 - prog * 0.65
            self._add_industrial_drill(sc, (drill_x, 0.15, 0.28), t)
            add_crash_test_dummy(sc, pos=(-1.58, -0.88, 0.65), scale=0.68, yaw=0.38, pose="brace_impact", emotion="shock", t=t)

        elif scene_key == "deadbolts_fire_jam":
            # CLIMAX: Asymmetric sharp triangular glass shards shattering + 4 spring-driven deadbolts strictly IN-FRAME!
            fire = ease_out_cubic(clamp(prog * 1.35))
            cam = Camera3D(eye=(1.20 + shake, 0.68, 6.55), target=(0.08, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            # Sharp irregular triangular glass shards flying outward (NOT uniform confetti cubes!)
            for si in range(16):
                ang = (2.0 * math.pi * si) / 16.0 + 0.17 * (si % 3)
                dist = 0.22 + fire * (0.95 + (si % 4) * 0.24)
                sx_c = 0.52 + math.cos(ang) * dist
                sy_c = 0.18 + math.sin(ang) * dist * 0.82
                sz_c = 0.24 + fire * 0.30
                sz_tri = 0.12 + (si % 3) * 0.055
                a_r = ang + fire * (1.2 + si * 0.2)
                p0 = [sx_c + math.cos(a_r) * sz_tri, sy_c + math.sin(a_r) * sz_tri, sz_c]
                p1 = [sx_c + math.cos(a_r + 2.1) * sz_tri * 0.85, sy_c + math.sin(a_r + 2.1) * sz_tri * 0.85, sz_c + 0.04]
                p2 = [sx_c + math.cos(a_r + 4.0) * sz_tri * 0.70, sy_c + math.sin(a_r + 4.0) * sz_tri * 0.70, sz_c - 0.03]
                sc.add_quad(np.array([p0, p1, p2, p2], dtype=np.float32), rgb=GLASS_CYAN, emissive=0.45, alpha=0.80, double_sided=True)
            # Central vault steel bar permanently jammed by 4 helical-spring-driven deadbolts strictly inside frame!
            sc.add_box((0.52, 0.18, -0.05), (0.46, 2.25, 0.40), STEEL_MID, metallic=0.76)
            for sx, sy in ((-1, 0.62), (1, 0.62), (-1, -0.42), (1, -0.42)):
                bx = 0.52 + sx * (1.28 - fire * 0.82)
                sc.add_coil_spring((0.52 + sx * 1.58, 0.18 + sy, 0.05), (bx + sx * 0.28, 0.18 + sy, 0.05), coil_radius=0.095, wire_radius=0.022, turns=4, rgb=STEEL_LIGHT)
                sc.add_cylinder((bx + sx * 0.30, 0.18 + sy, 0.05), (bx - sx * 0.22, 0.18 + sy, 0.05), 0.105, 0.105, DANGER, segments=12, metallic=0.65, emissive=0.52, bloom=True)
                sc.add_arrow_3d((0.52 + sx * 1.52, 0.18 + sy + 0.22, 0.22), (0.52 + sx * 0.75, 0.18 + sy + 0.22, 0.22), DANGER, shaft_r=0.052, head_r=0.13)
            add_crash_test_dummy(sc, pos=(-1.55, -0.90, 0.65), scale=0.68, yaw=0.38, pose="panic_freefall", emotion="panic", t=t)
            overlays_2d.append(lambda d: draw_sparks(d, 615, 920, t, 24, 210, 165, p, seed=101))

        elif scene_key == "vault_permanently_sealed":
            # Vault door permanently jammed with 24 bolts + 4 crimson relockers (removed mismatched 2D dotted ring!) + thermal lance sparks attempting entry!
            cam = Camera3D(eye=(-1.35 + math.sin(t * 0.9) * 0.30, 0.65, 6.50), target=(0.05, 0.02, 0.0), fov_deg=41.0, cy_offset=45.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-2.15, span=7.0, step=1.0, t=t)
            self._add_3d_vault_door(sc, center=(0.55, 0.06, 0.0), radius=1.14, bolt_ext=1.0, wheel_ang=0.0, deadbolts_fired=True)
            add_crash_test_dummy(sc, pos=(-1.55, -0.86, 0.65), scale=0.70, yaw=0.38, pose="cta_shrug", emotion="shock", t=t)

        else:  # verdict_cta_card — Vault door cleanly offset RIGHT behind BOLT (ZERO bars/spokes spearing torso!) + safe-zone CTA buttons!
            cam = Camera3D(eye=(math.sin(t * 0.9) * 0.35, 0.55, 6.15), target=(0.0, 0.10, 0.0), fov_deg=41.0, cy_offset=20.0)
            sc = Scene3D(cam)
            sc.add_floor_grid(y_level=-1.75, span=7.0, step=1.0, t=t)
            self._add_3d_vault_door(sc, center=(0.88, 0.32, -1.20), radius=1.08, bolt_ext=1.0, wheel_ang=0.2, deadbolts_fired=True)
            add_crash_test_dummy(sc, pos=(-0.72, -0.06, 0.45), scale=0.86, yaw=0.18 + math.sin(t * 1.8) * 0.12, pose="cta_shrug", emotion="cta", t=t)
            overlays_2d.append(lambda d: draw_cta_buttons(d, t, p, self.font_black, by=1150, right_col=p.emerald))

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
        rendered_bgr, overlays_2d = self._render_scene_3d("vault_door_hero", t=0.35, prog=0.45, rms=0.4, is_cover=True)
        rgb = cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB)
        img.paste(Image.fromarray(rgb, mode="RGB"))
        for fn in overlays_2d:
            fn(draw)
