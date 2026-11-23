"""Episode 02: Why Deep-Sea Hulls IMPLODE in Milliseconds — 2.5D CAD Vector Scene."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript
from cts_factory.engine.materials import Palette, build_stage_background, lerp_color, scale_rgb
from cts_factory.engine.primitives import (
    draw_bevel_rect,
    draw_comparison_bars,
    draw_dotted_arc,
    draw_force_arrow,
    draw_iso_box,
    draw_pressure_gauge,
    draw_sparks,
    load_font,
)
from cts_factory.engine.projection import clamp, ease_in_out_cubic, ease_out_cubic, get_camera
from cts_factory.episodes.base import EpisodeScene, register_scene


@register_scene("ep02_submersible_implosion_physics")
class SubmersibleImplosionScene(EpisodeScene):
    """Articulated 12-beat 2.5D materials-science & hydrostatic physics cutaway for Episode 02."""

    slug = "ep02_submersible_implosion_physics"
    episode_id = "ep02"

    def __init__(self) -> None:
        self.brand: BrandConfig | None = None
        self.script: EpisodeScript | None = None
        self.palette: Palette | None = None
        self.bg_ocean: Image.Image | None = None
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
        self.bg_ocean = build_stage_background(w, h, self.palette, spot_color=self.palette.cyan, ocean_gradient=True)
        self.bg_alert = build_stage_background(w, h, self.palette, spot_color=self.palette.danger, ocean_gradient=True)
        self.bg_safe = build_stage_background(w, h, self.palette, spot_color=self.palette.emerald, ocean_gradient=True)
        self.font_black = str(brand.visual_style.resolve_font_path("primary"))
        self.font_bold = str(brand.visual_style.resolve_font_path("secondary"))
        self.beat_map = {b.id: (b.camera_preset, b.scene_key) for b in script.beats}

    def _draw_titanium_sphere(
        self,
        draw: ImageDraw.ImageDraw,
        p: Palette,
        cx: float,
        cy: float,
        radius: float,
        ring_col: tuple[int, int, int] | None = None,
    ) -> None:
        """Draw a stylized 2.5D shaded metallic titanium pressure sphere with cutaway wall."""
        # Outer metallic rim
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=p.steel_dark, outline=p.ink, width=5)
        draw.ellipse(
            [cx - radius * 0.94, cy - radius * 0.94, cx + radius * 0.88, cy + radius * 0.88],
            fill=p.steel_mid,
        )
        # Specular highlight crescent
        draw.ellipse(
            [cx - radius * 0.72, cy - radius * 0.74, cx + radius * 0.30, cy + radius * 0.28],
            fill=p.steel_light,
        )
        # Inner pressurized cabin cutaway circle
        inner_r = radius * 0.64
        draw.ellipse(
            [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
            fill=p.surface_panel,
            outline=ring_col or p.emerald,
            width=5,
        )
        # Viewport dome ring
        vp_r = inner_r * 0.42
        draw.ellipse(
            [cx - vp_r, cy - vp_r, cx + vp_r, cy + vp_r],
            fill=scale_rgb(p.cyan, 0.35),
            outline=p.cyan,
            width=3,
        )

    def _draw_composite_cylinder(
        self,
        draw: ImageDraw.ImageDraw,
        p: Palette,
        cx: float,
        cy: float,
        half_w: float = 195.0,
        half_h: float = 105.0,
        seam_stress: float = 0.0,
        buckling: float = 0.0,
    ) -> None:
        """Draw a 2.5D carbon-fiber cylindrical hull bonded to machined titanium endcaps."""
        # Left & right machined titanium hemispherical endcaps
        cap_w = half_h * 0.75
        for sign in (-1, 1):
            ex = cx + sign * half_w
            draw.ellipse(
                [ex - cap_w, cy - half_h, ex + cap_w, cy + half_h],
                fill=p.steel_mid,
                outline=p.ink,
                width=4,
            )
            draw.ellipse(
                [ex - cap_w * 0.65, cy - half_h * 0.75, ex + cap_w * 0.55, cy + half_h * 0.25],
                fill=p.steel_light,
            )

        # Central carbon-fiber composite tube with optional inward buckling waist
        n_steps = 18
        top_pts: list[tuple[float, float]] = []
        bot_pts: list[tuple[float, float]] = []
        for i in range(n_steps + 1):
            u = i / n_steps
            x = (cx - half_w) + u * (2.0 * half_w)
            pinch = math.sin(u * math.pi) ** 1.6 * buckling * half_h * 0.85
            top_pts.append((x, cy - half_h + pinch))
            bot_pts.append((x, cy + half_h - pinch))
        body_poly = top_pts + list(reversed(bot_pts))
        body_col = lerp_color((36, 46, 64), p.danger, buckling * 0.45)
        draw.polygon(body_poly, fill=body_col, outline=p.ink, width=4)

        # Carbon-fiber woven cross-hatch pattern
        for k in range(-6, 7):
            x_a = cx + k * 28
            if cx - half_w + 18 < x_a < cx + half_w - 18:
                draw.line([(x_a - 14, cy - half_h * 0.75), (x_a + 14, cy + half_h * 0.75)], fill=p.steel_dark, width=2)
                draw.line([(x_a + 14, cy - half_h * 0.75), (x_a - 14, cy + half_h * 0.75)], fill=p.steel_dark, width=2)

        # Specular rim highlight along top crown
        draw.line(top_pts[1:-1], fill=p.steel_light, width=3)

        # Titanium-to-carbon bonded end-rings (stress hotspots)
        ring_col = lerp_color(p.brass, p.danger, clamp(seam_stress))
        for sign in (-1, 1):
            rx = cx + sign * (half_w - 14)
            draw.rounded_rectangle(
                [rx - 14, cy - half_h - 6, rx + 14, cy + half_h + 6],
                radius=6,
                fill=ring_col,
                outline=p.ink,
                width=3,
            )
            if seam_stress > 0.35:
                draw.ellipse(
                    [rx - 28, cy - half_h - 18, rx + 28, cy + half_h + 18],
                    outline=p.danger,
                    width=4,
                )

    def _draw_radial_pressure_arrows(
        self,
        draw: ImageDraw.ImageDraw,
        p: Palette,
        cx: float,
        cy: float,
        rx_out: float,
        ry_out: float,
        rx_in: float,
        ry_in: float,
        count: int,
        color: tuple[int, int, int],
        t: float,
    ) -> None:
        for i in range(count):
            ang = (2.0 * math.pi * i) / count
            x0 = cx + math.cos(ang) * rx_out
            y0 = cy + math.sin(ang) * ry_out
            x1 = cx + math.cos(ang) * rx_in
            y1 = cy + math.sin(ang) * ry_in
            draw_force_arrow(draw, x0, y0, x1, y1, color, width=10, head_len=22, head_w=17, pulse=t * 2.2 + i * 0.1)

    def _scene_hull_pressure_peak(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 1 (Frame 0 HERO): Deep-sea hull ringed by 12 glowing inward pressure arrows."""
        cam = get_camera("FRAME0_HERO", t, rms=rms, impact=0.65)
        cx, cy = cam.cx, 995.0
        draw_dotted_arc(draw, cx, cy, 335 + 8 * math.sin(t * 7.0), 0, 360, p.cyan, width=4, step_deg=10)
        self._draw_composite_cylinder(draw, p, cx, cy, half_w=180, half_h=95, seam_stress=0.85, buckling=0.14 + 0.06 * math.sin(t * 14.0))
        self._draw_radial_pressure_arrows(draw, p, cx, cy, 370, 295, 225, 130, 12, p.danger, t)
        draw_sparks(draw, cx - 165, cy, t, 10, 90, 90, p, seed=19)
        draw_sparks(draw, cx + 165, cy, t, 10, 90, 90, p, seed=29)

    def _scene_depth_3800m_scale(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 2: Ocean depth scale descending down to 3,800 meters."""
        cam = get_camera("ISO_WIDE", t, rms=rms)
        cx = cam.cx + 45
        # Left bathymetric depth ruler
        ruler_x = 175
        draw.line([(ruler_x, 665), (ruler_x, 1315)], fill=p.cyan, width=4)
        f = load_font(self.font_bold, 24)
        for idx, depth_lbl in enumerate(("0 M", "1,000 M", "2,000 M", "3,000 M", "3,800 M")):
            ry = 680 + idx * 155
            draw.line([(ruler_x - 16, ry), (ruler_x + 18, ry)], fill=p.text_highlight if idx == 4 else p.cyan, width=3)
            draw.text((ruler_x + 28, ry - 14), depth_lbl, font=f, fill=p.text_highlight if idx == 4 else p.steel_light)

        # Descending submersible marker
        sub_y = 740 + ease_out_cubic(prog) * 475
        self._draw_composite_cylinder(draw, p, cx + 80, sub_y, half_w=120, half_h=58, seam_stress=prog * 0.6)
        draw.line([(ruler_x + 18, sub_y), (cx - 85, sub_y)], fill=p.amber, width=3)
        draw_force_arrow(draw, cx + 80, sub_y - 125, cx + 80, sub_y - 68, p.cyan, width=10, pulse=t * 2.0)

    def _scene_pressure_stack_arrows(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 3: 360-degree hydrostatic arrows + live 380 ATM pressure gauge."""
        cam = get_camera("ISO_WIDE", t, rms=rms)
        cx, cy = 415.0, 995.0
        self._draw_composite_cylinder(draw, p, cx, cy, half_w=135, half_h=72, seam_stress=0.45)
        self._draw_radial_pressure_arrows(draw, p, cx, cy, 270, 220, 170, 102, 10, p.cyan, t)
        atm = int(round(1 + prog * 379))
        draw_pressure_gauge(
            draw,
            cx=820,
            cy=995,
            radius=138,
            value_0_to_1=clamp(prog * 0.92 + 0.08),
            label="PRESSURE",
            reading=f"{atm} ATM",
            palette=p,
            font_path=self.font_black,
        )

    def _scene_tonnage_per_sqft(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 4: Isometric 1 sq ft hull plate crushed by 400-ton downward load vectors."""
        cam = get_camera("EXPLODED_BLUEPRINT", t, rms=rms)
        # 2.5D machined 1 FT x 1 FT steel plate
        draw_iso_box(
            draw,
            cam,
            x0=-130,
            y0=-130,
            z0=-145,
            dx=260,
            dy=260,
            dz=46,
            top_col=p.steel_light,
            left_col=p.steel_mid,
            right_col=p.steel_dark,
            ink_col=p.ink,
        )
        # 5 heavy amber/crimson downward load arrows pressing onto the 1 sq ft plate
        for off_x in (-160, -80, 0, 80, 160):
            draw_force_arrow(draw, 540 + off_x, 690, 540 + off_x, 965, p.amber if abs(off_x) > 80 else p.danger, width=13, pulse=t * 2.5)
        f = load_font(self.font_black, 42)
        bb = draw.textbbox((0, 0), "400 TONS / 1 SQ FT", font=f)
        draw.text((540 - (bb[2] - bb[0]) / 2, 1235), "400 TONS / 1 SQ FT", font=f, fill=p.text_highlight, stroke_width=5, stroke_fill=p.ink)

    def _scene_sphere_uniform_stress(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 5: Certified titanium sphere with uniform 360-deg emerald/cyan compression."""
        cam = get_camera("EXPLODED_BLUEPRINT", t, rms=rms)
        cx, cy = cam.cx, 965.0
        draw_dotted_arc(draw, cx, cy, 275, 0, 360, p.emerald, width=4, step_deg=8)
        self._draw_titanium_sphere(draw, p, cx, cy, 165, ring_col=p.emerald)
        self._draw_radial_pressure_arrows(draw, p, cx, cy, 300, 300, 188, 188, 12, p.emerald, t)
        f = load_font(self.font_bold, 28)
        lbl = "UNIFORM MEMBRANE STRESS"
        bb = draw.textbbox((0, 0), lbl, font=f)
        draw.text((cx - (bb[2] - bb[0]) / 2, 1300), lbl, font=f, fill=p.emerald)

    def _scene_cylinder_joint_hotspot(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 6: Carbon-fiber cylinder bonded to titanium end-rings with crimson seam hotspots."""
        cam = get_camera("EXPLODED_BLUEPRINT", t, rms=rms)
        cx, cy = cam.cx, 985.0
        pulse = 0.55 + 0.45 * math.sin(t * 9.0)
        self._draw_composite_cylinder(draw, p, cx, cy, half_w=205, half_h=110, seam_stress=pulse)
        # Exploded dimension callouts pointing at bonded seam
        f = load_font(self.font_bold, 26)
        draw.line([(cx - 190, cy - 118), (cx - 250, cy - 220)], fill=p.danger, width=4)
        draw.text((cx - 390, cy - 255), "TITANIUM BOND SEAM", font=f, fill=p.danger)
        draw.line([(cx, cy + 115), (cx, cy + 215)], fill=p.cyan, width=4)
        draw.text((cx - 175, cy + 225), "CARBON-FIBER WALL (TENSION)", font=f, fill=p.cyan)
        # Opposing tensile vs compressive comparison arrows
        draw_force_arrow(draw, cx - 95, cy, cx - 175, cy, p.emerald, width=9, head_len=18, head_w=14)
        draw_force_arrow(draw, cx + 95, cy, cx + 175, cy, p.emerald, width=9, head_len=18, head_w=14)
        draw_force_arrow(draw, cx, cy - 245, cx, cy - 125, p.danger, width=13, pulse=t * 2.4)

    def _scene_ply_shear_fatigue(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 7: Macro cross-section of carbon-fiber plies splitting via micro-delamination."""
        cam = get_camera("MACRO_CUTAWAY", t, rms=rms, impact=0.35 if prog > 0.4 else 0.0)
        cx, cy = cam.cx, 995.0
        n_plies = 8
        ply_h = 46
        start_y = cy - (n_plies * ply_h) / 2
        for i in range(n_plies):
            sep = (i - 3.5) * ease_in_out_cubic(prog) * 14.0
            y0 = start_y + i * ply_h + sep
            col = p.steel_dark if i % 2 == 0 else (42, 54, 74)
            draw_bevel_rect(draw, cx - 320, y0, cx + 320, y0 + ply_h - 8, fill=col, ink=p.ink, depth=14.0, radius=4)
            # Jagged crimson delamination crack unzipping between middle plies
            if i in (2, 4, 5):
                crack_len = clamp((prog - 0.15) * 1.4) * 520.0
                if crack_len > 15:
                    pts = []
                    steps = 12
                    for s in range(steps + 1):
                        ux = cx - 260 + (s / steps) * crack_len
                        uy = y0 + ply_h - 4 + math.sin(s * 2.7 + i) * 7.0
                        pts.append((ux, uy))
                    draw.line(pts, fill=p.danger, width=6)
                    draw.line(pts, fill=p.text_highlight, width=2)
        draw_force_arrow(draw, cx, start_y - 115, cx, start_y - 15, p.amber, width=14, pulse=t * 2.4)
        draw_force_arrow(draw, cx, start_y + n_plies * ply_h + 135, cx, start_y + n_plies * ply_h + 35, p.amber, width=14, pulse=t * 2.4)

    def _scene_dimple_instability(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 8: Rigid composite wall snaps an inward buckling dimple with crimson stress rings."""
        dimple = ease_out_cubic(clamp((prog - 0.35) / 0.55))
        cam = get_camera("MACRO_CUTAWAY", t, rms=rms, impact=0.7 * dimple)
        cx, cy = cam.cx, 995.0
        # Curved hull wall profile indenting sharply inward
        top_outer, top_inner = [], []
        for i in range(36):
            u = i / 35.0
            x = 160 + u * 760
            arch = math.sin(u * math.pi) * 65.0
            dent = math.exp(-((u - 0.5) / 0.11) ** 2) * dimple * 155.0
            y_out = cy - 95 - arch + dent
            top_outer.append((x, y_out))
            top_inner.append((x, y_out + 74))
        draw.polygon(top_outer + list(reversed(top_inner)), fill=p.steel_mid, outline=p.ink, width=4)
        draw.line(top_outer, fill=p.steel_light, width=4)
        # Concentric crimson instability rings centered on the dimple
        dy = cy - 160 + dimple * 155.0
        for r in (48, 88, 132):
            draw_dotted_arc(draw, cx, dy, r + dimple * 18, 0, 360, p.danger if dimple > 0.25 else p.amber, width=4, step_deg=12)
        draw_force_arrow(draw, cx, dy - 185, cx, dy - 22, p.danger, width=16, pulse=t * 3.0)
        f = load_font(self.font_black, 32)
        draw.text((cx - 195, cy + 165), "SYMMETRY BROKEN -> SNAP", font=f, fill=p.danger if dimple > 0.4 else p.text_highlight)

    def _scene_implosion_wave_020ms(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 9 (CLIMAX): Live 00.0 -> 20.0 ms collapse stopwatch + violent inward buckling."""
        collapse = ease_in_out_cubic(clamp(prog * 1.15))
        cam = get_camera("IMPACT_CLOSEUP", t, rms=rms, impact=1.0 if 0.2 < prog < 0.85 else 0.3)
        cx, cy = cam.cx, 1005.0

        # Imploding composite hull
        self._draw_composite_cylinder(
            draw,
            p,
            cx,
            cy,
            half_w=200 * (1.0 - 0.35 * collapse),
            half_h=110 * (1.0 - 0.42 * collapse),
            seam_stress=1.0,
            buckling=clamp(0.15 + collapse * 0.85),
        )
        # Radial pressure shockwave crashing inward
        r_wave = 340 * (1.0 - 0.55 * collapse)
        draw.ellipse([cx - r_wave, cy - r_wave * 0.72, cx + r_wave, cy + r_wave * 0.72], outline=p.cyan, width=6)
        self._draw_radial_pressure_arrows(
            draw, p, cx, cy, 380 - 90 * collapse, 290 - 70 * collapse, 200 - 110 * collapse, 120 - 65 * collapse, 12, p.danger, t * 2.0
        )
        if collapse > 0.45:
            draw_sparks(draw, cx, cy, t, 24, 240, 175, p, seed=131)

        # Crisp millisecond timer readout
        ms = min(20.0, prog * 22.0)
        f = load_font(self.font_black, 48)
        label = f"T + {ms:04.1f} MS"
        bb = draw.textbbox((0, 0), label, font=f)
        draw.rounded_rectangle([cx - 175, 1225, cx + 175, 1300], radius=14, fill=p.surface_panel, outline=p.danger, width=4)
        draw.text((cx - (bb[2] - bb[0]) / 2, 1236), label, font=f, fill=p.text_highlight)

    def _scene_air_compression_pulse(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 10: High-velocity >1,500 mph water jets adiabatically compressing trapped air core."""
        squeeze = ease_out_cubic(prog)
        cam = get_camera("IMPACT_CLOSEUP", t, rms=rms, impact=0.65)
        cx, cy = cam.cx, 965.0
        # Shrinking superheated central air pocket
        core_r = max(38.0, 155.0 * (1.0 - 0.72 * squeeze))
        for mult, col in ((2.1, p.danger), (1.5, p.amber), (1.0, p.text_highlight), (0.55, (255, 255, 240))):
            rr = core_r * mult
            draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
        # 8 supersonic cyan water inflow vectors slamming inward
        self._draw_radial_pressure_arrows(draw, p, cx, cy, 340, 265, core_r + 48, core_r + 48, 8, p.cyan, t * 2.8)
        f = load_font(self.font_black, 34)
        bb = draw.textbbox((0, 0), "ADIABATIC COMPRESSION", font=f)
        draw.text((cx - (bb[2] - bb[0]) / 2, 1280), "ADIABATIC COMPRESSION", font=f, fill=p.text_highlight, stroke_width=4, stroke_fill=p.ink)

    def _scene_nerve_bar_comparison(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 11: Live comparison bar chart (20 MS IMPLOSION vs 250 MS HUMAN VISUAL NERVE)."""
        draw_comparison_bars(
            draw,
            x0=105,
            y0=720,
            width=870,
            height=410,
            items=[
                ("HULL IMPLOSION COLLAPSE", "20 MS", 20.0 / 250.0, p.danger),
                ("HUMAN VISUAL NERVE SIGNAL", "250 MS", 1.0, p.cyan),
            ],
            progress=ease_out_cubic(min(1.0, prog * 1.45)),
            palette=p,
            font_path=self.font_black,
        )
        # Crisp 10X faster callout banner below bars
        draw.rounded_rectangle([185, 1175, 895, 1265], radius=16, fill=p.surface_panel, outline=p.text_highlight, width=4)
        f = load_font(self.font_black, 36)
        msg = "10X FASTER THAN HUMAN SIGHT"
        bb = draw.textbbox((0, 0), msg, font=f)
        draw.text((540 - (bb[2] - bb[0]) / 2, 1200), msg, font=f, fill=p.text_highlight)

    def _scene_verdict_cta_card(self, draw: ImageDraw.ImageDraw, p: Palette, t: float, prog: float, rms: float) -> None:
        """Beat 12 (CTA): Certified glowing titanium sphere + YES / NO decision chips."""
        cam = get_camera("ISO_WIDE", t, rms=rms)
        cx = cam.cx
        draw_dotted_arc(draw, cx, 890, 215, 0, 360, p.cyan, width=3, step_deg=10)
        self._draw_titanium_sphere(draw, p, cx, 890, 145, ring_col=p.emerald)
        pulse = 1.0 + 0.04 * math.sin(t * 7.0)
        for label, bx, col in (("YES", cx - 210, p.cyan), ("NO", cx + 210, p.amber)):
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
        assert self.palette is not None and self.bg_ocean is not None
        assert self.bg_alert is not None and self.bg_safe is not None
        p = self.palette
        _, scene_key = self.beat_map.get(beat_id, ("ISO_WIDE", "depth_3800m_scale"))

        if scene_key in ("hull_pressure_peak", "ply_shear_fatigue", "dimple_instability", "implosion_wave_020ms", "air_compression_pulse"):
            img.paste(self.bg_alert)
        elif scene_key in ("sphere_uniform_stress", "verdict_cta_card"):
            img.paste(self.bg_safe)
        else:
            img.paste(self.bg_ocean)

        dispatch = {
            "hull_pressure_peak": self._scene_hull_pressure_peak,
            "depth_3800m_scale": self._scene_depth_3800m_scale,
            "pressure_stack_arrows": self._scene_pressure_stack_arrows,
            "tonnage_per_sqft": self._scene_tonnage_per_sqft,
            "sphere_uniform_stress": self._scene_sphere_uniform_stress,
            "cylinder_joint_hotspot": self._scene_cylinder_joint_hotspot,
            "ply_shear_fatigue": self._scene_ply_shear_fatigue,
            "dimple_instability": self._scene_dimple_instability,
            "implosion_wave_020ms": self._scene_implosion_wave_020ms,
            "air_compression_pulse": self._scene_air_compression_pulse,
            "nerve_bar_comparison": self._scene_nerve_bar_comparison,
            "verdict_cta_card": self._scene_verdict_cta_card,
        }
        fn = dispatch.get(scene_key, self._scene_depth_3800m_scale)
        fn(draw, p, t, beat_progress, rms)

    def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        assert self.palette is not None and self.bg_alert is not None
        img.paste(self.bg_alert)
        self._scene_hull_pressure_peak(draw, self.palette, t=0.35, prog=0.5, rms=0.4)
