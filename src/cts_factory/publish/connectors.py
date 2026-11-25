"""Pluggable unified multi-platform publishing connectors (YouTube Shorts + TikTok + Instagram Reels).

Uses strictly Python standard library (urllib.request) — zero extra pip dependencies required in GitHub Actions.
Supported providers (set via PUBLISH_PROVIDER env/secret):
  - upload_post : Upload-Post.com multipart binary video upload (works on private GitHub repos!)
  - postiz      : Postiz Cloud / Self-hosted open-source API (2-step binary upload + multi-channel post)
  - ayrshare    : Ayrshare unified social API (posts via HTTPS video URL to YouTube/TikTok/Instagram)
  - webhook     : Universal JSON webhook for n8n / Make / Zapier / custom automation endpoint
  - dry_run     : Safe validation mode (never sends external HTTP traffic)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PublishPayload:
    episode_id: str
    slug: str
    platforms: list[str]
    youtube_title: str
    youtube_description: str
    caption: str
    hashtags: list[str]
    pinned_comment: str
    mp4_path: Path
    cover_path: Path
    video_url: str
    cover_url: str

    @property
    def full_caption(self) -> str:
        tags = " ".join(h for h in self.hashtags if h.strip())
        base = self.caption.strip()
        return f"{base}\n\n{tags}".strip() if tags else base


def _encode_multipart(
    fields: list[tuple[str, str]],
    files: list[tuple[str, str, str, bytes]],
) -> tuple[bytes, str]:
    """Build RFC 7578 multipart/form-data body using only Python stdlib."""
    boundary = f"----CTSFactory{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(value.encode("utf-8") + b"\r\n")
    for field_name, filename, content_type, data in files:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(data + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _http_request(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: int = 180,
) -> dict[str, Any]:
    req_headers = {"User-Agent": "FailSafeLab-CTS-Publisher/1.0", **headers}
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw) if raw.strip() else {"status_code": resp.status}
            except json.JSONDecodeError:
                return {"status_code": resp.status, "body": raw[:500]}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {err_body}") from exc


def publish_via_upload_post(payload: PublishPayload) -> dict[str, Any]:
    """Upload-Post.com unified multipart binary upload (YouTube Shorts + TikTok + Instagram Reels)."""
    api_key = (os.environ.get("PUBLISH_API_KEY") or "").strip()
    user = (os.environ.get("UPLOAD_POST_USER") or "").strip()
    base_url = (os.environ.get("UPLOAD_POST_BASE_URL") or "").strip() or "https://api.upload-post.com/api/upload"
    if not api_key or not user:
        raise RuntimeError("upload_post requires PUBLISH_API_KEY and UPLOAD_POST_USER secrets")

    fields: list[tuple[str, str]] = [
        ("user", user),
        ("title", payload.youtube_title),
        ("description", payload.full_caption),
        ("youtube_title", payload.youtube_title),
        ("youtube_description", payload.youtube_description),
        ("first_comment", payload.pinned_comment),
    ]
    for plat in payload.platforms:
        fields.append(("platform[]", plat))

    files = [
        ("video", payload.mp4_path.name, "video/mp4", payload.mp4_path.read_bytes()),
    ]
    body, content_type = _encode_multipart(fields, files)
    return _http_request(
        base_url,
        body=body,
        headers={
            "Authorization": f"Apikey {api_key}",
            "Content-Type": content_type,
        },
    )


def publish_via_postiz(payload: PublishPayload) -> dict[str, Any]:
    """Postiz Cloud or self-hosted API: uploads binary MP4, then posts to all configured integration IDs."""
    api_key = (os.environ.get("PUBLISH_API_KEY") or "").strip()
    base_url = ((os.environ.get("POSTIZ_BASE_URL") or "").strip() or "https://api.postiz.com/public/v1").rstrip("/")
    raw_ids = (os.environ.get("POSTIZ_INTEGRATION_IDS") or "").strip()
    integration_ids = [i.strip() for i in raw_ids.split(",") if i.strip()]
    if not api_key or not integration_ids:
        raise RuntimeError("postiz requires PUBLISH_API_KEY and POSTIZ_INTEGRATION_IDS (comma-separated) secrets")

    # Step 1: upload video binary directly to Postiz media storage
    up_body, up_ct = _encode_multipart(
        fields=[],
        files=[("file", payload.mp4_path.name, "video/mp4", payload.mp4_path.read_bytes())],
    )
    media = _http_request(
        f"{base_url}/upload",
        body=up_body,
        headers={"Authorization": api_key, "Content-Type": up_ct},
    )
    media_id = media.get("id") or media.get("mediaId") or ""
    media_path = media.get("path") or media.get("url") or payload.video_url

    # Step 2: create unified multi-channel immediate post
    posts_payload = {
        "type": "now",
        "shortLink": False,
        "tags": [],
        "posts": [
            {
                "integration": {"id": iid},
                "value": [
                    {
                        "content": payload.full_caption,
                        "image": [{"id": media_id, "path": media_path}],
                    }
                ],
                "settings": {
                    "title": payload.youtube_title,
                    "type": "public",
                },
            }
            for iid in integration_ids
        ],
    }
    return _http_request(
        f"{base_url}/posts",
        body=json.dumps(posts_payload).encode("utf-8"),
        headers={"Authorization": api_key, "Content-Type": "application/json"},
    )


def publish_via_ayrshare(payload: PublishPayload) -> dict[str, Any]:
    """Ayrshare unified social API posting via HTTPS media URL."""
    api_key = os.environ.get("PUBLISH_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ayrshare requires PUBLISH_API_KEY secret")

    req_body = {
        "post": payload.full_caption,
        "platforms": payload.platforms,
        "mediaUrls": [payload.video_url],
        "isVideo": True,
        "youTubeOptions": {
            "title": payload.youtube_title,
            "visibility": "public",
            "shorts": True,
            "thumbNail": payload.cover_url,
        },
        "instagramOptions": {
            "reels": True,
            "shareReelsFeed": True,
            "thumbNail": payload.cover_url,
        },
        "tikTokOptions": {
            "title": payload.youtube_title,
        },
    }
    return _http_request(
        "https://api.ayrshare.com/api/post",
        body=json.dumps(req_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )


def publish_via_webhook(payload: PublishPayload) -> dict[str, Any]:
    """Universal JSON webhook for n8n / Make / Zapier / custom automation workflows."""
    webhook_url = os.environ.get("PUBLISH_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("webhook provider requires PUBLISH_WEBHOOK_URL secret")

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("PUBLISH_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = {
        "episode_id": payload.episode_id,
        "slug": payload.slug,
        "platforms": payload.platforms,
        "youtube": {
            "title": payload.youtube_title,
            "description": payload.youtube_description,
            "pinned_comment": payload.pinned_comment,
        },
        "instagram_tiktok": {
            "caption": payload.caption,
            "hashtags": payload.hashtags,
            "full_caption": payload.full_caption,
            "pinned_comment": payload.pinned_comment,
        },
        "media": {
            "video_url": payload.video_url,
            "cover_url": payload.cover_url,
            "video_filename": payload.mp4_path.name,
            "video_size_bytes": payload.mp4_path.stat().st_size,
        },
    }
    return _http_request(webhook_url, body=json.dumps(body).encode("utf-8"), headers=headers)


def dispatch_publish(provider: str, payload: PublishPayload, dry_run: bool = False) -> dict[str, Any]:
    """Dispatch a single episode payload to the configured unified connector (or dry_run)."""
    prov = provider.strip().lower()
    if dry_run or prov == "dry_run":
        return {
            "dry_run": True,
            "provider": prov,
            "slug": payload.slug,
            "platforms": payload.platforms,
            "youtube_title": payload.youtube_title,
            "video_url": payload.video_url,
            "cover_url": payload.cover_url,
            "video_size_bytes": payload.mp4_path.stat().st_size,
        }

    dispatch_map = {
        "upload_post": publish_via_upload_post,
        "postiz": publish_via_postiz,
        "ayrshare": publish_via_ayrshare,
        "webhook": publish_via_webhook,
    }
    fn = dispatch_map.get(prov)
    if fn is None:
        raise ValueError(
            f"Unsupported PUBLISH_PROVIDER={provider!r}. Choose one of: {', '.join(sorted(dispatch_map))} or dry_run."
        )
    return fn(payload)
