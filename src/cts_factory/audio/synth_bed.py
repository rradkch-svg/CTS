"""Continuous stereo ambient documentary music bed & procedural mechanical SFX engine."""

from __future__ import annotations

import math

import numpy as np

from cts_factory.config import AudioTimeline, EpisodeScript

TARGET_SR = 48000


def _lowpass_simple(sig: np.ndarray, cutoff_hz: float, sr: int = TARGET_SR) -> np.ndarray:
    """Fast 1-pole exponential moving average lowpass filter."""
    rc = 1.0 / (2.0 * math.pi * max(cutoff_hz, 20.0))
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    out = np.empty_like(sig)
    # Vectorized via chunked IIR or FFT filter for speed & precision
    freqs = np.fft.rfftfreq(len(sig), d=1.0 / sr)
    H = 1.0 / np.sqrt(1.0 + (freqs / max(cutoff_hz, 20.0)) ** 4)
    out = np.fft.irfft(np.fft.rfft(sig) * H, n=len(sig)).astype(np.float32)
    return out


def _bandpass_fft(sig: np.ndarray, low_hz: float, high_hz: float, sr: int = TARGET_SR) -> np.ndarray:
    freqs = np.fft.rfftfreq(len(sig), d=1.0 / sr)
    hp = (freqs / max(low_hz, 10.0)) ** 2 / np.sqrt(1.0 + (freqs / max(low_hz, 10.0)) ** 4)
    lp = 1.0 / np.sqrt(1.0 + (freqs / max(high_hz, low_hz + 50.0)) ** 4)
    return np.fft.irfft(np.fft.rfft(sig) * hp * lp, n=len(sig)).astype(np.float32)


