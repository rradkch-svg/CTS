"""Core configuration dataclasses, JSON persistence, and strict validators for CTS Shorts Factory."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

VALID_ACTS: tuple[str, ...] = ("hook", "mechanism", "escalation", "climax", "cta")
ACT_ORDER: dict[str, int] = {act: idx for idx, act in enumerate(VALID_ACTS)}

VALID_CAMERA_PRESETS: tuple[str, ...] = (
    "FRAME0_HERO",
    "ISO_WIDE",
    "MACRO_CUTAWAY",
    "EXPLODED_BLUEPRINT",
    "IMPACT_CLOSEUP",
)

DEFAULT_TTS_MODELS: tuple[str, ...] = (
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-2.5-flash-preview-tts",
    "gemini-3.1-flash-tts-preview",
)

VALID_GEMINI_VOICES: frozenset[str] = frozenset(
    {
        "Achernar",
        "Achird",
        "Algenib",
        "Algieba",
        "Alnilam",
        "Aoede",
        "Autonoe",
        "Callirrhoe",
        "Charon",
        "Despina",
        "Enceladus",
        "Erinome",
        "Fenrir",
        "Gacrux",
        "Iapetus",
        "Kore",
        "Laomedeia",
        "Leda",
        "Orus",
        "Puck",
        "Pulcherrima",
        "Rasalgethi",
        "Sadachbia",
        "Sadaltager",
        "Schedar",
        "Sulafat",
        "Umbriel",
        "Vindemiatrix",
        "Zephyr",
        "Zubenelgenubi",
    }
)

REQUIRED_PALETTE_KEYS: tuple[str, ...] = (
    "background_dark",
    "primary_accent",
    "secondary_accent",
    "text_primary",
    "text_highlight",
)

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}\Z")
_HANDLE_RE = re.compile(r"^@[A-Za-z0-9._-]{3,30}\Z")
_SCHEDULE_HOUR_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d\Z")
_EPISODE_ID_RE = re.compile(r"^ep\d{2}\Z")
_SLUG_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*\Z")
_HASHTAG_RE = re.compile(r"^#[A-Za-z0-9_]+\Z")
_PT_DIACRITICS_RE = re.compile(r"[ãõçáéíóúâêôàÃÕÇÁÉÍÓÚÂÊÔÀ]")
_PT_LEAKAGE_RE = re.compile(
    r"\b(?:não|nao|você|voce|porque|então|entao|cofre|submarino|elevador|comente|inscreva)\b",
    re.IGNORECASE,
)
_ROTA_CRITICA_RE = re.compile(r"rota\s+cr[ií]tica", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"\b(?:DEFINIR|TODO|TBD)\b|DEFINIR_", re.IGNORECASE)
_SUBSCRIBE_PROMPT_RE = re.compile(
    r"\b(?:subscribe|like\s+and\s+subscribe|hit\s+(?:the\s+)?(?:like|bell|subscribe)|"
    r"smash\s+that|follow\s+(?:me|us|for\s+more)|don't\s+forget\s+to\s+like)\b",
    re.IGNORECASE,
)
_WHISPER_POSITIVE_RE = re.compile(
    r"(?<!\bno\s)(?<!\bavoid\s)(?<!\bzero\s)(?<!\bnever\s)(?<!\bnot\s)(?<!\bnon-sibilant\s)"
    r"\bwhisper(?:ing|ed|s)?\b",
    re.IGNORECASE,
)
_SLOW_HOOK_FILLER_RE = re.compile(
    r"^\s*(?:hey\s+guys|welcome\s+back|in\s+this\s+video|today\s+we|hello\s+everyone|what'?s\s+up)\b",
    re.IGNORECASE,
)
_CTA_ACTION_RE = re.compile(r"\b(?:comment|type|drop)\b", re.IGNORECASE)
_CTA_ACTION_VERBS: frozenset[str] = frozenset({"COMMENT", "TYPE", "DROP"})
_TITLE_TOKEN_SPLIT_RE = re.compile(r"[\s/\u2014\u2013]+")


class ValidationError(ValueError):
    """Raised when strict contract validation fails."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = list(violations)
        summary = "; ".join(self.violations)
        super().__init__(f"Validation failed ({len(self.violations)} issues): {summary}")


class _DictLikeMixin:
    """Provides dict-like read access alongside dataclass attribute access."""

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and hasattr(self, key)

    def keys(self) -> list[str]:
        return [f.name for f in fields(self)]  # type: ignore[arg-type]


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def _reject_non_finite_json(token: str) -> Any:
    raise ValueError(f"Non-finite JSON constant is not allowed: {token!r}")


def _is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _ensure_mapping(value: Any, name: str, *, allow_none: bool = True) -> Mapping[str, Any]:
    if value is None:
        if allow_none:
            return {}
        raise ValueError(f"{name} must be a mapping, got None.")
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping, got {type(value).__name__}.")
    return value


