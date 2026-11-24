"""Channel Profile Picture (PFP 1080x1080), Circular Crop Preview, and YouTube Watermark (150x150) for BOLT (UNIT-01)."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cts_factory.config import BrandConfig
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette, build_stage_background
from cts_factory.engine.primitives import draw_dotted_arc, load_font
from cts_factory.engine.renderer3d import Camera3D, Scene3D


def build_channel_pfp_and_watermark(
    brand: BrandConfig,
    marca_dir: Path,
    repo_root: Path | None = None,
) -> dict[str, Path]:
    """Generate 1080x1080 3D PFP of BOLT (UNIT-01), multi-size circular preview, and 150x150 YouTube watermark."""
    marca_dir.mkdir(parents=True, exist_ok=True)
    p = Palette.from_brand(brand)
    size = 1080

    # Deep studio radial spotlight background tuned for instant pop inside small circular avatars
    base_img = build_stage_background(size, size, p, spot_color=p.cyan, spot_cy=0.48, grid_step=72)
    bg_bgr = cv2.cvtColor(np.array(base_img), cv2.COLOR_RGB2BGR)

    # Heroic close-up of BOLT (UNIT-01) framed cleanly inside a CNC machined brass gear halo with zero ring overlap!
    cam = Camera3D(eye=(0.0, 0.70, 4.85), target=(0.0, 0.62, 0.0), fov_deg=34.0, width=size, height=size, cy_offset=28.0)
    sc = Scene3D(cam)
    # Framing CNC brass gear halo right behind BOLT's head & shoulders (reads unmistakably even at 48px!)
    sc.add_gear_3d((0.0, 0.66, -0.92), 1.32, 0.24, 18, 0.22, (224, 174, 72), metallic=0.78)
    # Subtle glowing cyan outer calibration nodes around the gear ring
    for i in range(12):
        a = i * (2.0 * math.pi / 12.0)
        sc.add_sphere((math.cos(a) * 1.48, 0.66 + math.sin(a) * 1.48, -0.88), 0.052, (0, 212, 255), emissive=0.90, bloom=True)

    # BOLT (UNIT-01) hero bust & friendly greeting pose cleanly inside circular safe zone
    add_crash_test_dummy(
        sc,
        pos=(0.0, -0.22, 0.24),
        scale=1.06,
        yaw=-0.08,
        pose="relief_wave",
        emotion="cta",
        t=0.45,
        ground_shadow=False,
    )

    rendered_bgr = sc.render_to_bgr(bg_bgr)
    pfp = Image.fromarray(cv2.cvtColor(rendered_bgr, cv2.COLOR_BGR2RGB), mode="RGB")
    draw = ImageDraw.Draw(pfp)

    # Crisp circular HUD telemetry rings hugging the outer circular border cleanly (zero overlap on BOLT!)
    draw_dotted_arc(draw, 540, 540, 514, 0, 360, p.cyan, width=6, step_deg=12)
    draw.ellipse([540 - 494, 540 - 494, 540 + 494, 540 + 494], outline=p.amber, width=8)

    pfp_path = marca_dir / "pfp_bolt_1080x1080.png"
    pfp.save(pfp_path, format="PNG", optimize=True)

    # Multi-size circular crop preview sheet (512px profile, 160px Shorts shelf, 64px comment avatar)
    sheet = Image.new("RGB", (1080, 720), (14, 20, 32))
    sdraw = ImageDraw.Draw(sheet)
    font_bold = str(brand.visual_style.resolve_font_path("secondary", repo_root=repo_root))
    f_hdr = load_font(font_bold, 30)
    f_lbl = load_font(font_bold, 22)
    sdraw.text((48, 32), "FAILSAFE LAB // BOLT (UNIT-01) PFP CIRCULAR CROP PREVIEW", font=f_hdr, fill=p.text_highlight)

    def _paste_circle(src: Image.Image, target_d: int, cx: int, cy: int, label: str) -> None:
        resized = src.resize((target_d, target_d), Image.Resampling.LANCZOS)
        mask = Image.new("L", (target_d, target_d), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, target_d - 1, target_d - 1], fill=255)
        sheet.paste(resized, (cx - target_d // 2, cy - target_d // 2), mask)
        sdraw.ellipse(
            [cx - target_d // 2 - 2, cy - target_d // 2 - 2, cx + target_d // 2 + 2, cy + target_d // 2 + 2],
            outline=p.cyan,
            width=3,
        )
        bb = sdraw.textbbox((0, 0), label, font=f_lbl)
        sdraw.text((cx - (bb[2] - bb[0]) / 2, cy + target_d // 2 + 18), label, font=f_lbl, fill=p.text_primary)

    _paste_circle(pfp, 440, 290, 355, "Channel Page (440px)")
    _paste_circle(pfp, 180, 695, 290, "Shorts / Reels (180px)")
    _paste_circle(pfp, 72, 920, 290, "Comment (72px)")
    _paste_circle(pfp, 48, 920, 455, "Tiny (48px)")

    preview_path = marca_dir / "pfp_bolt_circle_preview.png"
    sheet.save(preview_path, format="PNG", optimize=True)

    # 150x150 transparent circular YouTube Video Watermark (Studio Branding button)
    wm_size = 150
    wm_rgb = pfp.resize((wm_size, wm_size), Image.Resampling.LANCZOS).convert("RGBA")
    wm_mask = Image.new("L", (wm_size, wm_size), 0)
    ImageDraw.Draw(wm_mask).ellipse([2, 2, wm_size - 3, wm_size - 3], fill=255)
    wm = Image.new("RGBA", (wm_size, wm_size), (0, 0, 0, 0))
    wm.paste(wm_rgb, (0, 0), wm_mask)
    ImageDraw.Draw(wm).ellipse([3, 3, wm_size - 4, wm_size - 4], outline=(*p.amber, 255), width=4)
    wm_path = marca_dir / "youtube_watermark_150x150.png"
    wm.save(wm_path, format="PNG", optimize=True)

    return {
        "pfp": pfp_path,
        "pfp_preview": preview_path,
        "watermark": wm_path,
    }