def generate_ambient_bed(
    duration_s: float,
    bpm: int = 104,
    mood: str = "mechanical",
    sr: int = TARGET_SR,
) -> np.ndarray:
    """Generate a continuous, rich stereo ambient documentary bed (shape: [N, 2], float32).

    Ensures zero dead silence (-60 dB) anywhere across the entire episode while remaining
    dark, modern, non-distracting, and dynamically escalating toward the climax.
    """
    n = int(round(duration_s * sr))
    t = np.arange(n, dtype=np.float32) / sr
    rng = np.random.default_rng(42 if mood == "mechanical" else 137)

    # Root fundamental (D minor / F# minor industrial documentary feel)
    f0 = 55.0 if mood == "mechanical" else 46.25  # A1 or F#1
    fifth = f0 * 1.5
    minor_third = f0 * 1.1892
    octave = f0 * 2.0

    # Slow cinematic swell across the episode (escalating into climax around 60-85%)
    arc = 0.65 + 0.35 * np.sin(np.pi * np.clip(t / max(duration_s, 1.0), 0.0, 1.0)) ** 1.3
    lfo = 0.5 + 0.5 * np.sin(2.0 * np.pi * 0.14 * t)

    # Warm stereo sub + pad harmonics (slight detune between L/R for width)
    pad_l = (
        0.38 * np.sin(2.0 * np.pi * f0 * t)
        + 0.22 * np.sin(2.0 * np.pi * (octave * 1.002) * t + 0.4)
        + 0.16 * np.sin(2.0 * np.pi * (fifth * 0.998) * t + 1.1) * (0.6 + 0.4 * lfo)
        + 0.11 * np.sin(2.0 * np.pi * (minor_third * 2.001) * t) * arc
    )
    pad_r = (
        0.38 * np.sin(2.0 * np.pi * (f0 * 1.0015) * t + 0.15)
        + 0.22 * np.sin(2.0 * np.pi * (octave * 0.998) * t + 1.3)
        + 0.16 * np.sin(2.0 * np.pi * (fifth * 1.002) * t + 0.2) * (0.6 + 0.4 * (1.0 - lfo))
        + 0.11 * np.sin(2.0 * np.pi * (minor_third * 1.998) * t + 0.7) * arc
    )

    # Subtle rhythmic documentary pulse synced to BPM (tight low-mid pulse, never muddy)
    beat_hz = bpm / 60.0
    beat_phase = (t * beat_hz) % 1.0
    sub_pulse = np.exp(-beat_phase * 9.0) * np.sin(2.0 * np.pi * (f0 * 1.5) * t) * 0.20 * arc

    # Soft precision tick on off-beats (gives hypnotic mechanical/telemetry forward momentum)
    eighth_phase = (t * beat_hz * 2.0) % 1.0
    tick_env = np.exp(-eighth_phase * 55.0)
    noise_tick = _bandpass_fft(rng.standard_normal(n).astype(np.float32), 2200.0, 5200.0, sr)
    tick_l = tick_env * noise_tick * 0.045 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 0.25 * t))
    tick_r = tick_env * noise_tick * 0.045 * (0.5 - 0.5 * np.sin(2.0 * np.pi * 0.25 * t))

    # Subtle continuous air/room texture floor so RMS never collapses
    room_l = _bandpass_fft(rng.standard_normal(n).astype(np.float32), 180.0, 900.0, sr) * 0.04
    room_r = _bandpass_fft(rng.standard_normal(n).astype(np.float32), 180.0, 900.0, sr) * 0.04

    left = _lowpass_simple((pad_l + sub_pulse).astype(np.float32), 680.0, sr) + tick_l + room_l
    right = _lowpass_simple((pad_r + sub_pulse).astype(np.float32), 680.0, sr) + tick_r + room_r

    stereo = np.stack([left, right], axis=1).astype(np.float32)

    # Gentle fade-in (150ms) and fade-out (400ms)
    fi = min(int(sr * 0.15), n // 10)
    fo = min(int(sr * 0.40), n // 6)
    if fi > 1:
        stereo[:fi] *= np.linspace(0.25, 1.0, fi, dtype=np.float32)[:, None]
    if fo > 1:
        stereo[-fo:] *= np.linspace(1.0, 0.15, fo, dtype=np.float32)[:, None]

    # Normalize bed RMS to ~ -22 dBFS so mixer can scale cleanly
    rms = float(np.sqrt(np.mean(stereo * stereo) + 1e-12))
    if rms > 1e-6:
        stereo = stereo * (0.08 / rms)
    return np.clip(stereo, -0.9, 0.9)


def synthesize_sfx(name: str, sr: int = TARGET_SR) -> np.ndarray:
    """Synthesize a crisp procedural mono SFX clip (float32, peak ~0.85)."""
    rng = np.random.default_rng(abs(hash(name)) % (2**32))

    if name == "cable_snap":
        dur = 0.55
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        whip = rng.standard_normal(len(t)).astype(np.float32) * np.exp(-t * 38.0)
        whip = _bandpass_fft(whip, 1400.0, 7500.0, sr) * 1.4
        twang = (
            np.sin(2.0 * np.pi * (420.0 * np.exp(-t * 2.5) + 130.0) * t) * np.exp(-t * 9.0)
            + 0.5 * np.sin(2.0 * np.pi * 1180.0 * t) * np.exp(-t * 15.0)
        )
        sig = whip + 0.7 * twang
    elif name == "alarm_ping":
        dur = 0.45
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        sig = (
            0.7 * np.sin(2.0 * np.pi * 1320.0 * t)
            + 0.4 * np.sin(2.0 * np.pi * 1980.0 * t)
        ) * np.exp(-t * 8.5)
    elif name == "whoosh_cut":
        dur = 0.35
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        env = np.sin(np.pi * t / dur) ** 1.6
        sig = _bandpass_fft(rng.standard_normal(len(t)).astype(np.float32), 250.0, 2600.0, sr) * env
    elif name in ("wedge_lock_slam", "implosion_thud"):
        dur = 0.75
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        f_drop = 140.0 * np.exp(-t * 14.0) + (38.0 if name == "implosion_thud" else 52.0)
        sub = np.sin(2.0 * np.pi * np.cumsum(f_drop) / sr) * np.exp(-t * 6.5)
        crack = _bandpass_fft(rng.standard_normal(len(t)).astype(np.float32), 600.0, 5000.0, sr) * np.exp(-t * 28.0)
        ring = np.sin(2.0 * np.pi * 760.0 * t) * np.exp(-t * 16.0) * (0.4 if name == "wedge_lock_slam" else 0.15)
        sig = 1.2 * sub + 0.8 * crack + ring
    elif name == "ui_tick":
        dur = 0.08
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        sig = (
            np.sin(2.0 * np.pi * 2400.0 * t) + 0.5 * np.sin(2.0 * np.pi * 4100.0 * t)
        ) * np.exp(-t * 65.0)
    elif name == "metal_clank":
        dur = 0.42
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        partials = [520.0, 910.0, 1480.0, 2310.0]
        sig = sum(
            (0.6 ** i) * np.sin(2.0 * np.pi * f * t) * np.exp(-t * (10.0 + i * 5.0))
            for i, f in enumerate(partials)
        )
        sig += _bandpass_fft(rng.standard_normal(len(t)).astype(np.float32), 1200.0, 6000.0, sr) * np.exp(-t * 45.0)
    elif name == "servo_hum":
        dur = 0.90
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        env = np.sin(np.pi * t / dur) ** 0.7
        sig = (
            0.6 * np.sin(2.0 * np.pi * (180.0 + 35.0 * t) * t)
            + 0.3 * np.sin(2.0 * np.pi * (360.0 + 70.0 * t) * t)
        ) * env
    elif name == "gear_ratchet":
        dur = 0.70
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        clicks = np.zeros_like(t)
        for i in range(9):
            pos = int((0.03 + i * 0.068) * sr)
            if pos + 600 < len(t):
                ct = np.arange(600, dtype=np.float32) / sr
                clicks[pos : pos + 600] += np.sin(2.0 * np.pi * (1600.0 + i * 90.0) * ct) * np.exp(-ct * 90.0)
        sig = clicks
    elif name == "friction_screech":
        dur = 0.70
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        env = np.exp(-t * 3.5) * np.minimum(1.0, t / 0.05)
        raw = rng.standard_normal(len(t)).astype(np.float32)
        sig = (
            _bandpass_fft(raw, 2200.0, 4400.0, sr) * 0.7
            + 0.35 * np.sin(2.0 * np.pi * (2850.0 - 400.0 * t) * t)
        ) * env
    elif name == "hydraulic_hiss":
        dur = 0.85
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        env = np.minimum(1.0, t / 0.08) * np.exp(-t * 2.8)
        sig = _bandpass_fft(rng.standard_normal(len(t)).astype(np.float32), 1100.0, 5800.0, sr) * env
    elif name == "deep_sonar_pulse":
        dur = 1.2
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        sig = (
            np.sin(2.0 * np.pi * 660.0 * t) * np.exp(-t * 3.4)
            + 0.35 * np.sin(2.0 * np.pi * 1320.0 * t) * np.exp(-t * 6.0)
        )
    elif name == "pressure_rumble":
        dur = 1.4
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        env = np.sin(np.pi * t / dur) ** 0.8
        raw = rng.standard_normal(len(t)).astype(np.float32)
        sig = (
            _bandpass_fft(raw, 30.0, 140.0, sr) * 1.4
            + 0.45 * np.sin(2.0 * np.pi * 48.0 * t)
        ) * env
    elif name == "hull_creak":
        dur = 0.95
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        env = np.sin(np.pi * t / dur) ** 0.9
        freq = 140.0 + 40.0 * np.sin(2.0 * np.pi * 3.2 * t)
        sig = (
            0.7 * np.sin(2.0 * np.pi * np.cumsum(freq) / sr)
            + 0.4 * np.sin(2.0 * np.pi * np.cumsum(freq * 2.13) / sr)
        ) * env
    elif name == "glass_crack":
        dur = 0.32
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        sig = np.zeros_like(t)
        for offset in (0.0, 0.055, 0.13):
            pos = int(offset * sr)
            seg_len = min(len(t) - pos, int(0.14 * sr))
            if seg_len > 10:
                ct = np.arange(seg_len, dtype=np.float32) / sr
                burst = _bandpass_fft(rng.standard_normal(seg_len).astype(np.float32), 2800.0, 9500.0, sr)
                sig[pos : pos + seg_len] += burst * np.exp(-ct * 48.0)
    else:
        dur = 0.25
        t = np.arange(int(sr * dur), dtype=np.float32) / sr
        sig = np.sin(2.0 * np.pi * 880.0 * t) * np.exp(-t * 16.0)

    sig = sig.astype(np.float32)
    peak = float(np.max(np.abs(sig))) if len(sig) else 0.0
    if peak > 1e-6:
        sig = sig * (0.85 / peak)
    return sig


def render_sfx_track(
    script: EpisodeScript,
    timeline: AudioTimeline,
    sr: int = TARGET_SR,
) -> np.ndarray:
    """Render all declarative beat SFX cues onto a stereo 48 kHz track."""
    total_samples = int(round(timeline.total_duration_s * sr))
    track = np.zeros((total_samples, 2), dtype=np.float32)
    timing_map = {b.id: b for b in timeline.beats}
    sfx_cache: dict[str, np.ndarray] = {}

    for beat in script.beats:
        bt = timing_map.get(beat.id)
        if bt is None:
            continue
        for cue in beat.sfx_cues:
            if cue.name not in sfx_cache:
                sfx_cache[cue.name] = synthesize_sfx(cue.name, sr=sr)
            clip = sfx_cache[cue.name]
            gain = 10.0 ** (cue.gain_db / 20.0) * 0.45
            pan = max(-1.0, min(1.0, cue.pan))
            left_g = gain * math.sqrt(0.5 * (1.0 - pan))
            right_g = gain * math.sqrt(0.5 * (1.0 + pan))

            start_idx = int(round((bt.start_s + cue.offset_s) * sr))
            if start_idx >= total_samples or start_idx < 0:
                continue
            end_idx = min(total_samples, start_idx + len(clip))
            seg = clip[: end_idx - start_idx]
            track[start_idx:end_idx, 0] += seg * left_g
            track[start_idx:end_idx, 1] += seg * right_g

    return np.clip(track, -0.95, 0.95)
