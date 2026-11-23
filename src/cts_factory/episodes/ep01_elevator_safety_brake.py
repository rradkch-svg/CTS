"""Episode 01: How Elevators STOP When Every Cable Snaps — 2.5D CAD Vector Scene."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript
from cts_factory.engine.materials import Palette, build_stage_background, lerp_color, scale_rgb
from cts_factory.engine.primitives import (
    draw_bevel_rect,
    draw_comparison_bars,
    draw_dotted_arc,
    draw_force_arrow,
    draw_gear_25d,
    draw_iso_box,
    draw_pressure_gauge,
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_back, ease_out_cubic, get_camera
from cts_factory.episodes.base import EpisodeScene, register_scene


@register_scene("ep01_elevator_safety_brake")
class ElevatorSafetyBrakeScene(EpisodeScene):
    """Articulated 12-beat 2.5D CAD cutaway choreography for Episode 01."""

    slug = "ep01_elevator_safety_brake"
    episode_id = "ep01"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_default: Image.Image | None = None
        self.bg_alert: Image.Image | None = None
        self.bg_safe: Image.Image | None = None
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
        self.bg_default = build_stage_background(w, h, self.palette, spot_color=self.palette.cyan)
        self.bg_alert = build_stage_background(w, h, self.palette, spot_color=self.palette.amber)
        self.bg_safe = build_stage_background(w, h, self.palette, spot_color=self.palette.emerald)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _draw_t_rails(
        self,
        draw: ImageDraw.ImageDraw,
        p: Palette,
        lx: float,
        rx: float,
        y_top: float,
        y_bot: float,
        scroll_y: float = 0.0,
    ) -> None:
        """Draw twin vertical machined steel T-guide rails along shaft walls."""
        for rail_x, side in ((lx, -1), (rx, 1)):
            # Rail backing flange
            draw.rectangle(
                [rail_x - 18, y_top, rail_x + 18, y_bot],
                fill=p.steel_dark,
                outline=p.ink,
                width=3,
            )
            # Machined guide blade facing inward
            blade_x0 = rail_x + (4 if side == -1 else -14)
            blade_x1 = blade_x0 + 10
            draw.rectangle([blade_x0, y_top, blade_x1, y_bot], fill=p.steel_light, outline=p.ink, width=2)
            # Periodic mounting brackets scrolling cleanly
            spacing = 120.0
            off = scroll_y % spacing
            y = y_top + off
            while y < y_bot - 16:
                bx0 = rail_x - 34 if side == -1 else rail_x + 14
                draw.rectangle([bx0, y, bx0 + 20, y + 18], fill=p.steel_mid, outline=p.ink, width=2)
                y += spacing

    def _draw_elevator_cab_25d(
        self,
        draw: ImageDraw.ImageDraw,
        p: Palette,
        cx: float,
        cy: float,
        w: float = 290.0,
        h: float = 340.0,
        clamp_locked: bool = False,
        glow_col: tuple[int, int, int] | None = None,
    ) -> None:
        """Draw a crisp 2.5D extruded steel elevator cab with interior cutaway & guide shoes."""
        x0, y0 = cx - w / 2, cy - h / 2
        x1, y1 = cx + w / 2, cy + h / 2
        draw_bevel_rect(draw, x0, y0, x1, y1, fill=p.steel_mid, ink=p.ink, depth=22.0, radius=10)
        # Cutaway interior cabin bay
        draw.rounded_rectangle(
            [x0 + 22, y0 + 26, x1 - 22, y1 - 30],
            radius=6,
            fill=p.surface_panel,
            outline=p.ink,
            width=3,
        )
        # Interior ceiling light strip + subtle architectural ribs
        light_col = glow_col or p.cyan
        draw.rectangle([x0 + 50, y0 + 34, x1 - 50, y0 + 44], fill=light_col)
        for rx in (x0 + w * 0.35, x0 + w * 0.65):
            draw.line([(rx, y0 + 48), (rx, y1 - 34)], fill=p.steel_dark, width=2)
        # Structural steel crosshead beam on roof & safety plank underneath
        draw_bevel_rect(draw, x0 - 14, y0 - 26, x1 + 14, y0 + 4, fill=p.steel_light, ink=p.ink, depth=14.0, radius=4)
        plank_col = p.emerald if clamp_locked else p.brass
        draw_bevel_rect(draw, x0 - 18, y1 - 4, x1 + 18, y1 + 28, fill=plank_col, ink=p.ink, depth=14.0, radius=4)
        # Left & right wedge clamp housings gripping T-rails
        for sx in (x0 - 28, x1 + 6):
            draw.rounded_rectangle(
                [sx, y1 - 8, sx + 22, y1 + 34],
                radius=4,
                fill=p.emerald if clamp_locked else p.amber,
                outline=p.ink,
                width=3,
            )

    def _draw_braided_cables(
        self,
        draw: ImageDraw.ImageDraw,
        p: Palette,
        cx: float,
        y_top: float,
        y_bot: float,
        count: int = 8,
        spread: float = 150.0,
        highlight_idx: int = -1,
        snapped_count: int = 0,
        snap_t: float = 0.0,
        single_active: bool = False,
    ) -> None:
        """Draw 8 parallel braided steel hoist ropes with optional animated snapping recoil."""
        for i in range(count):
            frac = (i / max(1, count - 1)) - 0.5
            x = cx + frac * spread
            is_snapped = i < snapped_count
            if single_active and i != count // 2:
                # Ghosted dashed cable
                y = y_top
                while y < y_bot:
                    draw.line([(x, y), (x, min(y_bot, y + 14))], fill=p.steel_dark, width=3)
                    y += 28
                continue

            col = p.cyan if (single_active or i == highlight_idx) else p.steel_light
            if is_snapped:
                col = p.danger
                mid_y = y_top + (y_bot - y_top) * (0.42 + 0.05 * math.sin(i * 2.1))
                recoil = 28.0 + 95.0 * clamp(snap_t)
                whip = math.sin(snap_t * 28.0 + i * 1.7) * 26.0 * (1.0 - 0.5 * clamp(snap_t))
                # Upper recoiling cable end
                draw.line([(x, y_top), (x + whip, mid_y - recoil)], fill=p.ink, width=9)
                draw.line([(x, y_top), (x + whip, mid_y - recoil)], fill=p.amber, width=5)
                # Lower whipping stub
                draw.line([(x - whip * 0.8, mid_y + recoil * 0.65), (x, y_bot)], fill=p.ink, width=9)
                draw.line([(x - whip * 0.8, mid_y + recoil * 0.65), (x, y_bot)], fill=col, width=5)
            else:
                w = 8 if (single_active or i == highlight_idx) else 5
                draw.line([(x, y_top), (x, y_bot)], fill=p.ink, width=w + 4)
                draw.line([(x, y_top), (x, y_bot)], fill=col, width=w)
                # Diagonal braid texture ticks
                y = y_top + 10
                while y < y_bot - 10:
                    draw.line([(x - 3, y), (x + 3, y + 7)], fill=p.steel_dark, width=1)
                    y += 16

    def _scene_cables_snap_peak(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 1 (Frame 0 HERO): Macro steel hitch + 8 snapping braided cables + flying sparks."""
        cam = get_camera("FRAME0_HERO", t, rms=rms, impact=0.85 if prog < 0.5 else 0.35)
        cx, cy = cam.cx, cam.cy + 145
        # Vertical background shaft rails framing the hero
        self._draw_t_rails(draw, p, 175, 905, 490, 1340, scroll_y=t * 220.0)
        # Massive steel roof crosshead hitch block at bottom of hero stage
        draw_bevel_rect(draw, cx - 250, cy + 75, cx + 250, cy + 165, fill=p.steel_mid, ink=p.ink, depth=24.0, radius=10)
        draw_bevel_rect(draw, cx - 190, cy + 35, cx + 190, cy + 88, fill=p.steel_light, ink=p.ink, depth=18.0, radius=8)
        # 8 cables snapping violently right at t=0.0s (already mid-snap on Frame 0!)
        snap_t = clamp(0.28 + prog * 0.85)
        self._draw_braided_cables(
            draw, p, cx, y_top=490, y_bot=cy + 45, count=8, spread=280.0, snapped_count=8, snap_t=snap_t
        )
        # Dramatic crimson/amber sparks & downward gravity force vectors
        draw_sparks(draw, cx - 70, cy - 110, t + 0.12, 16, 210, 140, p, seed=11)
        draw_sparks(draw, cx + 70, cy - 95, t + 0.35, 16, 210, 140, p, seed=23)
        draw_force_arrow(draw, cx - 295, cy - 130, cx - 295, cy + 110, p.danger, width=14, pulse=t * 2.5)
        draw_force_arrow(draw, cx + 295, cy - 130, cx + 295, cy + 110, p.danger, width=14, pulse=t * 2.5)
        # Dotted tension rupture halo
        draw_dotted_arc(draw, cx, cy - 95, 195 + 12 * math.sin(t * 9.0), 0, 360, p.amber, width=4, step_deg=12)

    def _scene_cab_halts_midshaft(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 2: Cab drops briefly then hard-locks mid-shaft with <6 INCHES measurement callout."""
        locked = prog > 0.38
        drop = ease_out_cubic(min(1.0, prog / 0.38)) * 88.0
        cam = get_camera("ISO_WIDE", t, rms=rms, impact=0.9 if 0.38 <= prog <= 0.50 else 0.0)
        cx = cam.cx
        cy = 910.0 + drop
        self._draw_t_rails(draw, p, cx - 210, cx + 210, 645, 1340, scroll_y=0.0 if locked else prog * 140.0)
        self._draw_braided_cables(draw, p, cx, 645, cy - 190, count=8, spread=120.0, snapped_count=8, snap_t=0.75)
        self._draw_elevator_cab_25d(draw, p, cx, cy, w=280, h=310, clamp_locked=locked, glow_col=p.emerald if locked else p.amber)
        if locked:
            draw_sparks(draw, cx - 175, cy + 160, t, 12, 95, 70, p, seed=31)
            draw_sparks(draw, cx + 175, cy + 160, t, 12, 95, 70, p, seed=37)
            # Crisp upward stopping force arrows
            draw_force_arrow(draw, cx - 265, cy + 150, cx - 265, cy - 40, p.emerald, width=13, pulse=t * 1.8)
            draw_force_arrow(draw, cx + 265, cy + 150, cx + 265, cy - 40, p.emerald, width=13, pulse=t * 1.8)
            # Measurement bracket showing tiny drop distance
            draw.line([(cx + 190, 910 - 155), (cx + 245, 910 - 155)], fill=p.cyan, width=3)
            draw.line([(cx + 190, cy - 155), (cx + 245, cy - 155)], fill=p.cyan, width=3)
            draw.line([(cx + 235, 910 - 155), (cx + 235, cy - 155)], fill=p.text_highlight, width=4)
            f = load_font(self.font_bold, 26)
            draw.text((cx + 252, (910 + cy) / 2 - 170), "DROP:\n< 6 IN", font=f, fill=p.text_highlight)
        else:
            draw_force_arrow(draw, cx, cy + 185, cx, cy + 275, p.danger, width=13, pulse=t * 3.0)

    def _scene_multi_cable_xray(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 3: Overhead traction sheave + 8 braided steel ropes lighting up 1..8."""
        cam = get_camera("ISO_WIDE", t, rms=rms)
        cx = cam.cx
        self._draw_t_rails(draw, p, cx - 240, cx + 240, 650, 1340)
        # Spinning traction sheave at top
        draw_gear_25d(draw, cx, 755, 110, 18, t * 1.3, p.steel_mid, p.steel_dark, p.ink, depth_px=20.0, hub_col=p.brass)
        active_rope = int(prog * 8) % 8
        self._draw_braided_cables(draw, p, cx, 790, 1085, count=8, spread=190.0, highlight_idx=active_rope)
        self._draw_elevator_cab_25d(draw, p, cx, 1210, w=270, h=220, clamp_locked=False, glow_col=p.cyan)
        # Upward load-sharing arrows
        for offset in (-265, 265):
            draw_force_arrow(draw, cx + offset, 1050, cx + offset, 840, p.cyan, width=11, pulse=t * 1.5)
        f = load_font(self.font_bold, 26)
        for i in range(8):
            rx = cx + ((i / 7.0) - 0.5) * 190.0
            col = p.text_highlight if i <= active_rope else p.steel_mid
            draw.ellipse([rx - 14, 935, rx + 14, 963], fill=p.surface_panel, outline=col, width=2)
            draw.text((rx - 7, 936), str(i + 1), font=load_font(self.font_bold, 20), fill=col)

    def _scene_single_cable_load_test(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 4: Exploded blueprint proving 1 single cable holds 100% loaded cab."""
        cam = get_camera("EXPLODED_BLUEPRINT", t, rms=rms)
        cx = cam.cx
        draw_dotted_arc(draw, cx, 995, 305, 0, 360, p.steel_mid, width=3, step_deg=10)
        self._draw_braided_cables(draw, p, cx, 660, 965, count=8, spread=180.0, single_active=True)
        bob = math.sin(t * 2.5) * 6.0
        self._draw_elevator_cab_25d(draw, p, cx, 1120 + bob, w=270, h=250, clamp_locked=False, glow_col=p.emerald)
        # Equal & opposite equilibrium force vectors
        draw_force_arrow(draw, cx - 220, 940, cx - 220, 720, p.emerald, width=14, pulse=t * 1.6)
        draw_force_arrow(draw, cx + 220, 940, cx + 220, 1160, p.amber, width=14, pulse=t * 1.6)
        f = load_font(self.font_bold, 26)
        draw.text((cx - 345, 765), "1 ROPE\n100% MAX", font=f, fill=p.emerald)
        draw.text((cx + 245, 1020), "FULL CAB\nLOAD", font=f, fill=p.amber)

    def _scene_governor_spinning(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 5: Macro cutaway of rooftop centrifugal overspeed governor flywheel."""
        cam = get_camera("MACRO_CUTAWAY", t, rms=rms)
        cx, cy = cam.cx, 975.0
        # Governor steel mounting frame
        draw_bevel_rect(draw, cx - 260, cy - 230, cx + 260, cy + 230, fill=p.surface_panel, ink=p.ink, depth=20.0, radius=18)
        # Safety governor rope descending vertically
        for rx in (cx - 165, cx + 165):
            draw.line([(rx, cy), (rx, 1340)], fill=p.ink, width=11)
            draw.line([(rx, cy), (rx, 1340)], fill=p.cyan, width=6)
        # Spinning brass flywheel
        ang = t * 2.6
        draw_gear_25d(draw, cx, cy, 175, 20, ang, p.brass, scale_rgb(p.brass, 0.58), p.ink, depth_px=22.0, hub_col=p.steel_light)
        # Twin pivoted centrifugal brass flyweights held inward by springs
        for sign in (-1, 1):
            a = ang + (0 if sign == 1 else math.pi)
            px = cx + math.cos(a) * 85
            py = cy + math.sin(a) * 85
            draw.ellipse([px - 26, py - 26, px + 26, py + 26], fill=p.amber, outline=p.ink, width=3)
            draw.line([(cx, cy), (px, py)], fill=p.cyan, width=4)
        draw_dotted_arc(draw, cx, cy, 215, 20, 340, p.cyan, width=4, step_deg=10)
        f = load_font(self.font_bold, 24)
        lbl = "NORMAL RPM: SAFE"
        bb = draw.textbbox((0, 0), lbl, font=f)
        draw.text((cx - (bb[2] - bb[0]) / 2, cy + 245), lbl, font=f, fill=p.emerald)

    def _scene_all_ropes_severed(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 6: All 8 hoist ropes sever sequentially while overspeed dial hits +15%."""
        cam = get_camera("IMPACT_CLOSEUP", t, rms=rms, impact=0.8 if 0.25 < prog < 0.75 else 0.2)
        cx = cam.cx - 115
        snapped = min(8, 2 + int(prog * 7.5))
        self._draw_braided_cables(draw, p, cx, 650, 1280, count=8, spread=210.0, snapped_count=snapped, snap_t=prog)
        if snapped >= 3:
            draw_sparks(draw, cx, 930, t, 20, 210, 150, p, seed=55)
        # Live overspeed dial on right sweeping past +15%
        speed_v = clamp(0.45 + prog * 0.45)
        pct = int(round(prog * 18))
        draw_pressure_gauge(
            draw,
            cx=790,
            cy=960,
            radius=145,
            value_0_to_1=speed_v,
            label="OVERSPEED",
            reading=f"+{pct}%",
            palette=p,
            font_path=self.font_black,
        )
        draw_force_arrow(draw, cx - 155, 760, cx - 155, 1140, p.danger, width=14, pulse=t * 3.2)

    def _scene_flyweights_flare_latch(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 7: Centrifugal flyweights swing outward & jam into outer steel ratchet ring."""
        latched = prog > 0.62
        cam = get_camera("MACRO_CUTAWAY", t, rms=rms, impact=1.0 if 0.62 <= prog <= 0.78 else 0.15)
        cx, cy = cam.cx, 975.0
        # Outer stationary notched steel ratchet ring
        draw.ellipse([cx - 245, cy - 245, cx + 245, cy + 245], fill=p.steel_dark, outline=p.ink, width=5)
        draw.ellipse([cx - 210, cy - 210, cx + 210, cy + 210], fill=p.surface_panel, outline=p.steel_light, width=3)
        for i in range(16):
            ra = i * (2 * math.pi / 16)
            x1 = cx + math.cos(ra) * 210
            y1 = cy + math.sin(ra) * 210
            x2 = cx + math.cos(ra + 0.12) * 185
            y2 = cy + math.sin(ra + 0.12) * 185
            draw.line([(x1, y1), (x2, y2)], fill=p.steel_light, width=7)

        # Accelerating flywheel then hard STOP at latch
        spin_ang = (prog * 14.0) if not latched else (0.62 * 14.0)
        draw_gear_25d(draw, cx, cy, 155, 16, spin_ang, p.brass, scale_rgb(p.brass, 0.55), p.ink, depth_px=18.0)

        # Articulated flyweights flaring radially outward with centrifugal arrows
        flare = ease_out_cubic(min(1.0, prog / 0.62))
        fw_r = 78.0 + flare * 102.0
        for sign in (-1, 1):
            a = spin_ang + (0 if sign == 1 else math.pi)
            fx = cx + math.cos(a) * fw_r
            fy = cy + math.sin(a) * fw_r
            draw.line([(cx, cy), (fx, fy)], fill=p.amber if not latched else p.danger, width=10)
            draw.ellipse([fx - 30, fy - 30, fx + 30, fy + 30], fill=p.danger if latched else p.amber, outline=p.ink, width=4)
            if not latched:
                ax1 = cx + math.cos(a) * (fw_r + 75)
                ay1 = cy + math.sin(a) * (fw_r + 75)
                draw_force_arrow(draw, fx, fy, ax1, ay1, p.amber, width=9, head_len=20, head_w=16)

        if latched:
            draw_sparks(draw, cx + math.cos(spin_ang) * 185, cy + math.sin(spin_ang) * 185, t, 14, 140, 120, p, seed=71)
            f = load_font(self.font_black, 36)
            draw.text((cx - 165, cy + 265), "RATCHET LOCKED!", font=f, fill=p.text_highlight, stroke_width=4, stroke_fill=p.ink)

    def _scene_linkage_rod_lift(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 8: Stopped safety rope yanks under-cab scissor linkage rods upward."""
        cam = get_camera("EXPLODED_BLUEPRINT", t, rms=rms)
        cx, cy = cam.cx, 1005.0
        lift = ease_in_out_cubic(prog) * 78.0
        # Under-cab steel chassis frame
        draw_bevel_rect(draw, cx - 320, cy - 180, cx + 320, cy - 95, fill=p.steel_mid, ink=p.ink, depth=20.0, radius=8)
        draw_bevel_rect(draw, cx - 340, cy + 80, cx + 340, cy + 165, fill=p.steel_dark, ink=p.ink, depth=20.0, radius=8)
        # Stopped governor rope pulling straight UP on left actuator
        rope_x = cx - 255
        draw.line([(rope_x, 650), (rope_x, cy - 50 - lift)], fill=p.ink, width=12)
        draw.line([(rope_x, 650), (rope_x, cy - 50 - lift)], fill=p.cyan, width=7)
        draw_force_arrow(draw, rope_x - 65, cy + 40, rope_x - 65, cy - 150, p.cyan, width=13, pulse=t * 2.0)

        # Articulated horizontal transfer shaft + twin scissor linkages lifting brake wedges
        bar_y = cy + 25 - lift * 0.7
        draw.line([(cx - 255, bar_y), (cx + 255, bar_y)], fill=p.ink, width=22)
        draw.line([(cx - 255, bar_y), (cx + 255, bar_y)], fill=p.brass, width=14)
        for sign in (-1, 1):
            px = cx + sign * 245
            draw.line([(cx + sign * 110, cy + 110), (px, bar_y)], fill=p.ink, width=18)
            draw.line([(cx + sign * 110, cy + 110), (px, bar_y)], fill=p.steel_light, width=11)
            # Pivot pins
            draw.ellipse([px - 16, bar_y - 16, px + 16, bar_y + 16], fill=p.amber, outline=p.ink, width=3)
            # Lifting serrated steel wedge
            wy = cy + 50 - lift
            pts = [
                (px - 22 * sign, wy + 55),
                (px + 28 * sign, wy + 55),
                (px + 12 * sign, wy - 45),
                (px - 22 * sign, wy - 45),
            ]
            draw.polygon(pts, fill=p.amber, outline=p.ink, width=4)
            draw_force_arrow(draw, px + 55 * sign, wy + 50, px + 55 * sign, wy - 60, p.amber, width=11, pulse=t * 2.2)

    def _scene_wedges_pinch_rails(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 9 (CLIMAX): Hardened serrated wedges jam into vertical T-rail, biting tighter with gravity."""
        bite = ease_out_cubic(min(1.0, prog * 1.35))
        cam = get_camera("IMPACT_CLOSEUP", t, rms=rms, impact=0.95 * (1.0 - 0.5 * prog))
        cx, cy = cam.cx, 995.0

        # Massive central vertical steel T-rail
        draw_bevel_rect(draw, cx - 44, 650, cx + 44, 1345, fill=p.steel_light, ink=p.ink, depth=26.0, radius=4)
        draw.rectangle([cx - 12, 650, cx + 12, 1345], fill=scale_rgb(p.steel_light, 1.18))

        # Tapered outer housing jaws
        for sign in (-1, 1):
            jx0 = cx + sign * 240
            jx1 = cx + sign * 125
            jaw = [
                (jx0, cy - 205),
                (jx1, cy - 205),
                (cx + sign * 155, cy + 215),
                (jx0, cy + 215),
            ]
            draw.polygon(jaw, fill=p.steel_dark, outline=p.ink, width=4)

            # Sliding serrated hardened-steel wedge moving UP and INWARD into rail
            gap = (1.0 - bite) * 65.0
            wy = cy + (1.0 - bite) * 95.0
            wx_in = cx + sign * (45.0 + gap * 0.45)
            wx_out_top = cx + sign * (128.0 + gap * 0.45)
            wx_out_bot = cx + sign * (152.0 + gap * 0.45)
            wedge_col = lerp_color(p.brass, p.amber, bite)
            wedge = [
                (wx_in, wy - 130),
                (wx_out_top, wy - 130),
                (wx_out_bot, wy + 130),
                (wx_in, wy + 130),
            ]
            draw.polygon(wedge, fill=wedge_col, outline=p.ink, width=4)
            # Serrated gripping teeth biting rail
            for k in range(8):
                ty = wy - 110 + k * 30
                draw.polygon(
                    [(wx_in, ty), (wx_in - sign * 10, ty + 10), (wx_in, ty + 20)],
                    fill=p.text_highlight,
                    outline=p.ink,
                    width=2,
                )
            # Massive opposing clamping force vectors growing brighter as wedge locks
            draw_force_arrow(
                draw,
                cx + sign * 395,
                cy,
                cx + sign * 165,
                cy,
                p.danger if bite > 0.7 else p.amber,
                width=16,
                head_len=34,
                head_w=26,
                pulse=t * 2.8,
            )

        # Downward gravity arrow feeding clamping force
        draw_force_arrow(draw, cx, 675, cx, 820, p.cyan, width=14, pulse=t * 2.2)
        if bite > 0.45:
            draw_sparks(draw, cx - 44, cy - 60, t, 18, 175, 130, p, seed=91)
            draw_sparks(draw, cx + 44, cy + 40, t, 18, 175, 130, p, seed=97)

    def _scene_cab_frozen_spark_fade(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 10: Locked cab frozen rock-solid with cooling sparks & OTIS 1853 schematic ring."""
        cam = get_camera("IMPACT_CLOSEUP", t, rms=rms)
        cx, cy = cam.cx, 990.0
        self._draw_t_rails(draw, p, cx - 220, cx + 220, 650, 1340)
        draw_dotted_arc(draw, cx, cy, 315, 0, 360, p.emerald, width=4, step_deg=10)
        self._draw_elevator_cab_25d(draw, p, cx, cy, w=290, h=320, clamp_locked=True, glow_col=p.emerald)
        if prog < 0.75:
            draw_sparks(draw, cx - 180, cy + 160, t, int(10 * (1.0 - prog)), 80, 50, p, seed=103)
            draw_sparks(draw, cx + 180, cy + 160, t, int(10 * (1.0 - prog)), 80, 50, p, seed=107)
        # Clean schematic badge inside hero zone
        draw.rounded_rectangle([cx - 210, cy + 205, cx + 210, cy + 275], radius=14, fill=p.surface_panel, outline=p.emerald, width=3)
        f = load_font(self.font_black, 30)
        draw.text((cx - 175, cy + 221), "OTIS 1853 — LOCKED", font=f, fill=p.emerald)

    def _scene_hydraulic_buffer_cutaway(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 11: Pit hydraulic oil piston buffer compressing smoothly with damping vectors."""
        cam = get_camera("ISO_WIDE", t, rms=rms)
        cx = cam.cx
        compress = ease_in_out_cubic(math.sin(prog * math.pi)) * 125.0
        # Shaft concrete pit floor
        draw_bevel_rect(draw, 140, 1250, 940, 1320, fill=p.steel_dark, ink=p.ink, depth=20.0, radius=6)
        # Outer hydraulic cylinder housing
        draw_bevel_rect(draw, cx - 120, 960, cx + 120, 1250, fill=p.steel_mid, ink=p.ink, depth=22.0, radius=8)
        # Glowing cutaway pressurized hydraulic oil chamber
        oil_top = 995 + compress * 0.45
        draw.rounded_rectangle([cx - 88, oil_top, cx + 88, 1235], radius=6, fill=p.cyan, outline=p.ink, width=3)
        # Moving steel plunger rod + top impact bumper pad
        rod_top = 740 + compress
        draw_bevel_rect(draw, cx - 42, rod_top, cx + 42, oil_top + 25, fill=p.steel_light, ink=p.ink, depth=14.0, radius=4)
        draw_bevel_rect(draw, cx - 155, rod_top - 42, cx + 155, rod_top + 6, fill=p.amber, ink=p.ink, depth=16.0, radius=8)
        # Upward hydraulic damping arrows
        draw_force_arrow(draw, cx - 225, 1210, cx - 225, 960, p.emerald, width=13, pulse=t * 1.8)
        draw_force_arrow(draw, cx + 225, 1210, cx + 225, 960, p.emerald, width=13, pulse=t * 1.8)
        f = load_font(self.font_black, 19)
        oil_lbl = "HYDRAULIC\nOIL"
        bb = draw.multiline_textbbox((0, 0), oil_lbl, font=f, align="center")
        draw.multiline_text(
            (cx - (bb[2] - bb[0]) / 2, 1140),
            oil_lbl,
            font=f,
            fill=p.ink,
            align="center",
        )

    def _scene_verdict_cta_card(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 12 (CTA): Locked elevator cutaway + clean YES / NO choice chips."""
        cam = get_camera("ISO_WIDE", t, rms=rms)
        cx = cam.cx
        self._draw_t_rails(draw, p, cx - 220, cx + 220, 660, 1140)
        self._draw_elevator_cab_25d(draw, p, cx, 880, w=240, h=250, clamp_locked=True, glow_col=p.emerald)
        # High-contrast YES / NO CTA cards cleanly above caption safe zone
        pulse = 1.0 + 0.04 * math.sin(t * 7.0)
        for label, bx, col in (("YES", cx - 210, p.amber), ("NO", cx + 210, p.emerald)):
            bw, bh = int(155 * pulse), int(92 * pulse)
            draw.rounded_rectangle([bx - bw, 1175, bx + bw, 1175 + bh], radius=18, fill=p.surface_panel, outline=col, width=5)
            f = load_font(self.font_black, 48)
            bb = draw.textbbox((0, 0), label, font=f)
            draw.text((bx - (bb[2] - bb[0]) / 2, 1175 + (bh - (bb[3] - bb[1])) / 2 - 4), label, font=f, fill=col)

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
        assert self.palette is not None and self.bg_default is not None
        assert self.bg_alert is not None and self.bg_safe is not None
        p = self.palette
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "cab_halts_midshaft"))

        if scene_key in ("cables_snap_peak", "all_ropes_severed", "flyweights_flare_latch", "wedges_pinch_rails"):
            img.paste(self.bg_alert)
        elif scene_key in ("cab_frozen_spark_fade", "verdict_cta_card"):
            img.paste(self.bg_safe)
        else:
            img.paste(self.bg_default)

        dispatch = {
            "cables_snap_peak": self._scene_cables_snap_peak,
            "cab_halts_midshaft": self._scene_cab_halts_midshaft,
            "multi_cable_xray": self._scene_multi_cable_xray,
            "single_cable_load_test": self._scene_single_cable_load_test,
            "governor_spinning": self._scene_governor_spinning,
            "all_ropes_severed": self._scene_all_ropes_severed,
            "flyweights_flare_latch": self._scene_flyweights_flare_latch,
            "linkage_rod_lift": self._scene_linkage_rod_lift,
            "wedges_pinch_rails": self._scene_wedges_pinch_rails,
            "cab_frozen_spark_fade": self._scene_cab_frozen_spark_fade,
            "hydraulic_buffer_cutaway": self._scene_hydraulic_buffer_cutaway,
            "verdict_cta_card": self._scene_verdict_cta_card,
        }
        fn = dispatch.get(scene_key, self._scene_cab_halts_midshaft)
        fn(draw, p, t, beat_progress, rms)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        assert self.palette is not None and self.bg_alert is not None
        img.paste(self.bg_alert)
        self._scene_wedges_pinch_rails(draw, self.palette, t=0.45, prog=0.85, rms=0.4)
