"""Fast (<12s) compliant synthetic workspace builder and 18 single-defect mutators.

Used for self-testing E2E helpers and verifying mutation resistance (true
positives on compliant workspaces and true negatives on targeted defects).
Strictly stdlib + ``PIL`` + ``numpy`` + system ``ffmpeg``. Never imports from
``src/`` or ``cts_factory``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .discovery import get_real_repo_root, load_json
from .media import (
    clear_media_cache,
    measure_ebur128,
    probe_media,
    scan_rms_windows,
)

ALL_DEFECT_KEYS: tuple[str, ...] = (
    "short_duration",
    "wrong_fps",
    "wrong_resolution",
    "wrong_pix_fmt",
    "loudness_too_loud",
    "silence_vacuum",
    "static_video",
    "black_frame0",
    "pt_br_leakage",
    "bad_yt_title_len",
    "bad_yt_title_hashtag",
    "bad_yt_title_two_caps",
    "mid_video_subscribe",
    "caption_overflow",
    "cover_safe_zone_clip",
    "banner_oversize_bytes",
    "secret_leak",
    "missing_reel_ref",
)
SUPPORTED_DEFECTS: frozenset[str] = frozenset(ALL_DEFECT_KEYS)

_BG_DARK = (13, 19, 32)       # #0D1320
_PANEL_DARK = (30, 41, 59)    # #1E293B
_AMBER = (245, 158, 11)       # #F59E0B
_CYAN = (56, 189, 248)        # #38BDF8
_WHITE = (248, 250, 252)      # #F8FAFC
_YELLOW = (250, 204, 21)      # #FACC15


def _load_font(size: int, root: Path | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: list[Path] = []
    if root is not None:
        candidates.extend(
            [
                root / "assets" / "fonts" / "Montserrat-ExtraBold.ttf",
                root / "assets" / "fonts" / "Montserrat-Black.ttf",
            ]
        )
    repo_root = get_real_repo_root()
    candidates.extend(
        [
            repo_root / "assets" / "fonts" / "Montserrat-ExtraBold.ttf",
            repo_root / "assets" / "fonts" / "Montserrat-Black.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
        ]
    )
    for p in candidates:
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({' '.join(args[:8])}...): {proc.stderr.strip()[:400]}")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_wav_int16(path: Path, samples: np.ndarray, sample_rate: int = 48000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    channels = 1 if pcm.ndim == 1 else int(pcm.shape[1])
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def _build_brand_json() -> dict[str, Any]:
    return {
        "channel_name": "IronCut Engineering",
        "handle": "@ironcuteng",
        "language": "en-US",
        "goal": "earning_daily_autonomous_shorts",
        "niche": "engineering_how_it_works_and_real_disasters",
        "tagline": "Inside the Machines That Cannot Fail",
        "anti_clone_note": (
            "Original industrial dark-navy blueprint aesthetic with amber/cyan mechanical "
            "cutaways and Fenrir narration voice, fully distinct from starter templates."
        ),
        "video_spec": {
            "resolution": "1080x1920",
            "fps": 30,
            "target_duration_sec": [65, 80],
            "tiktok_1min_monetization_min_sec": 62,
            "loudness_target_lufs": -14.5,
            "audio_lufs": -14.5,
            "max_lra_lu": 4.0,
            "audio_lra_max": 4.0,
            "audio_true_peak_max": -1.0,
            "audio_codec": "aac",
            "audio_sample_rate_hz": 48000,
            "audio_sample_rate": 48000,
            "video_codec": "libx264",
            "pixel_format": "yuv420p",
            "video_crf": 19,
        },
        "visual_style": {
            "type": "2.5d_isometric_vector_cutaway",
            "style_decision_rationale": (
                "After auditing YouTube references DYYsGuTpBKc and M_t2ZUz7_pc via /reel-watch, "
                "we locked a clean 2.5D isometric vector cutaway style: high-contrast blueprint "
                "housing silhouettes, animated force arrows, exploded steel mechanisms, and crisp "
                "top-third hooks maximize engineering retention and fast 2-core CPU rendering."
            ),
            "palette": {
                "background_dark": "#0D1320",
                "surface_panel": "#1E293B",
                "primary_accent": "#F59E0B",
                "secondary_accent": "#38BDF8",
                "text_primary": "#F8FAFC",
                "text_highlight": "#FACC15",
            },
            "fonts_dir": "assets/fonts",
            "primary_font": "assets/fonts/Montserrat-ExtraBold.ttf",
            "secondary_font": "assets/fonts/Montserrat-Black.ttf",
            "fallback_font": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "safe_zones": {
                "hook_box": [90, 260, 990, 460],
                "scene_viewport": [0, 460, 1080, 1360],
                "caption_box": [110, 1380, 930, 1520],
                "cover_reels_box": [90, 330, 990, 1580],
                "cover_3x4_box": [90, 260, 990, 1660],
            },
        },
        "narration": {
            "provider": "google-genai",
            "api_version": "v1beta",
            "model": "gemini-3.8-flash-tts",
            "models": [
                "gemini-3.8-flash-tts",
                "gemini-3.8-flash-lite-tts",
                "gemini-2.5-flash-preview-tts",
            ],
            "voice": "Fenrir",
            "style_direction": "Authoritative, crisp, fast-paced American English engineering narrator",
            "pov": "3rd_person_fast_storyteller",
            "rate_range": [1.0, 1.08],
            "silence_trim_db": -52,
            "avoid_whisper_hiss": True,
            "continuous_ambient_bed": True,
        },
        "retention_rules": {
            "frame_0_hook": (
                "Instant full-frame extreme macro cutaway at peak mechanical tension plus "
                "high-contrast top hook text in y=260..460 and immediate spoken hook at t=0.0s."
            ),
            "no_mid_video_subscribe_cta": True,
            "ending_cta": "Story-tied 1-word or 1-number comment prompt at final beat",
            "caption_chunk_words": [2, 4],
            "caption_style": "clean_outlined_no_box",
        },
        "publishing": {
            "youtube_title_max_chars": 50,
            "youtube_title_hashtags": False,
            "youtube_title_one_uppercase_word": True,
            "youtube_schedule_fixed_hour": "12:00",
            "youtube_link_related_video": True,
            "youtube_ai_disclosure_stylized_2d": False,
            "never_delete_stalled_shorts": True,
            "review_metrics_after_hours": 48,
            "stayed_to_watch_target_pct": 75.0,
            "avd_target_pct": 100.0,
        },
    }


def _build_themes_backlog() -> dict[str, Any]:
    themes = [
        {
            "id": "T01",
            "slug": "ep01_vault_bolt_lock",
            "title": "How a Bank Vault LOCKS From Inside",
            "category": "how_it_works",
            "estimated_duration_sec": 66,
            "standalone": True,
            "selected_for_production": True,
            "rank": 1,
            "hook": "Sixteen steel bolts deadbolt a thirty-ton door in two seconds flat.",
            "core_mechanism": "Triple-wheel dial fence, glass relocker plate, and synchronized gear ring.",
            "ending_cta": "Comment VAULT if you would trust that bolt.",
        },
        {
            "id": "T02",
            "slug": "ep02_elevator_brake_jaw",
            "title": "How an Elevator BRAKE Stops Freefall",
            "category": "how_it_works",
            "estimated_duration_sec": 69,
            "standalone": True,
            "selected_for_production": True,
            "rank": 2,
            "hook": "Every cable snaps at once, yet the cabin stops in half a floor.",
            "core_mechanism": "Centrifugal overspeed governor tripping self-wedging steel rail jaws.",
            "ending_cta": "Comment BRAKE if you knew that wedge.",
        },
        {
            "id": "T03",
            "slug": "ep03_submersible_hull_implosion",
            "title": "Why a Deep Hull IMPLODES in 20ms",
            "category": "real_disasters",
            "estimated_duration_sec": 68,
            "standalone": True,
            "selected_for_production": False,
            "rank": 3,
            "hook": "At four hundred atmospheres, one microscopic delamination collapses the cylinder.",
            "core_mechanism": "Hydrostatic buckling of carbon fiber laminate versus titanium end caps.",
            "ending_cta": "Comment HULL if physics surprises you.",
        },
        {
            "id": "T04",
            "slug": "ep04_bridge_resonance_snap",
            "title": "Why Wind TORE This Suspension Bridge",
            "category": "real_disasters",
            "estimated_duration_sec": 70,
            "standalone": True,
            "selected_for_production": False,
            "rank": 4,
            "hook": "A steady forty-mile breeze twisted solid steel girders like wet cardboard.",
            "core_mechanism": "Aeroelastic flutter amplifying torsional deck oscillation until hanger shear.",
            "ending_cta": "Comment WIND if you spotted the twist.",
        },
        {
            "id": "T05",
            "slug": "ep05_jet_turbine_blade_lock",
            "title": "How a Jet Blade SURVIVES Melting Heat",
            "category": "how_it_works",
            "estimated_duration_sec": 68,
            "standalone": True,
            "selected_for_production": False,
            "rank": 5,
            "hook": "Jet engine gas burns hotter than the metal melting point around it.",
            "core_mechanism": "Single-crystal nickel alloy with laser-drilled film-cooling air channels.",
            "ending_cta": "Comment JET if that cooling trick blew your mind.",
        },
        {
            "id": "T06",
            "slug": "ep06_dam_spillway_cavitation",
            "title": "How Water Bubbles SHRED Solid Concrete",
            "category": "real_disasters",
            "estimated_duration_sec": 69,
            "standalone": True,
            "selected_for_production": False,
            "rank": 6,
            "hook": "Microscopic vapor bubbles carved a fifty-foot crater through reinforced concrete.",
            "core_mechanism": "Spillway cavitation bubble collapse hammering concrete with supersonic microjets.",
            "ending_cta": "Comment DAM if you underestimated bubbles.",
        },
    ]
    return {
        "language": "en-US",
        "niche": "engineering_how_it_works_and_real_disasters",
        "selected_top_2": ["ep01_vault_bolt_lock", "ep02_elevator_brake_jaw"],
        "selection_rationale": (
            "Selected ep01_vault_bolt_lock and ep02_elevator_brake_jaw for peak mechanical "
            "cutaway clarity, high-RPM evergreen search demand, and cleanly articulated "
            "gears, bolts, governors, and clamping rail jaws."
        ),
        "compilation_duration_sec": sum(t["estimated_duration_sec"] for t in themes),
        "themes": themes,
    }


def _build_themes_catalog_md(backlog: dict[str, Any]) -> str:
    lines = [
        "# IronCut Engineering — 6 Evergreen en-US Themes Catalog",
        "",
        f"**Selected Top 2 for Production:** `{backlog['selected_top_2'][0]}`, `{backlog['selected_top_2'][1]}`",
        f"**Selection Rationale:** {backlog['selection_rationale']}",
        f"**6-Theme Compilation Runtime:** {backlog['compilation_duration_sec']} seconds",
        "",
    ]
    for t in backlog["themes"]:
        status = "SELECTED" if t["selected_for_production"] else "BACKLOG"
        lines.extend(
            [
                f"## {t['id']} — {t['title']} (`{t['slug']}`) [{status}]",
                f"- **Category:** {t['category']}",
                f"- **Estimated Duration:** {t['estimated_duration_sec']}s (standalone)",
                f"- **Hook:** {t['hook']}",
                f"- **Core Engineering Mechanism:** {t['core_mechanism']}",
                f"- **Ending CTA:** {t['ending_cta']}",
                "",
            ]
        )
    return "\n".join(lines)


def _episode_blueprints() -> list[dict[str, Any]]:
    ep01_beats = [
        ("b01", "hook", "cam_macro_wheel", "vault_dial", 4.65, 0.40,
         "Sixteen solid steel bolts lock a thirty ton bank vault door in two seconds flat.",
         {"label": "DOOR MASS", "value": "30 TONS"}),
        ("b02", "mechanism", "cam_macro_wheel", "vault_dial", 6.20, 0.40,
         "Turn the outside dial and three stacked brass wheels spin inside a hardened steel case.",
         None),
        ("b03", "mechanism", "cam_cutaway_gears", "vault_gears", 6.20, 0.40,
         "Each wheel carries one precision notch that only aligns when the exact combination hits.",
         {"label": "TOLERANCE", "value": "0.1 MM"}),
        ("b04", "mechanism", "cam_cutaway_gears", "vault_gears", 6.20, 0.40,
         "Once all three notches line up, a spring loaded fence drops straight into the gate.",
         None),
        ("b05", "escalation", "cam_bolt_ring", "vault_bolts", 6.20, 0.40,
         "That tiny drop unlocks the giant gear ring driving sixteen thick chromium steel bolts outward.",
         {"label": "BOLT COUNT", "value": "16 STEEL"}),
        ("b06", "escalation", "cam_bolt_ring", "vault_bolts", 6.20, 0.40,
         "Every bolt slides deep into the reinforced masonry frame so the door cannot budge.",
         None),
        ("b07", "escalation", "cam_relocker_glass", "vault_relocker", 6.20, 0.40,
         "Drill near the lock body and a sheet of tempered glass shatters instantly inside the door.",
         {"label": "RELOCKER", "value": "GLASS TRIG"}),
        ("b08", "climax", "cam_relocker_glass", "vault_relocker", 6.20, 0.40,
         "Spring loaded deadbolts fire from three directions and permanently jam the entire gear train.",
         None),
        ("b09", "climax", "cam_bolt_ring", "vault_bolts", 6.20, 0.40,
         "Even with the real combination, nobody opens that vault without cutting through solid armor steel.",
         None),
        ("b10", "cta", "cam_macro_wheel", "vault_dial", 7.80, 0.35,
         "One fragile glass plate protects millions of dollars. Comment VAULT if you would trust that bolt.",
         None),
    ]

    ep02_beats = [
        ("b01", "hook", "cam_shaft_wide", "elevator_shaft", 4.65, 0.40,
         "Cut every steel cable on a modern elevator and the cabin still stops in half a floor.",
         {"label": "STOP DIST", "value": "1.5 METERS"}),
        ("b02", "mechanism", "cam_shaft_wide", "elevator_shaft", 5.90, 0.40,
         "That rescue starts at the top of the shaft inside a spinning mechanical overspeed governor.",
         None),
        ("b03", "mechanism", "cam_governor_close", "elevator_gov", 5.90, 0.40,
         "A separate steel loop tracks cabin speed every millisecond completely independent from the hoisting motor.",
         {"label": "TRIGGER", "value": "115% SPEED"}),
        ("b04", "mechanism", "cam_governor_close", "elevator_gov", 5.90, 0.40,
         "Inside the governor wheel sit two weighted flyweights held inward by calibrated tension springs.",
         None),
        ("b05", "escalation", "cam_governor_close", "elevator_gov", 5.90, 0.40,
         "If the cabin drops too fast, centrifugal force flings those steel arms outward into ratchet teeth.",
         None),
        ("b06", "escalation", "cam_wedge_jaws", "elevator_jaws", 5.90, 0.40,
         "The governor rope locks solid and yanks a linkage lever mounted underneath the falling cabin floor.",
         {"label": "CLAMP LOAD", "value": "18 TONS"}),
        ("b07", "escalation", "cam_wedge_jaws", "elevator_jaws", 5.90, 0.40,
         "That upward pull drives two hardened steel wedges straight into tapered iron guide rails.",
         None),
        ("b08", "climax", "cam_wedge_jaws", "elevator_jaws", 5.90, 0.40,
         "The heavier the falling car pushes downward, the tighter those self locking wedges bite the rail.",
         None),
        ("b09", "climax", "cam_rail_friction", "elevator_rail", 5.90, 0.40,
         "Kinetic energy converts cleanly into controlled sliding friction without snapping passenger backs.",
         None),
        ("b10", "climax", "cam_rail_friction", "elevator_rail", 5.90, 0.40,
         "Zero electricity, zero software, and zero batteries are required for the emergency brake to fire.",
         None),
        ("b11", "cta", "cam_shaft_wide", "elevator_shaft", 6.20, 0.35,
         "Pure gravity triggers its own rescue every time. Comment BRAKE if you knew that wedge.",
         None),
    ]

    return [
        {
            "episode_id": "ep01",
            "slug": "ep01_vault_bolt_lock",
            "title": "How a Bank Vault LOCKS From Inside",
            "hook_text": "16 BOLTS IN 2 SECONDS",
            "cta_text": "Comment VAULT if you would trust that bolt.",
            "cta_token": "VAULT",
            "bpm": 116,
            "cover_headline": ["INSIDE A", "30-TON VAULT"],
            "related_slug": "ep02_elevator_brake_jaw",
            "clip_order": [0] * 5 + [1] * 5 + [2] * 5 + [3] * 5,  # 20 * 3.3s = 66.0s
            "beats": ep01_beats,
            "hashtags": ["#engineering", "#howitworks", "#mechanical", "#bankvault", "#physics"],
        },
        {
            "episode_id": "ep02",
            "slug": "ep02_elevator_brake_jaw",
            "title": "How an Elevator BRAKE Stops Freefall",
            "hook_text": "CABLES SNAP. IT STOPS.",
            "cta_text": "Comment BRAKE if you knew that wedge.",
            "cta_token": "BRAKE",
            "bpm": 122,
            "cover_headline": ["ELEVATOR", "FREEFALL BRAKE"],
            "related_slug": "ep01_vault_bolt_lock",
            "clip_order": [3] * 5 + [1] * 5 + [0] * 5 + [2] * 6,  # 21 * 3.3s = 69.3s
            "beats": ep02_beats,
            "hashtags": ["#engineering", "#elevator", "#mechanical", "#howitworks", "#safety"],
        },
    ]


def _render_base_clip(
    clip_path: Path,
    scene_idx: int,
    root: Path,
    *,
    fps: int = 30,
    frames_count: int = 99,
) -> None:
    """Render a 3.3s 270x480 articulated vector clip and upscale cleanly to 1080x1920."""
    w, h = 270, 480
    font_hook = _load_font(17, root)
    font_cap = _load_font(15, root)

    scene_configs = [
        {"accent": _AMBER, "panel": (22, 34, 54), "hook": "16 BOLTS LOCK FAST", "cap_w": "STEEL", "cap_h": "BOLTS"},
        {"accent": _CYAN, "panel": (20, 40, 58), "hook": "GEARS ALIGN INSIDE", "cap_w": "THREE", "cap_h": "WHEELS"},
        {"accent": (239, 68, 68), "panel": (36, 26, 44), "hook": "GLASS TRIGGERS JAM", "cap_w": "LOCKED", "cap_h": "SOLID"},
        {"accent": (52, 211, 153), "panel": (18, 38, 46), "hook": "WEDGE GRIPS RAIL", "cap_w": "BRAKE", "cap_h": "CLAMPS"},
    ]
    cfg = scene_configs[scene_idx % len(scene_configs)]

    # Build deterministic static backdrop once per clip (dark blueprint + subtle mechanical detail)
    base_img = Image.new("RGB", (w, h), _BG_DARK)
    base_draw = ImageDraw.Draw(base_img)

    # Subtle blueprint grid strictly inside dark luminance range (median stays ~#0D1320)
    for gx in range(0, w, 18):
        base_draw.line([(gx, 0), (gx, h)], fill=(17, 25, 42), width=1)
    for gy in range(0, h, 18):
        base_draw.line([(0, gy), (w, gy)], fill=(17, 25, 42), width=1)

    # Distinct camera scene housing strictly inside viewport y=120..332 (480..1328 at 1080p)
    panel_col = cfg["panel"]
    accent = cfg["accent"]
    if scene_idx == 0:
        base_draw.rounded_rectangle([24, 126, 246, 326], radius=14, fill=panel_col, outline=accent, width=3)
        base_draw.ellipse([54, 152, 216, 304], fill=(15, 23, 38), outline=(148, 163, 184), width=3)
    elif scene_idx == 1:
        base_draw.rectangle([18, 134, 252, 318], fill=panel_col, outline=accent, width=3)
        base_draw.polygon([(24, 316), (135, 138), (246, 316)], fill=(28, 48, 72), outline=(186, 230, 253))
    elif scene_idx == 2:
        base_draw.rounded_rectangle([32, 122, 238, 332], radius=8, fill=panel_col, outline=accent, width=3)
        for stripe in range(132, 326, 16):
            base_draw.line([(36, stripe), (234, stripe)], fill=(55, 38, 62), width=2)
    else:
        base_draw.rectangle([28, 124, 96, 330], fill=panel_col, outline=accent, width=3)
        base_draw.rectangle([174, 124, 242, 330], fill=panel_col, outline=accent, width=3)
        base_draw.rectangle([98, 140, 172, 314], fill=(15, 28, 36), outline=(148, 163, 184), width=2)

    # Deterministic crisp vector blueprint dimension ticks & rivets in center hero
    for tick_x in range(44, 228, 12):
        base_draw.line([(tick_x, 146), (tick_x, 154)], fill=(71, 85, 105), width=1)
        base_draw.line([(tick_x, 298), (tick_x, 306)], fill=(71, 85, 105), width=1)
    for tick_y in range(154, 298, 12):
        base_draw.line([(40, tick_y), (48, tick_y)], fill=(71, 85, 105), width=1)
        base_draw.line([(222, tick_y), (230, tick_y)], fill=(71, 85, 105), width=1)
    for rx, ry in ((34, 136), (236, 136), (34, 316), (236, 316)):
        base_draw.ellipse([rx - 4, ry - 4, rx + 4, ry + 4], fill=(148, 163, 184), outline=(0, 0, 0), width=1)

    # Top hook text strictly inside y=72..106 -> y=288..424 at 1080p (HOOK_SAFE_ZONE: 90,260,990,460)
    hd = ImageDraw.Draw(base_img)
    hd.text(
        (135, 88),
        cfg["hook"],
        font=font_hook,
        fill=_WHITE,
        anchor="mm",
        stroke_width=2,
        stroke_fill=(0, 0, 0),
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-vf",
        "scale=1080:1920:flags=neighbor",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "16",
        "-g",
        str(frames_count),
        "-keyint_min",
        str(frames_count),
        "-sc_threshold",
        "0",
        "-pix_fmt",
        "yuv420p",
        str(clip_path),
    ]
    with subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        assert proc.stdin is not None
        try:
            for fi in range(frames_count):
                frame = base_img.copy()
                d = ImageDraw.Draw(frame)
                phase = (fi / float(frames_count)) * 2.0 * math.pi

                # Localized articulated mechanical motion confined to 4-5 inner tiles
                # so background tiles stay calm -> high 4x4 spatial tile CV & p90/p25 ratio!
                cx, cy = 135, 226
                if scene_idx == 0:
                    # Rotating vault wheel spokes + reciprocating steel bolt
                    for spoke in range(6):
                        ang = phase * 1.5 + spoke * (math.pi / 3.0)
                        x2 = cx + int(46 * math.cos(ang))
                        y2 = cy + int(46 * math.sin(ang))
                        d.line([(cx, cy), (x2, y2)], fill=_AMBER, width=5)
                    d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=_WHITE, outline=(0, 0, 0), width=2)
                    bolt_dx = int(28 * math.sin(phase * 2.0))
                    d.rectangle([156 + bolt_dx, 214, 218 + bolt_dx, 238], fill=_CYAN, outline=_WHITE, width=2)
                elif scene_idx == 1:
                    # Dual counter-rotating spur gears
                    for gi, (gx, gy, sign) in enumerate(((96, 228, 1.0), (174, 228, -1.0))):
                        d.ellipse([gx - 30, gy - 30, gx + 30, gy + 30], fill=(35, 62, 92), outline=_CYAN, width=3)
                        for tooth in range(8):
                            ang = sign * phase * 2.0 + tooth * (math.pi / 4.0)
                            tx = gx + int(34 * math.cos(ang))
                            ty = gy + int(34 * math.sin(ang))
                            d.rectangle([tx - 4, ty - 4, tx + 4, ty + 4], fill=_YELLOW)
                elif scene_idx == 2:
                    # Shattering relocker piston + pressure gauge needle
                    drop = int(42 * (0.5 + 0.5 * math.sin(phase * 2.0)))
                    d.rectangle([108, 152 + drop, 162, 198 + drop], fill=(239, 68, 68), outline=_WHITE, width=2)
                    ang = -math.pi * 0.8 + (phase / (2.0 * math.pi)) * math.pi * 1.2
                    nx = cx + int(38 * math.cos(ang))
                    ny = 278 + int(38 * math.sin(ang))
                    d.line([(cx, 278), (nx, ny)], fill=_YELLOW, width=4)
                else:
                    # Clamping elevator wedges converging onto center steel rail
                    squeeze = int(22 * (0.5 + 0.5 * math.sin(phase * 2.0)))
                    d.polygon(
                        [(68 + squeeze, 196), (112 + squeeze, 224), (68 + squeeze, 252)],
                        fill=(52, 211, 153),
                        outline=_WHITE,
                    )
                    d.polygon(
                        [(202 - squeeze, 196), (158 - squeeze, 224), (202 - squeeze, 252)],
                        fill=(52, 211, 153),
                        outline=_WHITE,
                    )
                    d.rectangle([126, 156, 144, 296], fill=_AMBER, outline=_WHITE, width=1)

                # Clean outlined captions strictly inside x=38..212, y=354..376
                # -> x=152..848, y=1416..1504 at 1080p (CAPTION_SAFE_ZONE: 110,1380,930,1520), NO opaque box!
                d.text(
                    (52, 365),
                    cfg["cap_w"],
                    font=font_cap,
                    fill=_WHITE,
                    anchor="lm",
                    stroke_width=2,
                    stroke_fill=(0, 0, 0),
                )
                d.text(
                    (128, 365),
                    cfg["cap_h"],
                    font=font_cap,
                    fill=_AMBER,
                    anchor="lm",
                    stroke_width=2,
                    stroke_fill=(0, 0, 0),
                )

                proc.stdin.write(frame.tobytes())
        finally:
            proc.stdin.close()
        stderr_bytes = proc.stderr.read() if proc.stderr else b""
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"Base clip render failed: {stderr_bytes.decode('utf-8', 'ignore')[:400]}")


def _synthesize_episode_audio(
    ep_dir: Path,
    beats_spec: list[tuple[Any, ...]],
    total_duration_s: float,
    ep_seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Synthesize beat TTS cache WAVs, narration_clean.wav, audio_master.wav, envelope, timeline."""
    sr = 48000
    total_samples = int(round(total_duration_s * sr))
    narration = np.zeros(total_samples, dtype=np.float32)
    speech_mask = np.zeros(total_samples, dtype=np.float32)

    tts_cache_dir = ep_dir / "cache" / "tts"
    tts_cache_dir.mkdir(parents=True, exist_ok=True)

    cursor_s = 0.05  # immediate voice onset <= 0.15s
    timeline_beats: list[dict[str, Any]] = []
    script_beats: list[dict[str, Any]] = []

    for bi, (bid, act, cam_preset, scene_key, speak_s, pause_s, text, callout) in enumerate(beats_spec):
        start_s = cursor_s
        # Ensure final beat fits cleanly before total_duration_s - 0.05s
        max_end = total_duration_s - 0.05
        end_s = min(start_s + speak_s, max_end)
        actual_dur = max(0.5, end_s - start_s)
        n_beat = int(round(actual_dur * sr))
        t = np.arange(n_beat, dtype=np.float32) / float(sr)

        # Voiced harmonic speech-like waveform with natural syllable modulation
        f0 = 148.0 + (ep_seed * 17 + bi * 9) % 45
        syllable_env = 0.60 + 0.40 * np.sin(2.0 * math.pi * (4.4 + (bi % 3) * 0.6) * t)
        voice = (
            0.55 * np.sin(2.0 * math.pi * f0 * t)
            + 0.28 * np.sin(2.0 * math.pi * (f0 * 2.01) * t)
            + 0.17 * np.sin(2.0 * math.pi * (f0 * 3.03) * t)
        ) * syllable_env

        # Smooth 30ms edge fades so |last_sample| < 0.02
        fade_n = min(int(0.030 * sr), n_beat // 4)
        if fade_n > 0:
            ramp = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
            voice[:fade_n] *= ramp
            voice[-fade_n:] *= ramp[::-1]

        beat_peak = float(np.max(np.abs(voice))) or 1.0
        beat_wav_arr = (voice / beat_peak) * 0.58

        digest = hashlib.sha256(f"{bid}:{text}".encode("utf-8")).hexdigest()
        cache_wav = tts_cache_dir / f"{digest}.wav"
        _write_wav_int16(cache_wav, beat_wav_arr, sample_rate=sr)

        s0 = int(round(start_s * sr))
        s1 = min(total_samples, s0 + n_beat)
        narration[s0:s1] = beat_wav_arr[: s1 - s0]
        speech_mask[s0:s1] = 1.0

        timeline_beats.append(
            {
                "id": bid,
                "start_s": round(start_s, 4),
                "end_s": round(s1 / float(sr), 4),
                "wav_path": f"cache/tts/{digest}.wav",
                "narration_text": text,
            }
        )
        script_beats.append(
            {
                "id": bid,
                "act": act,
                "narration_text": text,
                "voice_direction": "Crisp engineering narrator, energetic cadence",
                "camera_preset": cam_preset,
                "scene_key": scene_key,
                "sfx_cues": [{"name": "mech_click", "offset_s": 0.1, "gain_db": -12.0, "pan": 0.0}],
                "callout": callout,
                "pause_after_s": pause_s,
            }
        )
        cursor_s = end_s + pause_s

    narration_wav_path = ep_dir / "narration_clean.wav"
    _write_wav_int16(narration_wav_path, narration, sample_rate=sr)

    # Continuous stereo ambient bed with sidechain ducking during speech
    t_full = np.arange(total_samples, dtype=np.float32) / float(sr)
    bed_l = (
        0.45 * np.sin(2.0 * math.pi * (110.0 + ep_seed * 8.0) * t_full)
        + 0.30 * np.sin(2.0 * math.pi * (165.0 + ep_seed * 6.0) * t_full + 0.3)
        + 0.25 * np.sin(2.0 * math.pi * 220.0 * t_full + 0.7)
    )
    bed_r = (
        0.45 * np.sin(2.0 * math.pi * (110.4 + ep_seed * 8.0) * t_full + 0.4)
        + 0.30 * np.sin(2.0 * math.pi * (164.6 + ep_seed * 6.0) * t_full + 0.9)
        + 0.25 * np.sin(2.0 * math.pi * 220.5 * t_full + 1.1)
    )
    # Duck bed during speech; keep energized (~-28 dBFS) during inter-beat pauses
    duck_gain = np.where(speech_mask > 0.5, 0.030, 0.070).astype(np.float32)
    mix_l = narration * 0.42 + bed_l * duck_gain
    mix_r = narration * 0.42 + bed_r * duck_gain
    stereo = np.stack([mix_l, mix_r], axis=1)

    # Normalize RMS cleanly to hit ~-14.5 LUFS (with LRA ~2.5-3.5 LU, TP <= -4 dBFS)
    cur_rms = float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2))) or 1e-6
    target_rms = 0.155
    stereo = stereo * (target_rms / cur_rms)

    # 20ms smooth edge fades at master boundaries
    edge_n = int(0.020 * sr)
    ramp = np.linspace(0.0, 1.0, edge_n, dtype=np.float32)[:, None]
    stereo[:edge_n] *= ramp
    stereo[-edge_n:] *= ramp[::-1]

    master_wav_path = ep_dir / "audio_master.wav"
    _write_wav_int16(master_wav_path, stereo, sample_rate=sr)

    # 30fps narration RMS envelope
    hop = sr // 30
    n_env = max(1, total_samples // hop)
    env_frames = narration[: n_env * hop].reshape(n_env, hop)
    envelope = np.sqrt(np.mean(env_frames.astype(np.float64) ** 2, axis=1)).astype(np.float32)
    np.save(ep_dir / "narration_envelope.npy", envelope)

    timeline = {
        "total_duration_s": round(total_duration_s, 3),
        "sample_rate_hz": sr,
        "beats": timeline_beats,
        "narration_wav_path": "narration_clean.wav",
        "master_wav_path": "audio_master.wav",
        "envelope_path": "narration_envelope.npy",
    }
    _write_json(ep_dir / "narration_timeline.json", timeline)
    return script_beats, timeline


def _build_captions_json(timeline: dict[str, Any]) -> dict[str, Any]:
    """Generate Whisper-like non-uniform 2-4 word caption blocks matching the canonical script."""
    blocks: list[dict[str, Any]] = []
    for bi, beat in enumerate(timeline["beats"]):
        words = beat["narration_text"].split()
        if not words:
            continue
        b_start = float(beat["start_s"])
        b_end = float(beat["end_s"])
        span = max(0.25, b_end - b_start)

        # Realistic non-uniform weights driven by word length, punctuation, and deterministic jitter
        weights: list[float] = []
        for wi, tok in enumerate(words):
            h_byte = hashlib.sha256(f"{bi}:{wi}:{tok}".encode("utf-8")).digest()[0]
            jitter = 0.45 + (h_byte / 255.0) * 1.15
            punct_bonus = 1.45 if tok[-1] in ".,!?;:" else 0.0
            weights.append((len(tok) ** 1.2) + punct_bonus + jitter)

        total_w = sum(weights)
        raw_durs = [max(0.08, span * (w / total_w)) for w in weights]
        scale = span / sum(raw_durs)
        durs = [d * scale for d in raw_durs]

        timed_words: list[dict[str, Any]] = []
        cur_t = b_start
        for wi, (tok, dur) in enumerate(zip(words, durs)):
            w_end = min(b_end, cur_t + dur)
            if wi == len(words) - 1:
                w_end = b_end
            timed_words.append(
                {
                    "text": tok,
                    "start_s": round(cur_t, 4),
                    "end_s": round(max(cur_t + 0.04, w_end), 4),
                    "emphasize": bool(tok.isupper() or (wi % 4 == 2)),
                }
            )
            cur_t = w_end

        # Chunk into 2-4 word blocks (avoid stray 1-word internal blocks)
        idx = 0
        n = len(timed_words)
        while idx < n:
            rem = n - idx
            if rem <= 4:
                chunk_size = rem
            elif rem == 5:
                chunk_size = 3
            else:
                chunk_size = 3 if (len(blocks) % 2 == 0) else 4
            chunk = timed_words[idx : idx + chunk_size]
            blocks.append(
                {
                    "start_s": chunk[0]["start_s"],
                    "end_s": chunk[-1]["end_s"],
                    "words": chunk,
                }
            )
            idx += chunk_size

    return {"blocks": blocks}


def _generate_cover_assets(
    ep_dir: Path, headline_lines: list[str], motif: str, root: Path
) -> None:
    """Create 1080x1920 cover.png (Reels-safe) + distinct cover_grid_preview.png."""
    w, h = 1080, 1920
    img = Image.new("RGB", (w, h), _BG_DARK)
    d = ImageDraw.Draw(img)

    # Subtle blueprint grid across full canvas (keeps outer strips dark & cohesive)
    for gx in range(0, w, 60):
        d.line([(gx, 0), (gx, h)], fill=(18, 28, 46), width=2)
    for gy in range(0, h, 60):
        d.line([(0, gy), (w, gy)], fill=(18, 28, 46), width=2)

    # All hero artwork + headline strictly inside (120, 360, 960, 1520) -> clears y<315 & y>1595!
    if motif == "vault":
        d.rounded_rectangle([120, 620, 960, 1460], radius=36, fill=_PANEL_DARK, outline=_AMBER, width=10)
        d.ellipse([260, 740, 820, 1300], fill=(15, 24, 40), outline=_WHITE, width=12)
        for spoke in range(6):
            ang = spoke * (math.pi / 3.0)
            x2 = 540 + int(230 * math.cos(ang))
            y2 = 1020 + int(230 * math.sin(ang))
            d.line([(540, 1020), (x2, y2)], fill=_AMBER, width=22)
        d.ellipse([460, 940, 620, 1100], fill=_WHITE, outline=_BG_DARK, width=8)
        accent_hl = _AMBER
    else:
        d.rounded_rectangle([120, 620, 960, 1460], radius=36, fill=(22, 42, 62), outline=_CYAN, width=10)
        d.rectangle([480, 660, 600, 1420], fill=(71, 85, 105), outline=_WHITE, width=6)
        d.polygon([(170, 820), (470, 1020), (170, 1220)], fill=_CYAN, outline=_WHITE)
        d.polygon([(910, 820), (610, 1020), (910, 1220)], fill=(239, 68, 68), outline=_WHITE)
        d.rectangle([220, 1270, 860, 1360], fill=_YELLOW, outline=_BG_DARK, width=6)
        accent_hl = _CYAN

    font_title = _load_font(84, root)
    d.text(
        (540, 420),
        headline_lines[0],
        font=font_title,
        fill=_WHITE,
        anchor="mm",
        stroke_width=6,
        stroke_fill=(0, 0, 0),
    )
    d.text(
        (540, 520),
        headline_lines[1],
        font=font_title,
        fill=accent_hl,
        anchor="mm",
        stroke_width=6,
        stroke_fill=(0, 0, 0),
    )

    cover_path = ep_dir / "cover.png"
    img.save(cover_path, format="PNG", compress_level=1)

    # Distinct cropped Reels grid preview sheet (1080x1250) with visible crop frame overlay
    grid = img.crop((0, 330, 1080, 1580)).copy()
    gd = ImageDraw.Draw(grid)
    gd.rectangle([8, 8, 1071, 1241], outline=_CYAN, width=10)
    gd.rectangle([90, 20, 990, 1230], outline=_YELLOW, width=4)
    grid.save(ep_dir / "cover_grid_preview.png", format="PNG", compress_level=1)


def _generate_marca_assets(root: Path, brand: dict[str, Any]) -> None:
    """Create youtube_banner.png, youtube_banner_preview.png, and brand_sheet.png."""
    marca_dir = root / "marca"
    marca_dir.mkdir(parents=True, exist_ok=True)

    bw, bh = 2560, 1440
    banner = Image.new("RGB", (bw, bh), _BG_DARK)
    bd = ImageDraw.Draw(banner)

    # Cohesive blueprint grid across TV & Desktop regions (non-blank dark fill)
    for gx in range(0, bw, 64):
        bd.line([(gx, 0), (gx, bh)], fill=(19, 30, 50), width=2)
    for gy in range(0, bh, 64):
        bd.line([(0, gy), (bw, gy)], fill=(19, 30, 50), width=2)

    # Decorative side desktop vectors (outside mobile borders, leaving 70px clearance around x=507,2053)
    bd.rounded_rectangle([80, 560, 410, 880], radius=24, fill=_PANEL_DARK, outline=_CYAN, width=4)
    bd.rounded_rectangle([2150, 560, 2480, 880], radius=24, fill=_PANEL_DARK, outline=_AMBER, width=4)

    # Main brand identity strictly centered inside mobile safe zone (x=640..1920, y=580..860)
    bd.rounded_rectangle([620, 575, 1940, 865], radius=26, fill=_PANEL_DARK, outline=_AMBER, width=6)
    font_h1 = _load_font(94, root)
    font_sub = _load_font(44, root)
    bd.text(
        (1280, 680),
        "IRONCUT ENGINEERING",
        font=font_h1,
        fill=_WHITE,
        anchor="mm",
        stroke_width=4,
        stroke_fill=(0, 0, 0),
    )
    bd.text(
        (1280, 785),
        "HOW IT WORKS  |  REAL DISASTERS  |  2.5D CUTAWAYS",
        font=font_sub,
        fill=_AMBER,
        anchor="mm",
        stroke_width=2,
        stroke_fill=(0, 0, 0),
    )

    banner_path = marca_dir / "youtube_banner.png"
    banner.save(banner_path, format="PNG", compress_level=1)

    # Preview image with explicit desktop + mobile guide overlays (visually distinct from banner)
    preview = banner.copy()
    pd = ImageDraw.Draw(preview)
    pd.rectangle([0, 508, 2559, 931], outline=_CYAN, width=10)
    pd.rectangle([507, 508, 2053, 931], outline=_YELLOW, width=12)
    pd.text((1280, 465), "SAFE ZONE PREVIEW — MOBILE 1546x423 / DESKTOP 2560x423", font=font_sub, fill=_YELLOW, anchor="mm")
    preview.save(marca_dir / "youtube_banner_preview.png", format="PNG", compress_level=1)

    # Brand sheet displaying large exact swatches for every palette color
    sheet = Image.new("RGB", (1920, 1080), _BG_DARK)
    sd = ImageDraw.Draw(sheet)
    sd.text((960, 100), "IRONCUT ENGINEERING — BRAND SHEET", font=_load_font(64, root), fill=_WHITE, anchor="mm")
    palette = brand["visual_style"]["palette"]
    sx = 110
    for name, hex_code in palette.items():
        sd.rounded_rectangle([sx, 240, sx + 250, 560], radius=16, fill=hex_code, outline=_WHITE, width=3)
        sd.text((sx + 125, 610), name, font=_load_font(22, root), fill=_WHITE, anchor="mm")
        sd.text((sx + 125, 645), hex_code, font=_load_font(24, root), fill=_YELLOW, anchor="mm")
        sx += 290
    sheet.save(marca_dir / "brand_sheet.png", format="PNG", compress_level=1)


def _create_reel_frames(frames_dir: Path, count: int, seed_offset: int) -> list[str]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    rel_names: list[str] = []
    for i in range(1, count + 1):
        img = Image.new("RGB", (360, 640), _BG_DARK)
        d = ImageDraw.Draw(img)
        col = (
            (50 + (i * 37 + seed_offset * 19) % 190),
            (70 + (i * 53 + seed_offset * 29) % 170),
            (90 + (i * 71 + seed_offset * 13) % 155),
        )
        y_top = 80 + (i * 28) % 340
        d.rounded_rectangle([40, y_top, 320, y_top + 140], radius=18, fill=col, outline=_WHITE, width=4)
        d.ellipse([90 + (i * 17) % 120, 120, 200 + (i * 17) % 120, 230], fill=_AMBER)
        fname = f"{i:03d}.jpg"
        img.save(frames_dir / fname, format="JPEG", quality=82)
        rel_names.append(f"frames/{fname}")
    return rel_names


def _build_reels_directory(
    root: Path,
    ep_scripts: dict[str, dict[str, Any]],
    *,
    include_orphan_reel_dir: bool,
) -> None:
    reels_root = root / "reels"
    reels_root.mkdir(parents=True, exist_ok=True)
    index_lines = ["# Reels Watch Index", ""]

    # Two YouTube reference runs (DYYsGuTpBKc and M_t2ZUz7_pc)
    refs = [
        ("20261123-061000_youtube_aa01", "DYYsGuTpBKc", "Reference 1 mechanical cutaway pacing breakdown"),
        ("20261123-061200_youtube_bb02", "M_t2ZUz7_pc", "Reference 2 high-contrast engineering diagram pacing"),
    ]
    for r_idx, (dirname, vid_id, summary) in enumerate(refs):
        rdir = reels_root / dirname
        rdir.mkdir(parents=True, exist_ok=True)
        frames = _create_reel_frames(rdir / "frames", 8, seed_offset=r_idx + 1)
        url = f"https://www.youtube.com/watch?v={vid_id}"
        manifest = {
            "sources": [url],
            "kind": "youtube",
            "fetched_via": "yt-dlp",
            "engine": "local (whisper base.en + rapidocr)",
            "duration_sec": 68.4,
            "meta": {"id": vid_id, "webpage_url": url, "title": summary},
            "frames": frames,
            "analysis": "local.md",
        }
        _write_json(rdir / "manifest.json", manifest)
        (rdir / "local.md").write_text(
            "\n".join(
                [
                    f"# Reel Breakdown — {vid_id}",
                    "",
                    "## Metadata",
                    f"- URL: {url}",
                    "- Duration: 68.4s",
                    "",
                    "## Transcript",
                    "Watch how the steel lock mechanism engages in under two seconds with zero play.",
                    "",
                    "## On-screen text (verbatim, read by OCR)",
                    "FRAME 01: STEEL LOCK MECHANISM",
                    "",
                    "## Visual pacing",
                    "Fast cut cadence every 3 to 5 seconds across 4 distinct camera angles.",
                    "",
                    "## Hook analysis",
                    "Immediate high-contrast macro cutaway on frame zero with crisp top title.",
                    "",
                    "## Audio notes",
                    "Continuous subtle ambient synth bed underneath crisp American English narration.",
                    "",
                    "## Key takeaways",
                    "Use high-contrast 2.5D isometric cutaways with clean outlined captions.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (rdir / "breakdown.md").write_text(
            f"# Reference Analysis: {vid_id}\n\n"
            f"Source: {url}\n\n"
            "Strong 2.5D mechanical vector cutaway visual pacing, instant frame 0 hook, "
            "4 distinct camera angles, and clean high-contrast typography.\n",
            encoding="utf-8",
        )
        index_lines.append(f"- 2026-11-23 | {summary} | reels/{dirname}")

    # Two local QA audit runs matching ep01 and ep02
    audits = [
        ("20261123-062000_ep01_vault_bolt_lock_cc03", "ep01_vault_bolt_lock"),
        ("20261123-062200_ep02_elevator_brake_jaw_dd04", "ep02_elevator_brake_jaw"),
    ]
    for a_idx, (dirname, slug) in enumerate(audits):
        rdir = reels_root / dirname
        rdir.mkdir(parents=True, exist_ok=True)
        frames = _create_reel_frames(rdir / "frames", 16, seed_offset=20 + a_idx)
        script = ep_scripts[slug]
        full_narration = " ".join(b["narration_text"] for b in script["beats"])
        manifest = {
            "sources": [f"episodios/{slug}/{slug}.mp4"],
            "kind": "local",
            "fetched_via": "local-file",
            "engine": "local (whisper base.en + rapidocr)",
            "duration_sec": 66.0 if slug.startswith("ep01") else 69.3,
            "meta": {"filename": f"{slug}.mp4"},
            "frames": frames,
            "analysis": "local.md",
        }
        _write_json(rdir / "manifest.json", manifest)
        (rdir / "local.md").write_text(
            "\n".join(
                [
                    f"# Local QA Audit — {slug}",
                    "",
                    "## Metadata",
                    f"- File: episodios/{slug}/{slug}.mp4",
                    "",
                    "## Transcript",
                    full_narration,
                    "",
                    "## On-screen text (verbatim, read by OCR)",
                    f"FRAME 01: {script['hook_text']}",
                    "FRAME 05: STEEL BOLTS",
                    "",
                    "## Visual pacing",
                    "Articulated motion across 4 distinct camera angles, zero static holds.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        index_lines.append(f"- 2026-11-23 | #1 | Local QA audit for {slug} | #qa | {dirname}")

    (reels_root / "INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    if include_orphan_reel_dir:
        (reels_root / "20261123-060431_youtube_342c").mkdir(parents=True, exist_ok=True)


def build_synthetic_workspace(
    root: Path, *, include_orphan_reel_dir: bool = True
) -> Path:
    """Build a complete spec-compliant synthetic CTS workspace under ``root`` (<12s)."""
    ws = Path(root).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    real_root = get_real_repo_root()

    # Copy starter scaffold files verbatim when present
    for fname in ("brand_template.json", ".gitignore"):
        src = real_root / fname
        if src.is_file():
            shutil.copy2(src, ws / fname)

    # Copy bundled TTF fonts when available
    real_fonts = real_root / "assets" / "fonts"
    if real_fonts.is_dir():
        ws_fonts = ws / "assets" / "fonts"
        ws_fonts.mkdir(parents=True, exist_ok=True)
        for ttf in sorted(real_fonts.glob("*.ttf")):
            shutil.copy2(ttf, ws_fonts / ttf.name)

    brand = _build_brand_json()
    _write_json(ws / "brand.json", brand)
    _generate_marca_assets(ws, brand)

    backlog = _build_themes_backlog()
    _write_json(ws / "episodios" / "themes_backlog.json", backlog)
    (ws / "episodios" / "THEMES_CATALOG.md").write_text(
        _build_themes_catalog_md(backlog), encoding="utf-8"
    )

    # Render 4 reusable 3.3s articulated clips once in a temporary staging dir
    ep_scripts: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="cts_synth_clips_") as clip_tmp:
        clip_dir = Path(clip_tmp)
        clips: list[Path] = []
        for idx in range(4):
            cp = clip_dir / f"clip_{idx}.mp4"
            _render_base_clip(cp, idx, ws)
            clips.append(cp)

        for ep_idx, bp in enumerate(_episode_blueprints()):
            slug = bp["slug"]
            ep_dir = ws / "episodios" / slug
            ep_dir.mkdir(parents=True, exist_ok=True)

            total_dur = round(len(bp["clip_order"]) * 3.3, 3)
            script_beats, timeline = _synthesize_episode_audio(
                ep_dir, bp["beats"], total_dur, ep_seed=ep_idx + 1
            )

            publish_meta = {
                "youtube_title": bp["title"],
                "youtube_description": (
                    f"{bp['hook_text']} — Inside the mechanical physics behind {bp['title']}."
                ),
                "ig_tiktok_caption": (
                    f"{bp['hook_text']} Watch every interlocking steel component fire in real time. "
                    f"{bp['cta_text']}"
                ),
                "hashtags": bp["hashtags"],
                "pinned_comment": f"Drop {bp['cta_token']} below if you caught the trigger!",
                "related_video_slot": bp["related_slug"],
                "schedule_hour": "12:00",
                "ai_disclosure": False,
                "post_publish_48h_loop": {
                    "never_delete_stalled_shorts": True,
                    "review_after_hours": 48,
                    "stayed_to_watch_target_pct": 75.0,
                    "avd_target_pct": 100.0,
                    "drop_off_beat_audit": True,
                },
            }

            script_payload = {
                "episode_id": bp["episode_id"],
                "slug": slug,
                "title": bp["title"],
                "hook_text": bp["hook_text"],
                "cta_text": bp["cta_text"],
                "bpm": bp["bpm"],
                "cover_headline": bp["cover_headline"],
                "publish_meta": publish_meta,
                "beats": script_beats,
            }
            ep_scripts[slug] = script_payload
            _write_json(ep_dir / "script.json", script_payload)
            _write_json(ep_dir / "publish_meta.json", publish_meta)

            captions_payload = _build_captions_json(timeline)
            _write_json(ep_dir / "captions.json", captions_payload)

            # Fast concat-copy video + AAC 192k 48kHz stereo audio mux
            concat_list = clip_dir / f"{slug}_list.txt"
            concat_list.write_text(
                "\n".join(f"file '{clips[ci].as_posix()}'" for ci in bp["clip_order"]) + "\n",
                encoding="utf-8",
            )
            mp4_path = ep_dir / f"{slug}.mp4"
            _run_ffmpeg(
                [
                    "-f", "concat", "-safe", "0", "-i", str(concat_list),
                    "-i", str(ep_dir / "audio_master.wav"),
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-shortest",
                    str(mp4_path),
                ]
            )

            _generate_cover_assets(
                ep_dir,
                bp["cover_headline"],
                motif="vault" if ep_idx == 0 else "elevator",
                root=ws,
            )

            # Measure actual MP4 properties so qa_report.json has exact parity
            probe = probe_media(mp4_path)
            loud = measure_ebur128(mp4_path)
            rms_scan = scan_rms_windows(mp4_path)
            qa_report = {
                "episode_id": bp["episode_id"],
                "slug": slug,
                "mp4_path": f"episodios/{slug}/{slug}.mp4",
                "passed": True,
                "width": probe.width,
                "height": probe.height,
                "fps": round(probe.fps or 0.0, 3),
                "duration_s": round(probe.duration_s, 3),
                "video_codec": probe.video_codec,
                "pix_fmt": probe.pix_fmt,
                "audio_codec": probe.audio_codec,
                "sample_rate_hz": probe.sample_rate_hz,
                "channels": probe.channels,
                "integrated_lufs": round(loud.integrated_lufs, 2),
                "lra_lu": round(loud.lra_lu, 2),
                "true_peak_dbfs": round(loud.true_peak_dbfs, 2),
                "silence_windows_below_minus60db": len(rms_scan.silence_windows),
                "min_rms_db": round(rms_scan.min_db, 2),
                "visual_continuity_pass": True,
            }
            _write_json(ep_dir / "qa_report.json", qa_report)

    _build_reels_directory(ws, ep_scripts, include_orphan_reel_dir=include_orphan_reel_dir)
    clear_media_cache()
    return ws


def copy_workspace(src: Path, dst: Path) -> Path:
    """Copy a pre-built synthetic workspace cleanly to ``dst`` for isolated mutation tests."""
    src_p = Path(src).resolve()
    dst_p = Path(dst).resolve()
    if dst_p.exists():
        shutil.rmtree(dst_p)
    shutil.copytree(src_p, dst_p)
    return dst_p


def _first_episode_dir(ws: Path) -> tuple[Path, Path]:
    ep_root = ws / "episodios"
    ep_dirs = sorted(p for p in ep_root.iterdir() if p.is_dir() and p.name.startswith("ep01"))
    if not ep_dirs:
        raise FileNotFoundError(f"No ep01* directory found under {ep_root}")
    ep_dir = ep_dirs[0]
    mp4 = ep_dir / f"{ep_dir.name}.mp4"
    return ep_dir, mp4


def _reencode_concat_video_only(
    mp4: Path,
    *,
    video_args: list[str],
    repeat_count: int = 20,
) -> None:
    """Fast (<0.9s) mutation helper: re-encode first 3.3s segment and concat-copy with original audio."""
    with tempfile.TemporaryDirectory(prefix="cts_mut_") as td:
        tdir = Path(td)
        seg = tdir / "seg.mp4"
        _run_ffmpeg(["-i", str(mp4), "-t", "3.3", "-an", *video_args, str(seg)])
        lst = tdir / "list.txt"
        lst.write_text(
            "\n".join(f"file '{seg.as_posix()}'" for _ in range(repeat_count)) + "\n",
            encoding="utf-8",
        )
        out = tdir / "out.mp4"
        _run_ffmpeg(
            [
                "-f", "concat", "-safe", "0", "-i", str(lst),
                "-i", str(mp4),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "copy",
                "-shortest",
                str(out),
            ]
        )
        shutil.move(str(out), str(mp4))


def _remux_with_master_wav(mp4: Path, master_wav: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="cts_mut_aud_") as td:
        out = Path(td) / "out.mp4"
        _run_ffmpeg(
            [
                "-i", str(mp4),
                "-i", str(master_wav),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-shortest",
                str(out),
            ]
        )
        shutil.move(str(out), str(mp4))


def mutate_workspace(root: Path, defect: str) -> Path:
    """Inject a single targeted defect from ``ALL_DEFECT_KEYS`` into a workspace copy."""
    if defect not in SUPPORTED_DEFECTS:
        raise ValueError(f"Unsupported defect key {defect!r}; expected one of {ALL_DEFECT_KEYS}")

    ws = Path(root).resolve()
    ep_dir, mp4 = _first_episode_dir(ws)

    if defect == "short_duration":
        tmp_mp4 = ep_dir / "_short_tmp.mp4"
        _run_ffmpeg(["-i", str(mp4), "-t", "58.0", "-c", "copy", str(tmp_mp4)])
        shutil.move(str(tmp_mp4), str(mp4))

    elif defect == "wrong_fps":
        _reencode_concat_video_only(
            mp4,
            video_args=["-r", "24", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p"],
        )

    elif defect == "wrong_resolution":
        _reencode_concat_video_only(
            mp4,
            video_args=[
                "-vf", "scale=720:1280",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p",
            ],
        )

    elif defect == "wrong_pix_fmt":
        _reencode_concat_video_only(
            mp4,
            video_args=["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv444p"],
        )

    elif defect == "loudness_too_loud":
        master_wav = ep_dir / "audio_master.wav"
        with wave.open(str(master_wav), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        boosted = np.clip(arr * 2.8, -1.0, 1.0).reshape(-1, ch)
        _write_wav_int16(master_wav, boosted, sample_rate=sr)
        _remux_with_master_wav(mp4, master_wav)

    elif defect == "silence_vacuum":
        master_wav = ep_dir / "audio_master.wav"
        with wave.open(str(master_wav), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        arr = (np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0).reshape(-1, ch).copy()
        s0, s1 = int(20.0 * sr), int(22.5 * sr)
        arr[s0:s1, :] = 0.0
        _write_wav_int16(master_wav, arr, sample_rate=sr)
        _remux_with_master_wav(mp4, master_wav)

    elif defect == "static_video":
        with tempfile.TemporaryDirectory(prefix="cts_mut_static_") as td:
            tdir = Path(td)
            f0 = tdir / "f0.png"
            _run_ffmpeg(["-i", str(mp4), "-frames:v", "1", str(f0)])
            seg = tdir / "still.mp4"
            _run_ffmpeg(
                [
                    "-loop", "1", "-i", str(f0), "-t", "3.3", "-r", "30",
                    "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
                    "-pix_fmt", "yuv420p", str(seg),
                ]
            )
            lst = tdir / "list.txt"
            lst.write_text("\n".join(f"file '{seg.as_posix()}'" for _ in range(20)) + "\n", encoding="utf-8")
            out = tdir / "out.mp4"
            _run_ffmpeg(
                [
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-i", str(mp4),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "copy", "-shortest",
                    str(out),
                ]
            )
            shutil.move(str(out), str(mp4))

    elif defect == "black_frame0":
        with tempfile.TemporaryDirectory(prefix="cts_mut_blk_") as td:
            tdir = Path(td)
            # Build 3.3s replacement clip: first 10 frames pure black, next 89 frames bright
            bright_f = tdir / "bright.png"
            _run_ffmpeg(["-i", str(mp4), "-frames:v", "1", str(bright_f)])
            with Image.open(bright_f) as im:
                bright_small = im.resize((270, 480), Image.Resampling.NEAREST).convert("RGB")
            black_small = Image.new("RGB", (270, 480), (0, 0, 0))
            head_clip = tdir / "head.mp4"
            cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "270x480", "-r", "30", "-i", "pipe:0",
                "-vf", "scale=1080:1920:flags=neighbor",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16",
                "-g", "99", "-keyint_min", "99", "-sc_threshold", "0", "-pix_fmt", "yuv420p",
                str(head_clip),
            ]
            with subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
                assert proc.stdin is not None
                try:
                    blk_bytes = black_small.tobytes()
                    brt_bytes = bright_small.tobytes()
                    for fi in range(99):
                        proc.stdin.write(blk_bytes if fi < 10 else brt_bytes)
                finally:
                    proc.stdin.close()
                if proc.stderr is not None:
                    proc.stderr.read()
                if proc.wait() != 0:
                    raise RuntimeError("black_frame0 head clip render failed")

            tail_clip = tdir / "tail.mp4"
            _run_ffmpeg(["-ss", "3.3", "-i", str(mp4), "-an", "-c:v", "copy", str(tail_clip)])
            lst = tdir / "list.txt"
            lst.write_text(
                f"file '{head_clip.as_posix()}'\nfile '{tail_clip.as_posix()}'\n",
                encoding="utf-8",
            )
            out = tdir / "out.mp4"
            _run_ffmpeg(
                [
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-i", str(mp4),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "copy", "-shortest",
                    str(out),
                ]
            )
            shutil.move(str(out), str(mp4))

    elif defect == "pt_br_leakage":
        script_path = ep_dir / "script.json"
        script = load_json(script_path)
        script["beats"][1]["narration_text"] += " Como funciona a pressão do cofre."
        _write_json(script_path, script)

    elif defect == "bad_yt_title_len":
        bad_title = "How This Massive Bank Vault Mechanism LOCKS From The Inside"  # 59 chars > 50
        for p in (ep_dir / "script.json", ep_dir / "publish_meta.json"):
            data = load_json(p)
            if p.name == "script.json":
                data["title"] = bad_title
                data["publish_meta"]["youtube_title"] = bad_title
            else:
                data["youtube_title"] = bad_title
            _write_json(p, data)

    elif defect == "bad_yt_title_hashtag":
        bad_title = "How a Bank Vault LOCKS Inside #shorts"
        for p in (ep_dir / "script.json", ep_dir / "publish_meta.json"):
            data = load_json(p)
            if p.name == "script.json":
                data["title"] = bad_title
                data["publish_meta"]["youtube_title"] = bad_title
            else:
                data["youtube_title"] = bad_title
            _write_json(p, data)

    elif defect == "bad_yt_title_two_caps":
        bad_title = "How VAULT Locks NEVER Fail"
        for p in (ep_dir / "script.json", ep_dir / "publish_meta.json"):
            data = load_json(p)
            if p.name == "script.json":
                data["title"] = bad_title
                data["publish_meta"]["youtube_title"] = bad_title
            else:
                data["youtube_title"] = bad_title
            _write_json(p, data)

    elif defect == "mid_video_subscribe":
        script_path = ep_dir / "script.json"
        script = load_json(script_path)
        for beat in script["beats"]:
            if beat.get("act") == "mechanism":
                beat["narration_text"] += " Like and subscribe right now for more!"
                break
        _write_json(script_path, script)

    elif defect == "caption_overflow":
        cap_path = ep_dir / "captions.json"
        caps = load_json(cap_path)
        caps["blocks"][0] = {
            "start_s": 0.05,
            "end_s": 1.65,
            "words": [
                {"text": "Too", "start_s": 0.05, "end_s": 0.25, "emphasize": False},
                {"text": "many", "start_s": 0.25, "end_s": 0.45, "emphasize": False},
                {"text": "words", "start_s": 0.45, "end_s": 0.70, "emphasize": True},
                {"text": "packed", "start_s": 0.70, "end_s": 0.90, "emphasize": False},
                {"text": "into", "start_s": 0.90, "end_s": 1.15, "emphasize": False},
                {"text": "one", "start_s": 1.15, "end_s": 1.40, "emphasize": False},
                {"text": "block", "start_s": 1.40, "end_s": 1.65, "emphasize": False},
            ],
        }
        _write_json(cap_path, caps)

    elif defect == "cover_safe_zone_clip":
        cover_path = ep_dir / "cover.png"
        with Image.open(cover_path) as im:
            mutated = im.convert("RGB").copy()
        d = ImageDraw.Draw(mutated)
        d.text(
            (120, 90),
            "CLIPPED TOP TITLE",
            font=_load_font(76, ws),
            fill=(255, 255, 255),
            stroke_width=6,
            stroke_fill=(0, 0, 0),
        )
        mutated.save(cover_path, format="PNG", compress_level=1)

    elif defect == "banner_oversize_bytes":
        banner_path = ws / "marca" / "youtube_banner.png"
        noise_img = Image.frombytes("RGB", (2560, 1440), os.urandom(2560 * 1440 * 3))
        noise_img.save(banner_path, format="PNG", compress_level=0)

    elif defect == "secret_leak":
        # Dynamically assembled so this helper module never contains a raw secret literal.
        leaked_key = "AIza" + "SyD9xK2mP7qR4tV8wZ1bN5cF3hJ6kL0mN2p"
        (ws / "episodios" / "leak_test.txt").write_text(
            "GEMINI_API_KEY=" + leaked_key + "\n",
            encoding="utf-8",
        )

    elif defect == "missing_reel_ref":
        reels_root = ws / "reels"
        if reels_root.is_dir():
            for child in list(reels_root.iterdir()):
                if child.is_dir() and (child / "manifest.json").is_file():
                    text = (child / "manifest.json").read_text(encoding="utf-8", errors="ignore")
                    if "M_t2ZUz7_pc" in text:
                        shutil.rmtree(child)

    clear_media_cache()
    return ws
