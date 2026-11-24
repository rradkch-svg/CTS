"""Gemini v1beta TTS narration synthesis with SHA-256 disk caching and soft silence trimming."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

from cts_factory.config import AudioBeatTiming, AudioTimeline, BrandConfig, EpisodeScript

TARGET_SR = 48000


def _load_api_key(repo_root: Path | None = None) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    candidates = [Path.cwd() / ".env"]
    if repo_root is not None:
        candidates.insert(0, Path(repo_root) / ".env")
    for env_file in candidates:
        if env_file.is_file():
            for raw_line in env_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "GEMINI_API_KEY":
                    cleaned = v.strip().strip('"').strip("'")
                    if cleaned:
                        return cleaned
    raise RuntimeError("GEMINI_API_KEY not found in environment or local .env file.")


def _read_wav_float(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())
    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM WAV in {path}, got sampwidth={sampwidth}")
    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, sr


def _write_wav_mono(path: Path, samples: np.ndarray, sr: int = TARGET_SR) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return path


def _decode_tts_bytes_to_48k_wav(raw_bytes: bytes, mime_type: str, out_wav: Path) -> Path:
    """Decode WAV or raw PCM (audio/L16) bytes from Gemini TTS to canonical 48 kHz mono 16-bit WAV."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_in = Path(tmpdir) / "tts_raw"
        if raw_bytes[:4] == b"RIFF":
            tmp_in = tmp_in.with_suffix(".wav")
            tmp_in.write_bytes(raw_bytes)
            cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(tmp_in),
                "-ac",
                "1",
                "-ar",
                str(TARGET_SR),
                "-sample_fmt",
                "s16",
                str(out_wav),
            ]
        else:
            rate_match = re.search(r"rate=(\d+)", mime_type or "")
            in_rate = int(rate_match.group(1)) if rate_match else 24000
            tmp_in = tmp_in.with_suffix(".pcm")
            tmp_in.write_bytes(raw_bytes)
            cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "s16le",
                "-ar",
                str(in_rate),
                "-ac",
                "1",
                "-i",
                str(tmp_in),
                "-ac",
                "1",
                "-ar",
                str(TARGET_SR),
                "-sample_fmt",
                "s16",
                str(out_wav),
            ]
        subprocess.run(cmd, check=True)
    return out_wav


def soft_trim_silence(
    samples: np.ndarray,
    sr: int = TARGET_SR,
    threshold_db: float = -52.0,
    head_pad_ms: int = 70,
    tail_pad_ms: int = 90,
) -> np.ndarray:
    """Trim leading/trailing dead silence softly without clipping final syllables."""
    if len(samples) == 0:
        return samples
    win = max(1, int(sr * 0.010))
    n_win = max(1, len(samples) // win)
    trimmed_len = n_win * win
    blocks = samples[:trimmed_len].reshape(n_win, win)
    rms = np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-12)
    db = 20.0 * np.log10(rms)
    active = np.where(db > threshold_db)[0]
    if len(active) == 0:
        return samples
    start_idx = max(0, int(active[0]) * win - int(sr * head_pad_ms / 1000.0))
    end_idx = min(len(samples), int(active[-1] + 1) * win + int(sr * tail_pad_ms / 1000.0))
    out = samples[start_idx:end_idx].copy()
    fade = min(int(sr * 0.008), len(out) // 4)
    if fade > 1:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        out[:fade] *= ramp
        out[-fade:] *= ramp[::-1]
    return out


def _apply_atempo(wav_path: Path, tempo: float) -> np.ndarray:
    """Time-stretch a mono 48kHz WAV slightly without pitch shift via ffmpeg atempo."""
    if abs(tempo - 1.0) < 0.005:
        samples, _ = _read_wav_float(wav_path)
        return samples
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "stretched.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(wav_path),
                "-filter:a",
                f"atempo={tempo:.4f}",
                "-ac",
                "1",
                "-ar",
                str(TARGET_SR),
                "-sample_fmt",
                "s16",
                str(out),
            ],
            check=True,
        )
        samples, _ = _read_wav_float(out)
        return samples


