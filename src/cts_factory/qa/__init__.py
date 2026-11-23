"""Technical QA gate: ffprobe, ebur128 loudness, 0.5s RMS silence scan, and /reel-watch audit."""

from cts_factory.qa.validator import run_episode_qa

__all__ = ["run_episode_qa"]
