"""Orchestrator for automated batch publishing from publish_queue.json."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cts_factory.publish.connectors import PublishPayload, dispatch_publish
from cts_factory.publish.queue import QueueItem, sync_publish_queue, validate_episode_ready_to_publish


def _resolve_media_urls(slug: str) -> tuple[str, str]:
    """Compute public HTTPS URLs for video & cover (GitHub raw default or custom PUBLISH_MEDIA_BASE_URL)."""
    custom_base = (os.environ.get("PUBLISH_MEDIA_BASE_URL") or "").strip().rstrip("/")
    if custom_base:
        return f"{custom_base}/{slug}/{slug}.mp4", f"{custom_base}/{slug}/cover.jpg"

    repo = (os.environ.get("GITHUB_REPOSITORY") or "rradkch-svg/CTS").strip()
    ref = (os.environ.get("GITHUB_REF_NAME") or "main").strip()
    raw_base = f"https://raw.githubusercontent.com/{repo}/{ref}/episodios/{slug}"
    return f"{raw_base}/{slug}.mp4", f"{raw_base}/cover.jpg"


def _resolve_provider(explicit: str | None) -> str:
    if explicit and explicit != "auto":
        return explicit.strip().lower()
    env_prov = (os.environ.get("PUBLISH_PROVIDER") or "").strip().lower()
    if env_prov:
        return env_prov
    if (os.environ.get("PUBLISH_WEBHOOK_URL") or "").strip():
        return "webhook"
    return "dry_run"


def _select_targets(
    items: list[QueueItem],
    now_utc: datetime,
    count: int,
    episode: str | None,
    batch: str | None,
    retry_failed: bool = False,
) -> list[QueueItem]:
    allowed_statuses = ("pending", "failed") if retry_failed else ("pending",)
    if episode:
        return [it for it in items if it.slug == episode and it.status in allowed_statuses]
    selected: list[QueueItem] = []
    for it in items:
        if batch and it.batch != batch:
            continue
        if it.is_due(now_utc, include_failed=retry_failed):
            selected.append(it)
            if len(selected) >= count:
                break
    return selected


def run_publish_batch(
    repo_root: Path,
    count: int = 1,
    episode: str | None = None,
    batch: str | None = None,
    provider: str | None = None,
    dry_run: bool = False,
    queue_path: Path | None = None,
    platforms_override: list[str] | None = None,
    scheduled_date: str | None = None,
    tz_name: str | None = None,
    add_to_queue: bool = False,
    retry_failed: bool = False,
) -> dict[str, Any]:
    """Publish up to `count` pending QA-verified episodes and persist updated publish_queue.json per episode."""
    qpath = queue_path or (repo_root / "publish_queue.json")
    queue = sync_publish_queue(repo_root, queue_path=qpath)
    resolved_provider = _resolve_provider(provider)
    effective_dry_run = dry_run or (resolved_provider == "dry_run")
    now_utc = datetime.now(timezone.utc)

    targets = _select_targets(
        queue.items,
        now_utc,
        count=max(1, count),
        episode=episode,
        batch=batch,
        retry_failed=retry_failed,
    )
    results: list[dict[str, Any]] = []
    failures = 0

    for item in targets:
        ready, reason, info = validate_episode_ready_to_publish(repo_root, item.slug)
        if not ready:
            failures += 1
            item.last_error = reason
            results.append({"slug": item.slug, "status": "blocked_qa", "error": reason})
            if not effective_dry_run:
                queue.save(qpath)
            continue

        meta = info["meta"]
        video_url, cover_url = _resolve_media_urls(item.slug)
        if platforms_override:
            target_platforms = [p.strip().lower() for p in platforms_override if p.strip()]
        else:
            env_plats = [p.strip().lower() for p in (os.environ.get("PUBLISH_PLATFORMS") or "").split(",") if p.strip()]
            target_platforms = env_plats if env_plats else list(item.platforms)

        payload = PublishPayload(
            episode_id=item.episode_id,
            slug=item.slug,
            platforms=target_platforms,
            youtube_title=str(meta["youtube_title"]),
            youtube_description=str(meta.get("youtube_description", "")),
            caption=str(meta.get("ig_tiktok_caption", "")),
            hashtags=list(meta.get("hashtags", [])),
            pinned_comment=str(meta.get("pinned_comment", "")),
            mp4_path=info["mp4_path"],
            cover_path=info["cover_path"],
            cover_jpg_path=info.get("cover_jpg_path"),
            video_url=video_url,
            cover_url=cover_url,
            ai_disclosure=bool(meta.get("ai_disclosure", False)),
            language=str(meta.get("language", "en-US")),
            scheduled_date=(scheduled_date or "").strip() or None,
            timezone=(tz_name or "").strip() or None,
            add_to_queue=bool(add_to_queue),
            youtube_playlist_id=(os.environ.get("YOUTUBE_PLAYLIST_ID") or "").strip() or None,
        )

        try:
            resp = dispatch_publish(resolved_provider, payload, dry_run=effective_dry_run)
            dispatch_state = str(resp.get("dispatch_state") or "published") if isinstance(resp, dict) else "published"
            if dispatch_state == "scheduled":
                final_status = "scheduled"
            elif dispatch_state == "submitted_async":
                final_status = "submitted"
            else:
                final_status = "published"

            if not effective_dry_run:
                item.status = final_status
                item.published_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                item.provider = resolved_provider
                item.external_ids = resp if isinstance(resp, dict) else {"raw": str(resp)}
                item.last_error = None
                queue.save(qpath)

            results.append(
                {
                    "slug": item.slug,
                    "status": "dry_run" if effective_dry_run else final_status,
                    "provider": resolved_provider,
                    "response": resp,
                }
            )
        except Exception as exc:
            failures += 1
            item.status = "failed"
            item.provider = resolved_provider
            item.last_error = str(exc)
            if not effective_dry_run:
                queue.save(qpath)
            results.append({"slug": item.slug, "status": "failed", "provider": resolved_provider, "error": str(exc)})

    return {
        "provider": resolved_provider,
        "dry_run": effective_dry_run,
        "selected": len(targets),
        "failures": failures,
        "results": results,
    }
