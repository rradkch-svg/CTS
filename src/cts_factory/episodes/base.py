"""Abstract base class and registry for CTS Shorts Factory episode scenes."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from PIL import Image, ImageDraw

    from cts_factory.config import AudioTimeline, BrandConfig, EpisodeScript


class EpisodeScene(ABC):
    """Contract implemented by every episode renderer under ``cts_factory.episodes``.

    Downstream renderers (M2 ``engine/renderer.py``), cover generators (M4
    ``packaging/cover.py``), and episode modules (M5 ``ep01_*`` / ``ep02_*``)
    interact strictly through this interface.
    """

    slug: str = ""
    episode_id: str = ""

    @abstractmethod
    def prepare(
        self,
        brand: BrandConfig,
        script: EpisodeScript,
        timeline: AudioTimeline | None = None,
    ) -> None:
        """Initialize cached backgrounds, geometry, fonts, and timing tables."""

    @abstractmethod
    def render_frame(
        self,
        frame_idx: int,
        t: float,
        beat_id: str,
        beat_progress: float,
        rms: float,
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
    ) -> None:
        """Render a single 1080x1920 video frame onto ``img`` using ``draw``."""

    @abstractmethod
    def render_cover_hero(
        self,
        img: Image.Image,
        draw: ImageDraw.ImageDraw,
    ) -> None:
        """Render the high-contrast hero artwork for the 1080x1920 episode cover."""


_SCENE_REGISTRY: dict[str, type[EpisodeScene]] = {}


def _validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not slug.strip():
        raise ValueError("Scene slug must be a non-empty string.")
    normalized = slug.strip()
    if normalized != slug or any(ch.isspace() for ch in normalized):
        raise ValueError(f"Scene slug must not contain whitespace: {slug!r}")
    return normalized


def _validate_scene_class(scene_cls: object) -> type[EpisodeScene]:
    if not inspect.isclass(scene_cls) or not issubclass(scene_cls, EpisodeScene):
        raise TypeError(
            f"Registered scene must be a concrete subclass of EpisodeScene, got {scene_cls!r}."
        )
    if inspect.isabstract(scene_cls):
        missing = ", ".join(sorted(getattr(scene_cls, "__abstractmethods__", ())))
        raise TypeError(
            f"Cannot register abstract EpisodeScene subclass {scene_cls.__name__!r}; "
            f"missing implementations for: {missing}."
        )
    return scene_cls


@overload
def register_scene(
    slug: str,
    scene_cls: type[EpisodeScene],
    *,
    overwrite: bool = False,
) -> type[EpisodeScene]: ...


@overload
def register_scene(
    slug: str,
    scene_cls: None = None,
    *,
    overwrite: bool = False,
) -> Callable[[type[EpisodeScene]], type[EpisodeScene]]: ...


def register_scene(
    slug: str,
    scene_cls: type[EpisodeScene] | None = None,
    *,
    overwrite: bool = False,
) -> type[EpisodeScene] | Callable[[type[EpisodeScene]], type[EpisodeScene]]:
    """Register an ``EpisodeScene`` subclass under ``slug``.

    Supports both direct invocation ``register_scene("ep01_...", Cls)`` and
    decorator usage ``@register_scene("ep01_...")``.
    """
    normalized_slug = _validate_slug(slug)

    def _register(cls: type[EpisodeScene]) -> type[EpisodeScene]:
        validated = _validate_scene_class(cls)
        if not overwrite and normalized_slug in _SCENE_REGISTRY:
            existing = _SCENE_REGISTRY[normalized_slug]
            raise ValueError(
                f"Scene slug {normalized_slug!r} is already registered to {existing.__name__}. "
                f"Pass overwrite=True to replace it."
            )
        _SCENE_REGISTRY[normalized_slug] = validated
        return validated

    if scene_cls is not None:
        return _register(scene_cls)
    return _register


def get_scene(slug: str) -> EpisodeScene:
    """Instantiate and return the registered ``EpisodeScene`` for ``slug``."""
    normalized_slug = _validate_slug(slug)
    if normalized_slug not in _SCENE_REGISTRY:
        available = ", ".join(sorted(_SCENE_REGISTRY.keys())) or "<none>"
        raise KeyError(
            f"Unknown episode scene slug {normalized_slug!r}. Available scenes: {available}."
        )
    scene_cls = _SCENE_REGISTRY[normalized_slug]
    return scene_cls()


def list_scenes() -> list[str]:
    """Return a sorted list of all registered episode scene slugs."""
    return sorted(_SCENE_REGISTRY.keys())


def unregister_scene(slug: str, *, missing_ok: bool = True) -> None:
    """Remove ``slug`` from the scene registry (primarily for test isolation)."""
    normalized_slug = _validate_slug(slug)
    if normalized_slug in _SCENE_REGISTRY:
        del _SCENE_REGISTRY[normalized_slug]
    elif not missing_ok:
        raise KeyError(f"Scene slug {normalized_slug!r} is not registered.")


__all__ = [
    "EpisodeScene",
    "get_scene",
    "list_scenes",
    "register_scene",
    "unregister_scene",
]
