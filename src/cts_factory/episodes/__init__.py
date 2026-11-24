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
from cts_factory.episodes.ep03_bank_vault_lock import BankVaultLockScene
from cts_factory.episodes.ep04_tacoma_bridge_flutter import TacomaBridgeFlutterScene
from cts_factory.episodes.ep05_car_differential_gear import CarDifferentialGearScene
from cts_factory.episodes.ep06_skywalk_bolt_load import SkywalkBoltLoadScene

__all__ = [
    "BankVaultLockScene",
    "CarDifferentialGearScene",
    "ElevatorSafetyBrakeScene",
    "EpisodeScene",
    "SkywalkBoltLoadScene",
    "SubmersibleImplosionScene",
    "TacomaBridgeFlutterScene",
    "get_scene",
    "list_scenes",
    "register_scene",
    "unregister_scene",
]
