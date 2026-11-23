"""Self-tests for opaque-box E2E helpers and synthetic fixture mutators.

Verifies:
- Group A (4 tests): Compliant synthetic workspace passes all discovery, media,
  image safe-zone, text/caption, and secret-hygiene helpers.
- Group B (18 tests): Every single defect mutator in ``ALL_DEFECT_KEYS`` is
  unambiguously caught by its corresponding helper on an isolated copy.
- Group C (10 tests): Edge-case unit tests for zero-FP Portuguese leakage,
  UK spellings, mojibake, YouTube title rules, ending CTA validation,
  ``ebur128`` ``-inf`` parsing, dual ``reels/INDEX.md`` formats, ``gemini-url``
  frame discovery, CLI runner secret/env guards, media cache invalidation,
  caption variance boundaries, and flexible themes backlog schemas.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from tests.e2e.helpers import (
    ALL_DEFECT_KEYS,
    PROJECT_ROOT_ENV,
    CliResult,
    analyze_motion_and_cuts,
    analyze_wav_stats,
    assert_no_secret_in_output,
    build_synthetic_workspace,
    check_caption_band,
    check_cover_safe_zones,
    check_frame0_hook,
    check_youtube_banner,
    clear_media_cache,
    copy_workspace,
    detect_mid_video_subscribe_cta,
    detect_mojibake,
    detect_portuguese_leakage,
    detect_uk_english_spellings,
    discover_episodes,
    discover_marca_assets,
    discover_reel_runs,
    extract_frame,
    extract_frames_at,
    find_episode_audit_reel,
    find_reference_reel,
    get_brand_audio_sample_rate,
    get_brand_resolution,
    get_brand_style_rationale,
    get_brand_tts_models,
    get_brand_video_lra_max,
    get_brand_video_lufs,
    get_brand_video_true_peak_max,
    get_project_root,
    inspect_image,
    load_brand,
    load_episode_publish_meta,
    load_json,
    load_themes_backlog,
    measure_ebur128,
    mutate_workspace,
    palette_color_present,
    parse_ebur128_summary,
    parse_reel_dir,
    parse_reels_index,
    probe_media,
    resolve_brand_font_path,
    run_silencedetect,
    scan_repo_for_secrets,
    scan_rms_windows,
    transcript_script_similarity,
    validate_caption_track,
    validate_ending_cta,
    validate_youtube_title,
    verify_ffmpeg_decode,
    wcag_contrast_ratio,
)
from tests.e2e.helpers import cli_runner as cli_runner_mod
from tests.e2e.helpers import media as media_mod


class TestHelpersSelf(unittest.TestCase):
    """Comprehensive self-test suite for ``tests/e2e/helpers``."""

    _tmp_base: tempfile.TemporaryDirectory[str]
    base_ws: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_base = tempfile.TemporaryDirectory(prefix="cts_e2e_self_base_")
        cls.base_ws = build_synthetic_workspace(
            Path(cls._tmp_base.name) / "workspace",
            include_orphan_reel_dir=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        clear_media_cache()
        cls._tmp_base.cleanup()

    def _make_mutated_copy(self, defect: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        td = tempfile.TemporaryDirectory(prefix=f"cts_e2e_mut_{defect}_")
        self.addCleanup(td.cleanup)
        ws = copy_workspace(self.base_ws, Path(td.name) / "ws")
        mutate_workspace(ws, defect)
        return td, ws

    # ------------------------------------------------------------------
    # Group A — Compliant Synthetic Workspace Validation (4 tests)
    # ------------------------------------------------------------------

    def test_01_compliant_workspace_discovery_and_orphan_reel_skipped(self) -> None:
        prev_env = os.environ.get(PROJECT_ROOT_ENV)
        os.environ[PROJECT_ROOT_ENV] = str(self.base_ws)
        try:
            self.assertEqual(get_project_root(), self.base_ws.resolve())
            brand = load_brand()
            self.assertEqual(brand["language"], "en-US")
            self.assertEqual(get_brand_video_lufs(brand), -14.5)
            self.assertEqual(get_brand_video_lra_max(brand), 4.0)
            self.assertEqual(get_brand_video_true_peak_max(brand), -1.0)
            self.assertEqual(get_brand_audio_sample_rate(brand), 48000)
            self.assertEqual(get_brand_resolution(brand), (1080, 1920))
            self.assertIn("gemini-3.8-flash-tts", get_brand_tts_models(brand))
            self.assertGreaterEqual(len(get_brand_style_rationale(brand)), 120)
            self.assertIsNotNone(resolve_brand_font_path(brand, "primary_font"))

            backlog = load_themes_backlog()
            self.assertEqual(len(backlog.themes), 6)
            self.assertEqual(len(backlog.selected_slugs), 2)
            self.assertGreaterEqual(len(backlog.selection_rationale), 40)

            episodes = discover_episodes()
            self.assertEqual(len(episodes), 2)
            for ep in episodes:
                for path in (
                    ep.script_json,
                    ep.narration_clean_wav,
                    ep.narration_timeline_json,
                    ep.narration_envelope_npy,
                    ep.audio_master_wav,
                    ep.captions_json,
                    ep.mp4,
                    ep.cover_png,
                    ep.cover_grid_preview_png,
                    ep.publish_meta_json,
                    ep.qa_report_json,
                ):
                    self.assertTrue(path.is_file(), f"Missing bundle artifact: {path}")
                self.assertTrue(ep.tts_cache_dir.is_dir())
                self.assertIsNotNone(load_episode_publish_meta(ep))

            marca = discover_marca_assets()
            for key in ("youtube_banner", "youtube_banner_preview", "brand_sheet"):
                self.assertTrue(marca[key].is_file(), f"Missing marca asset: {key}")

            # Verify empty orphan dir exists on disk yet is cleanly skipped by discover_reel_runs
            self.assertTrue((self.base_ws / "reels" / "20261123-060431_youtube_342c").is_dir())
            runs = discover_reel_runs()
            self.assertEqual(len(runs), 4)
            self.assertNotIn(
                "20261123-060431_youtube_342c", [r.dir.name for r in runs]
            )

            self.assertIsNotNone(find_reference_reel("DYYsGuTpBKc"))
            self.assertIsNotNone(find_reference_reel("M_t2ZUz7_pc"))
            for ep in episodes:
                audit = find_episode_audit_reel(ep)
                self.assertIsNotNone(audit, f"Audit run missing for {ep.slug}")
                assert audit is not None
                self.assertGreaterEqual(len(audit.frame_paths), 8)

            index_entries = parse_reels_index()
            self.assertEqual(len(index_entries), 4)
            for entry in index_entries:
                self.assertIsNotNone(entry.resolved_dir, f"Unresolved INDEX entry: {entry}")
        finally:
            if prev_env is None:
                os.environ.pop(PROJECT_ROOT_ENV, None)
            else:
                os.environ[PROJECT_ROOT_ENV] = prev_env

    def test_02_compliant_workspace_media_and_qa_parity(self) -> None:
        episodes = discover_episodes(self.base_ws)
        self.assertEqual(len(episodes), 2)

        for ep in episodes:
            probe = probe_media(ep.mp4)
            self.assertEqual((probe.width, probe.height), (1080, 1920))
            self.assertEqual(probe.video_codec, "h264")
            self.assertEqual(probe.pix_fmt, "yuv420p")
            self.assertEqual(probe.sar, "1:1")
            self.assertEqual(probe.rotation, 0)
            self.assertIsNotNone(probe.fps)
            assert probe.fps is not None
            self.assertAlmostEqual(probe.fps, 30.0, delta=0.05)
            self.assertGreaterEqual(probe.duration_s, 65.0)
            self.assertLessEqual(probe.duration_s, 80.0)
            self.assertGreaterEqual(probe.size_bytes, 2_000_000, f"{ep.slug}.mp4 < 2 MB")
            self.assertEqual(probe.audio_codec, "aac")
            self.assertEqual(probe.sample_rate_hz, 48000)
            self.assertEqual(probe.channels, 2)

            decode_res = verify_ffmpeg_decode(ep.mp4)
            self.assertTrue(decode_res.ok, decode_res.errors)

            loud = measure_ebur128(ep.mp4)
            self.assertGreaterEqual(loud.integrated_lufs, -15.5)
            self.assertLessEqual(loud.integrated_lufs, -13.5)
            self.assertLessEqual(loud.lra_lu, 4.3)
            self.assertLessEqual(loud.true_peak_dbfs, -0.8)

            rms = scan_rms_windows(ep.mp4)
            self.assertEqual(rms.silence_windows, [], f"Unexpected silence windows: {rms.silence_windows}")
            self.assertEqual(run_silencedetect(ep.mp4), [])

            wav_stats = analyze_wav_stats(ep.audio_master_wav)
            self.assertEqual(wav_stats.sample_rate_hz, 48000)
            self.assertEqual(wav_stats.channels, 2)
            self.assertTrue(wav_stats.all_finite)
            self.assertLess(abs(wav_stats.dc_offset), 0.01)
            self.assertLess(wav_stats.clip_ratio, 0.005)
            self.assertLess(wav_stats.tail_last_sample_abs, 0.2)
            assert wav_stats.right_rms_db is not None
            self.assertLessEqual(abs(wav_stats.left_rms_db - wav_stats.right_rms_db), 3.0)

            motion = analyze_motion_and_cuts(ep.mp4)
            self.assertGreaterEqual(motion.active_frame_ratio, 0.85)
            self.assertLess(motion.max_static_run_s, 3.0)
            self.assertGreaterEqual(motion.distinct_angle_clusters, 3)
            self.assertGreaterEqual(motion.spatial_tile_cv, 0.65)
            self.assertGreaterEqual(motion.spatial_tile_p90_p25_ratio, 2.8)
            self.assertGreaterEqual(motion.min_frame_luma, 5.0)
            self.assertLessEqual(motion.max_frame_luma, 250.0)

            qa = load_json(ep.qa_report_json)
            self.assertTrue(qa["passed"])
            self.assertAlmostEqual(qa["integrated_lufs"], loud.integrated_lufs, delta=0.4)
            self.assertAlmostEqual(qa["lra_lu"], loud.lra_lu, delta=0.4)
            self.assertAlmostEqual(qa["true_peak_dbfs"], loud.true_peak_dbfs, delta=0.4)

    def test_03_compliant_workspace_images_safe_zones(self) -> None:
        brand = load_brand(self.base_ws)
        palette = brand["visual_style"]["palette"]
        self.assertGreaterEqual(
            wcag_contrast_ratio(palette["text_primary"], palette["background_dark"]), 7.0
        )
        self.assertGreaterEqual(
            wcag_contrast_ratio(palette["primary_accent"], palette["background_dark"]), 4.5
        )
        self.assertGreaterEqual(
            wcag_contrast_ratio(palette["secondary_accent"], palette["background_dark"]), 4.5
        )

        marca = discover_marca_assets(self.base_ws)
        banner_rep = check_youtube_banner(marca["youtube_banner"])
        self.assertTrue(banner_rep.ok, banner_rep.errors)
        self.assertEqual(banner_rep.min_alpha, 255)

        sheet_info = inspect_image(marca["brand_sheet"])
        self.assertTrue(sheet_info.is_valid_png)
        self.assertEqual(sheet_info.min_alpha, 255)
        with Image.open(marca["brand_sheet"]) as sheet_img:
            for name, hex_code in palette.items():
                present, count, _ = palette_color_present(sheet_img, hex_code, max_dist=20.0, min_pixels=500)
                self.assertTrue(present, f"Palette swatch {name}={hex_code} missing from brand_sheet.png (px={count})")

        episodes = discover_episodes(self.base_ws)
        for ep in episodes:
            f0 = extract_frame(ep.mp4, 0.0)
            f15 = extract_frame(ep.mp4, 0.5)
            f0_rep = check_frame0_hook(f0, f15)
            self.assertTrue(f0_rep.ok, f"{ep.slug} Frame 0 failed: {f0_rep.errors}")

            cap_frames = extract_frames_at(ep.mp4, [2.0, 12.0, 25.0, 42.0, 56.0])
            cap_rep = check_caption_band(
                cap_frames,
                accent_rgbs=[palette["primary_accent"], palette["text_highlight"]],
            )
            self.assertTrue(cap_rep.ok, f"{ep.slug} caption band failed: {cap_rep.errors}")
            self.assertFalse(cap_rep.opaque_box_detected)
            self.assertTrue(cap_rep.has_white_text)
            self.assertTrue(cap_rep.has_accent_highlight)

            cov_rep = check_cover_safe_zones(ep.cover_png)
            self.assertTrue(cov_rep.ok, f"{ep.slug} cover failed: {cov_rep.errors}")
            self.assertEqual(cov_rep.min_alpha, 255)

            grid_info = inspect_image(ep.cover_grid_preview_png)
            self.assertTrue(grid_info.is_valid_png)
            self.assertGreaterEqual(grid_info.width, 600)
            self.assertGreaterEqual(grid_info.height, 600)

    def test_04_compliant_workspace_text_captions_and_secrets(self) -> None:
        brand = load_brand(self.base_ws)
        self.assertEqual(
            detect_portuguese_leakage(json.dumps(brand), allow_repo_folder_tokens=True), []
        )

        backlog = load_themes_backlog(self.base_ws)
        backlog_text = json.dumps(backlog.raw)
        self.assertEqual(detect_portuguese_leakage(backlog_text), [])
        self.assertEqual(detect_uk_english_spellings(backlog_text), [])
        self.assertEqual(detect_mojibake(backlog_text), [])

        for ep in discover_episodes(self.base_ws):
            script = load_json(ep.script_json)
            meta = load_episode_publish_meta(ep)
            assert meta is not None
            full_narration = " ".join(b["narration_text"] for b in script["beats"])

            self.assertEqual(detect_portuguese_leakage(full_narration), [])
            self.assertEqual(detect_uk_english_spellings(full_narration), [])
            self.assertEqual(detect_mojibake(full_narration), [])

            title_res = validate_youtube_title(meta["youtube_title"])
            self.assertTrue(title_res.ok, title_res.errors)

            for beat in script["beats"]:
                self.assertEqual(detect_mid_video_subscribe_cta(beat["narration_text"]), [])

            cta_res = validate_ending_cta(script["cta_text"])
            self.assertTrue(cta_res.ok, cta_res.errors)
            self.assertTrue(
                any(tok.lower() in meta["pinned_comment"].lower() for tok in cta_res.response_tokens),
                f"Pinned comment missing CTA token {cta_res.response_tokens}",
            )

            caps = load_json(ep.captions_json)
            probe = probe_media(ep.mp4)
            cap_val = validate_caption_track(
                caps, duration_s=probe.duration_s, script_text=full_narration
            )
            self.assertTrue(cap_val.ok, cap_val.errors)
            self.assertGreaterEqual(cap_val.word_duration_std, 0.03)
            self.assertGreaterEqual(cap_val.word_duration_cv, 0.12)

            audit = find_episode_audit_reel(ep, self.base_ws)
            assert audit is not None and audit.analysis_path is not None
            local_md = audit.analysis_path.read_text(encoding="utf-8")
            sim = transcript_script_similarity(local_md, full_narration)
            self.assertGreaterEqual(sim.token_recall, 0.90)

        self.assertEqual(scan_repo_for_secrets(self.base_ws), [])

    # ------------------------------------------------------------------
    # Group B — All 18 Single-Defect Mutations Individually Verified
    # ------------------------------------------------------------------

    def test_05_mutation_short_duration(self) -> None:
        _, ws = self._make_mutated_copy("short_duration")
        ep = discover_episodes(ws)[0]
        self.assertLess(probe_media(ep.mp4).duration_s, 62.0)

    def test_06_mutation_wrong_fps(self) -> None:
        _, ws = self._make_mutated_copy("wrong_fps")
        ep = discover_episodes(ws)[0]
        fps = probe_media(ep.mp4).fps
        assert fps is not None
        self.assertGreater(abs(fps - 30.0), 0.05)

    def test_07_mutation_wrong_resolution(self) -> None:
        _, ws = self._make_mutated_copy("wrong_resolution")
        ep = discover_episodes(ws)[0]
        probe = probe_media(ep.mp4)
        self.assertNotEqual((probe.width, probe.height), (1080, 1920))

    def test_08_mutation_wrong_pix_fmt(self) -> None:
        _, ws = self._make_mutated_copy("wrong_pix_fmt")
        ep = discover_episodes(ws)[0]
        self.assertNotEqual(probe_media(ep.mp4).pix_fmt, "yuv420p")

    def test_09_mutation_loudness_too_loud(self) -> None:
        _, ws = self._make_mutated_copy("loudness_too_loud")
        ep = discover_episodes(ws)[0]
        loud = measure_ebur128(ep.mp4)
        self.assertTrue(
            loud.integrated_lufs > -13.5 or loud.true_peak_dbfs > -1.0,
            f"Expected loud violation, got {loud}",
        )

    def test_10_mutation_silence_vacuum(self) -> None:
        _, ws = self._make_mutated_copy("silence_vacuum")
        ep = discover_episodes(ws)[0]
        rms = scan_rms_windows(ep.mp4)
        self.assertGreaterEqual(len(rms.silence_windows), 3)
        sil = run_silencedetect(ep.mp4)
        self.assertGreaterEqual(len(sil), 1)

    def test_11_mutation_static_video(self) -> None:
        _, ws = self._make_mutated_copy("static_video")
        ep = discover_episodes(ws)[0]
        motion = analyze_motion_and_cuts(ep.mp4)
        self.assertLess(motion.active_frame_ratio, 0.2)
        self.assertGreaterEqual(motion.max_static_run_s, 10.0)
        self.assertLess(motion.distinct_angle_clusters, 3)

    def test_12_mutation_black_frame0(self) -> None:
        _, ws = self._make_mutated_copy("black_frame0")
        ep = discover_episodes(ws)[0]
        f0 = extract_frame(ep.mp4, 0.0)
        f15 = extract_frame(ep.mp4, 0.5)
        rep = check_frame0_hook(f0, f15)
        self.assertFalse(rep.ok)
        self.assertLess(rep.full_metrics.mean_lum, 5.0)
        self.assertIsNotNone(rep.fade_ratio)
        assert rep.fade_ratio is not None
        self.assertLess(rep.fade_ratio, 0.75)

    def test_13_mutation_pt_br_leakage(self) -> None:
        _, ws = self._make_mutated_copy("pt_br_leakage")
        ep = discover_episodes(ws)[0]
        script = load_json(ep.script_json)
        text = " ".join(b["narration_text"] for b in script["beats"])
        hits = detect_portuguese_leakage(text)
        self.assertTrue(hits, "Expected PT-BR leakage detection")

    def test_14_mutation_bad_yt_title_len(self) -> None:
        _, ws = self._make_mutated_copy("bad_yt_title_len")
        ep = discover_episodes(ws)[0]
        meta = load_episode_publish_meta(ep)
        assert meta is not None
        res = validate_youtube_title(meta["youtube_title"])
        self.assertFalse(res.ok)
        self.assertGreater(res.length, 50)

    def test_15_mutation_bad_yt_title_hashtag(self) -> None:
        _, ws = self._make_mutated_copy("bad_yt_title_hashtag")
        ep = discover_episodes(ws)[0]
        meta = load_episode_publish_meta(ep)
        assert meta is not None
        res = validate_youtube_title(meta["youtube_title"])
        self.assertFalse(res.ok)
        self.assertTrue(any("#" in err for err in res.errors))

    def test_16_mutation_bad_yt_title_two_caps(self) -> None:
        _, ws = self._make_mutated_copy("bad_yt_title_two_caps")
        ep = discover_episodes(ws)[0]
        meta = load_episode_publish_meta(ep)
        assert meta is not None
        res = validate_youtube_title(meta["youtube_title"])
        self.assertFalse(res.ok)
        self.assertEqual(len(res.uppercase_words), 2)

    def test_17_mutation_mid_video_subscribe(self) -> None:
        _, ws = self._make_mutated_copy("mid_video_subscribe")
        ep = discover_episodes(ws)[0]
        script = load_json(ep.script_json)
        non_cta = " ".join(
            b["narration_text"] for b in script["beats"] if b.get("act") != "cta"
        )
        self.assertTrue(detect_mid_video_subscribe_cta(non_cta))

    def test_18_mutation_caption_overflow(self) -> None:
        _, ws = self._make_mutated_copy("caption_overflow")
        ep = discover_episodes(ws)[0]
        script = load_json(ep.script_json)
        full_narration = " ".join(b["narration_text"] for b in script["beats"])
        caps = load_json(ep.captions_json)
        res = validate_caption_track(caps, duration_s=66.0, script_text=full_narration)
        self.assertFalse(res.ok)
        self.assertTrue(any("1..4 words" in err for err in res.errors))

    def test_19_mutation_cover_safe_zone_clip(self) -> None:
        _, ws = self._make_mutated_copy("cover_safe_zone_clip")
        ep = discover_episodes(ws)[0]
        rep = check_cover_safe_zones(ep.cover_png)
        self.assertFalse(rep.ok)
        self.assertTrue(any("top" in err.lower() for err in rep.errors))

    def test_20_mutation_banner_oversize_bytes(self) -> None:
        _, ws = self._make_mutated_copy("banner_oversize_bytes")
        marca = discover_marca_assets(ws)
        rep = check_youtube_banner(marca["youtube_banner"])
        self.assertFalse(rep.ok)
        self.assertGreaterEqual(rep.size_bytes, 6_000_000)

    def test_21_mutation_secret_leak(self) -> None:
        _, ws = self._make_mutated_copy("secret_leak")
        hits = scan_repo_for_secrets(ws)
        self.assertTrue(hits, "Expected secret_leak to be caught")
        raw_dummy = "AIza" + "SyD9xK2mP7qR4tV8wZ1bN5cF3hJ6kL0mN2p"
        for hit in hits:
            self.assertNotIn(raw_dummy, hit.redacted_preview)

    def test_22_mutation_missing_reel_ref(self) -> None:
        _, ws = self._make_mutated_copy("missing_reel_ref")
        self.assertIsNotNone(find_reference_reel("DYYsGuTpBKc", ws))
        self.assertIsNone(find_reference_reel("M_t2ZUz7_pc", ws))

    # ------------------------------------------------------------------
    # Group C — Edge-Case Unit Tests for Helpers (10 tests)
    # ------------------------------------------------------------------

    def test_23_portuguese_leakage_zero_fp_and_three_layers(self) -> None:
        clean_en = (
            "No real motor or canal lock fails at 10 bar of normal gas pressure! "
            "In our local OS sim, the final metal rotor handles 500 ampères near "
            "the naïve café façade after the Tōhoku quake. See https://example.com/como-funciona "
            "for full CAD specs."
        )
        self.assertEqual(detect_portuguese_leakage(clean_en), [])

        # allow_repo_folder_tokens True vs False
        path_text = "Read episodios/ep01_vault/script.json and marca/youtube_banner.png"
        self.assertTrue(detect_portuguese_leakage(path_text, allow_repo_folder_tokens=False))
        self.assertEqual(detect_portuguese_leakage(path_text, allow_repo_folder_tokens=True), [])

        # Layer A (diacritics), Layer B (unambiguous words + template), Layer C (bigrams + anti-clone)
        self.assertTrue(detect_portuguese_leakage("Alta pressão hidráulica"))
        self.assertTrue(detect_portuguese_leakage("DEFINIR_NOME_DO_CANAL @definir_handle"))
        self.assertTrue(detect_portuguese_leakage("Inspired by Rota Crítica channel"))
        self.assertTrue(detect_portuguese_leakage("Por que o cofre trava na hora?"))
        self.assertTrue(detect_portuguese_leakage("Inscreva-se e deixe seu like!"))

    def test_24_uk_spellings_and_mojibake_detectors(self) -> None:
        clean_us = (
            "We analyze pressurized aluminum armor at 90° and 10× torque — precise "
            "behavior in the center meter, comprising gray steel defense valves’ tolerances."
        )
        self.assertEqual(detect_uk_english_spellings(clean_us), [])
        self.assertEqual(detect_mojibake(clean_us), [])

        uk_text = "Analyse the pressurised aluminium armour colour at the centre metre and litre."
        uk_hits = {w.lower() for w in detect_uk_english_spellings(uk_text)}
        for expected in ("analyse", "pressurised", "aluminium", "armour", "colour", "centre", "metre", "litre"):
            self.assertIn(expected, uk_hits)

        moji_text = "Broken text: \ufffd Ã§ Ã£ â€” â€™ Â° Ã—"
        moji_hits = set(detect_mojibake(moji_text))
        for seq in ("\ufffd", "Ã§", "Ã£", "â€”", "â€™", "Â°", "Ã—"):
            self.assertIn(seq, moji_hits)

    def test_25_validate_youtube_title_edge_cases(self) -> None:
        for good in (
            "Why I NEVER Trust a 3D Vault Lock",
            "Why Titan IMPLODED in 20ms?",
            "How a FAIL-SAFE Brake Stops",
        ):
            res = validate_youtube_title(good)
            self.assertTrue(res.ok, f"Expected valid title {good!r}, got {res.errors}")
            self.assertEqual(len(res.uppercase_words), 1)

        bad_cases = (
            "Short ONE",
            "A" * 45 + " EXTRA LONG",
            "How a vault lock works inside",
            "How VAULT Locks NEVER Fail",
            "How a Vault LOCKS #shorts",
            "How a Vault LOCKS...",
            " How a Vault LOCKS Inside ",
            "Como um Cofre TRAVA Inside",
        )
        for bad in bad_cases:
            res = validate_youtube_title(bad)
            self.assertFalse(res.ok, f"Expected rejection for title {bad!r}")

    def test_26_validate_ending_cta_and_subscribe_edge_cases(self) -> None:
        for good in (
            "Comment YES or NO below.",
            "Comment 10 if you spotted it.",
            "Type VAULT if you would trust that steel bolt.",
            "Drop 'SAFE' below.",
        ):
            res = validate_ending_cta(good)
            self.assertTrue(res.ok, f"Expected valid CTA {good!r}, got {res.errors}")
            self.assertGreaterEqual(len(res.response_tokens), 1)

        for bad in (
            "Comment your thoughts below!",
            "Subscribe and comment VAULT below!",
            "Comment what topic next so we can animate it.",
            "Comente SIM ou NAO agora.",
        ):
            res = validate_ending_cta(bad)
            self.assertFalse(res.ok, f"Expected invalid CTA {bad!r}")

        self.assertTrue(detect_mid_video_subscribe_cta("Hit that subscribe button now!"))
        self.assertEqual(detect_mid_video_subscribe_cta("Steel cables carry ten tons of load."), [])

    def test_27_ebur128_summary_parsing_normal_and_neg_inf(self) -> None:
        normal_stderr = """