def _synthesize_beat_tts(
    client,
    models: list[str],
    voice: str,
    global_direction: str,
    beat_direction: str,
    narration_text: str,
    cache_wav: Path,
) -> Path:
    if cache_wav.is_file() and cache_wav.stat().st_size > 1000:
        return cache_wav

    from google.genai import types

    word_count = max(1, len(narration_text.split()))
    max_expected_s = max(11.0, word_count * 0.78 + 2.5)

    last_err: Exception | None = None
    for model in models:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=narration_text.strip(),
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice
                                )
                            )
                        ),
                    ),
                )
                candidates = getattr(resp, "candidates", None) or []
                if not candidates or not candidates[0].content or not candidates[0].content.parts:
                    raise RuntimeError(f"Empty audio response from {model}")
                audio_part = None
                for part in candidates[0].content.parts:
                    inline = getattr(part, "inline_data", None)
                    if inline is not None and getattr(inline, "data", None):
                        audio_part = inline
                        break
                if audio_part is None:
                    raise RuntimeError(f"No inline_data audio part returned by {model}")
                _decode_tts_bytes_to_48k_wav(
                    audio_part.data,
                    getattr(audio_part, "mime_type", "") or "",
                    cache_wav,
                )
                samples, sr = _read_wav_float(cache_wav)
                dur_s = len(samples) / float(sr)
                if dur_s > max_expected_s or dur_s < 0.8:
                    cache_wav.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"Anomalous TTS duration {dur_s:.2f}s for {word_count} words (max {max_expected_s:.2f}s)"
                    )
                return cache_wav
            except Exception as exc:
                last_err = exc
                msg = str(exc)
                if any(code in msg for code in ("404", "NOT_FOUND", "not found", "UNSUPPORTED", "RESOURCE_EXHAUSTED", "429")):
                    break
                time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"All Gemini TTS models failed ({models}): {last_err}")


def _split_batched_wav_into_beats(
    full_wav: Path,
    beats: list,
    out_paths: list[Path],
) -> None:
    """Use faster-whisper word timestamps to slice a single full-episode WAV cleanly into per-beat WAVs."""
    from faster_whisper import WhisperModel

    samples, sr = _read_wav_float(full_wav)
    total_s = len(samples) / float(sr)

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(full_wav), language="en", word_timestamps=True, vad_filter=False)
    words: list[tuple[str, float, float]] = []
    for seg in segments:
        for w in seg.words or []:
            tok = re.sub(r"[^a-z0-9]", "", (w.word or "").lower())
            if tok:
                words.append((tok, float(w.start), float(w.end)))

    # Greedy monotonic alignment of each beat's word count / anchor tokens onto Whisper word timeline
    beat_word_lists = [
        [re.sub(r"[^a-z0-9]", "", t.lower()) for t in b.narration_text.split() if re.sub(r"[^a-z0-9]", "", t.lower())]
        for b in beats
    ]
    total_target_words = max(1, sum(len(wl) for wl in beat_word_lists))

    # Build start/end timestamps per beat by matching anchor words around expected cumulative position
    boundaries: list[float] = [0.0]
    w_cursor = 0
    n_w = len(words)
    cum_target = 0
    for bi in range(len(beats) - 1):
        wl = beat_word_lists[bi]
        next_wl = beat_word_lists[bi + 1]
        cum_target += len(wl)
        est_idx = int(round((cum_target / float(total_target_words)) * n_w))
        lo = max(w_cursor + 2, est_idx - 7)
        hi = min(n_w - 2, est_idx + 7)
        best_idx = max(w_cursor + 1, min(n_w - 1, est_idx))
        best_score = -1.0
        tail_tok = wl[-1] if wl else ""
        head_tok = next_wl[0] if next_wl else ""
        head2_tok = next_wl[1] if len(next_wl) > 1 else ""
        for idx in range(lo, hi + 1):
            score = 0.0
            if tail_tok and words[idx - 1][0] == tail_tok:
                score += 3.0
            if head_tok and words[idx][0] == head_tok:
                score += 3.0
            if head2_tok and idx + 1 < n_w and words[idx + 1][0] == head2_tok:
                score += 1.5
            # Slight preference for longer natural pause gap between words
            gap = max(0.0, words[idx][1] - words[idx - 1][2])
            score += min(1.5, gap * 2.5)
            score -= abs(idx - est_idx) * 0.08
            if score > best_score:
                best_score = score
                best_idx = idx
        w_cursor = best_idx
        cut_s = 0.5 * (words[best_idx - 1][2] + words[best_idx][1])
        boundaries.append(max(boundaries[-1] + 0.5, min(total_s - 0.5, cut_s)))
    boundaries.append(total_s)

    for bi, out_wav in enumerate(out_paths):
        i0 = max(0, int(round(boundaries[bi] * sr)))
        i1 = min(len(samples), int(round(boundaries[bi + 1] * sr)))
        if i1 - i0 < int(0.4 * sr):
            raise RuntimeError(f"Batched TTS slice too short for beat {beats[bi].id}: {(i1 - i0) / sr:.2f}s")
        _write_wav_mono(out_wav, samples[i0:i1], sr)


