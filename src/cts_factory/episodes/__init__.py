"""Episode scene registry and built-in episode modules."""

from cts_factory.episodes.base import (
    EpisodeScene,
    get_scene,
    list_scenes,
    register_scene,
    unregister_scene,
)
from cts_factory.episodes.ep01_elevator_safety_brake import ElevatorSafetyBrakeScene
from cts_factory.episodes.ep02_submersible_implosion_physics import SubmersibleImplosionScene

__all__ = [
    "ElevatorSafetyBrakeScene",
    "EpisodeScene",
    "SubmersibleImplosionScene",
    "get_scene",
    "list_scenes",
    "register_scene",
    "unregister_scene",
]