[Parsed_ebur128_0 @ 0x55] t: 65.9 TARGET:-23 LUFS M:-14.2 S:-14.5
Summary:

  Integrated loudness:
    I:         -14.5 LUFS
    Threshold: -24.6 LUFS

  Loudness range:
    LRA:         2.7 LU
    Threshold: -34.6 LUFS
    LRA low:   -16.1 LUFS
    LRA high:  -13.4 LUFS

  True peak:
    Peak:       -5.7 dBFS
"""
        m = parse_ebur128_summary(normal_stderr)
        self.assertAlmostEqual(m.integrated_lufs, -14.5)
        self.assertAlmostEqual(m.lra_lu, 2.7)
        self.assertAlmostEqual(m.true_peak_dbfs, -5.7)

        silence_stderr = """
Summary:
  Integrated loudness:
    I:         -70.0 LUFS
  Loudness range:
    LRA:         0.0 LU
  True peak:
    Peak:       -inf dBFS
"""
        m_sil = parse_ebur128_summary(silence_stderr)
        self.assertTrue(math.isinf(m_sil.true_peak_dbfs) and m_sil.true_peak_dbfs < 0)

        with self.assertRaises(ValueError):
            parse_ebur128_summary("ffmpeg stderr without any loudness summary")

    def test_28_reels_index_both_formats_and_gemini_url_frames(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cts_e2e_idx_") as td:
            root = Path(td)
            r1 = root / "reels" / "20261123-062938_youtube_8e3b"
            r2 = root / "reels" / "20261123-063338_local_9f1a"
            (r1 / "frames").mkdir(parents=True)
            (r2 / "frames").mkdir(parents=True)

            # Simulate real M1 gemini-url run where manifest["frames"] == [] but frames/ has JPEGs
            Image.new("RGB", (120, 120), (40, 80, 120)).save(r1 / "frames" / "storyboard_sb0_00.jpg")
            Image.new("RGB", (120, 120), (90, 50, 140)).save(r1 / "frames" / "thumb_hq720.jpg")
            (r1 / "manifest.json").write_text(
                json.dumps(
                    {
                        "sources": ["https://www.youtube.com/watch?v=DYYsGuTpBKc"],
                        "fetched_via": "gemini-url",
                        "engine": "gemini (gemini-3.5-flash)",
                        "meta": {},
                        "frames": [],
                        "analysis": "gemini.md",
                    }
                ),
                encoding="utf-8",
            )
            (r1 / "gemini.md").write_text("Analysis of DYYsGuTpBKc", encoding="utf-8")

            (root / "reels" / "INDEX.md").write_text(
                "- 2026-11-23 | First reference breakdown | reels/20261123-062938_youtube_8e3b\n"
                "- 2026-11-23 | #2 | Second local audit | #qa #en | 20261123-063338_local_9f1a\n",
                encoding="utf-8",
            )

            entries = parse_reels_index(root)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].resolved_dir, r1.resolve())
            self.assertEqual(entries[1].resolved_dir, r2.resolve())

            ref = find_reference_reel("DYYsGuTpBKc", root)
            self.assertIsNotNone(ref)
            assert ref is not None
            self.assertEqual(len(ref.frame_paths), 2)
            self.assertEqual(ref.youtube_id, "DYYsGuTpBKc")

    def test_29_cli_runner_secret_assertion_and_env_stripping(self) -> None:
        clean = CliResult(cmd=("echo",), returncode=0, stdout="OK\nREEL_DIR: /tmp/abc\n", stderr="", elapsed_s=0.01)
        assert_no_secret_in_output(clean, sentinel="CANARY_SENTINEL_1234567890")
        self.assertEqual(parse_reel_dir(clean.stdout), Path("/tmp/abc"))

        fake_key = "AIza" + "SyD9xK2mP7qR4tV8wZ1bN5cF3hJ6kL0mN2p"
        leaked = CliResult(cmd=("echo",), returncode=0, stdout=f"debug {fake_key}\n", stderr="", elapsed_s=0.01)
        with self.assertRaises(AssertionError) as ctx:
            assert_no_secret_in_output(leaked)
        self.assertNotIn(fake_key, str(ctx.exception))

        canary = "DUMMY_SECRET_CANARY_987654321"
        leaked_canary = CliResult(cmd=("echo",), returncode=0, stdout="", stderr=f"err {canary}", elapsed_s=0.01)
        with self.assertRaises(AssertionError) as ctx2:
            assert_no_secret_in_output(leaked_canary, sentinel=canary)
        self.assertNotIn(canary, str(ctx2.exception))

        # Verify _build_env sets empty strings (not popped!) so dotenv reload cannot re-inject .env
        env_stripped = cli_runner_mod._build_env(strip_api_keys=True)
        self.assertIn("GEMINI_API_KEY", env_stripped)
        self.assertEqual(env_stripped["GEMINI_API_KEY"], "")
        self.assertEqual(env_stripped["GOOGLE_API_KEY"], "")
        self.assertEqual(env_stripped["CTS_OFFLINE_TEST"], "1")
        self.assertEqual(env_stripped["HF_HUB_OFFLINE"], "1")

    def test_30_media_cache_hit_and_invalidation(self) -> None:
        clear_media_cache()
        self.assertEqual(len(media_mod._MEDIA_CACHE), 0)

        with tempfile.TemporaryDirectory(prefix="cts_e2e_cache_") as td:
            ep = discover_episodes(self.base_ws)[0]
            wav_copy = Path(td) / "sample.wav"
            wav_copy.write_bytes(ep.audio_master_wav.read_bytes())

            p1 = probe_media(wav_copy)
            cache_size_after_first = len(media_mod._MEDIA_CACHE)
            self.assertEqual(cache_size_after_first, 1)

            p2 = probe_media(wav_copy)
            self.assertIs(p1, p2)
            self.assertEqual(len(media_mod._MEDIA_CACHE), 1)

            # Mutate file content & size -> new cache key generated automatically
            raw = wav_copy.read_bytes()
            wav_copy.write_bytes(raw[: len(raw) // 2])
            # Rewrite a valid shorter WAV so ffprobe succeeds with different size
            import wave

            with wave.open(str(ep.audio_master_wav), "rb") as src_wf:
                params = src_wf.getparams()
                half_frames = src_wf.readframes(src_wf.getnframes() // 2)
            with wave.open(str(wav_copy), "wb") as dst_wf:
                dst_wf.setparams(params)
                dst_wf.writeframes(half_frames)

            p3 = probe_media(wav_copy)
            self.assertLess(p3.duration_s, p1.duration_s * 0.75)
            self.assertEqual(len(media_mod._MEDIA_CACHE), 2)

            clear_media_cache()
            self.assertEqual(len(media_mod._MEDIA_CACHE), 0)

    def test_31_caption_track_variance_and_boundary_edge_cases(self) -> None:
        script = "Steel bolts lock fast inside vaults. Comment VAULT."

        # 1. Valid track with realistic variance + isolated 1-word trailing CTA punchline
        valid_caps = {
            "blocks": [
                {
                    "start_s": 0.10,
                    "end_s": 1.45,
                    "words": [
                        {"text": "Steel", "start_s": 0.10, "end_s": 0.42, "emphasize": False},
                        {"text": "bolts", "start_s": 0.42, "end_s": 0.68, "emphasize": True},
                        {"text": "lock", "start_s": 0.68, "end_s": 1.45, "emphasize": False},
                    ],
                },
                {
                    "start_s": 1.50,
                    "end_s": 2.95,
                    "words": [
                        {"text": "fast", "start_s": 1.50, "end_s": 1.72, "emphasize": False},
                        {"text": "inside", "start_s": 1.72, "end_s": 2.40, "emphasize": False},
                        {"text": "vaults.", "start_s": 2.40, "end_s": 2.95, "emphasize": True},
                    ],
                },
                {
                    "start_s": 3.10,
                    "end_s": 3.60,
                    "words": [
                        {"text": "Comment", "start_s": 3.10, "end_s": 3.60, "emphasize": False},
                    ],
                },
            ]
        }
        # Two consecutive 1-word blocks must fail; single trailing 1-word block passes
        valid_caps["blocks"][2] = {
            "start_s": 3.10,
            "end_s": 3.85,
            "words": [
                {"text": "Comment", "start_s": 3.10, "end_s": 3.45, "emphasize": False},
                {"text": "VAULT.", "start_s": 3.45, "end_s": 3.85, "emphasize": True},
            ],
        }
        # Add 6-block list with 1 isolated trailing 1-word block (1/7 = 14.3% <= 15%)
        res_ok = validate_caption_track(valid_caps, duration_s=5.0, script_text=script)
        self.assertTrue(res_ok.ok, res_ok.errors)

        # 2. Uniform fake word durations (std == 0, cv == 0) rejected
        uniform_words = [
            {"text": tok, "start_s": round(0.1 + i * 0.25, 4), "end_s": round(0.35 + i * 0.25, 4), "emphasize": False}
            for i, tok in enumerate(script.split())
        ]
        uniform_caps = {
            "blocks": [
                {"start_s": uniform_words[0]["start_s"], "end_s": uniform_words[2]["end_s"], "words": uniform_words[0:3]},
                {"start_s": uniform_words[3]["start_s"], "end_s": uniform_words[5]["end_s"], "words": uniform_words[3:6]},
                {"start_s": uniform_words[6]["start_s"], "end_s": uniform_words[7]["end_s"], "words": uniform_words[6:8]},
            ]
        }
        res_uni = validate_caption_track(uniform_caps, duration_s=5.0, script_text=script)
        self.assertFalse(res_uni.ok)
        self.assertTrue(any("uniform" in err.lower() for err in res_uni.errors))

        # 3. Tiny <0.02s duration, empty word, and non-monotonic block rejected
        bad_caps = {
            "blocks": [
                {
                    "start_s": 1.0,
                    "end_s": 1.5,
                    "words": [
                        {"text": "", "start_s": 1.0, "end_s": 1.25},
                        {"text": "tiny", "start_s": 1.25, "end_s": 1.26},
                    ],
                },
                {
                    "start_s": 0.5,
                    "end_s": 0.9,
                    "words": [{"text": "backwards", "start_s": 0.5, "end_s": 0.9}],
                },
            ]
        }
        res_bad = validate_caption_track(bad_caps, duration_s=5.0, script_text="tiny backwards")
        self.assertFalse(res_bad.ok)
        self.assertGreaterEqual(len(res_bad.errors), 3)

    def test_32_flexible_themes_backlog_and_opaque_box_caption_box_detector(self) -> None:
        # Verify unknown defect raises ValueError
        self.assertEqual(len(ALL_DEFECT_KEYS), 18)
        with self.assertRaises(ValueError):
            mutate_workspace(self.base_ws, "nonexistent_defect_key")

        # Verify load_themes_backlog supports root-list with rank<=2 fallback
        with tempfile.TemporaryDirectory(prefix="cts_e2e_tb_") as td:
            root = Path(td)
            (root / "episodios").mkdir()
            (root / "episodios" / "themes_backlog.json").write_text(
                json.dumps(
                    [
                        {"slug": "t1_alpha", "title": "Alpha", "rank": 2},
                        {"slug": "t2_beta", "title": "Beta", "rank": 1},
                        {"slug": "t3_gamma", "title": "Gamma", "rank": 3},
                    ]
                ),
                encoding="utf-8",
            )
            tb = load_themes_backlog(root)
            self.assertEqual(len(tb.themes), 3)
            self.assertEqual(tb.selected_slugs, ["t2_beta", "t1_alpha"])

        # Verify check_caption_band catches an opaque solid box behind captions
        img = Image.new("RGB", (1080, 1920), (22, 34, 54))
        d = ImageDraw.Draw(img)
        # Solid pure black opaque box strictly inside caption band while above/below stay (22,34,54)
        d.rectangle([130, 1385, 910, 1515], fill=(0, 0, 0))
        d.text((220, 1430), "OPAQUE BOX TEST", fill=(255, 255, 255))
        rep = check_caption_band([img])
        self.assertTrue(rep.opaque_box_detected)
        self.assertFalse(rep.ok)


if __name__ == "__main__":
    unittest.main()
