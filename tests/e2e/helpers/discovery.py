"""Dynamic opaque-box discovery for CTS Shorts Factory deliverables.

Supports ``CTS_E2E_PROJECT_ROOT`` override for dual-target validation against
either the real repository or a temporary synthetic workspace. Never imports
from ``src/`` or ``cts_factory``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT_ENV = "CTS_E2E_PROJECT_ROOT"
REAL_REPO_ROOT = Path(__file__).resolve().parents[3]
YOUTUBE_REF_IDS: tuple[str, str] = ("DYYsGuTpBKc", "M_t2ZUz7_pc")

# Matches both standalone SKILL.md format:
#   - 2026-11-23 | summary text | reels/20261123-...
# and jobs.py done format:
#   - 2026-11-23 | #1 | summary text | #tag1 #tag2 | 20261123-...
INDEX_LINE_RE = re.compile(
    r"^-\s+(?P<date>\d{4}-\d{2}-\d{2})\s*\|\s*"
    r"(?:#\d+\s*\|\s*)?"
    r"(?P<summary>.+?)\s*\|\s*"
    r"(?:#\S+(?:\s+#\S+)*\s*\|\s*)?"
    r"(?P<dir>\S+)\s*$"
)

_EPISODE_DIR_RE = re.compile(r"^ep0?[1-9][_-][a-z0-9][a-z0-9_-]*$", re.IGNORECASE)
_EPISODE_ID_PREFIX_RE = re.compile(r"^(ep0?\d+)[_-]", re.IGNORECASE)
_YOUTUBE_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|shorts/|live/|embed/)([A-Za-z0-9_-]{11})(?:[&?/#\s\"']|$)"
)
_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_DRAFT_MP4_TOKENS = ("draft", "preview", "tmp", "temp")


@dataclass(frozen=True)
class EpisodePaths:
    """Resolved deliverable paths for a single episode bundle."""

    episode_id: str
    slug: str
    dir: Path
    script_json: Path
    narration_clean_wav: Path
    narration_timeline_json: Path
    narration_envelope_npy: Path
    audio_master_wav: Path
    captions_json: Path
    mp4: Path
    cover_png: Path
    cover_grid_preview_png: Path
    publish_meta_json: Path
    qa_report_json: Path
    tts_cache_dir: Path


@dataclass(frozen=True)
class ThemesBacklog:
    """Normalized representation of ``episodios/themes_backlog.json``."""

    raw: Any
    themes: list[dict[str, Any]]
    selected_themes: list[dict[str, Any]]
    selected_slugs: list[str]
    selection_rationale: str


@dataclass(frozen=True)
class ReelRun:
    """Discovered ``/reel-watch`` output run directory under ``reels/``."""

    dir: Path
    manifest_path: Path
    manifest: dict[str, Any]
    sources: tuple[str, ...]
    kind: str
    engine: str
    fetched_via: str
    frames_dir: Path
    frame_paths: tuple[Path, ...]
    analysis_path: Path | None
    breakdown_path: Path | None
    youtube_id: str | None


@dataclass(frozen=True)
class IndexEntry:
    """Parsed line entry from ``reels/INDEX.md``."""

    date: str
    summary: str
    raw_dir: str
    resolved_dir: Path | None
    raw_line: str


def get_real_repo_root() -> Path:
    """Return the canonical repository root regardless of env overrides."""
    return REAL_REPO_ROOT


def get_project_root(root: Path | None = None) -> Path:
    """Resolve the active project root, honoring ``CTS_E2E_PROJECT_ROOT``."""
    if root is not None:
        return Path(root).resolve()
    env_override = os.environ.get(PROJECT_ROOT_ENV, "").strip()
    if env_override:
        return Path(env_override).resolve()
    return REAL_REPO_ROOT


def load_json(path: Path) -> Any:
    """Load and decode a UTF-8 JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_slug(slug: str) -> str:
    """Normalize an episode/theme slug by lowercasing and stripping ``ep0X_``."""
    cleaned = slug.strip().lower().replace("-", "_")
    return re.sub(r"^ep0?\d+_", "", cleaned)


# ---------------------------------------------------------------------------
# Brand manifest loading & schema alias normalizers
# ---------------------------------------------------------------------------


