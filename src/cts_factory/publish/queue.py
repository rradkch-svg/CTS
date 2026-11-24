"""Persistent idempotent publishing queue (publish_queue.json) with strict QA gate enforcement."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PLATFORMS = ["youtube", "tiktok", "instagram"]


@dataclass
class QueueItem:
    episode_id: str
    slug: str
    status: str = "pending"  # pending | published | failed | skipped
    platforms: list[str] = field(default_factory=lambda: list(DEFAULT_PLATFORMS))
    batch: str = "daily"
    publish_after_utc: str | None = None
    published_at_utc: str | None = None
    provider: str | None = None
    external_ids: dict[str, Any] = field(default_factory=dict)
    last_error: str | None = None

    def is_due(self, now_utc: datetime) -> bool:
        if self.status != "pending":
            return False
        if not self.publish_after_utc:
            return True
        target = datetime.fromisoformat(self.publish_after_utc.replace("Z", "+00:00"))
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        return now_utc >= target


@dataclass
class PublishQueue:
    version: int = 1
    channel_name: str = "FailSafe Lab"
    default_platforms: list[str] = field(default_factory=lambda: list(DEFAULT_PLATFORMS))
    items: list[QueueItem] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "PublishQueue":
        if not path.is_file():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = [QueueItem(**item) for item in raw.get("items", [])]
        return cls(
            version=int(raw.get("version", 1)),
            channel_name=str(raw.get("channel_name", "FailSafe Lab")),
            default_platforms=list(raw.get("default_platforms", DEFAULT_PLATFORMS)),
            items=items,
        )

    def save(self, path: Path) -> None:
        payload = {
            "version": self.version,
            "channel_name": self.channel_name,
            "default_platforms": self.default_platforms,
            "items": [asdict(item) for item in self.items],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def get_by_slug(self, slug: str) -> QueueItem | None:
        for item in self.items:
            if item.slug == slug:
                return item
        return None


def validate_episode_ready_to_publish(repo_root: Path, slug: str) -> tuple[bool, str, dict[str, Any]]:
    """Enforce mandatory QA & packaging gate before allowing automated publication."""
    ep_dir = repo_root / "episodios" / slug
    mp4_path = ep_dir / f"{slug}.mp4"
    cover_path = ep_dir / "cover.png"
    meta_path = ep_dir / "publish_meta.json"
    qa_path = ep_dir / "qa_report.json"

    for label, p in (("MP4", mp4_path), ("cover.png", cover_path), ("publish_meta.json", meta_path), ("qa_report.json", qa_path)):
        if not p.is_file():
            return False, f"Missing required artifact {label} at {p}", {}

    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    if not qa.get("passed", False):
        return False, f"QA gate failed for {slug}: {qa.get('violations', [])}", {}

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return True, "ok", {
        "mp4_path": mp4_path,
        "cover_path": cover_path,
        "meta": meta,
        "qa": qa,
    }


def sync_publish_queue(repo_root: Path, queue_path: Path | None = None) -> PublishQueue:
    """Discover all QA-passed episodes under episodios/ and append missing entries without clobbering state."""
    qpath = queue_path or (repo_root / "publish_queue.json")
    queue = PublishQueue.load(qpath)
    existing = {item.slug for item in queue.items}

    ep_dirs = sorted((repo_root / "episodios").glob("ep*"))
    for idx, ep_dir in enumerate(ep_dirs):
        if not ep_dir.is_dir():
            continue
        slug = ep_dir.name
        if slug in existing:
            continue
        ready, _, info = validate_episode_ready_to_publish(repo_root, slug)
        if not ready:
            continue
        ep_id = str(info["meta"].get("episode_id", slug[:4]))
        batch = "launch-3" if idx < 3 else "daily"
        queue.items.append(
            QueueItem(
                episode_id=ep_id,
                slug=slug,
                status="pending",
                platforms=list(queue.default_platforms),
                batch=batch,
            )
        )
        existing.add(slug)

    queue.save(qpath)
    return queue
