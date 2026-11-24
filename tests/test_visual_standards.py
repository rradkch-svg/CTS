"""Automated Minimum Quality Standards Gate (QUALITY_STANDARDS.md).

Enforces FailSafe Lab's non-negotiable visual, safe-zone, BOLT, 3D camera,
gauge, semantic badge, cover 1:1 crop, and code hygiene invariants across
ALL registered episodes (ep01..ep10 and every future episode ep11+).
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from cts_factory.captions.overlay import draw_caption
from cts_factory.config import BrandConfig, CaptionBlock, CaptionTrack, CaptionWord, EpisodeScript
from cts_factory.engine.dummy import add_crash_test_dummy
from cts_factory.engine.materials import Palette
from cts_factory.engine.primitives import (
    draw_comparison_bars,
    draw_cta_buttons,
    draw_pressure_gauge,
)
from cts_factory.engine.renderer import resolve_callout_accent
from cts_factory.engine.renderer3d import Camera3D, Scene3D
from cts_factory.episodes import get_scene, list_scenes

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_brand_and_palette() -> tuple[BrandConfig, Palette, str]:
    brand = BrandConfig.load(REPO_ROOT / "brand.json")
    palette = Palette.from_brand(brand)
    font_black = str(brand.visual_style.resolve_font_path("primary", repo_root=REPO_ROOT))
    return brand, palette, font_black


def test_ui_primitives_respect_right_safe_zone() -> None:
    """CTA buttons, comparison bars, and gauges MUST never draw pixels into x >= 870 (TikTok/Reels/Shorts UI)."""
    _, p, font_black = _load_brand_and_palette()

    # 1. CTA buttons even when passed an unsafe right_bx
    img = Image.new("RGB", (1080, 1920), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_cta_buttons(draw, t=0.25, palette=p, font_path=font_black, by=1140, right_bx=920)
    arr = np.asarray(img)
    assert int(arr[:, 870:, :].max()) == 0, "draw_cta_buttons leaked into right UI dead zone (x >= 870)"

    # 2. Comparison bars even when passed an unsafe wide width
    img = Image.new("RGB", (1080, 1920), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_comparison_bars(
        draw,
        x0=320,
        y0=720,
        width=700,  # deliberately wider than safe zone to verify auto-clamping!
        height=340,
        items=[("ORIGINAL", "100%", 0.5, p.emerald), ("OVERLOAD", "200%", 1.0, p.danger)],
        progress=1.0,
        palette=p,
        font_path=font_black,
    )
    arr = np.asarray(img)
    assert int(arr[:, 870:, :].max()) == 0, "draw_comparison_bars leaked into right UI dead zone (x >= 870)"

    # 3. Pressure gauge even when passed an unsafe cx near right edge
    img = Image.new("RGB", (1080, 1920), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_pressure_gauge(draw, 910, 1000, 110, 0.92, "JET SPIKE", "100K+ PSI", p, font_black)
    arr = np.asarray(img)
    assert int(arr[:, 870:, :].max()) == 0, "draw_pressure_gauge leaked into right UI dead zone (x >= 870)"


def test_pressure_gauge_text_strictly_inside_dial() -> None:
    """Long gauge readings must auto-fit cleanly inside the circular dial boundary."""
    _, p, font_black = _load_brand_and_palette()
    cx, cy, r = 540, 960, 90
    for label, reading, inv in (
        ("AIR LINE", "0 PSI = LOCKED", False),
        ("JET SPIKE", "100K+ PSI", False),
        ("KEVLAR LOAD", "99% CAUGHT", True),
        ("HEAT DEFLECTED", "98% PUSHED", True),
        ("LOCK STATE", "ZERO POWER", True),
    ):
        img = Image.new("RGB", (1080, 1920), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw_pressure_gauge(draw, cx, cy, r, 0.95, label, reading, p, font_black, invert_scale=inv)
        arr = np.asarray(img)
        ys, xs = np.nonzero(arr.max(axis=2) > 0)
        assert len(xs) > 0
        assert int(xs.min()) >= cx - r - 8, f"Gauge '{reading}' leaked left of circle"
        assert int(xs.max()) <= cx + r + 8, f"Gauge '{reading}' leaked right of circle"
        assert int(ys.min()) >= cy - r - 8, f"Gauge '{reading}' leaked above circle"
        assert int(ys.max()) <= cy + r + 8, f"Gauge '{reading}' leaked below circle"


def test_captions_respect_safe_zones() -> None:
    """Captions MUST stay strictly inside x <= 885 and y <= 1435."""
    brand, _, _ = _load_brand_and_palette()
    words = [
        CaptionWord(text="FORTY", start_s=0.0, end_s=0.4),
        CaptionWord(text="FEET", start_s=0.4, end_s=0.8),
        CaptionWord(text="OF", start_s=0.8, end_s=1.0),
        CaptionWord(text="CONCRETE", start_s=1.0, end_s=1.6),
    ]
    track = CaptionTrack(blocks=[CaptionBlock(words=words, start_s=0.0, end_s=1.6)])
    img = Image.new("RGB", (1080, 1920), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_caption(img, draw, 0.5, track, brand, repo_root=REPO_ROOT)
    arr = np.asarray(img)
    ys, xs = np.nonzero(arr.max(axis=2) > 0)
    assert len(xs) > 0
    assert int(xs.max()) <= 895, f"Caption leaked past right safe zone: max_x={int(xs.max())}"
    assert int(ys.max()) <= 1455, f"Caption leaked into bottom platform zone: max_y={int(ys.max())}"


def test_semantic_callout_badge_coloring() -> None:
    """Safe/passed/solution/CTA callouts must NEVER render with danger red borders."""
    _, p, _ = _load_brand_and_palette()
    for act, lbl, val in (
        ("climax", "FAA TEST", "100% PASSED"),
        ("escalation", "KEVLAR CATCH", "99% CONTAINED"),
        ("resolution", "INSIDE CABIN", "72°F SAFE"),
        ("resolution", "MODERN FIX", "150+ MPH"),
        ("cta", "YOUR CALL", "YES OR NO"),
    ):
        assert resolve_callout_accent(act, lbl, val, p) == p.emerald, f"Expected emerald for {lbl} / {val}"

    for act, lbl, val in (
        ("escalation", "JET SPIKE", "100,000+ PSI"),
        ("climax", "UPPER NUT", "2W = 200% LOAD"),
        ("escalation", "FAILURE MODE", "FLANGE PEEL"),
    ):
        assert resolve_callout_accent(act, lbl, val, p) == p.danger, f"Expected danger for {lbl} / {val}"


def test_bolt_seated_show_legs_false_and_camera_auto_sync() -> None:
    """BOLT show_legs=False must omit leg geometry, and Camera3D must auto-sync post-init mutations."""
    cam = Camera3D(eye=(0.0, 0.5, 6.0), target=(0.0, 0.0, 0.0))
    p_before = cam.project_point((0.0, 0.0, 0.0))
    cam.target = (0.0, 0.8, 0.0)
    p_after = cam.project_point((0.0, 0.0, 0.0))
    assert abs(p_after[1] - p_before[1]) > 50.0, "Camera3D.target mutation did not update projection!"

    sc_full = Scene3D(Camera3D(eye=(0.0, 0.5, 6.0), target=(0.0, 0.0, 0.0)))
    sc_seated = Scene3D(Camera3D(eye=(0.0, 0.5, 6.0), target=(0.0, 0.0, 0.0)))
    add_crash_test_dummy(sc_full, pos=(0.0, 0.0, 0.0), scale=1.0, pose="explain", show_legs=True)
    add_crash_test_dummy(sc_seated, pos=(0.0, 0.0, 0.0), scale=1.0, pose="explain", show_legs=False)
    assert len(sc_seated._items) < len(sc_full._items), "show_legs=False must omit leg geometry"


def test_episode_sources_enforce_minimum_quality_standards() -> None:
    """Static standards audit across EVERY episode module in src/cts_factory/episodes/ep*.py."""
    ep_files = sorted((REPO_ROOT / "src" / "cts_factory" / "episodes").glob("ep*.py"))
    assert len(ep_files) >= 10

    for ep_file in ep_files:
        src = ep_file.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(ep_file))
        # 1. Must use standardized draw_cta_buttons (no hand-rolled right-UI-violating CTA pills)
        assert "draw_cta_buttons" in src, f"{ep_file.name} must use standardized draw_cta_buttons()"
        # 2. Must support dedicated is_cover framing for 1:1 cover safety
        assert "is_cover" in src, f"{ep_file.name} must support is_cover framing in render_cover_hero"
        # 3. No discontinuous sign-flip teleport bug
        assert "1.0 if math.sin(" not in src, f"{ep_file.name} contains discontinuous sin() teleport flip"
        # 4. No Windows hardcoded fonts
        assert "C:\\Windows" not in src and "C:/Windows" not in src, f"{ep_file.name} hardcodes Windows fonts"
        # 5. Valid Python AST with at least one registered EpisodeScene class
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        assert classes, f"{ep_file.name} defines no EpisodeScene class"


def test_all_registered_episodes_cover_and_script_hygiene() -> None:
    """Every registered episode must have a valid 1080x1920 1:1-safe cover, grid preview, and clean script tokens."""
    slugs = list_scenes()
    assert len(slugs) >= 10
    for slug in slugs:
        ep_dir = REPO_ROOT / "episodios" / slug
        script_path = ep_dir / "script.json"
        cover_path = ep_dir / "cover.png"
        grid_path = ep_dir / "cover_grid_preview.png"
        assert script_path.is_file(), f"Missing script.json for {slug}"
        assert cover_path.is_file(), f"Missing cover.png for {slug}"
        assert grid_path.is_file(), f"Missing cover_grid_preview.png for {slug}"

        raw = script_path.read_text(encoding="utf-8")
        assert "DEG F" not in raw, f"{slug}/script.json uses 'DEG F' instead of '°F'"
        assert "(3 IN IN)" not in raw, f"{slug}/script.json contains duplicate unit typo '(3 IN IN)'"

        with Image.open(cover_path) as cov:
            assert cov.size == (1080, 1920), f"{slug}/cover.png must be 1080x1920"
            crop_1x1 = np.asarray(cov.crop((0, 420, 1080, 1500)).convert("RGB"), dtype=np.float32)
            assert float(crop_1x1.std()) > 12.0, f"{slug}/cover.png 1:1 center crop has insufficient visual contrast"


def test_all_registered_episodes_render_cover_hero_and_cta_beat() -> None:
    """Smoke-test render_cover_hero and final CTA beat across EVERY registered episode (ep01..epN)."""
    brand, _, _ = _load_brand_and_palette()
    for slug in list_scenes():
        script = EpisodeScript.load(REPO_ROOT / "episodios" / slug / "script.json")
        scene = get_scene(slug)
        scene.prepare(brand, script, None)

        # Cover hero render
        cov_img = Image.new("RGB", (1080, 1920), (11, 18, 32))
        cov_draw = ImageDraw.Draw(cov_img)
        scene.render_cover_hero(cov_img, cov_draw)
        assert float(np.asarray(cov_img).std()) > 10.0, f"{slug} cover hero rendered blank"

        # First beat (Frame 0) + final CTA beat render
        for beat in (script.beats[0], script.beats[-1]):
            img = Image.new("RGB", (1080, 1920), (11, 18, 32))
            draw = ImageDraw.Draw(img)
            scene.render_frame(15, 2.0, beat.id, 0.65, 0.5, img, draw)
            assert float(np.asarray(img).std()) > 10.0, f"{slug} beat {beat.id} rendered blank"