def get_brand_path(root: Path | None = None) -> Path:
    """Return path to ``brand.json``."""
    return get_project_root(root) / "brand.json"


def get_brand_template_path(root: Path | None = None) -> Path:
    """Return path to ``brand_template.json``."""
    return get_project_root(root) / "brand_template.json"


def load_brand(root: Path | None = None) -> dict[str, Any]:
    """Load ``brand.json`` as a dictionary."""
    data = load_json(get_brand_path(root))
    if not isinstance(data, dict):
        raise ValueError(f"brand.json must be a JSON object, got {type(data).__name__}")
    return data


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_brand_video_lufs(brand: dict[str, Any]) -> float | None:
    """Read target LUFS honoring ``loudness_target_lufs`` and ``audio_lufs``."""
    vs = brand.get("video_spec") or {}
    if not isinstance(vs, dict):
        return None
    raw = vs.get("loudness_target_lufs")
    if raw is None:
        raw = vs.get("audio_lufs")
    return _as_float(raw)


def get_brand_video_lra_max(brand: dict[str, Any]) -> float | None:
    """Read max LRA honoring ``max_lra_lu`` and ``audio_lra_max``."""
    vs = brand.get("video_spec") or {}
    if not isinstance(vs, dict):
        return None
    raw = vs.get("max_lra_lu")
    if raw is None:
        raw = vs.get("audio_lra_max")
    return _as_float(raw)


def get_brand_video_true_peak_max(brand: dict[str, Any]) -> float | None:
    """Read max True Peak honoring ``audio_true_peak_max`` and ``true_peak_max_dbtp``."""
    vs = brand.get("video_spec") or {}
    if not isinstance(vs, dict):
        return None
    for key in ("audio_true_peak_max", "true_peak_max_dbtp", "max_true_peak_dbtp"):
        if key in vs and vs[key] is not None:
            return _as_float(vs[key])
    return None


def get_brand_audio_sample_rate(brand: dict[str, Any]) -> int | None:
    """Read audio sample rate honoring ``audio_sample_rate_hz`` and ``audio_sample_rate``."""
    vs = brand.get("video_spec") or {}
    if not isinstance(vs, dict):
        return None
    raw = vs.get("audio_sample_rate_hz")
    if raw is None:
        raw = vs.get("audio_sample_rate")
    return _as_int(raw)


def get_brand_resolution(brand: dict[str, Any]) -> tuple[int, int] | None:
    """Parse ``video_spec.resolution`` from ``'1080x1920'``, dict, or sequence."""
    vs = brand.get("video_spec") or {}
    if not isinstance(vs, dict):
        return None
    res = vs.get("resolution")
    if isinstance(res, str):
        m = re.match(r"^\s*(\d+)\s*[xX]\s*(\d+)\s*$", res)
        if m:
            return (int(m.group(1)), int(m.group(2)))
    elif isinstance(res, dict):
        w = _as_int(res.get("width"))
        h = _as_int(res.get("height"))
        if w is not None and h is not None:
            return (w, h)
    elif isinstance(res, (list, tuple)) and len(res) == 2:
        w = _as_int(res[0])
        h = _as_int(res[1])
        if w is not None and h is not None:
            return (w, h)
    w = _as_int(vs.get("width"))
    h = _as_int(vs.get("height"))
    if w is not None and h is not None:
        return (w, h)
    return None


def get_brand_tts_models(brand: dict[str, Any]) -> list[str]:
    """Return deduplicated order-preserving list of TTS models from ``brand.json``."""
    narration = brand.get("narration") or {}
    if not isinstance(narration, dict):
        return []
    seen: set[str] = set()
    out: list[str] = []

    def _add(item: Any) -> None:
        if isinstance(item, str):
            val = item.strip()
            if val and val not in seen:
                seen.add(val)
                out.append(val)

    models = narration.get("models")
    if isinstance(models, list):
        for m in models:
            _add(m)
    _add(narration.get("model"))
    fallback = narration.get("fallback_models")
    if isinstance(fallback, list):
        for m in fallback:
            _add(m)
    return out