def _ensure_sequence(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a list, got {type(value).__name__}.")
    return list(value)


def _read_json(path: str | Path) -> dict[str, Any]:
    raw = json.loads(
        Path(path).read_text(encoding="utf-8"),
        parse_constant=_reject_non_finite_json,
    )
    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object in {path}, got {type(raw).__name__}")
    return raw


def _as_int_pair(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return (int(value[0]), int(value[1]))
    raise ValueError(f"Expected 2-element integer sequence, got {value!r}")


def _as_float_pair(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return (float(value[0]), float(value[1]))
    raise ValueError(f"Expected 2-element float sequence, got {value!r}")


@dataclass
class SafeZoneRect(_DictLikeMixin):
    """Axis-aligned pixel safe zone rectangle."""

    x_min: int
    x_max: int
    y_min: int
    y_max: int
    max_width_px: int | None = None

    @property
    def width(self) -> int:
        return self.x_max - self.x_min

    @property
    def height(self) -> int:
        return self.y_max - self.y_min

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x_min, self.y_min, self.x_max, self.y_max)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
        }
        if self.max_width_px is not None:
            out["max_width_px"] = self.max_width_px
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SafeZoneRect:
        mapping = _ensure_mapping(data, "SafeZoneRect", allow_none=False)
        max_w = mapping.get("max_width_px", mapping.get("max_width"))
        return cls(
            x_min=int(mapping["x_min"]),
            x_max=int(mapping["x_max"]),
            y_min=int(mapping["y_min"]),
            y_max=int(mapping["y_max"]),
            max_width_px=int(max_w) if max_w is not None else None,
        )


@dataclass
class SafeZones(_DictLikeMixin):
    """T7 safe-zone geometry for Shorts/Reels/TikTok video, covers, and YT banner."""

    top_hook: SafeZoneRect = field(default_factory=lambda: SafeZoneRect(215, 865, 310, 485))
    captions: SafeZoneRect = field(
        default_factory=lambda: SafeZoneRect(110, 930, 1380, 1520, max_width_px=820)
    )
    callout_hud: SafeZoneRect = field(default_factory=lambda: SafeZoneRect(90, 930, 490, 640))
    cover_reels_grid: SafeZoneRect = field(
        default_factory=lambda: SafeZoneRect(90, 990, 330, 1580)
    )
    cover_3x4: SafeZoneRect = field(default_factory=lambda: SafeZoneRect(90, 990, 260, 1660))
    youtube_banner_desktop: SafeZoneRect = field(
        default_factory=lambda: SafeZoneRect(0, 2560, 508, 931)
    )
    youtube_banner_mobile: SafeZoneRect = field(
        default_factory=lambda: SafeZoneRect(507, 2053, 508, 931)
    )
    youtube_banner_width: int = 2560
    youtube_banner_height: int = 1440
    youtube_banner_max_bytes: int = 6291456

    def to_dict(self) -> dict[str, Any]:
        return {
            "top_hook": self.top_hook.to_dict(),
            "captions": self.captions.to_dict(),
            "callout_hud": self.callout_hud.to_dict(),
            "cover_reels_grid": self.cover_reels_grid.to_dict(),
            "cover_3x4": self.cover_3x4.to_dict(),
            "youtube_banner_desktop": self.youtube_banner_desktop.to_dict(),
            "youtube_banner_mobile": self.youtube_banner_mobile.to_dict(),
            "youtube_banner_width": self.youtube_banner_width,
            "youtube_banner_height": self.youtube_banner_height,
            "youtube_banner_max_bytes": self.youtube_banner_max_bytes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> SafeZones:
        defaults = cls()
        mapping = _ensure_mapping(data, "SafeZones")
        if not mapping:
            return defaults

        def _rect(keys: tuple[str, ...], fallback: SafeZoneRect) -> SafeZoneRect:
            for k in keys:
                if k in mapping and mapping[k] is not None:
                    return SafeZoneRect.from_dict(mapping[k])
            return fallback

        banner_w = mapping.get("youtube_banner_width")
        banner_h = mapping.get("youtube_banner_height")
        banner_max = mapping.get("youtube_banner_max_bytes")
        return cls(
            top_hook=_rect(("top_hook", "hook_top", "hook_text"), defaults.top_hook),
            captions=_rect(("captions", "captions_bottom"), defaults.captions),
            callout_hud=_rect(("callout_hud",), defaults.callout_hud),
            cover_reels_grid=_rect(
                ("cover_reels_grid", "cover_grid_safe"), defaults.cover_reels_grid
            ),
            cover_3x4=_rect(("cover_3x4", "cover_3_4"), defaults.cover_3x4),
            youtube_banner_desktop=_rect(
                ("youtube_banner_desktop", "banner_desktop"), defaults.youtube_banner_desktop
            ),
            youtube_banner_mobile=_rect(
                ("youtube_banner_mobile", "banner_mobile_safe"), defaults.youtube_banner_mobile
            ),
            youtube_banner_width=(
                defaults.youtube_banner_width if banner_w is None else int(banner_w)
            ),
            youtube_banner_height=(
                defaults.youtube_banner_height if banner_h is None else int(banner_h)
            ),
            youtube_banner_max_bytes=(
                defaults.youtube_banner_max_bytes if banner_max is None else int(banner_max)
            ),
        )


@dataclass
class VideoSpec(_DictLikeMixin):
    """Master video and audio encoding contract."""

    resolution: str = "1080x1920"
    fps: int = 30
    target_duration_sec: tuple[int, int] = (65, 80)
    tiktok_1min_monetization_min_sec: int = 62
    audio_lufs: float = -14.5
    audio_true_peak_max: float = -1.0
    audio_lra_max: float = 4.0
    audio_codec: str = "aac"
    audio_sample_rate: int = 48000
    audio_bitrate_kbps: int = 192
    audio_channels: int = 2
    video_codec: str = "libx264"
    video_crf: int = 19
    pixel_format: str = "yuv420p"

    @property
    def width(self) -> int:
        parts = self.resolution.lower().split("x")
        return int(parts[0]) if len(parts) == 2 and parts[0].isdigit() else 0

    @property
    def height(self) -> int:
        parts = self.resolution.lower().split("x")
        return int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0

    @property
    def loudness_target_lufs(self) -> float:
        return self.audio_lufs

    @property
    def max_lra_lu(self) -> float:
        return self.audio_lra_max

    @property
    def audio_sample_rate_hz(self) -> int:
        return self.audio_sample_rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "fps": self.fps,
            "target_duration_sec": list(self.target_duration_sec),
            "tiktok_1min_monetization_min_sec": self.tiktok_1min_monetization_min_sec,
            "audio_lufs": self.audio_lufs,
            "audio_true_peak_max": self.audio_true_peak_max,
            "audio_lra_max": self.audio_lra_max,
            "audio_codec": self.audio_codec,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_bitrate_kbps": self.audio_bitrate_kbps,
            "audio_channels": self.audio_channels,
            "video_codec": self.video_codec,
            "video_crf": self.video_crf,
            "pixel_format": self.pixel_format,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> VideoSpec:
        mapping = _ensure_mapping(data, "VideoSpec")
        audio_lufs = mapping.get("audio_lufs", mapping.get("loudness_target_lufs", -14.5))
        audio_lra = mapping.get("audio_lra_max", mapping.get("max_lra_lu", 4.0))
        sample_rate = mapping.get("audio_sample_rate", mapping.get("audio_sample_rate_hz", 48000))
        return cls(
            resolution=str(mapping.get("resolution", "1080x1920")),
            fps=int(mapping.get("fps", 30)),
            target_duration_sec=_as_int_pair(mapping.get("target_duration_sec"), (65, 80)),
            tiktok_1min_monetization_min_sec=int(
                mapping.get("tiktok_1min_monetization_min_sec", 62)
            ),
            audio_lufs=float(-14.5 if audio_lufs is None else audio_lufs),
            audio_true_peak_max=float(mapping.get("audio_true_peak_max", -1.0)),
            audio_lra_max=float(4.0 if audio_lra is None else audio_lra),
            audio_codec=str(mapping.get("audio_codec", "aac")),
            audio_sample_rate=int(48000 if sample_rate is None else sample_rate),
            audio_bitrate_kbps=int(mapping.get("audio_bitrate_kbps", 192)),
            audio_channels=int(mapping.get("audio_channels", 2)),
            video_codec=str(mapping.get("video_codec", "libx264")),
            video_crf=int(mapping.get("video_crf", 19)),
            pixel_format=str(mapping.get("pixel_format", "yuv420p")),
        )


@dataclass
class VisualStyle(_DictLikeMixin):
    """Visual aesthetic, palette, typography, and safe-zone specification."""

    type: str = "2.5d_projected_isometric_cad_vector"
    style_decision_rationale: str = ""
    palette: dict[str, str] = field(default_factory=dict)
    fonts_dir: str = "assets/fonts"
    primary_font: str = "Montserrat-Black.ttf"
    secondary_font: str = "Montserrat-ExtraBold.ttf"
    fallback_font: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    safe_zones: SafeZones = field(default_factory=SafeZones)
    reference_takeaways: dict[str, Any] = field(default_factory=dict)

    def resolve_font_path(self, role: str = "primary", repo_root: Path | None = None) -> Path:
        """Resolve a font file safely with Linux fallback if bundled font is absent."""
        base = Path(repo_root) if repo_root is not None else Path.cwd()
        font_name = self.primary_font if role == "primary" else self.secondary_font
        candidate = Path(font_name)
        if not candidate.is_absolute():
            candidate = base / self.fonts_dir / font_name
        if candidate.is_file():
            return candidate
        fallback = Path(self.fallback_font)
        if not fallback.is_absolute():
            fallback = base / fallback
        return fallback

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": self.type,
            "style_decision_rationale": self.style_decision_rationale,
            "palette": dict(self.palette),
            "fonts_dir": self.fonts_dir,
            "primary_font": self.primary_font,
            "secondary_font": self.secondary_font,
            "fallback_font": self.fallback_font,
            "safe_zones": self.safe_zones.to_dict(),
        }
        if self.reference_takeaways:
            out["reference_takeaways"] = dict(self.reference_takeaways)
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> VisualStyle:
        mapping = _ensure_mapping(data, "VisualStyle")
        palette_raw = _ensure_mapping(mapping.get("palette"), "visual_style.palette")
        palette = {str(k): str(v) for k, v in palette_raw.items()}
        takeaways_raw = _ensure_mapping(
            mapping.get("reference_takeaways"), "visual_style.reference_takeaways"
        )
        return cls(
            type=str(mapping.get("type", "")),
            style_decision_rationale=str(mapping.get("style_decision_rationale", "")),
            palette=palette,
            fonts_dir=str(mapping.get("fonts_dir", "assets/fonts")),
            primary_font=str(mapping.get("primary_font", "Montserrat-ExtraBold.ttf")),
            secondary_font=str(
                mapping.get(
                    "secondary_font", mapping.get("primary_font", "Montserrat-ExtraBold.ttf")
                )
            ),
            fallback_font=str(
                mapping.get("fallback_font", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
            ),
            safe_zones=SafeZones.from_dict(mapping.get("safe_zones")),
            reference_takeaways=dict(takeaways_raw),
        )


@dataclass
class NarrationConfig(_DictLikeMixin):
    """Gemini TTS provider, fallback chain, pacing, and audio conditioning config."""

    provider: str = "google-genai"
    api_version: str = "v1beta"
    models: list[str] = field(default_factory=lambda: list(DEFAULT_TTS_MODELS))
    voice: str = "Charon"
    pov: str = "3rd_person_authoritative_engineer"
    style_direction: str = ""
    rate_range: tuple[float, float] = (1.0, 1.08)
    silence_trim_db: float = -52.0
    silence_head_pad_ms: int = 70
    silence_tail_pad_ms: int = 90
    avoid_whisper_hiss: bool = True
    continuous_ambient_bed: bool = True

    @property
    def primary_model(self) -> str:
        return self.models[0] if self.models else ""

    @property
    def model(self) -> str:
        return self.primary_model

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "api_version": self.api_version,
            "models": list(self.models),
            "voice": self.voice,
            "pov": self.pov,
            "style_direction": self.style_direction,
            "rate_range": list(self.rate_range),
            "silence_trim_db": self.silence_trim_db,
            "silence_head_pad_ms": self.silence_head_pad_ms,
            "silence_tail_pad_ms": self.silence_tail_pad_ms,
            "avoid_whisper_hiss": self.avoid_whisper_hiss,
            "continuous_ambient_bed": self.continuous_ambient_bed,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> NarrationConfig:
        mapping = _ensure_mapping(data, "NarrationConfig")
        raw_models = mapping.get("models")
        if raw_models is None:
            single_model = mapping.get("model")
            models = [str(single_model)] if single_model else list(DEFAULT_TTS_MODELS)
        else:
            models = [str(m) for m in _ensure_sequence(raw_models, "narration.models")]
        return cls(
            provider=str(mapping.get("provider", "google-genai")),
            api_version=str(mapping.get("api_version", "v1beta")),
            models=models,
            voice=str(mapping.get("voice", "Charon")),
            pov=str(mapping.get("pov", "3rd_person_fast_storyteller")),
            style_direction=str(mapping.get("style_direction", "")),
            rate_range=_as_float_pair(mapping.get("rate_range"), (1.0, 1.08)),
            silence_trim_db=float(mapping.get("silence_trim_db", -52.0)),
            silence_head_pad_ms=int(mapping.get("silence_head_pad_ms", 70)),
            silence_tail_pad_ms=int(mapping.get("silence_tail_pad_ms", 90)),
            avoid_whisper_hiss=bool(mapping.get("avoid_whisper_hiss", True)),
            continuous_ambient_bed=bool(mapping.get("continuous_ambient_bed", True)),
        )


@dataclass
class RetentionRules(_DictLikeMixin):
    """Short-form retention invariants enforced across scripts and renders."""

    frame_0_hook: str = ""
    no_mid_video_subscribe_cta: bool = True
    ending_cta: str = ""
    caption_chunk_words: tuple[int, int] = (2, 4)
    caption_style: str = "clean_outlined_no_box"
    min_camera_angles: int = 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_0_hook": self.frame_0_hook,
            "no_mid_video_subscribe_cta": self.no_mid_video_subscribe_cta,
            "ending_cta": self.ending_cta,
            "caption_chunk_words": list(self.caption_chunk_words),
            "caption_style": self.caption_style,
            "min_camera_angles": self.min_camera_angles,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> RetentionRules:
        mapping = _ensure_mapping(data, "RetentionRules")
        return cls(
            frame_0_hook=str(mapping.get("frame_0_hook", "")),
            no_mid_video_subscribe_cta=bool(mapping.get("no_mid_video_subscribe_cta", True)),
            ending_cta=str(mapping.get("ending_cta", "")),
            caption_chunk_words=_as_int_pair(mapping.get("caption_chunk_words"), (2, 4)),
            caption_style=str(mapping.get("caption_style", "clean_outlined_no_box")),
            min_camera_angles=int(mapping.get("min_camera_angles", 4)),
        )


@dataclass
class PublishingConfig(_DictLikeMixin):
    """Publishing cadence, title rules, AI disclosure, and 48h review settings."""

    youtube_title_max_chars: int = 50
    youtube_title_hashtags: bool = False
    youtube_title_one_uppercase_word: bool = True
    youtube_schedule_fixed_hour: str = "12:00"
    youtube_link_related_video: bool = True
    youtube_ai_disclosure_stylized_2d: bool = False
    never_delete_stalled_shorts: bool = True
    review_metrics_after_hours: int = 48
    stayed_to_watch_target_pct: float = 75.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "youtube_title_max_chars": self.youtube_title_max_chars,
            "youtube_title_hashtags": self.youtube_title_hashtags,
            "youtube_title_one_uppercase_word": self.youtube_title_one_uppercase_word,
            "youtube_schedule_fixed_hour": self.youtube_schedule_fixed_hour,
            "youtube_link_related_video": self.youtube_link_related_video,
            "youtube_ai_disclosure_stylized_2d": self.youtube_ai_disclosure_stylized_2d,
            "never_delete_stalled_shorts": self.never_delete_stalled_shorts,
            "review_metrics_after_hours": self.review_metrics_after_hours,
            "stayed_to_watch_target_pct": self.stayed_to_watch_target_pct,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> PublishingConfig:
        mapping = _ensure_mapping(data, "PublishingConfig")
        return cls(
            youtube_title_max_chars=int(mapping.get("youtube_title_max_chars", 50)),
            youtube_title_hashtags=bool(mapping.get("youtube_title_hashtags", False)),
            youtube_title_one_uppercase_word=bool(
                mapping.get("youtube_title_one_uppercase_word", True)
            ),
            youtube_schedule_fixed_hour=str(mapping.get("youtube_schedule_fixed_hour", "12:00")),
            youtube_link_related_video=bool(mapping.get("youtube_link_related_video", True)),
            youtube_ai_disclosure_stylized_2d=bool(
                mapping.get("youtube_ai_disclosure_stylized_2d", False)
            ),
            never_delete_stalled_shorts=bool(mapping.get("never_delete_stalled_shorts", True)),
            review_metrics_after_hours=int(mapping.get("review_metrics_after_hours", 48)),
            stayed_to_watch_target_pct=float(mapping.get("stayed_to_watch_target_pct", 75.0)),
        )


@dataclass
class BrandConfig:
    """Active channel brand manifest loaded from ``brand.json``."""

    channel_name: str
    handle: str
    language: str
    goal: str
    niche: str
    tagline: str
    anti_clone_note: str
    video_spec: VideoSpec
    visual_style: VisualStyle
    narration: NarrationConfig
    retention_rules: RetentionRules
    publishing: PublishingConfig

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "handle": self.handle,
            "language": self.language,
            "goal": self.goal,
            "niche": self.niche,
            "tagline": self.tagline,
            "anti_clone_note": self.anti_clone_note,
            "video_spec": self.video_spec.to_dict(),
            "visual_style": self.visual_style.to_dict(),
            "narration": self.narration.to_dict(),
            "retention_rules": self.retention_rules.to_dict(),
            "publishing": self.publishing.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BrandConfig:
        mapping = _ensure_mapping(data, "BrandConfig", allow_none=False)
        return cls(
            channel_name=str(mapping.get("channel_name", "")),
            handle=str(mapping.get("handle", "")),
            language=str(mapping.get("language", "")),
            goal=str(mapping.get("goal", "")),
            niche=str(mapping.get("niche", "")),
            tagline=str(mapping.get("tagline", "")),
            anti_clone_note=str(mapping.get("anti_clone_note", "")),
            video_spec=VideoSpec.from_dict(mapping.get("video_spec")),
            visual_style=VisualStyle.from_dict(mapping.get("visual_style")),
            narration=NarrationConfig.from_dict(mapping.get("narration")),
            retention_rules=RetentionRules.from_dict(mapping.get("retention_rules")),
            publishing=PublishingConfig.from_dict(mapping.get("publishing")),
        )

    @classmethod
    def load(cls, path: str | Path) -> BrandConfig:
        return cls.from_dict(_read_json(path))

    def save(self, path: str | Path) -> Path:
        return _write_json(path, self.to_dict())


@dataclass
class SfxCue(_DictLikeMixin):
    """Declarative procedural SFX trigger relative to beat start."""

    name: str
    offset_s: float = 0.0
    gain_db: float = -6.0
    pan: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "offset_s": self.offset_s,
            "gain_db": self.gain_db,
            "pan": self.pan,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SfxCue:
        mapping = _ensure_mapping(data, "SfxCue", allow_none=False)
        return cls(
            name=str(mapping["name"]),
            offset_s=float(mapping.get("offset_s", 0.0)),
            gain_db=float(mapping.get("gain_db", -6.0)),
            pan=float(mapping.get("pan", 0.0)),
        )


@dataclass
class Callout(_DictLikeMixin):
    """Compact engineering telemetry callout rendered inside the HUD safe zone."""

    label: str
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "value": self.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Callout:
        mapping = _ensure_mapping(data, "Callout", allow_none=False)
        return cls(label=str(mapping["label"]), value=str(mapping["value"]))


@dataclass
class PublishMeta(_DictLikeMixin):
    """Cross-platform publishing metadata bundle for a single episode."""

    youtube_title: str
    youtube_description: str
    ig_tiktok_caption: str
    hashtags: list[str]
    pinned_comment: str
    related_video_slot: str
    schedule_hour: str
    ai_disclosure: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "youtube_title": self.youtube_title,
            "youtube_description": self.youtube_description,
            "ig_tiktok_caption": self.ig_tiktok_caption,
            "hashtags": list(self.hashtags),
            "pinned_comment": self.pinned_comment,
            "related_video_slot": self.related_video_slot,
            "schedule_hour": self.schedule_hour,
            "ai_disclosure": self.ai_disclosure,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> PublishMeta:
        mapping = _ensure_mapping(data, "PublishMeta")
        return cls(
            youtube_title=str(mapping.get("youtube_title", "")),
            youtube_description=str(mapping.get("youtube_description", "")),
            ig_tiktok_caption=str(mapping.get("ig_tiktok_caption", "")),
            hashtags=[str(h) for h in _ensure_sequence(mapping.get("hashtags"), "publish_meta.hashtags")],
            pinned_comment=str(mapping.get("pinned_comment", "")),
            related_video_slot=str(mapping.get("related_video_slot", "")),
            schedule_hour=str(mapping.get("schedule_hour", "12:00")),
            ai_disclosure=bool(mapping.get("ai_disclosure", False)),
        )


@dataclass
class Beat:
    """Single narrative, audio, camera, and telemetry beat inside an episode script."""

    id: str
    act: str
    narration_text: str
    voice_direction: str
    camera_preset: str
    scene_key: str
    sfx_cues: list[SfxCue] = field(default_factory=list)
    callout: Callout | None = None
    pause_after_s: float = 0.25

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "act": self.act,
            "narration_text": self.narration_text,
            "voice_direction": self.voice_direction,
            "camera_preset": self.camera_preset,
            "scene_key": self.scene_key,
            "sfx_cues": [cue.to_dict() for cue in self.sfx_cues],
            "callout": self.callout.to_dict() if self.callout is not None else None,
            "pause_after_s": self.pause_after_s,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Beat:
        mapping = _ensure_mapping(data, "Beat", allow_none=False)
        callout_raw = mapping.get("callout")
        return cls(
            id=str(mapping["id"]),
            act=str(mapping["act"]),
            narration_text=str(mapping["narration_text"]),
            voice_direction=str(mapping.get("voice_direction", "")),
            camera_preset=str(mapping["camera_preset"]),
            scene_key=str(mapping["scene_key"]),
            sfx_cues=[
                SfxCue.from_dict(c) for c in _ensure_sequence(mapping.get("sfx_cues"), "beat.sfx_cues")
            ],
            callout=Callout.from_dict(callout_raw) if callout_raw is not None else None,
            pause_after_s=float(mapping.get("pause_after_s", 0.25)),
        )


@dataclass
class EpisodeScript:
    """Production-ready beat-by-beat script contract (``episodios/<slug>/script.json``)."""

    episode_id: str
    slug: str
    title: str
    hook_text: str
    cta_text: str
    bpm: int
    cover_headline: list[str]
    publish_meta: PublishMeta
    beats: list[Beat]

    @property
    def folder_name(self) -> str:
        """Canonical directory name under ``episodios/`` (matches ``self.slug``)."""
        return self.slug

    @property
    def full_narration_text(self) -> str:
        return " ".join(b.narration_text.strip() for b in self.beats if b.narration_text.strip())

    @property
    def word_count(self) -> int:
        text = self.full_narration_text
        return len(text.split()) if text else 0

    @property
    def total_pause_s(self) -> float:
        return sum(b.pause_after_s for b in self.beats)

    @property
    def estimated_duration_s(self) -> float:
        return self.word_count / 2.65 + self.total_pause_s

    @property
    def distinct_camera_presets(self) -> list[str]:
        seen: list[str] = []
        for beat in self.beats:
            if beat.camera_preset not in seen:
                seen.append(beat.camera_preset)
        return seen

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "slug": self.slug,
            "title": self.title,
            "hook_text": self.hook_text,
            "cta_text": self.cta_text,
            "bpm": self.bpm,
            "cover_headline": list(self.cover_headline),
            "publish_meta": self.publish_meta.to_dict(),
            "beats": [b.to_dict() for b in self.beats],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpisodeScript:
        mapping = _ensure_mapping(data, "EpisodeScript", allow_none=False)
        return cls(
            episode_id=str(mapping["episode_id"]),
            slug=str(mapping["slug"]),
            title=str(mapping["title"]),
            hook_text=str(mapping["hook_text"]),
            cta_text=str(mapping["cta_text"]),
            bpm=int(mapping["bpm"]),
            cover_headline=[
                str(line) for line in _ensure_sequence(mapping.get("cover_headline"), "cover_headline")
            ],
            publish_meta=PublishMeta.from_dict(mapping.get("publish_meta")),
            beats=[Beat.from_dict(b) for b in _ensure_sequence(mapping.get("beats"), "beats")],
        )

    @classmethod
    def load(cls, path: str | Path) -> EpisodeScript:
        return cls.from_dict(_read_json(path))

    def save(self, path: str | Path) -> Path:
        return _write_json(path, self.to_dict())


@dataclass
class AudioBeatTiming(_DictLikeMixin):
    """Measured start/end timing for one synthesized beat WAV."""

    id: str
    start_s: float
    end_s: float
    wav_path: str
    narration_text: str = ""

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "wav_path": self.wav_path,
            "narration_text": self.narration_text,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AudioBeatTiming:
        mapping = _ensure_mapping(data, "AudioBeatTiming", allow_none=False)
        return cls(
            id=str(mapping["id"]),
            start_s=float(mapping["start_s"]),
            end_s=float(mapping["end_s"]),
            wav_path=str(mapping["wav_path"]),
            narration_text=str(mapping.get("narration_text", "")),
        )


@dataclass
class AudioTimeline:
    """Canonical narration and master audio timeline (``narration_timeline.json``)."""

    total_duration_s: float
    sample_rate_hz: int = 48000
    beats: list[AudioBeatTiming] = field(default_factory=list)
    narration_wav_path: str = ""
    master_wav_path: str = ""
    envelope_path: str = ""

    def beat_at(self, t: float) -> tuple[AudioBeatTiming, float]:
        """Return ``(active_beat, beat_progress_0_to_1)`` for timestamp ``t`` seconds."""
        if not self.beats:
            raise ValueError("AudioTimeline contains no beats.")
        if t <= self.beats[0].start_s:
            return (self.beats[0], 0.0)
        for idx, beat in enumerate(self.beats):
            if beat.start_s <= t < beat.end_s:
                span = max(beat.end_s - beat.start_s, 1e-9)
                progress = min(1.0, max(0.0, (t - beat.start_s) / span))
                return (beat, progress)
            if idx + 1 < len(self.beats) and beat.end_s <= t < self.beats[idx + 1].start_s:
                return (beat, 1.0)
        return (self.beats[-1], 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_duration_s": self.total_duration_s,
            "sample_rate_hz": self.sample_rate_hz,
            "beats": [b.to_dict() for b in self.beats],
            "narration_wav_path": self.narration_wav_path,
            "master_wav_path": self.master_wav_path,
            "envelope_path": self.envelope_path,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AudioTimeline:
        mapping = _ensure_mapping(data, "AudioTimeline", allow_none=False)
        return cls(
            total_duration_s=float(mapping["total_duration_s"]),
            sample_rate_hz=int(mapping.get("sample_rate_hz", 48000)),
            beats=[
                AudioBeatTiming.from_dict(b)
                for b in _ensure_sequence(mapping.get("beats"), "timeline.beats")
            ],
            narration_wav_path=str(mapping.get("narration_wav_path", "")),
            master_wav_path=str(mapping.get("master_wav_path", "")),
            envelope_path=str(mapping.get("envelope_path", "")),
        )

    @classmethod
    def load(cls, path: str | Path) -> AudioTimeline:
        return cls.from_dict(_read_json(path))

    def save(self, path: str | Path) -> Path:
        return _write_json(path, self.to_dict())


@dataclass
class CaptionWord(_DictLikeMixin):
    """Single word timing entry inside a Whisper-aligned caption block."""

    text: str
    start_s: float
    end_s: float
    emphasize: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "emphasize": self.emphasize,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CaptionWord:
        mapping = _ensure_mapping(data, "CaptionWord", allow_none=False)
        return cls(
            text=str(mapping["text"]),
            start_s=float(mapping["start_s"]),
            end_s=float(mapping["end_s"]),
            emphasize=bool(mapping.get("emphasize", False)),
        )


@dataclass
class CaptionBlock(_DictLikeMixin):
    """On-screen caption chunk (2–4 words, or isolated trailing punchline)."""

    start_s: float
    end_s: float
    words: list[CaptionWord] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_s": self.start_s,
            "end_s": self.end_s,
            "words": [w.to_dict() for w in self.words],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CaptionBlock:
        mapping = _ensure_mapping(data, "CaptionBlock", allow_none=False)
        return cls(
            start_s=float(mapping["start_s"]),
            end_s=float(mapping["end_s"]),
            words=[
                CaptionWord.from_dict(w)
                for w in _ensure_sequence(mapping.get("words"), "caption_block.words")
            ],
        )


@dataclass
class CaptionTrack:
    """Complete episode word-synced caption track (``captions.json``)."""

    blocks: list[CaptionBlock] = field(default_factory=list)

    def block_at(self, t: float) -> CaptionBlock | None:
        """Return the active ``CaptionBlock`` at timestamp ``t``, or ``None`` if silent."""
        for idx, block in enumerate(self.blocks):
            is_last = idx == len(self.blocks) - 1
            if block.start_s <= t < block.end_s or (is_last and block.start_s <= t <= block.end_s):
                return block
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"blocks": [b.to_dict() for b in self.blocks]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CaptionTrack:
        mapping = _ensure_mapping(data, "CaptionTrack", allow_none=False)
        return cls(
            blocks=[
                CaptionBlock.from_dict(b)
                for b in _ensure_sequence(mapping.get("blocks"), "caption_track.blocks")
            ]
        )

    @classmethod
    def load(cls, path: str | Path) -> CaptionTrack:
        return cls.from_dict(_read_json(path))

    def save(self, path: str | Path) -> Path:
        return _write_json(path, self.to_dict())


# ---------------------------------------------------------------------------
# Strict Contract Validators (return list[str]; empty list == valid)
# ---------------------------------------------------------------------------


def validate_youtube_title(title: str, max_chars: int = 50) -> list[str]:
    """Validate YouTube Shorts title against CTS retention & publishing rules."""
    violations: list[str] = []
    if not isinstance(title, str):
        return ["Title must be a string."]
    if not title or not title.strip():
        return ["Title must not be empty or whitespace-only."]
    if title != title.strip():
        violations.append("Title must not have leading or trailing whitespace.")
    if any(ch in "\t\n\r\v\f" or ord(ch) < 32 for ch in title):
        violations.append("Title must be a single line without tabs or control characters.")
    if len(title) > max_chars:
        violations.append(f"Title length {len(title)} exceeds max {max_chars} chars: {title!r}")
    if "#" in title:
        violations.append("Title must contain zero '#' hashtags.")
    if _PT_DIACRITICS_RE.search(title) or _PT_LEAKAGE_RE.search(title):
        violations.append("Title must be pure en-US (detected Portuguese diacritics/words).")
    if _PLACEHOLDER_RE.search(title):
        violations.append("Title must not contain placeholder tokens (DEFINIR/TODO/TBD).")

    uppercase_words: list[str] = []
    for tok in _TITLE_TOKEN_SPLIT_RE.split(title):
        if not tok:
            continue
        alpha = "".join(ch for ch in tok if ch.isalpha())
        if len(alpha) >= 2 and alpha.isupper():
            uppercase_words.append(tok)
    if len(uppercase_words) != 1:
        violations.append(
            f"Title must contain exactly 1 ALL-CAPS word (found {len(uppercase_words)}: {uppercase_words})."
        )
    return violations


def _check_safe_zone_bounds(
    name: str,
    rect: SafeZoneRect,
    max_w: int,
    max_h: int,
    violations: list[str],
) -> None:
    if not (0 <= rect.x_min < rect.x_max <= max_w):
        violations.append(
            f"safe_zones.{name} X bounds ({rect.x_min}, {rect.x_max}) outside [0, {max_w}]."
        )
    if not (0 <= rect.y_min < rect.y_max <= max_h):
        violations.append(
            f"safe_zones.{name} Y bounds ({rect.y_min}, {rect.y_max}) outside [0, {max_h}]."
        )


def validate_brand(brand: BrandConfig) -> list[str]:
    """Validate all BrandConfig invariants for M1–M6 compliance."""
    violations: list[str] = []

    if not brand.channel_name.strip():
        violations.append("channel_name must not be empty.")
    elif _PLACEHOLDER_RE.search(brand.channel_name):
        violations.append(f"channel_name contains placeholder text: {brand.channel_name!r}")

    if not _HANDLE_RE.match(brand.handle) or brand.handle.lower() == "@definir_handle":
        violations.append(f"Invalid handle: {brand.handle!r}")
    if brand.language != "en-US":
        violations.append(f"language must be 'en-US', got {brand.language!r}")
    if not brand.goal.strip():
        violations.append("goal must not be empty.")
    if not brand.niche.strip() or brand.niche == "what_if_survival_and_mysteries":
        violations.append(f"niche must be updated for engineering/disasters, got {brand.niche!r}")
    if not brand.tagline.strip() or len(brand.tagline) > 50:
        violations.append(f"tagline must be 1..50 chars, got {len(brand.tagline)}")
    if not brand.anti_clone_note.strip():
        violations.append("anti_clone_note must not be empty.")

    # Video spec
    vs = brand.video_spec
    if vs.resolution != "1080x1920":
        violations.append(f"video_spec.resolution must be '1080x1920', got {vs.resolution!r}")
    if vs.fps != 30:
        violations.append(f"video_spec.fps must be 30, got {vs.fps}")
    if vs.target_duration_sec != (65, 80):
        violations.append(
            f"video_spec.target_duration_sec must be (65, 80), got {vs.target_duration_sec}"
        )
    if vs.tiktok_1min_monetization_min_sec < 62:
        violations.append(
            f"video_spec.tiktok_1min_monetization_min_sec must be >= 62, got {vs.tiktok_1min_monetization_min_sec}"
        )
    if not (_is_finite(vs.audio_lufs) and -15.5 <= vs.audio_lufs <= -13.5):
        violations.append(f"video_spec.audio_lufs out of range [-15.5, -13.5]: {vs.audio_lufs}")
    if not (_is_finite(vs.audio_true_peak_max) and vs.audio_true_peak_max <= -1.0):
        violations.append(
            f"video_spec.audio_true_peak_max must be finite and <= -1.0, got {vs.audio_true_peak_max}"
        )
    if not (_is_finite(vs.audio_lra_max) and 0.0 < vs.audio_lra_max <= 4.0):
        violations.append(
            f"video_spec.audio_lra_max must be in (0, 4.0], got {vs.audio_lra_max}"
        )
    if vs.audio_codec != "aac":
        violations.append(f"video_spec.audio_codec must be 'aac', got {vs.audio_codec!r}")
    if vs.audio_sample_rate != 48000:
        violations.append(
            f"video_spec.audio_sample_rate must be 48000, got {vs.audio_sample_rate}"
        )
    if vs.audio_bitrate_kbps < 128:
        violations.append(
            f"video_spec.audio_bitrate_kbps must be >= 128, got {vs.audio_bitrate_kbps}"
        )
    if vs.audio_channels != 2:
        violations.append(f"video_spec.audio_channels must be 2, got {vs.audio_channels}")
    if vs.video_codec != "libx264":
        violations.append(f"video_spec.video_codec must be 'libx264', got {vs.video_codec!r}")
    if not (16 <= vs.video_crf <= 23):
        violations.append(f"video_spec.video_crf must be in [16, 23], got {vs.video_crf}")
    if vs.pixel_format != "yuv420p":
        violations.append(f"video_spec.pixel_format must be 'yuv420p', got {vs.pixel_format!r}")

    # Visual style
    style = brand.visual_style
    if not style.type.strip():
        violations.append("visual_style.type must not be empty.")
    if not style.style_decision_rationale.strip():
        violations.append("visual_style.style_decision_rationale must not be empty.")
    for req_key in REQUIRED_PALETTE_KEYS:
        if req_key not in style.palette:
            violations.append(f"visual_style.palette missing required key {req_key!r}.")
    for token, hex_val in style.palette.items():
        if not _HEX_COLOR_RE.match(hex_val):
            violations.append(f"visual_style.palette[{token!r}] invalid hex color: {hex_val!r}")
    for fname, fval in (
        ("fonts_dir", style.fonts_dir),
        ("primary_font", style.primary_font),
        ("secondary_font", style.secondary_font),
        ("fallback_font", style.fallback_font),
    ):
        if not fval.strip():
            violations.append(f"visual_style.{fname} must not be empty.")
        if "\\" in fval or ":" in fval:
            violations.append(f"visual_style.{fname} must be a POSIX path (no Windows paths): {fval!r}")

    sz = style.safe_zones
    _check_safe_zone_bounds("top_hook", sz.top_hook, 1080, 1920, violations)
    _check_safe_zone_bounds("captions", sz.captions, 1080, 1920, violations)
    _check_safe_zone_bounds("callout_hud", sz.callout_hud, 1080, 1920, violations)
    _check_safe_zone_bounds("cover_reels_grid", sz.cover_reels_grid, 1080, 1920, violations)
    _check_safe_zone_bounds("cover_3x4", sz.cover_3x4, 1080, 1920, violations)
    _check_safe_zone_bounds(
        "youtube_banner_desktop",
        sz.youtube_banner_desktop,
        sz.youtube_banner_width,
        sz.youtube_banner_height,
        violations,
    )
    _check_safe_zone_bounds(
        "youtube_banner_mobile",
        sz.youtube_banner_mobile,
        sz.youtube_banner_width,
        sz.youtube_banner_height,
        violations,
    )
    if sz.captions.max_width_px is None or not (0 < sz.captions.max_width_px <= 820):
        violations.append(
            f"safe_zones.captions.max_width_px must be in (0, 820], got {sz.captions.max_width_px}"
        )
    if sz.captions.width > 820:
        violations.append(f"safe_zones.captions width {sz.captions.width} exceeds 820px.")
    if sz.captions.x_max > 930:
        violations.append(
            f"safe_zones.captions.x_max ({sz.captions.x_max}) exceeds 930px T7 right-rail clearance."
        )
    if not (
        sz.cover_3x4.y_min <= sz.cover_reels_grid.y_min
        and sz.cover_reels_grid.y_max <= sz.cover_3x4.y_max
    ):
        violations.append("safe_zones.cover_reels_grid must sit inside cover_3x4 vertical bounds.")
    if not (
        sz.youtube_banner_desktop.x_min <= sz.youtube_banner_mobile.x_min
        and sz.youtube_banner_mobile.x_max <= sz.youtube_banner_desktop.x_max
        and sz.youtube_banner_desktop.y_min <= sz.youtube_banner_mobile.y_min
        and sz.youtube_banner_mobile.y_max <= sz.youtube_banner_desktop.y_max
    ):
        violations.append("safe_zones.youtube_banner_mobile must sit inside youtube_banner_desktop.")
    if sz.youtube_banner_width != 2560 or sz.youtube_banner_height != 1440:
        violations.append("YouTube banner dimensions must be 2560x1440.")
    if not (0 < sz.youtube_banner_max_bytes <= 6291456):
        violations.append(
            f"youtube_banner_max_bytes must be in (0, 6291456] (6 MB), got {sz.youtube_banner_max_bytes}"
        )

    # Narration
    nar = brand.narration
    if nar.provider != "google-genai":
        violations.append(f"narration.provider must be 'google-genai', got {nar.provider!r}")
    if nar.api_version != "v1beta":
        violations.append(
            f"narration.api_version must be 'v1beta' (v1 breaks TTS speechConfig), got {nar.api_version!r}"
        )
    if not nar.models or nar.models[0] != "gemini-3.8-flash-tts":
        violations.append("narration.models[0] must be 'gemini-3.8-flash-tts'.")
    if len(nar.models) < 2:
        violations.append("narration.models must include fallback TTS models (>= 2 entries).")
    seen_models: set[str] = set()
    for m_idx, model_name in enumerate(nar.models):
        if not isinstance(model_name, str) or not model_name.strip():
            violations.append(f"narration.models[{m_idx}] must not be empty.")
        elif model_name != model_name.strip() or any(ch.isspace() for ch in model_name):
            violations.append(
                f"narration.models[{m_idx}] must not contain whitespace: {model_name!r}"
            )
        elif model_name in seen_models:
            violations.append(f"narration.models contains duplicate entry: {model_name!r}")
        else:
            seen_models.add(model_name)
    if nar.voice not in VALID_GEMINI_VOICES:
        violations.append(f"narration.voice {nar.voice!r} is not a recognized Gemini TTS voice.")
    if not nar.pov.strip():
        violations.append("narration.pov must not be empty.")
    if not nar.style_direction.strip():
        violations.append("narration.style_direction must not be empty.")
    elif _WHISPER_POSITIVE_RE.search(nar.style_direction):
        violations.append(
            f"narration.style_direction requests whispering ({nar.style_direction!r}); "
            "use controlled half-voice instead to avoid sibilant hiss."
        )
    if not (
        _is_finite(nar.rate_range[0])
        and _is_finite(nar.rate_range[1])
        and 1.0 <= nar.rate_range[0] <= nar.rate_range[1] <= 1.15
    ):
        violations.append(f"narration.rate_range out of bounds [1.0, 1.15]: {nar.rate_range}")
    if not (_is_finite(nar.silence_trim_db) and -58.0 <= nar.silence_trim_db <= -48.0):
        violations.append(
            f"narration.silence_trim_db must be in [-58.0, -48.0], got {nar.silence_trim_db}"
        )
    if nar.silence_head_pad_ms < 30:
        violations.append(
            f"narration.silence_head_pad_ms must be >= 30, got {nar.silence_head_pad_ms}"
        )
    if nar.silence_tail_pad_ms < 50:
        violations.append(
            f"narration.silence_tail_pad_ms must be >= 50, got {nar.silence_tail_pad_ms}"
        )
    if nar.avoid_whisper_hiss is not True:
        violations.append("narration.avoid_whisper_hiss must be True.")
    if nar.continuous_ambient_bed is not True:
        violations.append("narration.continuous_ambient_bed must be True.")

    # Retention rules
    ret = brand.retention_rules
    if not ret.frame_0_hook.strip():
        violations.append("retention_rules.frame_0_hook must not be empty.")
    if ret.no_mid_video_subscribe_cta is not True:
        violations.append("retention_rules.no_mid_video_subscribe_cta must be True.")
    if not ret.ending_cta.strip():
        violations.append("retention_rules.ending_cta must not be empty.")
    if ret.caption_chunk_words != (2, 4):
        violations.append(
            f"retention_rules.caption_chunk_words must be (2, 4), got {ret.caption_chunk_words}"
        )
    if ret.caption_style != "clean_outlined_no_box":
        violations.append(
            f"retention_rules.caption_style must be 'clean_outlined_no_box', got {ret.caption_style!r}"
        )
    if not (3 <= ret.min_camera_angles <= 5):
        violations.append(
            f"retention_rules.min_camera_angles must be in [3, 5], got {ret.min_camera_angles}"
        )

    # Publishing
    pub = brand.publishing
    if pub.youtube_title_max_chars != 50:
        violations.append(
            f"publishing.youtube_title_max_chars must be 50, got {pub.youtube_title_max_chars}"
        )
    if pub.youtube_title_hashtags is not False:
        violations.append("publishing.youtube_title_hashtags must be False.")
    if pub.youtube_title_one_uppercase_word is not True:
        violations.append("publishing.youtube_title_one_uppercase_word must be True.")
    if not _SCHEDULE_HOUR_RE.match(pub.youtube_schedule_fixed_hour):
        violations.append(
            f"publishing.youtube_schedule_fixed_hour invalid HH:MM: {pub.youtube_schedule_fixed_hour!r}"
        )
    if pub.youtube_link_related_video is not True:
        violations.append("publishing.youtube_link_related_video must be True.")
    if pub.youtube_ai_disclosure_stylized_2d is not False:
        violations.append("publishing.youtube_ai_disclosure_stylized_2d must be False (T3).")
    if pub.never_delete_stalled_shorts is not True:
        violations.append("publishing.never_delete_stalled_shorts must be True.")
    if pub.review_metrics_after_hours != 48:
        violations.append(
            f"publishing.review_metrics_after_hours must be 48, got {pub.review_metrics_after_hours}"
        )
    if not (
        _is_finite(pub.stayed_to_watch_target_pct)
        and 75.0 <= pub.stayed_to_watch_target_pct <= 100.0
    ):
        violations.append(
            f"publishing.stayed_to_watch_target_pct must be in [75.0, 100.0], got {pub.stayed_to_watch_target_pct}"
        )

    # Pure en-US and anti-clone check across all brand text fields
    for label, text in (
        ("channel_name", brand.channel_name),
        ("tagline", brand.tagline),
        ("anti_clone_note", brand.anti_clone_note),
        ("visual_style.style_decision_rationale", brand.visual_style.style_decision_rationale),
        ("narration.style_direction", brand.narration.style_direction),
        ("retention_rules.frame_0_hook", brand.retention_rules.frame_0_hook),
        ("retention_rules.ending_cta", brand.retention_rules.ending_cta),
    ):
        if _ROTA_CRITICA_RE.search(text):
            violations.append(f"{label} must not clone or reference Rota Critica.")
        if _PT_DIACRITICS_RE.search(text) or _PT_LEAKAGE_RE.search(text):
            violations.append(f"{label} must be pure en-US (detected Portuguese text).")

    return violations


def validate_script(script: EpisodeScript, brand: BrandConfig | None = None) -> list[str]:
    """Validate an EpisodeScript against retention, duration, camera, and en-US rules."""
    violations: list[str] = []

    if not _EPISODE_ID_RE.match(script.episode_id):
        violations.append(f"episode_id must match ^ep\\d{{2}}$, got {script.episode_id!r}")

    if not _SLUG_RE.match(script.slug):
        violations.append(f"slug must be lowercase snake_case, got {script.slug!r}")
    else:
        expected_prefix = f"{script.episode_id}_"
        if not script.slug.startswith(expected_prefix):
            violations.append(
                f"slug {script.slug!r} must start with episode_id prefix {expected_prefix!r}."
            )
        elif script.slug.startswith(f"{expected_prefix}{expected_prefix}"):
            violations.append(f"slug {script.slug!r} must not double-prefix {expected_prefix!r}.")
        elif len(script.slug) <= len(expected_prefix):
            violations.append(f"slug {script.slug!r} must have a topic suffix after {expected_prefix!r}.")

    max_title = brand.publishing.youtube_title_max_chars if brand else 50
    for err in validate_youtube_title(script.title, max_chars=max_title):
        violations.append(f"title: {err}")

    # Publish meta
    pm = script.publish_meta
    if pm.youtube_title != script.title:
        violations.append("publish_meta.youtube_title must exactly match script.title.")
    if pm.ai_disclosure is not False:
        violations.append("publish_meta.ai_disclosure must be False for stylized 2.5D vector.")
    if len(pm.youtube_description) > 200:
        violations.append(
            f"publish_meta.youtube_description too long ({len(pm.youtube_description)} > 200)."
        )
    if "#" in pm.youtube_description:
        violations.append("publish_meta.youtube_description must not contain '#' hashtags.")
    if not pm.ig_tiktok_caption.strip():
        violations.append("publish_meta.ig_tiktok_caption must not be empty.")
    if len(pm.hashtags) < 3:
        violations.append(f"publish_meta.hashtags needs >= 3 tags, got {len(pm.hashtags)}.")
    for tag in pm.hashtags:
        if not _HASHTAG_RE.match(tag):
            violations.append(f"Invalid hashtag {tag!r} (must match ^#[A-Za-z0-9_]+$).")
    if not pm.pinned_comment.strip():
        violations.append("publish_meta.pinned_comment must not be empty.")
    if not pm.related_video_slot.strip():
        violations.append("publish_meta.related_video_slot must not be empty.")
    if not _SCHEDULE_HOUR_RE.match(pm.schedule_hour):
        violations.append(f"publish_meta.schedule_hour invalid HH:MM: {pm.schedule_hour!r}")
    elif brand is not None and pm.schedule_hour != brand.publishing.youtube_schedule_fixed_hour:
        violations.append(
            f"publish_meta.schedule_hour {pm.schedule_hour!r} does not match brand schedule "
            f"{brand.publishing.youtube_schedule_fixed_hour!r}."
        )

    # Hook, CTA, cover headline, BPM
    hook_words = script.hook_text.split()
    if not script.hook_text.strip() or not (2 <= len(hook_words) <= 7) or len(script.hook_text) > 45:
        violations.append(
            f"hook_text must be 2..7 words and <= 45 chars, got {script.hook_text!r}"
        )

    cta_words = script.cta_text.split()
    if not script.cta_text.strip() or len(cta_words) > 10:
        violations.append(f"cta_text must be concise (1..10 words), got {script.cta_text!r}")
    if not _CTA_ACTION_RE.search(script.cta_text):
        violations.append("cta_text must prompt a comment action (comment/type/drop).")

    def _is_cta_reply_token(tok: str) -> bool:
        if any(ch.isdigit() for ch in tok):
            return True
        alpha = "".join(c for c in tok if c.isalpha())
        return len(alpha) >= 2 and alpha.isupper() and alpha not in _CTA_ACTION_VERBS

    has_cta_token = any(_is_cta_reply_token(tok) for tok in cta_words)
    if not has_cta_token:
        violations.append(
            "cta_text must include a clear 1-word UPPERCASE or numeric response token (e.g., YES/NO or 1/2)."
        )

    if not (2 <= len(script.cover_headline) <= 3):
        violations.append(f"cover_headline must have 2..3 lines, got {len(script.cover_headline)}.")
    for idx, line in enumerate(script.cover_headline):
        if not line.strip() or len(line) > 24:
            violations.append(
                f"cover_headline[{idx}] must be 1..24 chars, got {line!r} ({len(line)})."
            )

    if not (60 <= script.bpm <= 180):
        violations.append(f"bpm must be in [60, 180], got {script.bpm}.")

    # Beats structural checks
    beats = script.beats
    if not (10 <= len(beats) <= 14):
        violations.append(f"Script must have 10..14 beats, got {len(beats)}.")

    if not beats:
        return violations

    seen_ids: set[str] = set()
    acts_seen: set[str] = set()
    presets_seen: set[str] = set()
    prev_act_order = -1
    total_sfx = 0
    total_callouts = 0

    for idx, beat in enumerate(beats):
        prefix = f"beats[{idx}] ({beat.id!r})"
        norm_id = beat.id.strip()
        if not norm_id:
            violations.append(f"beats[{idx}] has empty id.")
        else:
            if beat.id != norm_id or any(ch.isspace() for ch in beat.id):
                violations.append(
                    f"beats[{idx}] id must not contain whitespace: {beat.id!r}"
                )
            if norm_id in seen_ids:
                violations.append(f"Duplicate beat id: {beat.id!r}")
            seen_ids.add(norm_id)

        if beat.act not in ACT_ORDER:
            violations.append(f"{prefix}: invalid act {beat.act!r} (valid: {VALID_ACTS}).")
        else:
            acts_seen.add(beat.act)
            curr_order = ACT_ORDER[beat.act]
            if curr_order < prev_act_order:
                violations.append(
                    f"{prefix}: non-monotonic act progression ({beat.act!r} after higher act)."
                )
            prev_act_order = curr_order
            if beat.act == "cta" and idx != len(beats) - 1:
                violations.append(f"{prefix}: 'cta' act is only allowed on the final beat.")

        if not beat.narration_text.strip():
            violations.append(f"{prefix}: narration_text must not be empty.")
        if _SUBSCRIBE_PROMPT_RE.search(beat.narration_text):
            violations.append(f"{prefix}: forbidden subscribe/like prompt in narration_text.")

        if not beat.voice_direction.strip():
            violations.append(f"{prefix}: voice_direction must not be empty.")
        elif _WHISPER_POSITIVE_RE.search(beat.voice_direction):
            violations.append(
                f"{prefix}: voice_direction requests whispering ({beat.voice_direction!r}); "
                "use controlled half-voice instead to avoid sibilant hiss."
            )

        if beat.camera_preset not in VALID_CAMERA_PRESETS:
            violations.append(
                f"{prefix}: camera_preset {beat.camera_preset!r} not in {VALID_CAMERA_PRESETS}."
            )
        else:
            presets_seen.add(beat.camera_preset)

        if not beat.scene_key.strip():
            violations.append(f"{prefix}: scene_key must not be empty.")

        if not (_is_finite(beat.pause_after_s) and 0.0 <= beat.pause_after_s <= 1.5):
            violations.append(
                f"{prefix}: pause_after_s {beat.pause_after_s} out of range [0.0, 1.5]."
            )

        for cue_idx, cue in enumerate(beat.sfx_cues):
            total_sfx += 1
            if not cue.name.strip():
                violations.append(f"{prefix}.sfx_cues[{cue_idx}]: empty SFX name.")
            if not (_is_finite(cue.offset_s) and cue.offset_s >= 0.0):
                violations.append(
                    f"{prefix}.sfx_cues[{cue_idx}]: negative or non-finite offset_s {cue.offset_s}."
                )
            if not (_is_finite(cue.gain_db) and -36.0 <= cue.gain_db <= 6.0):
                violations.append(
                    f"{prefix}.sfx_cues[{cue_idx}]: gain_db {cue.gain_db} outside [-36, 6]."
                )
            if not (_is_finite(cue.pan) and -1.0 <= cue.pan <= 1.0):
                violations.append(f"{prefix}.sfx_cues[{cue_idx}]: pan {cue.pan} outside [-1, 1].")

        if beat.callout is not None:
            total_callouts += 1
            if not (1 <= len(beat.callout.label.strip()) <= 28):
                violations.append(
                    f"{prefix}.callout.label must be 1..28 chars, got {beat.callout.label!r}"
                )
            if not (1 <= len(beat.callout.value.strip()) <= 24):
                violations.append(
                    f"{prefix}.callout.value must be 1..24 chars, got {beat.callout.value!r}"
                )

    # First & last beat invariants
    if beats[0].act != "hook":
        violations.append(f"beats[0].act must be 'hook', got {beats[0].act!r}.")
    if beats[0].camera_preset != "FRAME0_HERO":
        violations.append(
            f"beats[0].camera_preset must be 'FRAME0_HERO', got {beats[0].camera_preset!r}."
        )
    if beats[0].callout is not None:
        violations.append("beats[0].callout must be None to keep Frame 0 hero uncluttered.")
    if _SLOW_HOOK_FILLER_RE.search(beats[0].narration_text):
        violations.append(
            f"beats[0].narration_text must start with an immediate hook (no slow filler): "
            f"{beats[0].narration_text!r}"
        )

    if beats[-1].act != "cta":
        violations.append(f"beats[-1].act must be 'cta', got {beats[-1].act!r}.")
    if not _CTA_ACTION_RE.search(beats[-1].narration_text):
        violations.append("beats[-1].narration_text must include the ending comment CTA.")

    missing_acts = [act for act in VALID_ACTS if act not in acts_seen]
    if missing_acts:
        violations.append(f"Script missing required acts: {missing_acts}")

    min_cams = brand.retention_rules.min_camera_angles if brand is not None else 4
    if not (min_cams <= len(presets_seen) <= 5):
        violations.append(
            f"Script must use {min_cams}..5 distinct camera_preset values, got {len(presets_seen)} ({sorted(presets_seen)})."
        )

    if total_sfx < 1:
        violations.append("Script must include at least 1 declarative SFX cue.")
    if total_callouts < 2:
        violations.append(f"Script must include at least 2 technical callouts, got {total_callouts}.")

    # Word count & estimated duration
    words = script.word_count
    if not (155 <= words <= 215):
        violations.append(f"Total spoken word count {words} outside valid range [155, 215].")
    est_dur = script.estimated_duration_s
    if not (_is_finite(est_dur) and 62.0 <= est_dur <= 82.0):
        violations.append(
            f"Estimated duration {est_dur:.1f}s outside valid range [62.0, 82.0]s "
            f"(words={words}, pauses={script.total_pause_s:.2f}s)."
        )

    # Pure en-US check across all script text fields
    en_us_fields: list[tuple[str, str]] = [
        ("title", script.title),
        ("hook_text", script.hook_text),
        ("cta_text", script.cta_text),
        ("publish_meta.youtube_description", pm.youtube_description),
        ("publish_meta.ig_tiktok_caption", pm.ig_tiktok_caption),
        ("publish_meta.pinned_comment", pm.pinned_comment),
    ]
    en_us_fields.extend((f"cover_headline[{i}]", line) for i, line in enumerate(script.cover_headline))
    en_us_fields.extend((f"beats[{i}].narration_text", b.narration_text) for i, b in enumerate(beats))
    en_us_fields.extend((f"beats[{i}].voice_direction", b.voice_direction) for i, b in enumerate(beats))
    for i, b in enumerate(beats):
        if b.callout is not None:
            en_us_fields.append((f"beats[{i}].callout.label", b.callout.label))
            en_us_fields.append((f"beats[{i}].callout.value", b.callout.value))
    for field_name, text in en_us_fields:
        if _PT_DIACRITICS_RE.search(text) or _PT_LEAKAGE_RE.search(text) or _ROTA_CRITICA_RE.search(text):
            violations.append(f"{field_name} contains non-en-US / Portuguese text: {text!r}")

    return violations


def validate_timeline(timeline: AudioTimeline) -> list[str]:
    """Validate AudioTimeline chronological ordering, bounds, and sample rate."""
    violations: list[str] = []
    total_dur_finite = _is_finite(timeline.total_duration_s)
    if not (total_dur_finite and timeline.total_duration_s > 0.0):
        violations.append(f"total_duration_s must be finite and > 0, got {timeline.total_duration_s}")
    if timeline.sample_rate_hz != 48000:
        violations.append(f"sample_rate_hz must be 48000, got {timeline.sample_rate_hz}")
    if not timeline.beats:
        violations.append("AudioTimeline must contain at least one beat.")
        return violations

    prev_end: float | None = None
    seen_ids: set[str] = set()
    for idx, beat in enumerate(timeline.beats):
        prefix = f"beats[{idx}] ({beat.id!r})"
        norm_id = beat.id.strip()
        if not norm_id:
            violations.append(f"beats[{idx}] has empty id.")
        else:
            if beat.id != norm_id or any(ch.isspace() for ch in beat.id):
                violations.append(f"beats[{idx}] id must not contain whitespace: {beat.id!r}")
            if norm_id in seen_ids:
                violations.append(f"Duplicate beat id in timeline: {beat.id!r}")
            seen_ids.add(norm_id)

        start_ok = _is_finite(beat.start_s)
        end_ok = _is_finite(beat.end_s)
        if not start_ok:
            violations.append(f"{prefix}: start_s must be finite, got {beat.start_s}.")
        if not end_ok:
            violations.append(f"{prefix}: end_s must be finite, got {beat.end_s}.")
        if start_ok and beat.start_s < 0.0:
            violations.append(f"{prefix}: start_s {beat.start_s} < 0.")
        if start_ok and end_ok and beat.start_s >= beat.end_s:
            violations.append(f"{prefix}: start_s ({beat.start_s}) must be < end_s ({beat.end_s}).")
        if end_ok and total_dur_finite and beat.end_s > timeline.total_duration_s + 1e-3:
            violations.append(
                f"{prefix}: end_s ({beat.end_s}) exceeds total_duration_s ({timeline.total_duration_s})."
            )
        if start_ok and prev_end is not None and beat.start_s + 1e-3 < prev_end:
            violations.append(
                f"{prefix}: overlaps previous beat (start_s={beat.start_s} < prev_end={prev_end})."
            )
        if end_ok:
            prev_end = beat.end_s

    return violations


def validate_captions(track: CaptionTrack) -> list[str]:
    """Validate CaptionTrack timing, ordering, and 2–4 word block sizing rules."""
    violations: list[str] = []
    if not track.blocks:
        violations.append("CaptionTrack must contain at least one block.")
        return violations

    prev_block_end: float | None = None
    for idx, block in enumerate(track.blocks):
        prefix = f"blocks[{idx}]"
        b_start_ok = _is_finite(block.start_s)
        b_end_ok = _is_finite(block.end_s)
        if not b_start_ok:
            violations.append(f"{prefix}: start_s must be finite, got {block.start_s}.")
        if not b_end_ok:
            violations.append(f"{prefix}: end_s must be finite, got {block.end_s}.")
        if b_start_ok and block.start_s < 0.0:
            violations.append(f"{prefix}: start_s {block.start_s} < 0.")
        if b_start_ok and b_end_ok and block.start_s >= block.end_s:
            violations.append(
                f"{prefix}: start_s ({block.start_s}) must be < end_s ({block.end_s})."
            )
        if b_start_ok and prev_block_end is not None and block.start_s + 1e-3 < prev_block_end:
            violations.append(
                f"{prefix}: overlaps previous block (start_s={block.start_s} < prev_end={prev_block_end})."
            )
        if b_end_ok:
            prev_block_end = block.end_s

        n_words = len(block.words)
        if n_words == 0:
            violations.append(f"{prefix}: block has 0 words.")
            continue
        if n_words > 4:
            violations.append(f"{prefix}: block has {n_words} words (max 4).")
        elif n_words == 1:
            is_last = idx == len(track.blocks) - 1
            next_start = track.blocks[idx + 1].start_s if idx + 1 < len(track.blocks) else None
            is_isolated = is_last or (
                next_start is not None
                and b_end_ok
                and _is_finite(next_start)
                and next_start - block.end_s >= 0.15
            )
            if not is_isolated:
                violations.append(
                    f"{prefix}: 1-word block allowed only for trailing/isolated punchline."
                )

        rendered_words = block.text.split()
        if len(rendered_words) > 4:
            violations.append(
                f"{prefix}: rendered block text has {len(rendered_words)} words (max 4): {block.text!r}"
            )

        prev_word_end: float | None = block.start_s if b_start_ok else None
        for w_idx, word in enumerate(block.words):
            if not word.text.strip():
                violations.append(f"{prefix}.words[{w_idx}]: empty word text.")
            elif word.text != word.text.strip() or len(word.text.split()) != 1:
                violations.append(
                    f"{prefix}.words[{w_idx}]: word text must be a single whitespace-free token, got {word.text!r}."
                )
            w_start_ok = _is_finite(word.start_s)
            w_end_ok = _is_finite(word.end_s)
            if not w_start_ok:
                violations.append(
                    f"{prefix}.words[{w_idx}]: start_s must be finite, got {word.start_s}."
                )
            if not w_end_ok:
                violations.append(
                    f"{prefix}.words[{w_idx}]: end_s must be finite, got {word.end_s}."
                )
            if w_start_ok and w_end_ok and word.start_s >= word.end_s:
                violations.append(
                    f"{prefix}.words[{w_idx}]: start_s ({word.start_s}) must be < end_s ({word.end_s})."
                )
            if w_start_ok and prev_word_end is not None and word.start_s + 1e-3 < prev_word_end:
                violations.append(
                    f"{prefix}.words[{w_idx}]: word overlaps previous word or starts before block."
                )
            if w_end_ok and b_end_ok and word.end_s > block.end_s + 1e-3:
                violations.append(
                    f"{prefix}.words[{w_idx}]: word end_s ({word.end_s}) exceeds block end_s ({block.end_s})."
                )
            if w_end_ok:
                prev_word_end = word.end_s

    return violations


__all__ = [
    "ACT_ORDER",
    "DEFAULT_TTS_MODELS",
    "REQUIRED_PALETTE_KEYS",
    "VALID_ACTS",
    "VALID_CAMERA_PRESETS",
    "VALID_GEMINI_VOICES",
    "AudioBeatTiming",
    "AudioTimeline",
    "Beat",
    "BrandConfig",
    "Callout",
    "CaptionBlock",
    "CaptionTrack",
    "CaptionWord",
    "EpisodeScript",
    "NarrationConfig",
    "PublishMeta",
    "PublishingConfig",
    "RetentionRules",
    "SafeZoneRect",
    "SafeZones",
    "SfxCue",
    "ValidationError",
    "VideoSpec",
    "VisualStyle",
    "validate_brand",
    "validate_captions",
    "validate_script",
    "validate_timeline",
    "validate_youtube_title",
]
