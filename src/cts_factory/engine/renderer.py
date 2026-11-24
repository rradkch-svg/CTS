"""Single-process Pillow 2.5D renderer piped directly to ffmpeg (1080x1920, 30 fps, H.264/AAC)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from cts_factory.captions.overlay import draw_caption
from cts_factory.config import AudioTimeline, BrandConfig, CaptionTrack, EpisodeScript
from cts_factory.engine.materials import Palette
from cts_factory.engine.primitives import draw_brand_header, draw_hud_callout, draw_top_hook
from cts_factory.episodes.base import EpisodeScene

_SAFE_BADGE_TOKENS = (
    "SAFE", "PASSED", "PROTECTED", "FLYABLE", "CUSHION", "AIR MIX",
    "SMART FIX", "MODERN FIX", "UPGRADE", "LIMITED SLIP", "PASSIVE",
    "PARACHUTE", "SPLASHDOWN", "KEVLAR", "CATCH", "CONSERVED",
    "OTIS", "150+", "RE-CHECK", "NEW RULE", "NEAR ZERO", "ZERO FRICTION",
    "ZERO POWER", "SPRING CLAMP", "IMPOSSIBLE", "50/50", "UNIFORM",
)
_DANGER_BADGE_TOKENS = (
    "FAILURE", "CRATER", "FLAW", "TRAP", "BLACKOUT", "WORST",
    "BLADE-OFF", "200%", "PEEL", "SNAPPED", "IMPLOSION", "SPIKE",
    "ZIPPER", "RUNAWAY", "45 DEG", "45°", "3,000+", "DAMAGE", "STUCK",
    "DELAMINATION", "DIMPLE", "BUCKLING", "0.02", "400 TONS", "OVERSPEED",
)


def resolve_callout_accent(act: str, label: str, value: str, palette: Palette) -> tuple[int, int, int]:
    """Enforce semantic HUD badge coloring: safe/CTA -> emerald, failure/climax -> danger, telemetry -> cyan."""
    tag_up = f"{label} {value}".upper()
    if act == "cta" or any(tok in tag_up for tok in _SAFE_BADGE_TOKENS):
        return palette.emerald
    if act in ("escalation", "climax") or any(tok in tag_up for tok in _DANGER_BADGE_TOKENS):
        return palette.danger
    return palette.cyan


def render_episode_video(
    brand: BrandConfig,
    script: EpisodeScript,
    timeline: AudioTimeline,
    captions: CaptionTrack,
    scene: EpisodeScene,
    out_mp4: Path,
    draft: bool = False,
    repo_root: Path | None = None,
) -> dict[str, float]:
    """Stream 1080x1920 RGB24 frames directly to ffmpeg and mux mastered 48 kHz AAC audio."""
    width = brand.video_spec.width
    height = brand.video_spec.height
    fps = brand.video_spec.fps
    total_frames = int(round(timeline.total_duration_s * fps))
    palette = Palette.from_brand(brand)

    scene.prepare(brand, script, timeline)

    env_path = Path(timeline.envelope_path)
    if env_path.is_file():
        envelope = np.load(env_path)
    else:
        envelope = np.zeros(total_frames, dtype=np.float32)

    beat_script_map = {b.id: b for b in script.beats}
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    preset = "ultrafast" if draft else "fast"
    crf = str(brand.video_spec.video_crf + (4 if draft else 0))

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-i",
        str(timeline.master_wav_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        brand.video_spec.video_codec,
        "-preset",
        preset,
        "-crf",
        crf,
        "-pix_fmt",
        brand.video_spec.pixel_format,
        "-r",
        str(fps),
        "-c:a",
        brand.video_spec.audio_codec,
        "-b:a",
        f"{brand.video_spec.audio_bitrate_kbps}k",
        "-ar",
        str(brand.video_spec.audio_sample_rate),
        "-ac",
        str(brand.video_spec.audio_channels),
        "-movflags",
        "+faststart",
        "-shortest",
        str(out_mp4),
    ]

    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    img = Image.new("RGB", (width, height), palette.bg_dark)
    draw = ImageDraw.Draw(img)

    try:
        for frame_idx in range(total_frames):
            t = frame_idx / float(fps)
            bt, beat_progress = timeline.beat_at(t)
            rms = float(envelope[frame_idx]) if frame_idx < len(envelope) else 0.0

            scene.render_frame(
                frame_idx=frame_idx,
                t=t,
                beat_id=bt.id,
                beat_progress=beat_progress,
                rms=rms,
                img=img,
                draw=draw,
            )

            beat_cfg = beat_script_map.get(bt.id)
            draw_brand_header(draw, brand, palette, repo_root=repo_root)

            # Beat 1 (Frame 0): crisp top hook text, zero HUD clutter
            if bt.id == script.beats[0].id:
                draw_top_hook(draw, script.hook_text, brand, palette, repo_root=repo_root)
            elif beat_cfg is not None and beat_cfg.callout is not None:
                accent = resolve_callout_accent(
                    beat_cfg.act,
                    beat_cfg.callout.label,
                    beat_cfg.callout.value,
                    palette,
                )
                draw_hud_callout(
                    draw,
                    beat_cfg.callout,
                    brand,
                    palette,
                    accent_color=accent,
                    progress=beat_progress,
                    repo_root=repo_root,
                )

            draw_caption(img, draw, t, captions, brand, repo_root=repo_root)
            proc.stdin.write(img.tobytes())
    finally:
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"ffmpeg render failed (exit {ret}): {stderr}")

    elapsed = max(0.01, time.monotonic() - t0)
    return {
        "frames": float(total_frames),
        "duration_s": float(timeline.total_duration_s),
        "render_elapsed_s": round(elapsed, 2),
        "render_fps": round(total_frames / elapsed, 2),
    }
