"""Comprehensive unit and live-artifact tests for CTS Shorts Factory M1 contracts."""

from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from cts_factory.config import (
    VALID_ACTS,
    VALID_CAMERA_PRESETS,
    AudioBeatTiming,
    AudioTimeline,
    Beat,
    BrandConfig,
    Callout,
    CaptionBlock,
    CaptionTrack,
    CaptionWord,
    EpisodeScript,
    SfxCue,
    validate_brand,
    validate_captions,
    validate_script,
    validate_timeline,
    validate_youtube_title,
)
from cts_factory.episodes import (
    EpisodeScene,
    get_scene,
    list_scenes,
    register_scene,
    unregister_scene,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestYouTubeTitleValidator(unittest.TestCase):
    """Boundary and edge-case tests for validate_youtube_title()."""

    def test_valid_titles_pass(self) -> None:
        valid_titles = [
            "How Elevators STOP When Every Cable Snaps",
            "Why Deep-Sea Hulls IMPLODE in Milliseconds",
            "A Vault Door Built to NEVER Open",
            "Why I NEVER Trust a Single Cable",
            "How 20ms Buckling CRUSHED a Steel Hull",
            "Why Brakes STOP! Even When Cables Fail",
            "Why Bolts CAN'T Hold Double Load",
            "A" + " " + "x" * 42 + " " + "BREAK",  # exact 50 chars
        ]
        for title in valid_titles:
            with self.subTest(title=title):
                self.assertEqual(validate_youtube_title(title), [])

    def test_length_50_passes_and_51_fails(self) -> None:
        exact_50 = "How One Gear Lets Every Car TURN Around a Bend Now"
        self.assertEqual(len(exact_50), 50)
        self.assertEqual(validate_youtube_title(exact_50), [])

        len_51 = exact_50 + "!"
        self.assertEqual(len(len_51), 51)
        errs = validate_youtube_title(len_51)
        self.assertTrue(any("exceeds max 50" in e for e in errs))

    def test_hashtags_rejected(self) -> None:
        errs = validate_youtube_title("How Elevators STOP #shorts")
        self.assertTrue(any("#" in e for e in errs))

    def test_zero_or_multiple_uppercase_words_rejected(self) -> None:
        errs_zero = validate_youtube_title("How Elevators Stop When Every Cable Snaps")
        self.assertTrue(any("exactly 1 ALL-CAPS word" in e for e in errs_zero))

        errs_two = validate_youtube_title("How Elevators STOP When CABLES Snap")
        self.assertTrue(any("exactly 1 ALL-CAPS word" in e for e in errs_two))

        errs_acronym = validate_youtube_title("How 6,000 PSI CRUSHED a Sub")
        self.assertTrue(any("exactly 1 ALL-CAPS word" in e for e in errs_acronym))

    def test_empty_whitespace_multiline_and_pt_br_rejected(self) -> None:
        for bad in (
            "",
            "   ",
            " Leading STOP Space",
            "Line1 STOP\nLine2",
            "How\tElevators STOP",
            "How\vElevators STOP",
            "How\fElevators STOP",
            "Como um Cofre TRAVA por Dentro",
            "Why TODO Brakes STOP",
            "Why Elevators NÃO Stop",
        ):
            with self.subTest(title=bad):
                self.assertTrue(len(validate_youtube_title(bad)) > 0)

    def test_slash_and_dash_joined_dual_caps_rejected_while_hyphen_compound_passes(self) -> None:
        self.assertEqual(validate_youtube_title("Why FAIL-SAFE Brakes Never Slip"), [])
        for bad in (
            "Why STOP/GO Fails Fast",
            "Why STOP\u2014NOW Fails Fast",
            "Why STOP\u2013NOW Fails Fast",
        ):
            with self.subTest(title=bad):
                errs = validate_youtube_title(bad)
                self.assertTrue(any("exactly 1 ALL-CAPS word" in e for e in errs))


class TestBrandConfigContract(unittest.TestCase):
    """Tests for BrandConfig JSON round-trips, template aliases, and strict validation."""

    def _load_live_brand(self) -> BrandConfig:
        return BrandConfig.load(REPO_ROOT / "brand.json")

    def test_brand_json_round_trip_equality(self) -> None:
        brand = self._load_live_brand()
        self.assertEqual(validate_brand(brand), [])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "brand_copy.json"
            brand.save(out)
            reloaded = BrandConfig.load(out)
            self.assertEqual(reloaded, brand)
            self.assertIsInstance(reloaded.video_spec.target_duration_sec, tuple)
            self.assertIsInstance(reloaded.narration.rate_range, tuple)
            self.assertIsInstance(reloaded.retention_rules.caption_chunk_words, tuple)

    def test_brand_template_alias_loading(self) -> None:
        tpl_path = REPO_ROOT / "brand_template.json"
        tpl = BrandConfig.load(tpl_path)
        self.assertEqual(tpl.video_spec.audio_lufs, -14.5)
        self.assertEqual(tpl.video_spec.audio_lra_max, 4.0)
        self.assertEqual(tpl.video_spec.audio_sample_rate, 48000)
        self.assertEqual(tpl.narration.models, ["gemini-3.8-flash-tts"])
        # Template still has placeholders & missing v1beta/niche updates, so validator flags it
        errs = validate_brand(tpl)
        self.assertTrue(any("placeholder" in e for e in errs))
        self.assertTrue(any("niche" in e for e in errs))

    def test_brand_validator_catches_critical_violations(self) -> None:
        base = self._load_live_brand()

        # v1 API breaks TTS speechConfig
        b1 = copy.deepcopy(base)
        b1.narration.api_version = "v1"
        self.assertTrue(any("v1beta" in e for e in validate_brand(b1)))

        # Non-en-US language
        b2 = copy.deepcopy(base)
        b2.language = "pt-BR"
        self.assertTrue(any("en-US" in e for e in validate_brand(b2)))

        # Placeholder channel name
        b3 = copy.deepcopy(base)
        b3.channel_name = "DEFINIR_CANAL"
        self.assertTrue(any("placeholder" in e for e in validate_brand(b3)))

        # Windows font path
        b4 = copy.deepcopy(base)
        b4.visual_style.fallback_font = r"C:\Windows\Fonts\arial.ttf"
        self.assertTrue(any("POSIX" in e for e in validate_brand(b4)))

        # AI disclosure turned on for stylized 2.5D
        b5 = copy.deepcopy(base)
        b5.publishing.youtube_ai_disclosure_stylized_2d = True
        self.assertTrue(any("youtube_ai_disclosure_stylized_2d" in e for e in validate_brand(b5)))

        # Mid-video subscribe CTA allowed
        b6 = copy.deepcopy(base)
        b6.retention_rules.no_mid_video_subscribe_cta = False
        self.assertTrue(any("no_mid_video_subscribe_cta" in e for e in validate_brand(b6)))

        # TikTok floor below 62s
        b7 = copy.deepcopy(base)
        b7.video_spec.tiktok_1min_monetization_min_sec = 59
        self.assertTrue(any("tiktok_1min_monetization_min_sec" in e for e in validate_brand(b7)))

        # Invalid hex color
        b8 = copy.deepcopy(base)
        b8.visual_style.palette["primary_accent"] = "orange"
        self.assertTrue(any("invalid hex" in e for e in validate_brand(b8)))

        # Oversized caption safe zone (> 820px)
        b9 = copy.deepcopy(base)
        b9.visual_style.safe_zones.captions.x_min = 20
        b9.visual_style.safe_zones.captions.x_max = 1040
        b9.visual_style.safe_zones.captions.max_width_px = 1020
        self.assertTrue(any("820" in e for e in validate_brand(b9)))

    def test_font_resolution_helper_finds_bundled_fonts_and_falls_back(self) -> None:
        brand = self._load_live_brand()
        primary = brand.visual_style.resolve_font_path("primary", repo_root=REPO_ROOT)
        secondary = brand.visual_style.resolve_font_path("secondary", repo_root=REPO_ROOT)
        self.assertTrue(primary.is_file(), f"Missing bundled primary font: {primary}")
        self.assertTrue(secondary.is_file(), f"Missing bundled secondary font: {secondary}")

        # Missing bundled fonts fall back cleanly to Linux DejaVuSans-Bold
        with tempfile.TemporaryDirectory() as empty_repo:
            fallback_primary = brand.visual_style.resolve_font_path(
                "primary", repo_root=Path(empty_repo)
            )
            fallback_secondary = brand.visual_style.resolve_font_path(
                "secondary", repo_root=Path(empty_repo)
            )
            expected_fallback = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
            self.assertEqual(fallback_primary, expected_fallback)
            self.assertEqual(fallback_secondary, expected_fallback)
            self.assertTrue(fallback_primary.is_file())

    def test_brand_validator_iteration2_hardening(self) -> None:
        base = self._load_live_brand()

        # Trailing newline bypass attempts on handle, hex color, schedule hour
        b_nl = copy.deepcopy(base)
        b_nl.handle = "@FailSafeLab\n"
        b_nl.visual_style.palette["primary_accent"] = "#FF8C1A\n"
        b_nl.publishing.youtube_schedule_fixed_hour = "12:00\n"
        errs_nl = validate_brand(b_nl)
        self.assertTrue(any("Invalid handle" in e for e in errs_nl))
        self.assertTrue(any("invalid hex" in e for e in errs_nl))
        self.assertTrue(any("youtube_schedule_fixed_hour" in e for e in errs_nl))

        # Whispering in narration.style_direction (including word ending in 'no')
        b_wh = copy.deepcopy(base)
        b_wh.narration.style_direction = "Breathy whispering narrator for suspense."
        self.assertTrue(any("whispering" in e for e in validate_brand(b_wh)))

        b_piano = copy.deepcopy(base)
        b_piano.narration.style_direction = "Soft piano whisper narrator."
        self.assertTrue(any("whispering" in e for e in validate_brand(b_piano)))

        # Empty, whitespace-padded, or duplicate fallback models
        b_empty_m = copy.deepcopy(base)
        b_empty_m.narration.models = ["gemini-3.8-flash-tts", ""]
        self.assertTrue(any("must not be empty" in e for e in validate_brand(b_empty_m)))

        b_ws_m = copy.deepcopy(base)
        b_ws_m.narration.models = ["gemini-3.8-flash-tts", " gemini-3.8-flash-lite-tts "]
        self.assertTrue(any("whitespace" in e for e in validate_brand(b_ws_m)))

        b_dup_m = copy.deepcopy(base)
        b_dup_m.narration.models = ["gemini-3.8-flash-tts", "gemini-3.8-flash-tts"]
        self.assertTrue(any("duplicate" in e for e in validate_brand(b_dup_m)))

        # Safe-zone bounds: max_width_px <= 0, x_max > 930 (T7), banner max bytes <= 0
        b_sz = copy.deepcopy(base)
        b_sz.visual_style.safe_zones.captions.max_width_px = 0
        b_sz.visual_style.safe_zones.captions.x_min = 260
        b_sz.visual_style.safe_zones.captions.x_max = 1080
        b_sz.visual_style.safe_zones.youtube_banner_max_bytes = 0
        b_sz.publishing.stayed_to_watch_target_pct = 150.0
        errs_sz = validate_brand(b_sz)
        self.assertTrue(any("max_width_px" in e for e in errs_sz))
        self.assertTrue(any("930px" in e for e in errs_sz))
        self.assertTrue(any("youtube_banner_max_bytes" in e for e in errs_sz))
        self.assertTrue(any("stayed_to_watch_target_pct" in e for e in errs_sz))

        # Non-finite floats in BrandConfig
        b_nan = copy.deepcopy(base)
        b_nan.video_spec.audio_lufs = float("nan")
        b_nan.video_spec.audio_true_peak_max = float("nan")
        b_nan.video_spec.audio_lra_max = float("inf")
        b_nan.narration.silence_trim_db = float("-inf")
        b_nan.publishing.stayed_to_watch_target_pct = float("nan")
        errs_nan = validate_brand(b_nan)
        self.assertTrue(any("audio_lufs" in e for e in errs_nan))
        self.assertTrue(any("audio_true_peak_max" in e for e in errs_nan))
        self.assertTrue(any("audio_lra_max" in e for e in errs_nan))
        self.assertTrue(any("silence_trim_db" in e for e in errs_nan))
        self.assertTrue(any("stayed_to_watch_target_pct" in e for e in errs_nan))

        # PT / Rota Critica leakage in anti_clone_note, rationale, and retention_rules
        b_pt = copy.deepcopy(base)
        b_pt.anti_clone_note = "Zero overlap with Rota Critica."
        b_pt.visual_style.style_decision_rationale = "Clean peças mecânicas vector."
        b_pt.retention_rules.ending_cta = "Comente SIM ou NÃO."
        errs_pt = validate_brand(b_pt)
        self.assertTrue(any("anti_clone_note" in e for e in errs_pt))
        self.assertTrue(any("style_decision_rationale" in e for e in errs_pt))
        self.assertTrue(any("retention_rules.ending_cta" in e for e in errs_pt))

    def test_null_safe_from_dict_and_non_finite_json_rejected(self) -> None:
        # Explicit JSON null sub-objects never crash with AttributeError
        null_brand = BrandConfig.from_dict(
            {
                "channel_name": "Test Lab",
                "video_spec": None,
                "visual_style": None,
                "narration": None,
                "retention_rules": None,
                "publishing": None,
            }
        )
        self.assertEqual(null_brand.channel_name, "Test Lab")
        self.assertEqual(null_brand.video_spec.fps, 30)

        null_script = EpisodeScript.from_dict(
            {
                "episode_id": "ep01",
                "slug": "ep01_null_test",
                "title": "Why Steel BREAKS Fast",
                "hook_text": "STEEL SNAP TEST",
                "cta_text": "Comment YES",
                "bpm": 120,
                "cover_headline": None,
                "publish_meta": None,
                "beats": None,
            }
        )
        self.assertEqual(null_script.beats, [])
        self.assertEqual(null_script.cover_headline, [])

        null_beat = Beat.from_dict(
            {
                "id": "b01",
                "act": "hook",
                "narration_text": "Snap.",
                "camera_preset": "FRAME0_HERO",
                "scene_key": "snap",
                "sfx_cues": None,
                "callout": None,
            }
        )
        self.assertEqual(null_beat.sfx_cues, [])

        null_tl = AudioTimeline.from_dict({"total_duration_s": 10.0, "beats": None})
        self.assertEqual(null_tl.beats, [])

        null_ct = CaptionTrack.from_dict({"blocks": None})
        self.assertEqual(null_ct.blocks, [])

        null_cb = CaptionBlock.from_dict({"start_s": 0.0, "end_s": 1.0, "words": None})
        self.assertEqual(null_cb.words, [])

        # Wrong non-mapping / non-list types raise clear TypeError
        with self.assertRaises(TypeError):
            BrandConfig.from_dict({"video_spec": "invalid"})
        with self.assertRaises(TypeError):
            EpisodeScript.from_dict(
                {
                    "episode_id": "ep01",
                    "slug": "ep01_bad",
                    "title": "T",
                    "hook_text": "H",
                    "cta_text": "C",
                    "bpm": 120,
                    "beats": "not_a_list",
                }
            )

        # JSON loader rejects NaN/Infinity constants on load
        with tempfile.TemporaryDirectory() as tmp:
            bad_json = Path(tmp) / "nan_timeline.json"
            bad_json.write_text('{"total_duration_s": NaN, "beats": []}', encoding="utf-8")
            with self.assertRaises(ValueError):
                AudioTimeline.load(bad_json)


class TestEpisodeScriptContract(unittest.TestCase):
    """Tests for EpisodeScript round-trips, dict-like submodels, and strict validation."""

    def _load_ep01(self) -> tuple[BrandConfig, EpisodeScript]:
        brand = BrandConfig.load(REPO_ROOT / "brand.json")
        script = EpisodeScript.load(REPO_ROOT / "episodios/ep01_elevator_safety_brake/script.json")
        return brand, script

    def test_script_json_round_trip_and_dict_like_access(self) -> None:
        brand, script = self._load_ep01()
        self.assertEqual(validate_script(script, brand), [])
        self.assertEqual(script.folder_name, "ep01_elevator_safety_brake")
        self.assertEqual(script.publish_meta["youtube_title"], script.title)
        self.assertEqual(script.publish_meta.get("ai_disclosure"), False)
        self.assertEqual(script.beats[1].callout["label"], "FREE FALL")  # type: ignore[index]
        self.assertEqual(script.beats[0].sfx_cues[0]["name"], "cable_snap")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "script_copy.json"
            script.save(out)
            reloaded = EpisodeScript.load(out)
            self.assertEqual(reloaded, script)

    def test_script_validator_rejects_structural_and_content_violations(self) -> None:
        brand, base = self._load_ep01()

        # Double-prefixed slug
        s_slug = copy.deepcopy(base)
        s_slug.slug = "ep01_ep01_elevator_safety_brake"
        self.assertTrue(any("double-prefix" in e for e in validate_script(s_slug, brand)))

        # Missing episode_id prefix on slug
        s_noprefix = copy.deepcopy(base)
        s_noprefix.slug = "elevator_safety_brake"
        self.assertTrue(any("must start with episode_id prefix" in e for e in validate_script(s_noprefix, brand)))

        # Invalid act literal
        s_act = copy.deepcopy(base)
        s_act.beats[2].act = "intro"
        self.assertTrue(any("invalid act" in e for e in validate_script(s_act, brand)))

        # Non-monotonic act order (mechanism after escalation)
        s_order = copy.deepcopy(base)
        s_order.beats[5].act = "escalation"
        s_order.beats[6].act = "mechanism"
        self.assertTrue(any("non-monotonic" in e for e in validate_script(s_order, brand)))

        # Duplicate beat ID
        s_dup = copy.deepcopy(base)
        s_dup.beats[3].id = s_dup.beats[2].id
        self.assertTrue(any("Duplicate beat id" in e for e in validate_script(s_dup, brand)))

        # Beat 0 wrong camera_preset and non-null callout
        s_f0 = copy.deepcopy(base)
        s_f0.beats[0].camera_preset = "ISO_WIDE"
        s_f0.beats[0].callout = Callout("CLUTTER", "BAD")
        errs_f0 = validate_script(s_f0, brand)
        self.assertTrue(any("FRAME0_HERO" in e for e in errs_f0))
        self.assertTrue(any("beats[0].callout" in e for e in errs_f0))

        # Fewer than 4 distinct camera presets
        s_cam = copy.deepcopy(base)
        for idx, beat in enumerate(s_cam.beats):
            beat.camera_preset = "FRAME0_HERO" if idx == 0 else "ISO_WIDE"
        self.assertTrue(any("4..5 distinct camera_preset" in e for e in validate_script(s_cam, brand)))

        # Too few beats (< 10)
        s_short = copy.deepcopy(base)
        s_short.beats = s_short.beats[:8]
        self.assertTrue(any("10..14 beats" in e for e in validate_script(s_short, brand)))

        # Word count too low
        s_words = copy.deepcopy(base)
        for beat in s_words.beats[:-1]:
            beat.narration_text = "Short mechanical fact."
        self.assertTrue(any("word count" in e for e in validate_script(s_words, brand)))

        # Mid-video subscribe prompt
        s_sub = copy.deepcopy(base)
        s_sub.beats[4].narration_text += " Hit subscribe for more."
        self.assertTrue(any("subscribe" in e for e in validate_script(s_sub, brand)))

        # Positive whisper direction rejected vs negation-safe passes
        s_whisper = copy.deepcopy(base)
        s_whisper.beats[3].voice_direction = "Dramatic whispering delivery."
        self.assertTrue(any("whisper" in e for e in validate_script(s_whisper, brand)))

        s_nowhisper = copy.deepcopy(base)
        s_nowhisper.beats[3].voice_direction = "Controlled half-voice, no whispering."
        self.assertEqual(validate_script(s_nowhisper, brand), [])

        # Missing CTA comment prompt
        s_cta = copy.deepcopy(base)
        s_cta.cta_text = "Think about it"
        self.assertTrue(any("cta_text" in e for e in validate_script(s_cta, brand)))

        # ai_disclosure=True & title mismatch
        s_meta = copy.deepcopy(base)
        s_meta.publish_meta.ai_disclosure = True
        s_meta.publish_meta.youtube_title = "Different Title STOP Here"
        errs_meta = validate_script(s_meta, brand)
        self.assertTrue(any("ai_disclosure" in e for e in errs_meta))
        self.assertTrue(any("must exactly match" in e for e in errs_meta))

        # PT-BR leakage
        s_pt = copy.deepcopy(base)
        s_pt.beats[2].narration_text += " Esse elevador trava."
        self.assertTrue(any("Portuguese" in e for e in validate_script(s_pt, brand)))

        # Invalid SFX pan/offset and oversized callout
        s_sfx = copy.deepcopy(base)
        s_sfx.beats[2].sfx_cues.append(SfxCue("bad", offset_s=-0.5, gain_db=12.0, pan=1.8))
        s_sfx.beats[2].callout = Callout("A" * 35, "B" * 30)
        errs_sfx = validate_script(s_sfx, brand)
        self.assertTrue(any("negative or non-finite offset_s" in e for e in errs_sfx))
        self.assertTrue(any("pan" in e for e in errs_sfx))
        self.assertTrue(any("callout.label" in e for e in errs_sfx))

    def test_script_validator_iteration2_hardening(self) -> None:
        brand, base = self._load_ep01()

        # Trailing newline bypass attempts on episode_id, slug, hashtag, schedule_hour
        s_nl = copy.deepcopy(base)
        s_nl.episode_id = "ep01\n"
        s_nl.slug = "ep01_elevator_safety_brake\n"
        s_nl.publish_meta.hashtags[0] = "#engineering\n"
        s_nl.publish_meta.schedule_hour = "12:00\n"
        errs_nl = validate_script(s_nl, brand)
        self.assertTrue(any("episode_id" in e for e in errs_nl))
        self.assertTrue(any("slug" in e for e in errs_nl))
        self.assertTrue(any("Invalid hashtag" in e for e in errs_nl))
        self.assertTrue(any("schedule_hour" in e for e in errs_nl))

        # Honors brand.retention_rules.min_camera_angles == 5
        b_five = copy.deepcopy(brand)
        b_five.retention_rules.min_camera_angles = 5
        s_four = copy.deepcopy(base)
        for beat in s_four.beats:
            if beat.camera_preset == "EXPLODED_BLUEPRINT":
                beat.camera_preset = "ISO_WIDE"
        self.assertTrue(any("5..5 distinct camera_preset" in e for e in validate_script(s_four, b_five)))

        # Rejects whitespace-padded duplicate beat IDs and internal whitespace
        s_ws = copy.deepcopy(base)
        s_ws.beats[2].id = " " + s_ws.beats[1].id + " "
        errs_ws = validate_script(s_ws, brand)
        self.assertTrue(any("whitespace" in e for e in errs_ws))
        self.assertTrue(any("Duplicate beat id" in e for e in errs_ws))

        # Rejects PT in callout and voice_direction
        s_pt = copy.deepcopy(base)
        s_pt.beats[1].callout = Callout("PRESSÃO MÁXIMA", "NÃO QUEBRA")
        s_pt.beats[2].voice_direction = "Voz dramática em português"
        errs_pt = validate_script(s_pt, brand)
        self.assertTrue(any("callout.label" in e for e in errs_pt))
        self.assertTrue(any("callout.value" in e for e in errs_pt))
        self.assertTrue(any("voice_direction" in e for e in errs_pt))

        # Rejects piano whisper word-boundary evasion
        s_piano = copy.deepcopy(base)
        s_piano.beats[2].voice_direction = "Quiet piano whisper tone."
        self.assertTrue(any("whispering" in e for e in validate_script(s_piano, brand)))

        # Rejects spoofed CTA where only action verb is uppercase
        for bad_cta in ("COMMENT below now", "TYPE your answer", "DROP an idea"):
            s_cta = copy.deepcopy(base)
            s_cta.cta_text = bad_cta
            with self.subTest(cta_text=bad_cta):
                self.assertTrue(any("response token" in e for e in validate_script(s_cta, brand)))

        # Rejects NaN / inf floats in pause_after_s and SFX cues
        s_nan = copy.deepcopy(base)
        s_nan.beats[1].pause_after_s = float("nan")
        s_nan.beats[0].sfx_cues[0].offset_s = float("nan")
        s_nan.beats[0].sfx_cues[0].gain_db = float("inf")
        s_nan.beats[0].sfx_cues[0].pan = float("-inf")
        errs_nan = validate_script(s_nan, brand)
        self.assertTrue(any("pause_after_s" in e for e in errs_nan))
        self.assertTrue(any("offset_s" in e for e in errs_nan))
        self.assertTrue(any("gain_db" in e for e in errs_nan))
        self.assertTrue(any("pan" in e for e in errs_nan))


class TestAudioTimelineAndCaptions(unittest.TestCase):
    """Tests for AudioTimeline and CaptionTrack round-trips, lookups, and validators."""

    def test_timeline_round_trip_lookup_and_validation(self) -> None:
        tl = AudioTimeline(
            total_duration_s=10.5,
            sample_rate_hz=48000,
            beats=[
                AudioBeatTiming("b01_hook", 0.0, 4.0, "cache/tts/b01.wav", "Hook line"),
                AudioBeatTiming("b02_next", 4.2, 10.2, "cache/tts/b02.wav", "Second line"),
            ],
            narration_wav_path="narration_clean.wav",
            master_wav_path="audio_master.wav",
            envelope_path="narration_envelope.npy",
        )
        self.assertEqual(validate_timeline(tl), [])

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "narration_timeline.json"
            tl.save(p)
            self.assertEqual(AudioTimeline.load(p), tl)

        beat0, prog0 = tl.beat_at(2.0)
        self.assertEqual(beat0.id, "b01_hook")
        self.assertAlmostEqual(prog0, 0.5)

        # Inter-beat pause holds previous beat at progress 1.0
        beat_gap, prog_gap = tl.beat_at(4.1)
        self.assertEqual(beat_gap.id, "b01_hook")
        self.assertAlmostEqual(prog_gap, 1.0)

        # Past end clamps to last beat at 1.0
        beat_end, prog_end = tl.beat_at(12.0)
        self.assertEqual(beat_end.id, "b02_next")
        self.assertAlmostEqual(prog_end, 1.0)

        # Overlapping beats fail validation
        bad_tl = copy.deepcopy(tl)
        bad_tl.beats[1].start_s = 3.5
        self.assertTrue(any("overlaps" in e for e in validate_timeline(bad_tl)))

    def test_captions_round_trip_lookup_and_validation(self) -> None:
        track = CaptionTrack(
            blocks=[
                CaptionBlock(
                    start_s=0.0,
                    end_s=1.2,
                    words=[
                        CaptionWord("ALL", 0.0, 0.35, emphasize=True),
                        CaptionWord("EIGHT", 0.35, 0.75, emphasize=False),
                        CaptionWord("CABLES", 0.75, 1.2, emphasize=True),
                    ],
                ),
                CaptionBlock(
                    start_s=1.35,
                    end_s=1.9,
                    words=[CaptionWord("SNAP.", 1.35, 1.9, emphasize=True)],
                ),
            ]
        )
        self.assertEqual(validate_captions(track), [])

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "captions.json"
            track.save(p)
            self.assertEqual(CaptionTrack.load(p), track)

        self.assertEqual(track.block_at(0.5).text, "ALL EIGHT CABLES")  # type: ignore[union-attr]
        self.assertIsNone(track.block_at(1.25))
        self.assertEqual(track.block_at(1.9).text, "SNAP.")  # type: ignore[union-attr]

        # Over 4 words fails
        too_long = CaptionTrack(
            blocks=[
                CaptionBlock(
                    0.0,
                    2.5,
                    [CaptionWord(f"W{i}", i * 0.4, (i + 1) * 0.4) for i in range(5)],
                )
            ]
        )
        self.assertTrue(any("max 4" in e for e in validate_captions(too_long)))

        # Inverted word timing fails
        bad_word = copy.deepcopy(track)
        bad_word.blocks[0].words[0].start_s = 0.5
        bad_word.blocks[0].words[0].end_s = 0.2
        self.assertTrue(any("must be < end_s" in e for e in validate_captions(bad_word)))

    def test_timeline_and_captions_iteration2_hardening(self) -> None:
        # NaN / inf rejection in AudioTimeline
        tl_nan = AudioTimeline(
            total_duration_s=float("nan"),
            beats=[AudioBeatTiming("b1", float("nan"), float("inf"), "a.wav")],
        )
        errs_tl = validate_timeline(tl_nan)
        self.assertTrue(any("total_duration_s" in e for e in errs_tl))
        self.assertTrue(any("start_s must be finite" in e for e in errs_tl))
        self.assertTrue(any("end_s must be finite" in e for e in errs_tl))

        # Multi-word CaptionWord.text and >4 rendered words rejected
        ct_multi = CaptionTrack(
            blocks=[
                CaptionBlock(
                    0.0,
                    2.0,
                    [
                        CaptionWord("ONE TWO THREE", 0.0, 1.0),
                        CaptionWord("FOUR FIVE SIX", 1.0, 2.0),
                    ],
                )
            ]
        )
        errs_multi = validate_captions(ct_multi)
        self.assertTrue(any("single whitespace-free token" in e for e in errs_multi))
        self.assertTrue(any("rendered block text" in e for e in errs_multi))

        # NaN / inf rejection in CaptionTrack
        ct_nan = CaptionTrack(
            blocks=[
                CaptionBlock(
                    float("nan"),
                    2.0,
                    [
                        CaptionWord("ONE", float("nan"), 1.0),
                        CaptionWord("TWO", 1.0, float("inf")),
                    ],
                )
            ]
        )
        errs_ct_nan = validate_captions(ct_nan)
        self.assertTrue(any("blocks[0]: start_s must be finite" in e for e in errs_ct_nan))
        self.assertTrue(any("words[0]: start_s must be finite" in e for e in errs_ct_nan))
        self.assertTrue(any("words[1]: end_s must be finite" in e for e in errs_ct_nan))

        # Consistent 1 ms tolerance on words[0].start_s
        ct_tol_ok = CaptionTrack(
            blocks=[
                CaptionBlock(
                    1.0,
                    2.0,
                    [
                        CaptionWord("STEEL", 0.9995, 1.5),
                        CaptionWord("LOCKS", 1.5, 2.0),
                    ],
                )
            ]
        )
        self.assertEqual(validate_captions(ct_tol_ok), [])

        ct_tol_bad = CaptionTrack(
            blocks=[
                CaptionBlock(
                    1.0,
                    2.0,
                    [
                        CaptionWord("STEEL", 0.9985, 1.5),
                        CaptionWord("LOCKS", 1.5, 2.0),
                    ],
                )
            ]
        )
        self.assertTrue(any("starts before block" in e for e in validate_captions(ct_tol_bad)))


class TestEpisodeSceneRegistry(unittest.TestCase):
    """Tests for EpisodeScene ABC enforcement and scene registry lifecycle."""

    def setUp(self) -> None:
        self._registered: list[str] = []

    def tearDown(self) -> None:
        for slug in self._registered:
            unregister_scene(slug, missing_ok=True)

    def test_abc_and_partial_subclass_rejected(self) -> None:
        with self.assertRaises(TypeError):
            EpisodeScene()  # type: ignore[abstract]

        class PartialScene(EpisodeScene):
            def prepare(self, brand: Any, script: Any, timeline: Any = None) -> None:
                return None

        with self.assertRaises(TypeError):
            register_scene("test_partial_scene", PartialScene)

        with self.assertRaises(TypeError):
            register_scene("test_not_scene", dict)  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            register_scene("   ", PartialScene)

    def test_direct_and_decorator_registration_lifecycle(self) -> None:
        class DummySceneA(EpisodeScene):
            slug = "test_dummy_a"
            episode_id = "ep98"

            def prepare(self, brand: BrandConfig, script: EpisodeScript, timeline: AudioTimeline | None = None) -> None:
                self.brand = brand

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
                draw.point((0, 0), fill=(255, 255, 255))

            def render_cover_hero(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
                draw.point((1, 1), fill=(255, 200, 61))

        register_scene("test_dummy_a", DummySceneA)
        self._registered.append("test_dummy_a")

        @register_scene("test_dummy_b")
        class DummySceneB(DummySceneA):
            slug = "test_dummy_b"
            episode_id = "ep99"

        self._registered.append("test_dummy_b")

        self.assertIn("test_dummy_a", list_scenes())
        self.assertIn("test_dummy_b", list_scenes())
        inst = get_scene("test_dummy_a")
        self.assertIsInstance(inst, DummySceneA)

        # Smoke test actual Pillow draw call
        img = Image.new("RGB", (16, 16), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        inst.render_frame(0, 0.0, "b01_hook", 0.0, 0.5, img, draw)
        inst.render_cover_hero(img, draw)
        self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))

        # Duplicate rejected without overwrite=True, allowed with overwrite=True
        with self.assertRaises(ValueError):
            register_scene("test_dummy_a", DummySceneB)
        register_scene("test_dummy_a", DummySceneB, overwrite=True)
        self.assertIsInstance(get_scene("test_dummy_a"), DummySceneB)

        with self.assertRaises(KeyError):
            get_scene("test_unknown_scene_xyz")


class TestLiveRepoArtifacts(unittest.TestCase):
    """Live validation against the actual M1 deliverables in the repository."""

    def test_live_brand_json_is_valid(self) -> None:
        brand = BrandConfig.load(REPO_ROOT / "brand.json")
        self.assertEqual(validate_brand(brand), [])
        self.assertEqual(brand.language, "en-US")
        self.assertEqual(brand.narration.api_version, "v1beta")
        self.assertFalse(brand.publishing.youtube_ai_disclosure_stylized_2d)

    def test_live_themes_backlog_and_top2_scripts(self) -> None:
        brand = BrandConfig.load(REPO_ROOT / "brand.json")
        backlog_path = REPO_ROOT / "episodios/themes_backlog.json"
        backlog = json.loads(backlog_path.read_text(encoding="utf-8"))

        self.assertEqual(backlog["language"], "en-US")
        self.assertEqual(backlog["channel_name"], brand.channel_name)
        themes = backlog["themes"]
        self.assertEqual(len(themes), 6)

        slugs = [t["slug"] for t in themes]
        self.assertEqual(len(set(slugs)), 6)

        selected = [t for t in themes if t["selected_for_production"]]
        self.assertEqual(len(selected), 2)
        self.assertEqual(backlog["selected_slugs"], [t["slug"] for t in selected])

        sub_niches = {t["sub_niche"] for t in themes}
        self.assertEqual(sub_niches, {"how_it_works", "real_disaster_physics"})

        for theme in themes:
            with self.subTest(slug=theme["slug"]):
                self.assertTrue(theme["standalone_verified"])
                self.assertEqual(validate_youtube_title(theme["youtube_title"]), [])
                self.assertIn(len(theme["camera_shots"]), (4, 5))
                self.assertNotIn("#", theme["youtube_description"])
                self.assertGreaterEqual(len(theme["hashtags"]), 4)
                self.assertTrue(theme["pinned_comment"].strip())

        # Validate both production scripts live
        for item in selected:
            script_path = REPO_ROOT / "episodios" / item["slug"] / "script.json"
            self.assertTrue(script_path.is_file(), f"Missing script.json: {script_path}")
            script = EpisodeScript.load(script_path)
            self.assertEqual(validate_script(script, brand), [])
            self.assertEqual(script.slug, item["slug"])
            self.assertEqual(script.episode_id, item["episode_id"])
            self.assertEqual(script.title, item["youtube_title"])
            self.assertEqual(len(script.beats), 12)
            self.assertEqual(set(script.distinct_camera_presets), set(VALID_CAMERA_PRESETS))
            self.assertEqual({b.act for b in script.beats}, set(VALID_ACTS))

    def test_live_deliverables_en_us_purity_cta_sync_and_reels_hygiene(self) -> None:
        pt_diacritics = re.compile(r"[ãõçáéíóúâêôàÃÕÇÁÉÍÓÚÂÊÔÀ]")
        rota_re = re.compile(r"rota\s+cr[ií]tica", re.IGNORECASE)

        files_to_check = [
            REPO_ROOT / "brand.json",
            REPO_ROOT / "episodios/STYLE_DECISION.md",
            REPO_ROOT / "episodios/THEMES_CATALOG.md",
            REPO_ROOT / "episodios/themes_backlog.json",
            REPO_ROOT / "episodios/ep01_elevator_safety_brake/script.json",
            REPO_ROOT / "episodios/ep02_submersible_implosion_physics/script.json",
            REPO_ROOT / "reels/20261123-063338_youtube_8c00/breakdown.md",
        ]
        for path in files_to_check:
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=str(path.relative_to(REPO_ROOT))):
                self.assertEqual(pt_diacritics.findall(text), [])
                self.assertEqual(rota_re.findall(text), [])

        # Verify ep03/ep04/ep05 CTA sentences in THEMES_CATALOG.md match themes_backlog.json verbatim
        catalog_text = (REPO_ROOT / "episodios/THEMES_CATALOG.md").read_text(encoding="utf-8")
        backlog = json.loads((REPO_ROOT / "episodios/themes_backlog.json").read_text(encoding="utf-8"))
        for theme in backlog["themes"]:
            if theme["slug"] in {
                "ep03_bank_vault_lock",
                "ep04_tacoma_bridge_flutter",
                "ep05_car_differential_gear",
            }:
                # Last two sentences of ig_tiktok_caption form the CTA sentence
                parts = theme["ig_tiktok_caption"].rsplit("? ", 1)
                self.assertEqual(len(parts), 2)
                question_sentence = parts[0].rsplit(". ", 1)[-1] + "? " + parts[1]
                self.assertIn(question_sentence, catalog_text)

        # Verify no empty orphan directories remain in reels/
        reels_dir = REPO_ROOT / "reels"
        empty_dirs = [d.name for d in reels_dir.iterdir() if d.is_dir() and not any(d.iterdir())]
        self.assertEqual(empty_dirs, [])


if __name__ == "__main__":
    unittest.main()
