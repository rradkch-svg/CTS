"""Audio synthesis, procedural bed/SFX, and broadcast loudness mastering."""

from cts_factory.audio.mixer import build_episode_audio, mix_and_master_audio
from cts_factory.audio.synth_bed import generate_ambient_bed, render_sfx_track, synthesize_sfx
from cts_factory.audio.tts import synthesize_narration

__all__ = [
    "build_episode_audio",
    "generate_ambient_bed",
    "mix_and_master_audio",
    "render_sfx_track",
    "synthesize_narration",
    "synthesize_sfx",
]
