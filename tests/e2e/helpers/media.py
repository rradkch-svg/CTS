"""Opaque-box media probing, audio loudness/silence, and video motion helpers.

Uses only Python 3.12 stdlib, ``PIL``, ``numpy``, and system ``ffprobe``/``ffmpeg``
subprocesses. Never imports from ``src/`` or ``cts_factory``.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import wave
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from PIL import Image

_MEDIA_CACHE: dict[tuple[Any, ...], Any] = {}

_NUM_OR_INF = r"([-+]?\d+(?:\.\d+)?|-?inf)"
_RE_EBUR_I = re.compile(rf"Integrated loudness:.*?^\s*I:\s*{_NUM_OR_INF}\s*LUFS", re.S | re.M)
_RE_EBUR_LRA = re.compile(rf"Loudness range:.*?^\s*LRA:\s*{_NUM_OR_INF}\s*LU", re.S | re.M)
_RE_EBUR_PEAK = re.compile(rf"True peak:.*?^\s*Peak:\s*{_NUM_OR_INF}\s*dBFS", re.S | re.M)

_RE_SIL_START = re.compile(r"silence_start:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)")
_RE_SIL_END = re.compile(
    r"silence_end:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*\|\s*"
    r"silence_duration:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
)


def clear_media_cache() -> None:
    """Clear all cached media probe, loudness, RMS, frame, and motion results."""
    _MEDIA_CACHE.clear()


def _cache_key(op_name: str, path: Path, params: tuple[Any, ...] = ()) -> tuple[Any, ...]:
    resolved = Path(path).resolve()
    st = resolved.stat()
    return (op_name, str(resolved), st.st_mtime_ns, st.st_size, params)


def _parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip()
    if not s or s.upper() == "N/A":
        return None
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip()
    if not s or s.upper() == "N/A":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_fps(rate_str: str | None) -> float | None:
    """Parse an ffprobe rational frame-rate string such as ``'30/1'`` via ``Fraction``."""
    if not rate_str:
        return None
    s = str(rate_str).strip()
    if not s or s in ("0/0", "N/A", "0"):
        return None
    try:
        frac = Fraction(s)
        val = float(frac)
        return val if val > 0.0 and math.isfinite(val) else None
    except (ValueError, ZeroDivisionError):
        return None


@dataclass(frozen=True)
class MediaProbe:
    """Structured ffprobe metadata for a video or audio container."""

    path: Path
    format_name: str
    duration_s: float
    size_bytes: int
    total_streams: int
    video_stream_count: int
    audio_stream_count: int
    video_codec: str | None
    width: int | None
    height: int | None
    avg_frame_rate: float | None
    r_frame_rate: float | None
    fps: float | None
    pix_fmt: str | None
    sar: str | None
    raw_sar: str | None
    rotation: int
    video_duration_s: float | None
    video_bitrate: int | None
    nb_video_frames: int | None
    audio_codec: str | None
    sample_rate_hz: int | None
    channels: int | None
    channel_layout: str | None
    audio_duration_s: float | None
    audio_bitrate: int | None
    overall_bitrate: int | None


@dataclass(frozen=True)
class DecodeCheckResult:
    """Result of full-stream ``ffmpeg -v error -f null -`` decode verification."""

    ok: bool
    returncode: int
    stderr: str
    errors: list[str]


@dataclass(frozen=True)
class LoudnessMetrics:
    """Parsed ITU-R BS.1770 / EBU R128 loudness metrics from ``ffmpeg -af ebur128``."""

    integrated_lufs: float
    lra_lu: float
    true_peak_dbfs: float
    raw_summary: str


@dataclass(frozen=True)
class SilenceInterval:
    """Detected silence interval from ``ffmpeg -af silencedetect``."""

    start_s: float
    end_s: float
    duration_s: float


@dataclass(frozen=True)
class RmsScanResult:
    """Windowed mono 48 kHz PCM RMS energy scan results."""

    window_s: float
    hop_s: float
    window_count: int
    min_db: float
    p05_db: float
    median_db: float
    max_db: float
    silence_windows: list[tuple[float, float]]
    window_dbs: tuple[float, ...]


@dataclass(frozen=True)
class AudioWaveformStats:
    """Direct waveform statistics for a PCM WAV artifact."""

    sample_rate_hz: int
    channels: int
    duration_s: float
    peak_abs: float
    clip_ratio: float
    dc_offset: float
    left_rms_db: float
    right_rms_db: float | None
    tail_last_sample_abs: float
    all_finite: bool


@dataclass(frozen=True)
class MotionAnalysis:
    """Viewport-masked articulated motion, static-run, and camera-cut analysis."""

    fps: float
    frame_count: int
    mad_per_step: tuple[float, ...]
    median_mad: float
    active_frame_ratio: float
    max_static_run_s: float
    camera_cut_timestamps_s: tuple[float, ...]
    distinct_angle_clusters: int
    spatial_tile_cv: float
    spatial_tile_p90_p25_ratio: float
    min_frame_luma: float
    max_frame_luma: float


def _extract_rotation(video_stream: dict[str, Any]) -> int:
    tags = video_stream.get("tags")
    if isinstance(tags, dict) and tags.get("rotate") is not None:
        val = _parse_float(tags.get("rotate"))
        if val is not None:
            return int(round(val)) % 360
    side_data = video_stream.get("side_data_list")
    if isinstance(side_data, list):
        for item in side_data:
            if isinstance(item, dict) and item.get("rotation") is not None:
                val = _parse_float(item.get("rotation"))
                if val is not None:
                    return int(round(val)) % 360
    return 0


def probe_media(path: Path) -> MediaProbe:
    """Probe media streams and container metadata via ``ffprobe`` (mtime+size cached)."""
    p = Path(path).resolve()
    key = _cache_key("probe_media", p)
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key]

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(p),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {p}: {proc.stderr.strip()}")

    data = json.loads(proc.stdout)
    fmt = data.get("format") or {}
    streams = data.get("streams") or []

    video_streams = [
        s
        for s in streams
        if s.get("codec_type") == "video"
        and not (isinstance(s.get("disposition"), dict) and s["disposition"].get("attached_pic") == 1)
    ]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    vs = video_streams[0] if video_streams else None
    aus = audio_streams[0] if audio_streams else None

    fmt_dur = _parse_float(fmt.get("duration"))
    v_dur = _parse_float(vs.get("duration")) if vs else None
    if vs is not None and v_dur is None:
        v_dur = fmt_dur
    a_dur = _parse_float(aus.get("duration")) if aus else None
    if aus is not None and a_dur is None:
        a_dur = fmt_dur
    dur = fmt_dur or v_dur or a_dur or 0.0

    avg_fr = parse_fps(vs.get("avg_frame_rate")) if vs else None
    r_fr = parse_fps(vs.get("r_frame_rate")) if vs else None
    fps = avg_fr if (avg_fr is not None and avg_fr > 0) else r_fr

    raw_sar = vs.get("sample_aspect_ratio") if vs else None
    if vs is None:
        sar = None
    elif raw_sar in (None, "", "N/A", "0:1"):
        sar = "1:1"
    else:
        sar = str(raw_sar)

    probe = MediaProbe(
        path=p,
        format_name=str(fmt.get("format_name", "")),
        duration_s=dur,
        size_bytes=int(fmt.get("size") or p.stat().st_size),
        total_streams=len(streams),
        video_stream_count=len(video_streams),
        audio_stream_count=len(audio_streams),
        video_codec=vs.get("codec_name") if vs else None,
        width=_parse_int(vs.get("width")) if vs else None,
        height=_parse_int(vs.get("height")) if vs else None,
        avg_frame_rate=avg_fr,
        r_frame_rate=r_fr,
        fps=fps,
        pix_fmt=vs.get("pix_fmt") if vs else None,
        sar=sar,
        raw_sar=str(raw_sar) if raw_sar is not None else None,
        rotation=_extract_rotation(vs) if vs else 0,
        video_duration_s=v_dur,
        video_bitrate=_parse_int(vs.get("bit_rate")) if vs else None,
        nb_video_frames=_parse_int(vs.get("nb_frames")) if vs else None,
        audio_codec=aus.get("codec_name") if aus else None,
        sample_rate_hz=_parse_int(aus.get("sample_rate")) if aus else None,
        channels=_parse_int(aus.get("channels")) if aus else None,
        channel_layout=aus.get("channel_layout") if aus else None,
        audio_duration_s=a_dur,
        audio_bitrate=_parse_int(aus.get("bit_rate")) if aus else None,
        overall_bitrate=_parse_int(fmt.get("bit_rate")),
    )
    _MEDIA_CACHE[key] = probe
    return probe


def verify_ffmpeg_decode(path: Path) -> DecodeCheckResult:
    """Decode the entire media file via ``ffmpeg -v error -f null -`` (cached)."""
    p = Path(path).resolve()
    key = _cache_key("verify_ffmpeg_decode", p)
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key]

    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(p), "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    stderr_clean = proc.stderr.strip()
    errors: list[str] = []
    if proc.returncode != 0:
        errors.append(f"ffmpeg decode exited with code {proc.returncode}")
    if stderr_clean:
        errors.append(f"ffmpeg decode emitted errors: {stderr_clean[:400]}")
    result = DecodeCheckResult(
        ok=(proc.returncode == 0 and stderr_clean == ""),
        returncode=proc.returncode,
        stderr=stderr_clean,
        errors=errors,
    )
    _MEDIA_CACHE[key] = result
    return result


def parse_ebur128_summary(stderr: str) -> LoudnessMetrics:
    """Parse ``Summary:`` block from ``ffmpeg -af ebur128=peak=true`` stderr."""
    idx = stderr.rfind("Summary:")
    if idx == -1:
        raise ValueError("ebur128 stderr does not contain a 'Summary:' block")
    summary = stderr[idx:]

    m_i = _RE_EBUR_I.search(summary)
    m_lra = _RE_EBUR_LRA.search(summary)
    m_peak = _RE_EBUR_PEAK.search(summary)
    if not (m_i and m_lra and m_peak):
        raise ValueError(
            f"Could not parse all ebur128 fields (I={bool(m_i)}, LRA={bool(m_lra)}, Peak={bool(m_peak)}) "
            f"from summary:\n{summary[:500]}"
        )

    return LoudnessMetrics(
        integrated_lufs=float(m_i.group(1)),
        lra_lu=float(m_lra.group(1)),
        true_peak_dbfs=float(m_peak.group(1)),
        raw_summary=summary.strip(),
    )


def measure_ebur128(path: Path) -> LoudnessMetrics:
    """Measure audio loudness/LRA/true-peak via ``ffmpeg -vn -af ebur128=peak=true`` (cached)."""
    p = Path(path).resolve()
    key = _cache_key("measure_ebur128", p)
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key]

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(p),
        "-vn",
        "-af",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg ebur128 failed on {p}: {proc.stderr.strip()[:400]}")
    metrics = parse_ebur128_summary(proc.stderr)
    _MEDIA_CACHE[key] = metrics
    return metrics


def load_pcm_stereo_or_mono(
    path: Path, *, sample_rate: int = 48000
) -> tuple[np.ndarray, int]:
    """Load audio as float32 ``(N, C)`` array in ``[-1, 1]`` and its sample rate."""
    p = Path(path).resolve()
    if p.suffix.lower() == ".wav":
        with wave.open(str(p), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
        if sw == 2:
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            return arr.reshape(-1, ch), sr
        if sw == 4:
            arr = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            return arr.reshape(-1, ch), sr
        if sw == 1:
            arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            return arr.reshape(-1, ch), sr

    probe = probe_media(p)
    ch = probe.channels or 2
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(p),
        "-vn",
        "-ac",
        str(ch),
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg PCM decode failed on {p}: {proc.stderr.decode('utf-8', 'ignore')}")
    arr = np.frombuffer(proc.stdout, dtype=np.float32)
    usable = (len(arr) // ch) * ch
    return arr[:usable].reshape(-1, ch), sample_rate


def scan_rms_windows(
    path: Path,
    *,
    window_s: float = 0.5,
    hop_s: float = 0.5,
    silence_db: float = -60.0,
    trim_edge_s: float = 0.25,
) -> RmsScanResult:
    """Decode audio to 48 kHz mono float32 PCM and scan RMS energy windows."""
    p = Path(path).resolve()
    params = (float(window_s), float(hop_s), float(silence_db), float(trim_edge_s))
    key = _cache_key("scan_rms_windows", p, params)
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key]

    sr = 48000
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(p),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sr),
        "-f",
        "f32le",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg RMS decode failed on {p}: {proc.stderr.decode('utf-8', 'ignore')}"
        )

    samples = np.frombuffer(proc.stdout, dtype=np.float32)
    win = max(1, int(round(window_s * sr)))
    hop = max(1, int(round(hop_s * sr)))
    trim = max(0, int(round(trim_edge_s * sr)))

    if trim > 0 and len(samples) > 2 * trim + win:
        body = samples[trim : len(samples) - trim]
        trim_offset_s = trim / float(sr)
    else:
        body = samples
        trim_offset_s = 0.0

    if len(body) < win:
        if len(body) == 0:
            rms_db = np.array([-200.0], dtype=np.float64)
        else:
            rms_val = float(np.sqrt(np.mean(body.astype(np.float64) ** 2)))
            rms_db = np.array([20.0 * math.log10(max(rms_val, 1e-10))], dtype=np.float64)
    elif hop == win:
        n_win = len(body) // win
        frames = body[: n_win * win].reshape(n_win, win)
        rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
        rms_db = 20.0 * np.log10(np.maximum(rms, 1e-10))
    else:
        frames = np.lib.stride_tricks.sliding_window_view(body, win)[::hop]
        rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
        rms_db = 20.0 * np.log10(np.maximum(rms, 1e-10))

    silence_windows: list[tuple[float, float]] = [
        (round(trim_offset_s + i * (hop / float(sr)), 4), float(db))
        for i, db in enumerate(rms_db)
        if float(db) <= silence_db
    ]

    result = RmsScanResult(
        window_s=window_s,
        hop_s=hop_s,
        window_count=int(len(rms_db)),
        min_db=float(np.min(rms_db)),
        p05_db=float(np.percentile(rms_db, 5)),
        median_db=float(np.median(rms_db)),
        max_db=float(np.max(rms_db)),
        silence_windows=silence_windows,
        window_dbs=tuple(float(x) for x in rms_db),
    )
    _MEDIA_CACHE[key] = result
    return result


def run_silencedetect(
    path: Path,
    *,
    noise_db: float = -60.0,
    min_duration_s: float = 0.5,
) -> list[SilenceInterval]:
    """Run ``ffmpeg -vn -af silencedetect`` and return detected silence intervals."""
    p = Path(path).resolve()
    params = (float(noise_db), float(min_duration_s))
    key = _cache_key("run_silencedetect", p, params)
    if key in _MEDIA_CACHE:
        return list(_MEDIA_CACHE[key])

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(p),
        "-vn",
        "-af",
        f"silencedetect=noise={noise_db:g}dB:d={min_duration_s:g}",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg silencedetect failed on {p}: {proc.stderr.strip()[:400]}")

    intervals: list[SilenceInterval] = []
    pending_start: float | None = None
    for line in proc.stderr.splitlines():
        m_start = _RE_SIL_START.search(line)
        if m_start:
            pending_start = max(0.0, float(m_start.group(1)))
            continue
        m_end = _RE_SIL_END.search(line)
        if m_end:
            end_s = float(m_end.group(1))
            dur_s = float(m_end.group(2))
            start_s = pending_start if pending_start is not None else max(0.0, end_s - dur_s)
            intervals.append(SilenceInterval(start_s=start_s, end_s=end_s, duration_s=dur_s))
            pending_start = None

    if pending_start is not None:
        total_dur = probe_media(p).duration_s
        if total_dur >= pending_start:
            dur_s = total_dur - pending_start
            if dur_s >= min_duration_s - 0.02:
                intervals.append(
                    SilenceInterval(start_s=pending_start, end_s=total_dur, duration_s=dur_s)
                )

    _MEDIA_CACHE[key] = tuple(intervals)
    return intervals


def analyze_wav_stats(path: Path) -> AudioWaveformStats:
    """Compute direct waveform integrity statistics on a WAV file."""
    p = Path(path).resolve()
    key = _cache_key("analyze_wav_stats", p)
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key]

    samples, sr = load_pcm_stereo_or_mono(p)
    n_frames, ch = samples.shape
    duration_s = n_frames / float(sr) if sr > 0 else 0.0
    all_finite = bool(np.all(np.isfinite(samples)))

    if n_frames == 0:
        stats = AudioWaveformStats(
            sample_rate_hz=sr,
            channels=ch,
            duration_s=0.0,
            peak_abs=0.0,
            clip_ratio=0.0,
            dc_offset=0.0,
            left_rms_db=-200.0,
            right_rms_db=-200.0 if ch >= 2 else None,
            tail_last_sample_abs=0.0,
            all_finite=all_finite,
        )
        _MEDIA_CACHE[key] = stats
        return stats

    abs_s = np.abs(samples)
    peak_abs = float(np.max(abs_s))
    clip_ratio = float(np.mean(abs_s >= 0.999))
    dc_offset = float(np.mean(samples.astype(np.float64)))

    left_rms = float(np.sqrt(np.mean(samples[:, 0].astype(np.float64) ** 2)))
    left_rms_db = 20.0 * math.log10(max(left_rms, 1e-10))
    right_rms_db: float | None = None
    if ch >= 2:
        right_rms = float(np.sqrt(np.mean(samples[:, 1].astype(np.float64) ** 2)))
        right_rms_db = 20.0 * math.log10(max(right_rms, 1e-10))

    tail_last_sample_abs = float(np.max(np.abs(samples[-1])))

    stats = AudioWaveformStats(
        sample_rate_hz=sr,
        channels=ch,
        duration_s=duration_s,
        peak_abs=peak_abs,
        clip_ratio=clip_ratio,
        dc_offset=dc_offset,
        left_rms_db=left_rms_db,
        right_rms_db=right_rms_db,
        tail_last_sample_abs=tail_last_sample_abs,
        all_finite=all_finite,
    )
    _MEDIA_CACHE[key] = stats
    return stats


def extract_frame(path: Path, t_s: float = 0.0) -> Image.Image:
    """Extract a single full-resolution RGB frame at ``t_s`` seconds (cached).

    Uses output seeking (``-i ... -ss``) for ``0.001 < t_s < 1.0`` so sub-second
    timestamps such as ``t=0.5s`` never snap back to keyframe ``0.0``.
    """
    p = Path(path).resolve()
    t_norm = round(max(0.0, float(t_s)), 3)
    key = _cache_key("extract_frame", p, (t_norm,))
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key].copy()

    probe = probe_media(p)
    if not probe.width or not probe.height:
        raise ValueError(f"Media {p} has no readable video stream dimensions")
    w, h = probe.width, probe.height

    if t_norm <= 0.001:
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(p),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]
    elif t_norm < 1.0:
        # Output seeking guarantees exact sub-second frame extraction across long GOPs.
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(p),
            "-ss",
            f"{t_norm:.3f}",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]
    else:
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{t_norm:.3f}",
            "-i",
            str(p),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]

    proc = subprocess.run(cmd, capture_output=True, check=False)
    expected = w * h * 3
    if proc.returncode != 0 or len(proc.stdout) < expected:
        raise RuntimeError(
            f"ffmpeg extract_frame failed on {p} at t={t_norm}s "
            f"(rc={proc.returncode}, bytes={len(proc.stdout)}/{expected}): "
            f"{proc.stderr.decode('utf-8', 'ignore')[:300]}"
        )
    img = Image.frombytes("RGB", (w, h), proc.stdout[:expected])
    _MEDIA_CACHE[key] = img
    return img.copy()


def extract_frames_at(path: Path, timestamps_s: Sequence[float]) -> list[Image.Image]:
    """Extract multiple RGB frames at the requested timestamps."""
    return [extract_frame(path, t) for t in timestamps_s]


def sample_video_rgb(
    path: Path,
    *,
    fps: float = 1.0,
    width: int = 270,
    height: int = 480,
) -> np.ndarray:
    """Decode video into a downsampled ``(N, H, W, 3)`` uint8 RGB NumPy tensor (cached)."""
    p = Path(path).resolve()
    params = (float(fps), int(width), int(height))
    key = _cache_key("sample_video_rgb", p, params)
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key]

    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(p),
        "-vf",
        f"fps={fps:g},scale={width}:{height}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg sample_video_rgb failed on {p}: {proc.stderr.decode('utf-8', 'ignore')[:300]}"
        )
    frame_bytes = width * height * 3
    n_frames = len(proc.stdout) // frame_bytes
    if n_frames == 0:
        arr = np.empty((0, height, width, 3), dtype=np.uint8)
    else:
        arr = np.frombuffer(proc.stdout[: n_frames * frame_bytes], dtype=np.uint8).reshape(
            n_frames, height, width, 3
        )
    _MEDIA_CACHE[key] = arr
    return arr


def _coarse_rgb_histograms(vp: np.ndarray) -> np.ndarray:
    """Compute normalized 4x4x4 (64-bin) RGB histograms per frame."""
    q = (vp.astype(np.int32) >> 6)  # 0..3 per channel
    bins = (q[..., 0] << 4) | (q[..., 1] << 2) | q[..., 2]
    n = vp.shape[0]
    flat = bins.reshape(n, -1)
    hists = np.zeros((n, 64), dtype=np.float32)
    denom = float(flat.shape[1]) if flat.shape[1] > 0 else 1.0
    for i in range(n):
        hists[i] = np.bincount(flat[i], minlength=64).astype(np.float32) / denom
    return hists


def analyze_motion_and_cuts(
    path: Path,
    *,
    fps: float = 1.0,
    width: int = 270,
    height: int = 480,
    mask_text_bands: bool = True,
    y_range_1920: tuple[int, int] = (460, 1360),
    motion_mad_min: float = 0.5,
    static_mad_max: float = 0.35,
    cut_mad_threshold: float = 12.0,
    cut_hist_threshold: float = 0.22,
    min_cut_gap_s: float = 1.5,
) -> MotionAnalysis:
    """Analyze articulated viewport motion, static runs, cuts, and 4x4 tile differential motion."""
    p = Path(path).resolve()
    params = (
        float(fps),
        int(width),
        int(height),
        bool(mask_text_bands),
        tuple(y_range_1920),
        float(motion_mad_min),
        float(static_mad_max),
        float(cut_mad_threshold),
        float(cut_hist_threshold),
        float(min_cut_gap_s),
    )
    key = _cache_key("analyze_motion_and_cuts", p, params)
    if key in _MEDIA_CACHE:
        return _MEDIA_CACHE[key]

    frames = sample_video_rgb(p, fps=fps, width=width, height=height)
    n_frames = int(frames.shape[0])
    if n_frames == 0:
        res = MotionAnalysis(
            fps=fps,
            frame_count=0,
            mad_per_step=(),
            median_mad=0.0,
            active_frame_ratio=0.0,
            max_static_run_s=0.0,
            camera_cut_timestamps_s=(),
            distinct_angle_clusters=0,
            spatial_tile_cv=0.0,
            spatial_tile_p90_p25_ratio=0.0,
            min_frame_luma=0.0,
            max_frame_luma=0.0,
        )
        _MEDIA_CACHE[key] = res
        return res

    # Full-frame Rec.709 mean luma per sampled frame (for black/white glitch-frame checks)
    full_luma = (
        0.2126 * frames[..., 0].astype(np.float32)
        + 0.7152 * frames[..., 1].astype(np.float32)
        + 0.0722 * frames[..., 2].astype(np.float32)
    )
    frame_mean_lumas = full_luma.mean(axis=(1, 2))
    min_frame_luma = float(np.min(frame_mean_lumas))
    max_frame_luma = float(np.max(frame_mean_lumas))

    if mask_text_bands:
        y0 = max(0, min(height - 1, int(round((y_range_1920[0] / 1920.0) * height))))
        y1 = max(y0 + 1, min(height, int(round((y_range_1920[1] / 1920.0) * height))))
        vp = frames[:, y0:y1, :, :].astype(np.float32)
    else:
        vp = frames.astype(np.float32)

    if n_frames == 1:
        res = MotionAnalysis(
            fps=fps,
            frame_count=1,
            mad_per_step=(),
            median_mad=0.0,
            active_frame_ratio=0.0,
            max_static_run_s=0.0,
            camera_cut_timestamps_s=(),
            distinct_angle_clusters=1,
            spatial_tile_cv=0.0,
            spatial_tile_p90_p25_ratio=0.0,
            min_frame_luma=min_frame_luma,
            max_frame_luma=max_frame_luma,
        )
        _MEDIA_CACHE[key] = res
        return res

    diffs = np.abs(np.diff(vp, axis=0)).mean(axis=3)  # (N-1, vh, vw)
    mad_per_step = diffs.mean(axis=(1, 2))
    median_mad = float(np.median(mad_per_step))
    active_frame_ratio = float(np.mean(mad_per_step >= motion_mad_min))

    # Longest contiguous static run
    cur_run = 0
    max_run = 0
    for val in mad_per_step:
        if float(val) < static_mad_max:
            cur_run += 1
            if cur_run > max_run:
                max_run = cur_run
        else:
            cur_run = 0
    max_static_run_s = max_run / float(fps)

    # Hard camera cuts via MAD + coarse 4x4x4 RGB histogram L1 distance
    hists = _coarse_rgb_histograms(vp)
    hist_l1 = 0.5 * np.abs(np.diff(hists, axis=0)).sum(axis=1)

    cut_indices: list[int] = []
    cut_times: list[float] = []
    for i in range(len(mad_per_step)):
        if float(mad_per_step[i]) >= cut_mad_threshold or float(hist_l1[i]) >= cut_hist_threshold:
            t_cut = (i + 1) / float(fps)
            if not cut_times or (t_cut - cut_times[-1]) >= min_cut_gap_s:
                cut_indices.append(i + 1)
                cut_times.append(round(t_cut, 3))
            elif float(mad_per_step[i]) > float(mad_per_step[cut_indices[-1] - 1]):
                cut_indices[-1] = i + 1
                cut_times[-1] = round(t_cut, 3)

    # Distinct angle clusters across cut-delimited segments
    boundaries = [0, *cut_indices, n_frames]
    vh, vw = vp.shape[1], vp.shape[2]
    ys_ds = np.linspace(0, vh - 1, 16, dtype=int)
    xs_ds = np.linspace(0, vw - 1, 9, dtype=int)
    clusters: list[np.ndarray] = []
    for seg_i in range(len(boundaries) - 1):
        s0, s1 = boundaries[seg_i], boundaries[seg_i + 1]
        if s1 <= s0:
            continue
        seg_small = vp[s0:s1][:, ys_ds, :, :][:, :, xs_ds, :]
        med_frame = np.median(seg_small, axis=0)
        if not any(float(np.abs(med_frame - c).mean()) <= 12.0 for c in clusters):
            clusters.append(med_frame)
    distinct_angle_clusters = len(clusters)

    # 4x4 spatial tile differential motion ratio (anti-Ken-Burns / anti-slideshow)
    y_edges = np.linspace(0, vh, 5, dtype=int)
    x_edges = np.linspace(0, vw, 5, dtype=int)
    tile_mads = np.zeros((diffs.shape[0], 16), dtype=np.float32)
    t_idx = 0
    for ty in range(4):
        for tx in range(4):
            tile = diffs[:, y_edges[ty] : y_edges[ty + 1], x_edges[tx] : x_edges[tx + 1]]
            tile_mads[:, t_idx] = tile.mean(axis=(1, 2))
            t_idx += 1

    intra_mask = (mad_per_step >= static_mad_max) & (mad_per_step < cut_mad_threshold)
    if int(np.sum(intra_mask)) == 0:
        spatial_tile_cv = 0.0
        spatial_tile_p90_p25_ratio = 0.0
    else:
        tm = tile_mads[intra_mask]
        tile_cv = tm.std(axis=1) / np.maximum(tm.mean(axis=1), 1e-6)
        p90 = np.percentile(tm, 90, axis=1)
        p25 = np.percentile(tm, 25, axis=1)
        p90_p25 = p90 / np.maximum(p25, 0.05)
        spatial_tile_cv = float(np.median(tile_cv))
        spatial_tile_p90_p25_ratio = float(np.median(p90_p25))

    result = MotionAnalysis(
        fps=fps,
        frame_count=n_frames,
        mad_per_step=tuple(float(x) for x in mad_per_step),
        median_mad=median_mad,
        active_frame_ratio=active_frame_ratio,
        max_static_run_s=max_static_run_s,
        camera_cut_timestamps_s=tuple(cut_times),
        distinct_angle_clusters=distinct_angle_clusters,
        spatial_tile_cv=spatial_tile_cv,
        spatial_tile_p90_p25_ratio=spatial_tile_p90_p25_ratio,
        min_frame_luma=min_frame_luma,
        max_frame_luma=max_frame_luma,
    )
    _MEDIA_CACHE[key] = result
    return result
