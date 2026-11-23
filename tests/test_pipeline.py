"""Unit tests for 2.5D engine, procedural audio/SFX, packaging, and QA modules."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from cts_factory.audio.synth_bed import generate_ambient_bed, synthesize_sfx
from cts_factory.audio.tts import soft_trim_silence
from cts_factory.captions.align import _group_into_blocks, _reconcile_beat_words
from cts_factory.config import BrandConfig, EpisodeScript
from cts_factory.engine.materials import Palette, build_stage_background
from cts_factory.episodes import get_scene, list_scenes
from cts_factory.packaging.banner import build_channel_banner
from cts_factory.packaging.cover import build_episode_package

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_registered_episodes_and_single_frame_render() -> None:
    slugs = list_scenes()
    assert "ep01_elevator_safety_brake" in slugs
    assert "ep02_submersible_implosion_physics" in slugs

    brand = BrandConfig.load(REPO_ROOT / "brand.json")
    for slug in ("ep01_elevator_safety_brake", "ep02_submersible_implosion_physics"):
        script = EpisodeScript.load(REPO_ROOT / "episodios" / slug / "script.json")
        scene = get_scene(slug)
        scene.prepare(brand, script, None)
        img = Image.new("RGB", (1080, 1920), (11, 18, 32))
        draw = ImageDraw.Draw(img)
        for beat in script.beats:
            scene.render_frame(0, 0.5, beat.id, 0.5, 0.4, img, draw)
        arr = np.asarray(img)
        assert arr.shape == (1920, 1080, 3)
        assert float(arr.std()) > 10.0


def test_ambient_bed_has_no_dead_silence_and_sfx_nonzero() -> None:
    bed = generate_ambient_bed(duration_s=6.0, bpm=104, mood="mechanical")
    assert bed.shape == (6 * 48000, 2)
    # Every 0.5s window must stay well above -55 dB
    win = 24000
    for i in range(1, 11):
        seg = bed[i * win : (i + 1) * win]
        rms_db = 20.0 * np.log10(float(np.sqrt(np.mean(seg * seg))) + 1e-12)
        assert rms_db > -45.0

    for name in ("cable_snap", "wedge_lock_slam", "implosion_thud", "deep_sonar_pulse", "glass_crack"):
        clip = synthesize_sfx(name)
        assert len(clip) > 1000
        assert float(np.max(np.abs(clip))) > 0.5


def test_soft_trim_preserves_tail_padding() -> None:
    sr = 48000
    sig = np.zeros(sr * 2, dtype=np.float32)
    t = np.arange(sr // 2, dtype=np.float32) / sr
    sig[sr // 2 : sr] = 0.5 * np.sin(2.0 * np.pi * 440.0 * t)
    trimmed = soft_trim_silence(sig, sr=sr, threshold_db=-52.0, head_pad_ms=70, tail_pad_ms=90)
    assert len(trimmed) > int(sr * 0.60)
    assert len(trimmed) < int(sr * 0.90)


def test_caption_reconciliation_and_chunking() -> None:
    tokens = ["Imagine", "stepping", "into", "a", "skyscraper", "elevator."]
    whisper = [(tok, 0.1 + i * 0.3, 0.35 + i * 0.3) for i, tok in enumerate(tokens)]
    words = _reconcile_beat_words(tokens, whisper, 0.0, 2.2)
    assert [w.text for w in words] == tokens
    blocks = _group_into_blocks(words, min_words=2, max_words=4)
    assert all(1 <= len(b.words) <= 4 for b in blocks)
    assert all(b.start_s < b.end_s for b in blocks)


def test_banner_and_cover_packaging(tmp_path: Path) -> None:
    brand = BrandConfig.load(REPO_ROOT / "brand.json")
    banner, preview = build_channel_banner(brand, tmp_path / "marca", repo_root=REPO_ROOT)
    assert banner.is_file() and preview.is_file()
    assert banner.stat().st_size < 6 * 1024 * 1024
    with Image.open(banner) as im:
        assert im.size == (2560, 1440)

    script = EpisodeScript.load(REPO_ROOT / "episodios/ep01_elevator_safety_brake/script.json")
    scene = get_scene(script.slug)
    out = build_episode_package(brand, script, scene, tmp_path / "ep01", repo_root=REPO_ROOT)
    assert out["cover"].is_file() and out["cover_grid_preview"].is_file()
    assert out["publish_meta"].is_file() and out["publish_checklist"].is_file()
    with Image.open(out["cover"]) as im:
        assert im.size == (1080, 1920)
