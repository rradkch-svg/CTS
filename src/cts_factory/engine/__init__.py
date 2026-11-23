"""2.5D projected isometric CAD vector animation & ffmpeg streaming renderer."""

from cts_factory.engine.materials import Palette, build_stage_background, hex_rgb, lerp_color
from cts_factory.engine.projection import (
    CAMERA_PRESETS,
    CameraState,
    clamp,
    ease_in_out_cubic,
    ease_out_back,
    ease_out_cubic,
    project_iso,
)
from cts_factory.engine.renderer import render_episode_video

__all__ = [
    "CAMERA_PRESETS",
    "CameraState",
    "Palette",
    "build_stage_background",
    "clamp",
    "ease_in_out_cubic",
    "ease_out_back",
    "ease_out_cubic",
    "hex_rgb",
    "lerp_color",
    "project_iso",
    "render_episode_video",
]
