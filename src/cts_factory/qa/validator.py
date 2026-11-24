"""Mandatory technical QA validator: ffprobe, ebur128, 0.5s RMS silence scan, and /reel-watch."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np

from cts_factory.config import BrandConfig


def _probe_video(mp4_path: Path) -> dict[str, Any]:
    res = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(mp4_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res.stdout)
    vstream = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    astream = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if vstream is None or astream is None:
        raise RuntimeError(f"Missing video or audio stream in {mp4_path}")

    fps_parts = str(vstream.get("r_frame_rate", "0/1")).split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) else 0.0
    return {
        "width": int(vstream["width"]),
        "height": int(vstream["height"]),
        "fps": round(fps, 3),
        "video_codec": str(vstream["codec_name"]),
        "pix_fmt": str(vstream["pix_fmt"]),
        "audio_codec": str(astream["codec_name"]),
        "audio_sample_rate": int(astream["sample_rate"]),
        "audio_channels": int(astream["channels"]),
        "duration_s": round(float(data["format"]["duration"]), 3),
        "size_bytes": int(data["format"]["size"]),
    }


def _measure_ebur128(mp4_path: Path) -> dict[str, float]:
    res = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(mp4_path),
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    stderr = res.stderr
    # Parse Summary block at end of ebur128 output
    summary_idx = stderr.rfind("Summary:")
    tail = stderr[summary_idx:] if summary_idx != -1 else stderr
    m_i = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", tail)
    m_lra = re.search(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", tail)
    m_tp = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", tail)
    return {
        "integrated_lufs": float(m_i.group(1)) if m_i else -99.0,
        "lra_lu": float(m_lra.group(1)) if m_lra else 99.0,
        "true_peak_dbtp": float(m_tp.group(1)) if m_tp else 0.0,
    }


def _scan_rms_gaps(mp4_path: Path, window_s: float = 0.5, silence_db: float = -55.0) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        wav = Path(tmpdir) / "decoded.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(mp4_path),
                "-ac",
                "1",
                "-ar",
                "48000",
                "-sample_fmt",
                "s16",
                str(wav),
            ],
            check=True,
        )
        with wave.open(str(wav), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    win = int(48000 * window_s)
    n_win = max(1, len(samples) // win)
    blocks = samples[: n_win * win].reshape(n_win, win)
    rms = np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-12)
    dbs = 20.0 * np.log10(rms)
    # Ignore very last half-second fadeout window if slightly quieter
    interior = dbs[:-1] if len(dbs) > 2 else dbs
    gaps = [round(i * window_s, 2) for i, val in enumerate(interior) if float(val) < silence_db]
    return {
        "min_rms_db": round(float(np.min(interior)), 2),
        "median_rms_db": round(float(np.median(interior)), 2),
        "silence_gap_timestamps_s": gaps,
        "silence_gap_count": len(gaps),
    }


def run_episode_qa(
    brand: BrandConfig,
    mp4_path: Path,
    episode_dir: Path,
    with_reel_watch: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Execute full technical QA gate and save qa_report.json."""
    probe = _probe_video(mp4_path)
    loud = _measure_ebur128(mp4_path)
    rms = _scan_rms_gaps(mp4_path)

    vs = brand.video_spec
    min_d, max_d = vs.target_duration_sec
    violations: list[str] = []

    if (probe["width"], probe["height"]) != (vs.width, vs.height):
        violations.append(f"Resolution {probe['width']}x{probe['height']} != {vs.width}x{vs.height}")
    if abs(probe["fps"] - vs.fps) > 0.05:
        violations.append(f"FPS {probe['fps']} != {vs.fps}")
    if probe["pix_fmt"] != vs.pixel_format:
        violations.append(f"pix_fmt {probe['pix_fmt']} != {vs.pixel_format}")
    if probe["audio_codec"] != vs.audio_codec:
        violations.append(f"audio_codec {probe['audio_codec']} != {vs.audio_codec}")
    if probe["audio_sample_rate"] != vs.audio_sample_rate:
        violations.append(f"audio_sample_rate {probe['audio_sample_rate']} != {vs.audio_sample_rate}")
    if probe["audio_channels"] != vs.audio_channels:
        violations.append(f"audio_channels {probe['audio_channels']} != {vs.audio_channels}")
    if not (min_d <= probe["duration_s"] <= max_d):
        violations.append(f"Duration {probe['duration_s']}s outside [{min_d}, {max_d}]s")
    if abs(loud["integrated_lufs"] - vs.audio_lufs) > 1.2:
        violations.append(f"Loudness {loud['integrated_lufs']} LUFS too far from {vs.audio_lufs}")
    if loud["true_peak_dbtp"] > vs.audio_true_peak_max:
        violations.append(f"True peak {loud['true_peak_dbtp']} dBTP > {vs.audio_true_peak_max}")
    if loud["lra_lu"] > vs.audio_lra_max + 0.2:
        violations.append(f"LRA {loud['lra_lu']} LU > {vs.audio_lra_max}")
    if rms["silence_gap_count"] > 0:
        violations.append(f"Detected {rms['silence_gap_count']} silence gaps < -55 dB at {rms['silence_gap_timestamps_s']}")

    # Minimum Visual & Packaging Standards Check (QUALITY_STANDARDS.md)
    from PIL import Image

    visual_standards: dict[str, Any] = {}
    cover_path = episode_dir / "cover.png"
    grid_preview_path = episode_dir / "cover_grid_preview.png"
    if not cover_path.is_file():
        violations.append("Missing cover.png (required by QUALITY_STANDARDS.md)")
    else:
        with Image.open(cover_path) as cov:
            cw, ch = cov.size
            visual_standards["cover_size"] = [cw, ch]
            if (cw, ch) != (vs.width, vs.height):
                violations.append(f"Cover size {cw}x{ch} != {vs.width}x{vs.height}")
            crop_1x1 = np.asarray(cov.crop((0, 420, cw, 1500)).convert("RGB"), dtype=np.float32)
            crop_std = round(float(crop_1x1.std()), 2)
            visual_standards["cover_1x1_std"] = crop_std
            if crop_std < 12.0:
                violations.append(f"Cover 1:1 center crop looks blank/low-contrast (std={crop_std})")
    if not grid_preview_path.is_file():
        violations.append("Missing cover_grid_preview.png (required by QUALITY_STANDARDS.md)")

    script_path = episode_dir / "script.json"
    if script_path.is_file():
        script_raw = script_path.read_text(encoding="utf-8")
        for banned in ("DEG F", "(3 IN IN)"):
            if banned in script_raw:
                violations.append(f"Banned formatting token {banned!r} found in script.json")
        visual_standards["script_format_clean"] = True

    reel_watch_out: str | None = None
    if with_reel_watch:
        root = Path(repo_root) if repo_root else Path.cwd()
        reel_script = root / ".agents" / "skills" / "reel-watch" / "scripts" / "reel.py"
        res = subprocess.run(
            [
                "uv",
                "run",
                "--offline",
                "--with",
                "faster-whisper",
                "--with",
                "rapidocr",
                "--with",
                "onnxruntime",
                "--with",
                "imageio-ffmpeg",
                "python",
                str(reel_script),
                str(mp4_path),
                "--engine",
                "local",
                "--max-frames",
                "16",
                "--llm",
                "off",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        reel_watch_out = res.stdout.strip()

    report: dict[str, Any] = {
        "mp4_path": str(mp4_path),
        "passed": len(violations) == 0,
        "violations": violations,
        "ffprobe": probe,
        "ebur128": loud,
        "rms_scan": rms,
        "visual_standards": visual_standards,
        "reel_watch_stdout": reel_watch_out,
    }
    (episode_dir / "qa_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report