def _synthesize_episode_batched_tts(
    client,
    models: list[str],
    voice: str,
    beats: list,
    out_paths: list[Path],
    cache_dir: Path,
) -> None:
    """Synthesize an entire episode in 1 Gemini TTS API call and slice cleanly into beat WAVs."""
    from google.genai import types

    full_text = "\n\n".join(b.narration_text.strip() for b in beats)
    batch_digest = hashlib.sha256(f"v2_batch|{voice}|{full_text}".encode("utf-8")).hexdigest()[:12]
    batch_wav = cache_dir / f"_episode_batch_{batch_digest}.wav"

    if not (batch_wav.is_file() and batch_wav.stat().st_size > 10000):
        candidate_models = list(models)
        if "gemini-2.5-pro-preview-tts" not in candidate_models:
            candidate_models.append("gemini-2.5-pro-preview-tts")
        last_err: Exception | None = None
        synthesized = False
        for model in candidate_models:
            for attempt in range(2):
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=full_text,
                        config=types.GenerateContentConfig(
                            response_modalities=["AUDIO"],
                            speech_config=types.SpeechConfig(
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=voice
                                    )
                                )
                            ),
                        ),
                    )
                    candidates = getattr(resp, "candidates", None) or []
                    if not candidates or not candidates[0].content or not candidates[0].content.parts:
                        raise RuntimeError(f"Empty audio response from {model}")
                    audio_part = None
                    for part in candidates[0].content.parts:
                        inline = getattr(part, "inline_data", None)
                        if inline is not None and getattr(inline, "data", None):
                            audio_part = inline
                            break
                    if audio_part is None:
                        raise RuntimeError(f"No inline_data audio part returned by {model}")
                    _decode_tts_bytes_to_48k_wav(
                        audio_part.data,
                        getattr(audio_part, "mime_type", "") or "",
                        batch_wav,
                    )
                    samples, sr = _read_wav_float(batch_wav)
                    dur_s = len(samples) / float(sr)
                    if dur_s < 40.0 or dur_s > 120.0:
                        batch_wav.unlink(missing_ok=True)
                        raise RuntimeError(f"Anomalous batched TTS duration {dur_s:.2f}s from {model}")
                    synthesized = True
                    break
                except Exception as exc:
                    last_err = exc
                    msg = str(exc)
                    if any(code in msg for code in ("404", "NOT_FOUND", "not found", "UNSUPPORTED", "RESOURCE_EXHAUSTED", "429")):
                        break
                    time.sleep(2.0 * (attempt + 1))
            if synthesized:
                break
        if not synthesized:
            raise RuntimeError(f"All Gemini TTS models failed ({candidate_models}): {last_err}")

    _split_batched_wav_into_beats(batch_wav, beats, out_paths)