def get_brand_style_rationale(brand: dict[str, Any]) -> str:
    """Extract style decision rationale across documented schema locations."""
    vs = brand.get("visual_style")
    if isinstance(vs, dict):
        for key in ("style_decision_rationale", "rationale", "decision_rationale"):
            val = vs.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    for key in ("style_decision_rationale", "style_rationale"):
        val = brand.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def resolve_brand_font_path(
    brand: dict[str, Any],
    key: str = "primary_font",
    *,
    root: Path | None = None,
) -> Path | None:
    """Resolve a font path declared under ``brand['visual_style'][key]``."""
    vs = brand.get("visual_style")
    if not isinstance(vs, dict):
        return None
    raw = vs.get(key)
    if not isinstance(raw, str) or not raw.strip():
        return None
    raw = raw.strip()
    # Preserve Windows paths verbatim as Path so callers can detect them easily.
    if re.match(r"^[A-Za-z]:[/\\]", raw):
        return Path(raw)
    p = Path(raw)
    if p.is_absolute():
        return p
    base = get_project_root(root)
    if "/" in raw or "\\" in raw:
        return base / raw
    fonts_dir = vs.get("fonts_dir")
    if isinstance(fonts_dir, str) and fonts_dir.strip():
        candidate = base / fonts_dir.strip() / raw
        if candidate.exists() or not (base / raw).exists():
            return candidate
    return base / "assets" / "fonts" / raw


# ---------------------------------------------------------------------------
# Themes backlog discovery
# ---------------------------------------------------------------------------


def get_themes_backlog_path(root: Path | None = None) -> Path:
    """Return path to ``episodios/themes_backlog.json``."""
    return get_project_root(root) / "episodios" / "themes_backlog.json"


def get_themes_catalog_path(root: Path | None = None) -> Path:
    """Return path to ``episodios/THEMES_CATALOG.md``."""
    return get_project_root(root) / "episodios" / "THEMES_CATALOG.md"


def _theme_identifier(theme: dict[str, Any]) -> str:
    for key in ("slug", "episode_slug", "id", "theme_id", "title"):
        val = theme.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _match_theme_by_token(
    themes: list[dict[str, Any]], token: str
) -> dict[str, Any] | None:
    tok_low = token.strip().lower()
    tok_norm = normalize_slug(token)
    for t in themes:
        for key in ("slug", "episode_slug", "id", "theme_id", "episode_id", "title"):
            val = t.get(key)
            if isinstance(val, str):
                if val.strip().lower() == tok_low or normalize_slug(val) == tok_norm:
                    return t
    return None


def load_themes_backlog(root: Path | None = None) -> ThemesBacklog:
    """Parse ``episodios/themes_backlog.json`` across flexible JSON schemas."""
    raw = load_json(get_themes_backlog_path(root))
    themes: list[dict[str, Any]] = []
    if isinstance(raw, list):
        themes = [item for item in raw if isinstance(item, dict)]
    elif isinstance(raw, dict):
        for key in ("themes", "backlog", "items", "candidates", "episodes"):
            val = raw.get(key)
            if isinstance(val, list):
                themes = [item for item in val if isinstance(item, dict)]
                break

    selected_themes: list[dict[str, Any]] = []
    selected_slugs: list[str] = []
    seen_slugs: set[str] = set()

    def _add_selected(theme: dict[str, Any] | None, fallback_slug: str = "") -> None:
        slug = _theme_identifier(theme) if theme is not None else fallback_slug.strip()
        if not slug:
            return
        norm = normalize_slug(slug)
        if norm in seen_slugs:
            return
        seen_slugs.add(norm)
        selected_slugs.append(slug)
        if theme is not None:
            selected_themes.append(theme)

    # Priority 1: Top-level selection keys
    if isinstance(raw, dict):
        top_keys = (
            "selected_top_2",
            "top_two_slugs",
            "selected_slugs",
            "selected_for_production",
            "selected",
            "produce",
            "top_2",
            "selected_ids",
        )
        for key in top_keys:
            val = raw.get(key)
            if isinstance(val, list) and val:
                for entry in val:
                    if isinstance(entry, dict):
                        slug_tok = _theme_identifier(entry)
                        matched = _match_theme_by_token(themes, slug_tok) if slug_tok else None
                        _add_selected(matched or entry, slug_tok)
                    elif isinstance(entry, str) and entry.strip():
                        matched = _match_theme_by_token(themes, entry)
                        _add_selected(matched, entry)
                if selected_slugs:
                    break

    # Priority 2: Per-theme boolean/status flags
    if not selected_slugs:
        for t in themes:
            status = str(t.get("status", "")).strip().lower()
            is_sel = (
                t.get("selected") is True
                or t.get("selected_for_production") is True
                or t.get("produce") is True
                or t.get("top_2") is True
                or status in {"selected", "produce", "producing", "top2", "top_2"}
            )
            if is_sel:
                _add_selected(t)

    # Priority 3: Per-theme rank / priority <= 2 fallback
    if not selected_slugs:
        ranked: list[tuple[int, dict[str, Any]]] = []
        for t in themes:
            r = _as_int(t.get("rank"))
            if r is None:
                r = _as_int(t.get("priority"))
            if r is not None and r in (1, 2):
                ranked.append((r, t))
        ranked.sort(key=lambda pair: pair[0])
        for _, t in ranked:
            _add_selected(t)

    # Extract rationale from top-level and/or per-selected-theme fields
    rationale_parts: list[str] = []
    if isinstance(raw, dict):
        for key in ("selection_rationale", "rationale", "top_2_rationale", "notes"):
            val = raw.get(key)
            if isinstance(val, str) and val.strip():
                rationale_parts.append(val.strip())
                break
    for t in selected_themes:
        for key in ("selection_rationale", "rationale", "why_selected"):
            val = t.get(key)
            if isinstance(val, str) and val.strip() and val.strip() not in rationale_parts:
                rationale_parts.append(val.strip())
                break

    return ThemesBacklog(
        raw=raw,
        themes=themes,
        selected_themes=selected_themes,
        selected_slugs=selected_slugs,
        selection_rationale=" ".join(rationale_parts).strip(),
    )


