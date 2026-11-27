"""Buffer Public GraphQL API connector (100% FREE tier supports 3 channels: YouTube Shorts + TikTok + Instagram Reels).

Official docs: https://developers.buffer.com
- Endpoint: POST https://api.buffer.com (Authorization: Bearer <BUFFER_API_KEY>)
- Free plan includes 3 channels (YouTube + TikTok + Instagram), 1 API key, 3,000 requests/month,
  and 10 queued posts per channel at a time (refillable — unlimited total monthly posts with shareNow!).
- Zero third-party pip dependencies (pure Python 3.12 stdlib).
- Auto-discovers connected channel IDs via account.organizations -> channels(input: { organizationId }).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cts_factory.publish.connectors import PublishPayload

BUFFER_GRAPHQL_URL = "https://api.buffer.com"
USER_AGENT = "FailSafeLab-CTS-BufferPublisher/1.0"
YOUTUBE_SCIENCE_TECH_CATEGORY_ID = "28"

_GET_ORGS_QUERY = """
query GetOrganizations {
  account {
    organizations {
      id
      name
    }
  }
}
"""

_GET_CHANNELS_QUERY = """
query GetChannels($orgId: OrganizationId!) {
  channels(input: { organizationId: $orgId }) {
    id
    name
    displayName
    service
    isQueuePaused
  }
}
"""

_CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post {
        id
        status
        dueAt
      }
    }
    ... on MutationError {
      message
    }
  }
}
"""


def _buffer_api_key() -> str:
    return (os.environ.get("BUFFER_API_KEY") or os.environ.get("PUBLISH_API_KEY") or "").strip()


def _buffer_graphql(api_key: str, query: str, variables: dict[str, Any] | None = None, timeout: int = 90) -> dict[str, Any]:
    """Execute a GraphQL request against https://api.buffer.com using stdlib urllib."""
    endpoint = (os.environ.get("BUFFER_API_URL") or "").strip() or BUFFER_GRAPHQL_URL
    body_obj: dict[str, Any] = {"query": query}
    if variables:
        body_obj["variables"] = variables
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body_obj).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} from Buffer GraphQL API: {err_body}") from exc

    if isinstance(parsed, dict) and parsed.get("errors"):
        raise RuntimeError(f"Buffer GraphQL errors: {parsed['errors']}")
    return parsed.get("data") or {}


