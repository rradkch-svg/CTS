"""Sidechain-ducked stereo mixing and 2-pass ffmpeg broadcast loudness mastering."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from cts_factory.audio.synth_bed import generate_ambient_bed, render_sfx_track
from cts_factory.audio.tts import TARGET_SR, _read_wav_float, synthesize_narration
from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript


def _write_wav_stereo(path: Path, stereo: np.ndarray, sr: int = TARGET_SR) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(stereo, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return path


def _compute_sidechain_duck(voice_mono: np.ndarray, sr: int = TARGET_SR) -> np.ndarray:
    """Compute smooth sidechain gain curve (0.48 during speech, 1.0 during pauses)."""
    win = int(sr * 0.05)  # 50ms window
    n = len(voice_mono)
    n_blocks = max(1, (n + win - 1) // win)
    padded = np.pad(voice_mono, (0, n_blocks * win - n))
    rms = np.sqrt(np.mean(padded.reshape(n_blocks, win) ** 2, axis=1) + 1e-12)
    speaking = (rms > 0.018).astype(np.float32)

    # Smooth attack/release across blocks
    smooth = np.empty_like(speaking)
    val = 0.0
    for i, s in enumerate(speaking):
        alpha = 0.45 if s > val else 0.14
        val = val + alpha * (s - val)
        smooth[i] = val

    block_gains = 1.0 - 0.52 * smooth  # ducks to 0.48 during speech, rises to 1.0 in pauses
    x_blocks = np.linspace(0.0, n - 1, n_blocks, dtype=np.float32)
    x_full = np.arange(n, dtype=np.float32)
    return np.interp(x_full, x_blocks, block_gains).astype(np.float32)


def _master_two_pass_loudnorm(
    in_wav: Path,
    out_wav: Path,
    target_i: float = -14.5,
    target_tp: float = -1.5,
    target_lra: float = 3.5,
) -> dict[str, float]:
    """Run 2-pass ffmpeg loudnorm targeting exact LUFS / TP / LRA specs."""
    # Pass 1: measure
    cmd_p1 = [
        "ffmpeg",
        "-y",
        "-i",
        str(in_wav),
        "-af",
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
        "-f",
        "null",
        "-",
    ]
    res1 = subprocess.run(cmd_p1, capture_output=True, text=True, check=True)
    m = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", res1.stderr)
    if not m:
        raise RuntimeError(f"loudnorm pass 1 failed to output JSON stats:\n{res1.stderr[-600:]}")
    stats = json.loads(m.group(0))

    # Pass 2: linear normalization with measured stats + gentle brickwall limiter
    af = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
        f":measured_I={stats['input_i']}"
        f":measured_TP={stats['input_tp']}"
        f":measured_LRA={stats['input_lra']}"
        f":measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}"
        f":linear=true:print_format=json"
    )
    cmd_p2 = [
        "ffmpeg",
        "-y",
        "-i",
        str(in_wav),
        "-af",
        af,
        "-ar",
        str(TARGET_SR),
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        str(out_wav),
    ]
    res2 = subprocess.run(cmd_p2, capture_output=True, text=True, check=True)
    m2 = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", res2.stderr)
    out_stats = json.loads(m2.group(0)) if m2 else {}
    return {
        "output_i": float(out_stats.get("output_i", target_i)),
        "output_tp": float(out_stats.get("output_tp", target_tp)),
        "output_lra": float(out_stats.get("output_lra", target_lra)),
    }


def mix_and_master_audio(
    brand: BrandConfig,
    script: EpisodeScript,
    timeline: AudioTimeline,
    episode_dir: Path,
) -> tuple[Path, dict[str, float]]:
    """Mix narration + ducked ambient bed + SFX cues and master via 2-pass loudnorm."""
    narration_mono, sr = _read_wav_float(Path(timeline.narration_wav_path))
    if sr != TARGET_SR:
        raise ValueError(f"Expected {TARGET_SR} Hz narration, got {sr}")

    mood = "underwater" if "submersible" in script.slug or "ocean" in script.slug else "mechanical"
    bed = generate_ambient_bed(
        duration_s=len(narration_mono) / TARGET_SR,
        bpm=script.bpm,
        mood=mood,
        sr=TARGET_SR,
    )
    # Match exact sample count
    n = len(narration_mono)
    if len(bed) < n:
        bed = np.pad(bed, ((0, n - len(bed)), (0, 0)))
    else:
        bed = bed[:n]

    sfx = render_sfx_track(script, timeline, sr=TARGET_SR)
    if len(sfx) < n:
        sfx = np.pad(sfx, ((0, n - len(sfx)), (0, 0)))
    else:
        sfx = sfx[:n]

    duck = _compute_sidechain_duck(narration_mono, sr=TARGET_SR)[:, None]
    voice_stereo = np.stack([narration_mono, narration_mono], axis=1)

    # Mix balance: crisp foreground narration + continuous warm ambient bed + punchy SFX
    mixed = voice_stereo * 0.92 + bed * duck * 0.62 + sfx * 0.65
    # Gentle soft-clip protection before loudnorm
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.95:
        mixed = mixed * (0.95 / peak)

    master_wav = episode_dir / "audio_master.wav"
    with tempfile.TemporaryDirectory() as tmpdir:
        pre_wav = Path(tmpdir) / "pre_master.wav"
        _write_wav_stereo(pre_wav, mixed, TARGET_SR)
        stats = _master_two_pass_loudnorm(
            pre_wav,
            master_wav,
            target_i=brand.video_spec.audio_lufs,
            target_tp=min(brand.video_spec.audio_true_peak_max - 0.4, -1.4),
            target_lra=min(brand.video_spec.audio_lra_max - 0.5, 3.5),
        )

    timeline.master_wav_path = str(master_wav)
    timeline.save(episode_dir / "narration_timeline.json")
    return master_wav, stats


def build_episode_audio(
    brand: BrandConfig,
    script: EpisodeScript,
    episode_dir: Path,
    repo_root: Path | None = None,
) -> tuple[AudioTimeline, dict[str, float]]:
    """Run full audio pipeline: Gemini TTS -> trim/timeline -> ambient+SFX mix -> loudnorm master."""
    timeline = synthesize_narration(brand, script, episode_dir, repo_root=repo_root)
    _, stats = mix_and_master_audio(brand, script, timeline, episode_dir)
    return timeline, stats