# ---------------------------------------------------------------------------
# Episodes & marca discovery
# ---------------------------------------------------------------------------


def _resolve_episode_mp4(ep_dir: Path, script_slug: str | None) -> Path:
    candidates = [ep_dir / f"{ep_dir.name}.mp4"]
    if script_slug and script_slug != ep_dir.name:
        candidates.append(ep_dir / f"{script_slug}.mp4")
    for cand in candidates:
        if cand.is_file():
            return cand

    mp4s = sorted(ep_dir.glob("*.mp4"))
    non_draft = [
        p
        for p in mp4s
        if not any(tok in p.stem.lower() for tok in _DRAFT_MP4_TOKENS)
    ]
    if len(non_draft) == 1:
        return non_draft[0]
    if non_draft:
        return non_draft[0]
    if mp4s:
        return mp4s[0]
    return ep_dir / f"{ep_dir.name}.mp4"


def discover_episodes(root: Path | None = None) -> list[EpisodePaths]:
    """Dynamically discover episode directories under ``episodios/``."""
    ep_root = get_project_root(root) / "episodios"
    if not ep_root.is_dir():
        return []

    dirs: list[Path] = []
    for child in sorted(ep_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if _EPISODE_DIR_RE.match(child.name):
            dirs.append(child)
        elif (child / "script.json").is_file() or any(child.glob("*.mp4")):
            dirs.append(child)

    episodes: list[EpisodePaths] = []
    for ep_dir in dirs:
        script_json = ep_dir / "script.json"
        script_data: dict[str, Any] = {}
        if script_json.is_file():
            try:
                loaded = load_json(script_json)
                if isinstance(loaded, dict):
                    script_data = loaded
            except (OSError, ValueError):
                script_data = {}

        ep_id = ""
        if isinstance(script_data.get("episode_id"), str) and script_data["episode_id"].strip():
            ep_id = script_data["episode_id"].strip()
        else:
            m = _EPISODE_ID_PREFIX_RE.match(ep_dir.name)
            ep_id = m.group(1).lower() if m else ep_dir.name

        script_slug = (
            script_data["slug"].strip()
            if isinstance(script_data.get("slug"), str) and script_data["slug"].strip()
            else None
        )
        slug = ep_dir.name
        mp4 = _resolve_episode_mp4(ep_dir, script_slug)

        episodes.append(
            EpisodePaths(
                episode_id=ep_id,
                slug=slug,
                dir=ep_dir,
                script_json=script_json,
                narration_clean_wav=ep_dir / "narration_clean.wav",
                narration_timeline_json=ep_dir / "narration_timeline.json",
                narration_envelope_npy=ep_dir / "narration_envelope.npy",
                audio_master_wav=ep_dir / "audio_master.wav",
                captions_json=ep_dir / "captions.json",
                mp4=mp4,
                cover_png=ep_dir / "cover.png",
                cover_grid_preview_png=ep_dir / "cover_grid_preview.png",
                publish_meta_json=ep_dir / "publish_meta.json",
                qa_report_json=ep_dir / "qa_report.json",
                tts_cache_dir=ep_dir / "cache" / "tts",
            )
        )
    return episodes


def load_episode_publish_meta(ep: EpisodePaths) -> dict[str, Any] | None:
    """Load ``publish_meta.json`` if present, else fall back to ``script.json['publish_meta']``."""
    if ep.publish_meta_json.is_file():
        data = load_json(ep.publish_meta_json)
        if isinstance(data, dict):
            return data
    if ep.script_json.is_file():
        script = load_json(ep.script_json)
        if isinstance(script, dict) and isinstance(script.get("publish_meta"), dict):
            return script["publish_meta"]
    return None


def discover_marca_assets(root: Path | None = None) -> dict[str, Path]:
    """Return canonical ``marca/`` asset paths plus any extra discovered files."""
    marca_dir = get_project_root(root) / "marca"
    assets: dict[str, Path] = {
        "youtube_banner": marca_dir / "youtube_banner.png",
        "youtube_banner_preview": marca_dir / "youtube_banner_preview.png",
        "brand_sheet": marca_dir / "brand_sheet.png",
    }
    if marca_dir.is_dir():
        known_paths = {p.resolve() for p in assets.values()}
        for item in sorted(marca_dir.iterdir(), key=lambda p: p.name):
            if item.is_file() and not item.name.startswith("."):
                if item.resolve() not in known_paths:
                    key = item.stem if item.stem not in assets else item.name
                    assets[key] = item
    return assets


# ---------------------------------------------------------------------------
# /reel-watch discovery & reels/INDEX.md parser
# ---------------------------------------------------------------------------


def _extract_youtube_id(texts: list[str]) -> str | None:
    for text in texts:
        m = _YOUTUBE_ID_RE.search(text)
        if m:
            return m.group(1)
    return None


def _discover_frame_paths(run_dir: Path, manifest: dict[str, Any]) -> tuple[Path, ...]:
    frames_dir = run_dir / "frames"
    found: list[Path] = []
    if frames_dir.is_dir():
        found = sorted(
            p
            for p in frames_dir.iterdir()
            if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
        )
    if found:
        return tuple(found)
    # Fallback to manifest["frames"] entries if files exist on disk
    raw_frames = manifest.get("frames")
    if isinstance(raw_frames, list):
        for entry in raw_frames:
            if isinstance(entry, str) and entry.strip():
                p = Path(entry)
                if not p.is_absolute():
                    p = run_dir / p
                if p.is_file():
                    found.append(p)
    return tuple(sorted(found))


def discover_reel_runs(root: Path | None = None) -> list[ReelRun]:
    """Discover valid ``/reel-watch`` runs under ``reels/``, skipping orphan/empty dirs."""
    reels_root = get_project_root(root) / "reels"
    if not reels_root.is_dir():
        return []

    runs: list[ReelRun] = []
    for child in sorted(reels_root.iterdir(), key=lambda p: p.name, reverse=True):
        if not child.is_dir() or child.name.startswith("."):
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = load_json(manifest_path)
        except (OSError, ValueError):
            continue
        if not isinstance(manifest, dict):
            continue

        raw_sources = manifest.get("sources")
        sources: tuple[str, ...] = (
            tuple(str(s) for s in raw_sources if isinstance(s, str))
            if isinstance(raw_sources, list)
            else ()
        )
        kind = str(manifest.get("kind", "") or "")
        engine = str(manifest.get("engine", "") or "")
        fetched_via = str(manifest.get("fetched_via", "") or "")

        frames_dir = child / "frames"
        frame_paths = _discover_frame_paths(child, manifest)

        analysis_path: Path | None = None
        raw_analysis = manifest.get("analysis")
        if isinstance(raw_analysis, str) and raw_analysis.strip():
            cand = Path(raw_analysis)
            if not cand.is_absolute():
                cand = child / cand
            if cand.is_file():
                analysis_path = cand
        if analysis_path is None:
            for fallback_name in ("local.md", "gemini.md"):
                cand = child / fallback_name
                if cand.is_file():
                    analysis_path = cand
                    break

        breakdown_cand = child / "breakdown.md"
        breakdown_path = breakdown_cand if breakdown_cand.is_file() else None

        meta = manifest.get("meta") if isinstance(manifest.get("meta"), dict) else {}
        id_search_pool = list(sources)
        webpage_url = meta.get("webpage_url")
        if isinstance(webpage_url, str):
            id_search_pool.append(webpage_url)
        youtube_id = _extract_youtube_id(id_search_pool)

        runs.append(
            ReelRun(
                dir=child,
                manifest_path=manifest_path,
                manifest=manifest,
                sources=sources,
                kind=kind,
                engine=engine,
                fetched_via=fetched_via,
                frames_dir=frames_dir,
                frame_paths=frame_paths,
                analysis_path=analysis_path,
                breakdown_path=breakdown_path,
                youtube_id=youtube_id,
            )
        )
    return runs


def _read_text_quiet(path: Path | None, max_bytes: int = 262_144) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        with path.open("rb") as fh:
            return fh.read(max_bytes).decode("utf-8", errors="ignore")
    except OSError:
        return ""


def find_reference_reel(video_id: str, root: Path | None = None) -> ReelRun | None:
    """Find the newest ``ReelRun`` matching a YouTube video ID across manifest & markdown."""
    target = video_id.strip()
    if not target:
        return None
    runs = discover_reel_runs(root)
    # First pass: exact structured match on youtube_id, sources, or webpage_url
    for run in runs:
        if run.youtube_id == target:
            return run
        meta = run.manifest.get("meta") if isinstance(run.manifest.get("meta"), dict) else {}
        webpage_url = str(meta.get("webpage_url", "") or "")
        if target in webpage_url or any(target in s for s in run.sources):
            return run
    # Second pass: match inside breakdown.md / gemini.md / local.md
    for run in runs:
        for doc in (run.breakdown_path, run.analysis_path, run.dir / "gemini.md", run.dir / "local.md"):
            if target in _read_text_quiet(doc):
                return run
    return None


def find_episode_audit_reel(ep: EpisodePaths, root: Path | None = None) -> ReelRun | None:
    """Find the newest local ``/reel-watch`` QA audit run for an episode."""
    slug_low = ep.slug.lower()
    mp4_name_low = ep.mp4.name.lower()
    mp4_stem_low = ep.mp4.stem.lower()
    norm_slug = normalize_slug(ep.slug)

    for run in discover_reel_runs(root):
        is_local = (
            run.fetched_via.lower() == "local-file"
            or "local" in run.engine.lower()
            or run.kind.lower() == "local"
        )
        if not is_local:
            continue
        haystack = " ".join([run.dir.name.lower(), *(s.lower() for s in run.sources)])
        if (
            slug_low in haystack
            or mp4_name_low in haystack
            or mp4_stem_low in haystack
            or (norm_slug and norm_slug in haystack)
        ):
            return run
    return None


def parse_reels_index(root: Path | None = None) -> list[IndexEntry]:
    """Parse ``reels/INDEX.md`` supporting both SKILL.md and ``jobs.py`` formats."""
    proj = get_project_root(root)
    index_path = proj / "reels" / "INDEX.md"
    if not index_path.is_file():
        return []

    entries: list[IndexEntry] = []
    for raw_line in index_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line.startswith("-"):
            continue
        m = INDEX_LINE_RE.match(line)
        if not m:
            continue
        raw_dir = m.group("dir").strip().strip("`").rstrip("/")
        resolved: Path | None = None
        cand_path = Path(raw_dir)
        if cand_path.is_absolute():
            if cand_path.is_dir():
                resolved = cand_path.resolve()
        else:
            for base in (proj, proj / "reels"):
                c = base / raw_dir
                if c.is_dir():
                    resolved = c.resolve()
                    break
        entries.append(
            IndexEntry(
                date=m.group("date"),
                summary=m.group("summary").strip(),
                raw_dir=raw_dir,
                resolved_dir=resolved,
                raw_line=raw_line,
            )
        )
    return entries