def _discover_buffer_channels(api_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Discover all organizations and connected channels on the Buffer account."""
    org_data = _buffer_graphql(api_key, _GET_ORGS_QUERY)
    orgs = ((org_data.get("account") or {}).get("organizations")) or []
    if not orgs:
        raise RuntimeError("No organizations found for this Buffer API key.")

    all_channels: list[dict[str, Any]] = []
    for org in orgs:
        org_id = str(org.get("id") or "").strip()
        if not org_id:
            continue
        ch_data = _buffer_graphql(api_key, _GET_CHANNELS_QUERY, variables={"orgId": org_id})
        for ch in ch_data.get("channels") or []:
            if isinstance(ch, dict):
                all_channels.append({**ch, "organizationId": org_id})
    return orgs, all_channels


def _sanitize_youtube_text(text: str) -> str:
    """Buffer/YouTube rejects '<' and '>' characters in descriptions/titles."""
    return text.replace("<", "(").replace(">", ")").strip()


def _build_channel_input(service: str, channel_id: str, payload: "PublishPayload") -> dict[str, Any]:
    """Build Buffer CreatePostInput tailored to YouTube Shorts, TikTok, or Instagram Reels."""
    is_scheduled = bool(payload.scheduled_date)
    is_queued = bool(payload.add_to_queue) and not is_scheduled

    if is_scheduled:
        mode = "customScheduled"
    elif is_queued:
        mode = "addToQueue"
    else:
        mode = (os.environ.get("BUFFER_SHARE_MODE") or "").strip() or "shareNow"

    video_asset: dict[str, Any] = {"url": payload.video_url}
    if service in ("instagram", "tiktok"):
        video_asset["metadata"] = {"thumbnailOffset": 0}

    post_input: dict[str, Any] = {
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": mode,
        "assets": [{"video": video_asset}],
    }
    if is_scheduled:
        post_input["dueAt"] = str(payload.scheduled_date).strip()

    if service == "youtube":
        # On YouTube, `text` becomes snippet.description and `metadata.youtube.title` is the video title.
        post_input["text"] = _sanitize_youtube_text(payload.youtube_description)
        post_input["metadata"] = {
            "youtube": {
                "title": _sanitize_youtube_text(payload.youtube_title)[:100],
                "categoryId": YOUTUBE_SCIENCE_TECH_CATEGORY_ID,
                "privacy": "public",
                "madeForKids": False,
                "embeddable": True,
                "notifySubscribers": True,
                "isAiGenerated": bool(payload.ai_disclosure),
            }
        }
    elif service == "tiktok":
        post_input["text"] = payload.full_caption[:2200]
        post_input["metadata"] = {
            "tiktok": {
                "isAiGenerated": bool(payload.ai_disclosure),
            }
        }
    elif service == "instagram":
        post_input["text"] = payload.full_caption[:2200]
        ig_meta: dict[str, Any] = {
            "type": "reel",
            "shouldShareToFeed": True,
            "isAiGenerated": bool(payload.ai_disclosure),
        }
        # Buffer Free plan rejects Instagram firstComment ("First comment requires a paid plan").
        # Only attach firstComment when explicitly enabled on a paid Buffer plan.
        if (os.environ.get("BUFFER_ENABLE_FIRST_COMMENT") or "").strip() == "1" and payload.pinned_comment.strip():
            ig_meta["firstComment"] = payload.pinned_comment.strip()
        post_input["metadata"] = {"instagram": ig_meta}
    else:
        post_input["text"] = payload.full_caption[:2200]

    return post_input


def publish_via_buffer(payload: "PublishPayload") -> dict[str, Any]:
    """Publish a Short/Reel/TikTok via Buffer Public GraphQL API (free on all plans, 3 channels included)."""
    api_key = _buffer_api_key()
    if not api_key:
        raise RuntimeError(
            "buffer requires PUBLISH_API_KEY (or BUFFER_API_KEY) secret. "
            "Generate one free at https://publish.buffer.com/settings/api"
        )

    _, channels = _discover_buffer_channels(api_key)
    by_service: dict[str, dict[str, Any]] = {}
    for ch in channels:
        svc = str(ch.get("service") or "").strip().lower()
        if svc and svc not in by_service:
            by_service[svc] = ch

    requested = [p.strip().lower() for p in payload.platforms if p.strip()]
    notes: list[str] = []
    warnings: list[str] = []
    results: dict[str, Any] = {}
    succeeded: list[str] = []
    failed: dict[str, str] = {}

    runnable: list[tuple[str, dict[str, Any]]] = []
    for plat in requested:
        ch = by_service.get(plat)
        if ch:
            runnable.append((plat, ch))
        else:
            notes.append(f"Skipped {plat!r}: not connected in Buffer (connected services: {sorted(by_service)}).")

    if not runnable:
        raise RuntimeError(
            f"None of requested platforms {requested} are connected in your Buffer account. "
            f"Connected services: {sorted(by_service)}. Connect YouTube/TikTok/Instagram in https://publish.buffer.com."
        )

    for plat, ch in runnable:
        ch_id = str(ch["id"])
        post_input = _build_channel_input(plat, ch_id, payload)
        try:
            data = _buffer_graphql(api_key, _CREATE_POST_MUTATION, variables={"input": post_input})
            res = data.get("createPost") or {}
            if res.get("message") and not res.get("post"):
                msg = str(res["message"])
                ig_meta = (post_input.get("metadata") or {}).get("instagram")
                if (
                    plat == "instagram"
                    and isinstance(ig_meta, dict)
                    and "firstComment" in ig_meta
                    and "first comment" in msg.lower()
                ):
                    ig_meta.pop("firstComment", None)
                    warnings.append(f"instagram firstComment omitted (requires paid Buffer plan): {msg}")
                    data = _buffer_graphql(api_key, _CREATE_POST_MUTATION, variables={"input": post_input})
                    res = data.get("createPost") or {}
                if res.get("message") and not res.get("post"):
                    raise RuntimeError(f"Buffer rejected {plat} post: {res['message']}")
            post = res.get("post") or {}
            if not post.get("id"):
                raise RuntimeError(f"Buffer returned unexpected createPost response for {plat}: {res}")
            results[plat] = {
                "success": True,
                "channel_id": ch_id,
                "channel_name": ch.get("displayName") or ch.get("name"),
                "post_id": post.get("id"),
                "status": post.get("status"),
                "due_at": post.get("dueAt"),
            }
            succeeded.append(plat)
        except Exception as exc:
            failed[plat] = str(exc)

    if not succeeded:
        raise RuntimeError(f"Buffer publish failed on all attempted platforms for {payload.slug}: {failed}")

    is_scheduled = bool(payload.scheduled_date) or bool(payload.add_to_queue)
    out: dict[str, Any] = {
        "ok": True,
        "provider": "buffer",
        "dispatch_state": "scheduled" if is_scheduled else "published",
        "effective_platforms": [p for p, _ in runnable],
        "succeeded_platforms": succeeded,
        "results": results,
        "notes": notes,
        "warnings": warnings,
    }
    if failed:
        out["partial_failures"] = failed
        out["warnings"] = list(warnings) + [f"Partial failure on {p}: {e}" for p, e in failed.items()]
    return out


def inspect_buffer_account() -> dict[str, Any]:
    """Read-only verification of Buffer organizations & connected channels (never prints API key)."""
    api_key = _buffer_api_key()
    if not api_key:
        raise RuntimeError("check-account for buffer requires PUBLISH_API_KEY (or BUFFER_API_KEY) secret")

    orgs, channels = _discover_buffer_channels(api_key)
    summarized = [
        {
            "service": str(ch.get("service") or "").lower(),
            "id": ch.get("id"),
            "name": ch.get("displayName") or ch.get("name"),
            "is_queue_paused": bool(ch.get("isQueuePaused", False)),
        }
        for ch in channels
    ]
    return {
        "provider": "buffer",
        "organizations": [{"id": o.get("id"), "name": o.get("name")} for o in orgs],
        "channels": summarized,
        "connected_services": sorted({c["service"] for c in summarized if c["service"]}),
        "resolution_error": None if summarized else "No social channels connected in Buffer yet.",
    }