def synthesize_narration(
    brand: BrandConfig,
    script: EpisodeScript,
    episode_dir: Path,
    repo_root: Path | None = None,
) -> AudioTimeline:
    """Synthesize all beats, soft-trim silence, fit inside 65-80s window, and save timeline."""
    from google import genai
    from google.genai import types

    api_key = _load_api_key(repo_root)
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version=brand.narration.api_version),
    )

    cache_dir = episode_dir / "cache" / "tts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    voice = brand.narration.voice
    models = list(brand.narration.models)
    global_dir = brand.narration.style_direction

    cache_paths: list[Path] = []
    for beat in script.beats:
        key_payload = "|".join(
            [
                "v2_pure_text",
                voice,
                beat.narration_text.strip(),
                ",".join(models),
            ]
        )
        digest = hashlib.sha256(key_payload.encode("utf-8")).hexdigest()[:12]
        cache_paths.append(cache_dir / f"{beat.id}_{digest}.wav")

    # If multiple beats are uncached, synthesize the entire episode in 1 Gemini TTS API call (12x quota efficiency!)
    missing = [p for p in cache_paths if not (p.is_file() and p.stat().st_size > 1000)]
    if len(missing) >= 2:
        _synthesize_episode_batched_tts(
            client=client,
            models=models,
            voice=voice,
            beats=script.beats,
            out_paths=cache_paths,
            cache_dir=cache_dir,
        )

    raw_beats: list[tuple[str, str, Path, np.ndarray, float]] = []
    for beat, cache_wav in zip(script.beats, cache_paths):
        _synthesize_beat_tts(
            client=client,
            models=models,
            voice=voice,
            global_direction=global_dir,
            beat_direction=beat.voice_direction,
            narration_text=beat.narration_text,
            cache_wav=cache_wav,
        )
        samples, sr = _read_wav_float(cache_wav)
        if sr != TARGET_SR:
            raise ValueError(f"Unexpected sample rate {sr} in {cache_wav}")
        trimmed = soft_trim_silence(
            samples,
            sr=TARGET_SR,
            threshold_db=brand.narration.silence_trim_db,
            head_pad_ms=brand.narration.silence_head_pad_ms,
            tail_pad_ms=brand.narration.silence_tail_pad_ms,
        )
        # Peak normalize each beat gently to -3 dBFS so voice stays consistent across beats
        peak = float(np.max(np.abs(trimmed))) if len(trimmed) else 0.0
        if peak > 1e-4:
            trimmed = trimmed * (0.7079 / peak)
        raw_beats.append((beat.id, beat.narration_text, cache_wav, trimmed, beat.pause_after_s))

    # Calculate raw duration and calibrate pauses / subtle tempo to hit 66.5..76.5s cleanly
    min_dur, max_dur = brand.video_spec.target_duration_sec
    target_low = max(float(min_dur) + 1.5, 66.5)
    target_high = min(float(max_dur) - 2.5, 77.5)
    lead_in_s = 0.05  # Immediate Frame 0 hook onset!
    tail_hold_s = 0.75

    speech_s = sum(len(b[3]) / TARGET_SR for b in raw_beats)
    pauses_s = sum(b[4] for b in raw_beats)
    raw_total_s = lead_in_s + speech_s + pauses_s + tail_hold_s

    pause_scale = 1.0
    tempo_factor = 1.0
    if raw_total_s < target_low:
        # First slow down slightly (0.94..1.0) and breathe pauses naturally to hit >= 67s
        needed = target_low - raw_total_s
        max_pause_add = min(needed, len(raw_beats) * 0.45)
        if pauses_s > 0:
            pause_scale = (pauses_s + max_pause_add) / pauses_s
        remaining = target_low - (lead_in_s + speech_s + pauses_s * pause_scale + tail_hold_s)
        if remaining > 0.1 and speech_s > 0:
            desired_speech = speech_s + remaining
            tempo_factor = max(0.88, min(1.0, speech_s / desired_speech))
    elif raw_total_s > target_high:
        # Speed up gently within 1.0..1.08 range
        desired_speech = max(45.0, target_high - lead_in_s - pauses_s - tail_hold_s)
        tempo_factor = min(1.08, max(1.0, speech_s / desired_speech))

    chunks: list[np.ndarray] = [np.zeros(int(lead_in_s * TARGET_SR), dtype=np.float32)]
    cursor = len(chunks[0])
    beat_timings: list[AudioBeatTiming] = []

    for beat_id, narration_text, cache_wav, trimmed, pause_after_s in raw_beats:
        if abs(tempo_factor - 1.0) >= 0.005:
            stretched_wav = cache_dir / f"{beat_id}_tmp_trim.wav"
            _write_wav_mono(stretched_wav, trimmed, TARGET_SR)
            beat_audio = _apply_atempo(stretched_wav, tempo_factor)
            stretched_wav.unlink(missing_ok=True)
        else:
            beat_audio = trimmed

        start_s = cursor / TARGET_SR
        chunks.append(beat_audio)
        cursor += len(beat_audio)
        end_s = cursor / TARGET_SR

        pause_len = int(round(pause_after_s * pause_scale * TARGET_SR))
        if pause_len > 0:
            chunks.append(np.zeros(pause_len, dtype=np.float32))
            cursor += pause_len

        beat_timings.append(
            AudioBeatTiming(
                id=beat_id,
                start_s=round(start_s, 4),
                end_s=round(end_s, 4),
                wav_path=str(cache_wav),
                narration_text=narration_text,
            )
        )

    # Ensure total duration is strictly inside [min_dur + 1.0, max_dur - 1.0]
    current_s = cursor / TARGET_SR
    extra_tail_s = max(tail_hold_s, target_low - current_s) if current_s + tail_hold_s < target_low else tail_hold_s
    chunks.append(np.zeros(int(round(extra_tail_s * TARGET_SR)), dtype=np.float32))

    narration_full = np.concatenate(chunks)
    total_duration_s = round(len(narration_full) / TARGET_SR, 4)

    narration_wav = episode_dir / "narration_clean.wav"
    _write_wav_mono(narration_wav, narration_full, TARGET_SR)

    # Compute 30 fps RMS envelope for reactive animation
    fps = brand.video_spec.fps
    num_frames = int(round(total_duration_s * fps))
    spf = TARGET_SR // fps
    env = np.zeros(num_frames, dtype=np.float32)
    for idx in range(num_frames):
        s0 = idx * spf
        s1 = min(len(narration_full), s0 + spf)
        if s1 > s0:
            seg = narration_full[s0:s1]
            env[idx] = float(np.sqrt(np.mean(seg * seg)))
    max_env = float(np.max(env)) if len(env) else 1.0
    if max_env > 1e-6:
        env = np.clip(env / max_env, 0.0, 1.0)
    envelope_path = episode_dir / "narration_envelope.npy"
    np.save(envelope_path, env)

    timeline = AudioTimeline(
        total_duration_s=total_duration_s,
        sample_rate_hz=TARGET_SR,
        beats=beat_timings,
        narration_wav_path=str(narration_wav),
        master_wav_path=str(episode_dir / "audio_master.wav"),
        envelope_path=str(envelope_path),
    )
    timeline.save(episode_dir / "narration_timeline.json")
    return timeline
