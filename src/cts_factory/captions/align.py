"""Word-level caption alignment using faster-whisper (16kHz float32 numpy, no PyAV)."""

from __future__ import annotations

import difflib
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from cts_factory.config import (
    AudioTimeline,
    BrandConfig,
    CaptionBlock,
    CaptionTrack,
    CaptionWord,
    EpisodeScript,
)

_EMPHASIS_WORDS = frozenset(
    {
        "STOP",
        "SNAP",
        "SNAPPED",
        "ZERO",
        "NEVER",
        "IMPOSSIBLE",
        "GRAVITY",
        "BITE",
        "TIGHTER",
        "YES",
        "NO",
        "IMPLODE",
        "COLLAPSE",
        "CRUSHED",
        "ERASES",
        "FOUR",
        "HUNDRED",
        "TONS",
        "TWENTY",
        "MILLISECONDS",
        "TEN",
        "FASTER",
        "FIFTEEN",
        "PERCENT",
        "LOCK",
        "EIGHT",
        "TITANIUM",
        "CRACKS",
        "DIMPLE",
        "SNAPS",
    }
)


def _decode_to_16k_float32(wav_path: Path) -> np.ndarray:
    """Decode any WAV to 16 kHz mono float32 numpy array via ffmpeg (bypasses PyAV)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_wav = Path(tmpdir) / "audio_16k.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(wav_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-sample_fmt",
                "s16",
                str(out_wav),
            ],
            check=True,
        )
        with wave.open(str(out_wav), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
    return (np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0).copy()


def _norm_token(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def _is_emphasized(word: str) -> bool:
    clean = re.sub(r"[^A-Za-z0-9]", "", word)
    if not clean:
        return False
    if any(ch.isdigit() for ch in clean):
        return True
    return clean.upper() in _EMPHASIS_WORDS


def _reconcile_beat_words(
    canonical_tokens: list[str],
    whisper_words: list[tuple[str, float, float]],
    beat_start_s: float,
    beat_end_s: float,
) -> list[CaptionWord]:
    """Map actual Whisper word timestamps onto canonical script spellings for zero typos."""
    if not canonical_tokens:
        return []
    span = max(0.2, beat_end_s - beat_start_s)
    if not whisper_words:
        step = span / len(canonical_tokens)
        return [
            CaptionWord(
                text=tok,
                start_s=round(beat_start_s + i * step, 3),
                end_s=round(beat_start_s + (i + 1) * step, 3),
                emphasize=_is_emphasized(tok),
            )
            for i, tok in enumerate(canonical_tokens)
        ]

    c_norm = [_norm_token(t) for t in canonical_tokens]
    w_norm = [_norm_token(w[0]) for w in whisper_words]
    matcher = difflib.SequenceMatcher(None, c_norm, w_norm, autojunk=False)

    starts: list[float | None] = [None] * len(canonical_tokens)
    ends: list[float | None] = [None] * len(canonical_tokens)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                starts[i1 + k] = whisper_words[j1 + k][1]
                ends[i1 + k] = whisper_words[j1 + k][2]
        elif tag == "replace" and j2 > j1 and i2 > i1:
            seg_s = whisper_words[j1][1]
            seg_e = whisper_words[j2 - 1][2]
            seg_span = max(0.05, seg_e - seg_s)
            count = i2 - i1
            for k in range(count):
                starts[i1 + k] = seg_s + seg_span * (k / count)
                ends[i1 + k] = seg_s + seg_span * ((k + 1) / count)

    # Fill any unmatched canonical tokens cleanly by interpolating between neighbors
    n = len(canonical_tokens)
    i = 0
    while i < n:
        if starts[i] is not None:
            i += 1
            continue
        j = i
        while j < n and starts[j] is None:
            j += 1
        left_t = ends[i - 1] if i > 0 and ends[i - 1] is not None else beat_start_s
        right_t = starts[j] if j < n and starts[j] is not None else beat_end_s
        if right_t <= left_t:
            right_t = left_t + 0.08 * (j - i)
        gap = right_t - left_t
        for k in range(j - i):
            starts[i + k] = left_t + gap * (k / (j - i))
            ends[i + k] = left_t + gap * ((k + 1) / (j - i))
        i = j

    out: list[CaptionWord] = []
    prev_end = beat_start_s
    for idx, tok in enumerate(canonical_tokens):
        s = max(beat_start_s, float(starts[idx] or prev_end))
        e = max(s + 0.04, float(ends[idx] or (s + 0.15)))
        if s < prev_end:
            s = prev_end
            e = max(s + 0.04, e)
        prev_end = e
        out.append(
            CaptionWord(
                text=tok,
                start_s=round(s, 3),
                end_s=round(e, 3),
                emphasize=_is_emphasized(tok),
            )
        )
    return out


def _group_into_blocks(
    words: list[CaptionWord],
    min_words: int = 2,
    max_words: int = 4,
) -> list[CaptionBlock]:
    """Group aligned words into punchy 2-4 word blocks, breaking at punctuation."""
    blocks: list[CaptionBlock] = []
    buf: list[CaptionWord] = []

    def _flush() -> None:
        if not buf:
            return
        blocks.append(
            CaptionBlock(
                start_s=buf[0].start_s,
                end_s=max(buf[-1].end_s, buf[0].start_s + 0.12),
                words=list(buf),
            )
        )
        buf.clear()

    for w in words:
        buf.append(w)
        ends_sentence = w.text.rstrip().endswith((".", "?", "!", ";"))
        ends_clause = w.text.rstrip().endswith((",", "—", ":"))
        total_chars = sum(len(x.text) for x in buf) + max(0, len(buf) - 1)
        if len(buf) >= max_words or (ends_sentence and len(buf) >= 1) or (ends_clause and len(buf) >= min_words) or (total_chars >= 22 and len(buf) >= min_words):
            _flush()
    _flush()

    # Merge stray 1-word non-final blocks into neighbor if total <= max_words
    merged: list[CaptionBlock] = []
    for blk in blocks:
        if (
            len(blk.words) == 1
            and merged
            and len(merged[-1].words) < max_words
            and not merged[-1].words[-1].text.endswith((".", "?", "!"))
        ):
            merged[-1].words.extend(blk.words)
            merged[-1].end_s = blk.end_s
        else:
            merged.append(blk)

    # Ensure strictly monotonic non-overlapping block times
    for idx in range(len(merged) - 1):
        if merged[idx].end_s > merged[idx + 1].start_s:
            merged[idx].end_s = max(merged[idx].start_s + 0.05, merged[idx + 1].start_s)
    return merged


def align_episode_captions(
    brand: BrandConfig,
    script: EpisodeScript,
    timeline: AudioTimeline,
    episode_dir: Path,
    whisper_model: str = "base.en",
) -> CaptionTrack:
    """Run faster-whisper word alignment on narration_clean.wav and emit captions.json."""
    from faster_whisper import WhisperModel

    narration_wav = Path(timeline.narration_wav_path)
    audio_16k = _decode_to_16k_float32(narration_wav)

    model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        audio_16k,
        language="en",
        word_timestamps=True,
        vad_filter=False,
        beam_size=5,
        condition_on_previous_text=True,
    )

    all_whisper_words: list[tuple[str, float, float]] = []
    for seg in segments:
        for w in seg.words or []:
            tok = (w.word or "").strip()
            if tok:
                all_whisper_words.append((tok, float(w.start), float(w.end)))

    min_w, max_w = brand.retention_rules.caption_chunk_words
    beat_script_map = {b.id: b for b in script.beats}
    all_blocks: list[CaptionBlock] = []

    for bt in timeline.beats:
        beat = beat_script_map.get(bt.id)
        if beat is None:
            continue
        # Select Whisper words whose midpoint falls within this beat's span (with small tolerance)
        beat_w = [
            w
            for w in all_whisper_words
            if (bt.start_s - 0.12) <= 0.5 * (w[1] + w[2]) <= (bt.end_s + 0.12)
        ]
        canonical_tokens = beat.narration_text.strip().split()
        aligned_words = _reconcile_beat_words(
            canonical_tokens=canonical_tokens,
            whisper_words=beat_w,
            beat_start_s=bt.start_s,
            beat_end_s=bt.end_s,
        )
        beat_blocks = _group_into_blocks(aligned_words, min_words=min_w, max_words=max_w)
        all_blocks.extend(beat_blocks)

    # Guarantee strictly non-overlapping timestamps across beats
    for idx in range(len(all_blocks) - 1):
        if all_blocks[idx].end_s > all_blocks[idx + 1].start_s:
            all_blocks[idx].end_s = max(
                all_blocks[idx].start_s + 0.05, all_blocks[idx + 1].start_s
            )

    track = CaptionTrack(blocks=all_blocks)
    track.save(episode_dir / "captions.json")
    return track
