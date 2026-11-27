"""Pluggable unified multi-platform publishing connectors (YouTube Shorts + TikTok + Instagram Reels).

Uses strictly Python standard library (urllib.request) — zero extra pip dependencies required in GitHub Actions.
Supported providers (set via PUBLISH_PROVIDER env/secret):
  - upload_post : Upload-Post.com official v1 API (profile auto-discovery, multipart video + custom covers,
                  platform-specific captions/titles, YouTube Shorts metadata, Idempotency-Key, async status polling,
                  native scheduling)
  - postiz      : Postiz Cloud / Self-hosted open-source API (2-step binary upload + multi-channel post)
  - ayrshare    : Ayrshare unified social API (posts via HTTPS video URL to YouTube/TikTok/Instagram)
  - webhook     : Universal JSON webhook for n8n / Make / Zapier / custom automation endpoint
  - dry_run     : Safe validation mode (never sends external HTTP traffic)
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

USER_AGENT = "FailSafeLab-CTS-Publisher/2.0"
DEFAULT_UPLOAD_POST_ORIGIN = "https://api.upload-post.com"
YOUTUBE_SCIENCE_TECH_CATEGORY_ID = "28"
DEFAULT_IG_AUDIO_NAME = "FailSafe Lab Original Audio"
DEFAULT_POLL_INTERVAL_S = 8.0
DEFAULT_POLL_TIMEOUT_S = 240.0


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
    cover_jpg_path: Path | None = None
    ai_disclosure: bool = False
    language: str = "en-US"
    scheduled_date: str | None = None
    timezone: str | None = None
    add_to_queue: bool = False
    youtube_playlist_id: str | None = None

    @property
    def full_caption(self) -> str:
        tags = " ".join(h for h in self.hashtags if h.strip())
        base = self.caption.strip()
        return f"{base}\n\n{tags}".strip() if tags else base

    def youtube_tags(self) -> list[str]:
        """Clean hashtags into YouTube API tags (no '#', deduped, within YouTube's 500-char total budget)."""
        raw_tags = [h.strip().lstrip("#") for h in self.hashtags if h.strip().lstrip("#")]
        for extra in ("Shorts", "FailSafeLab", "Engineering"):
            raw_tags.append(extra)
        deduped: list[str] = []
        seen: set[str] = set()
        total_chars = 0
        for tag in raw_tags:
            key = tag.lower()
            if key in seen:
                continue
            if total_chars + len(tag) + 1 > 450:
                break
            seen.add(key)
            deduped.append(tag)
            total_chars += len(tag) + 1
        return deduped


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


def _http_get(
    url: str,
    headers: dict[str, str],
    timeout: int = 60,
) -> dict[str, Any]:
    req_headers = {"User-Agent": USER_AGENT, **headers}
    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw) if raw.strip() else {"status_code": resp.status}
            except json.JSONDecodeError:
                return {"status_code": resp.status, "body": raw[:500]}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {err_body}") from exc


def _http_request(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: int = 180,
) -> dict[str, Any]:
    req_headers = {"User-Agent": USER_AGENT, **headers}
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw) if raw.strip() else {"status_code": resp.status}
            except json.JSONDecodeError:
                return {"status_code": resp.status, "body": raw[:500]}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {err_body}") from exc


def _upload_post_endpoints() -> tuple[str, str, str]:
    """Derive (upload_url, users_url, status_url) from UPLOAD_POST_BASE_URL or official default."""
    raw = (os.environ.get("UPLOAD_POST_BASE_URL") or "").strip().rstrip("/")
    if not raw:
        origin = DEFAULT_UPLOAD_POST_ORIGIN
        return f"{origin}/api/upload", f"{origin}/api/uploadposts/users", f"{origin}/api/uploadposts/status"
    if raw.endswith("/api/upload"):
        origin = raw[: -len("/api/upload")]
        return raw, f"{origin}/api/uploadposts/users", f"{origin}/api/uploadposts/status"
    if raw.endswith("/api"):
        origin = raw[: -len("/api")]
        return f"{raw}/upload", f"{origin}/api/uploadposts/users", f"{origin}/api/uploadposts/status"
    return f"{raw}/api/upload", f"{raw}/api/uploadposts/users", f"{raw}/api/uploadposts/status"


def _is_social_account_connected(account_val: Any) -> tuple[bool, bool]:
    """Inspect a profile.social_accounts.<platform> entry -> (is_connected, reauth_required)."""
    if not account_val:
        return False, False
    if isinstance(account_val, dict):
        reauth = bool(account_val.get("reauth_required", False))
        return (not reauth), reauth
    if isinstance(account_val, str):
        return bool(account_val.strip()), False
    return True, False


def fetch_upload_post_profiles(api_key: str, users_url: str | None = None) -> dict[str, Any]:
    """Call GET /api/uploadposts/users to list profiles and connected social accounts."""
    _, default_users_url, _ = _upload_post_endpoints()
    target_url = users_url or default_users_url
    return _http_get(target_url, headers={"Authorization": f"Apikey {api_key}"})


def resolve_upload_post_profile(
    api_key: str,
    requested_user: str,
    users_url: str | None = None,
) -> tuple[str, dict[str, Any] | None, list[str]]:
    """Resolve the exact Upload-Post profile username via GET /api/uploadposts/users.

    Handles the common misconfiguration where UPLOAD_POST_USER is left blank or set to a
    social handle (e.g. '@FailSafeLab') instead of the Upload-Post profile name (e.g. 'default').
    """
    notes: list[str] = []
    data = fetch_upload_post_profiles(api_key, users_url=users_url)
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, list) or not profiles:
        if requested_user:
            notes.append("GET /api/uploadposts/users returned no profiles list; using configured UPLOAD_POST_USER.")
            return requested_user, None, notes
        raise RuntimeError(
            "No Upload-Post profiles found for this API key. Connect YouTube/Instagram/TikTok in "
            "https://app.upload-post.com/manage-users first."
        )

    req_norm = requested_user.strip().lstrip("@").lower()

    # 1. Exact/case-insensitive match on profile username
    if req_norm:
        for prof in profiles:
            uname = str(prof.get("username") or "").strip()
            if uname.lower() == req_norm:
                return uname, prof, notes

        # 2. Match on profile display_name
        for prof in profiles:
            dname = str(prof.get("display_name") or "").strip().lstrip("@").lower()
            uname = str(prof.get("username") or "").strip()
            if dname and dname == req_norm and uname:
                notes.append(
                    f"Resolved UPLOAD_POST_USER={requested_user!r} via profile display_name to username={uname!r}."
                )
                return uname, prof, notes

        # 3. Match on any connected social account handle / display_name / username
        for prof in profiles:
            uname = str(prof.get("username") or "").strip()
            socials = prof.get("social_accounts") or {}
            if not isinstance(socials, dict) or not uname:
                continue
            for plat, acc in socials.items():
                if not isinstance(acc, dict):
                    continue
                candidates = {
                    str(acc.get("handle") or "").strip().lstrip("@").lower(),
                    str(acc.get("display_name") or "").strip().lstrip("@").lower(),
                    str(acc.get("username") or "").strip().lstrip("@").lower(),
                }
                if req_norm in candidates:
                    notes.append(
                        f"Resolved UPLOAD_POST_USER={requested_user!r} (matched {plat} handle) "
                        f"to Upload-Post profile username={uname!r}."
                    )
                    return uname, prof, notes

    # 4. Single-profile automatic fallback (e.g., default Upload-Post profile "default")
    if len(profiles) == 1:
        sole_uname = str(profiles[0].get("username") or "").strip()
        if sole_uname:
            if requested_user:
                notes.append(
                    f"Auto-selected sole Upload-Post profile {sole_uname!r} "
                    f"(UPLOAD_POST_USER={requested_user!r} is not a profile username; "
                    f"you can update UPLOAD_POST_USER to {sole_uname!r})."
                )
            else:
                notes.append(f"Auto-selected sole Upload-Post profile {sole_uname!r}.")
            return sole_uname, profiles[0], notes

    available = [str(p.get("username") or "") for p in profiles if p.get("username")]
    raise RuntimeError(
        f"UPLOAD_POST_USER={requested_user!r} does not match any Upload-Post profile. "
        f"Available profile usernames: {available}. "
        f"Update your UPLOAD_POST_USER GitHub Secret to one of these exact profile usernames."
    )


def inspect_upload_post_account() -> dict[str, Any]:
    """Read-only diagnostic summary of Upload-Post profiles and connected platforms (never exposes API key)."""
    api_key = (os.environ.get("PUBLISH_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("check-account requires PUBLISH_API_KEY secret")

    configured_user = (os.environ.get("UPLOAD_POST_USER") or "").strip()
    upload_url, users_url, _ = _upload_post_endpoints()
    raw = fetch_upload_post_profiles(api_key, users_url=users_url)

    resolved_user: str | None = None
    resolution_notes: list[str] = []
    resolution_error: str | None = None
    try:
        resolved_user, _, resolution_notes = resolve_upload_post_profile(api_key, configured_user, users_url=users_url)
    except Exception as exc:
        resolution_error = str(exc)

    summarized_profiles: list[dict[str, Any]] = []
    for prof in raw.get("profiles", []) if isinstance(raw, dict) else []:
        socials_summary: dict[str, Any] = {}
        raw_socials = prof.get("social_accounts") or {}
        if isinstance(raw_socials, dict):
            for plat, val in raw_socials.items():
                connected, reauth = _is_social_account_connected(val)
                entry: dict[str, Any] = {"connected": connected, "reauth_required": reauth}
                if isinstance(val, dict):
                    if val.get("handle"):
                        entry["handle"] = val["handle"]
                    if val.get("display_name"):
                        entry["display_name"] = val["display_name"]
                    if val.get("capabilities"):
                        entry["capabilities"] = list(val["capabilities"])
                socials_summary[plat] = entry
        summarized_profiles.append(
            {
                "username": prof.get("username"),
                "display_name": prof.get("display_name"),
                "social_accounts": socials_summary,
            }
        )

    return {
        "provider": "upload_post",
        "upload_endpoint": upload_url,
        "plan": raw.get("plan") if isinstance(raw, dict) else None,
        "profile_limit": raw.get("limit") if isinstance(raw, dict) else None,
        "configured_user": configured_user or None,
        "resolved_user": resolved_user,
        "resolution_notes": resolution_notes,
        "resolution_error": resolution_error,
        "profiles": summarized_profiles,
    }


def _poll_upload_post_status(
    status_url: str,
    api_key: str,
    request_id: str,
    timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
    interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> dict[str, Any]:
    """Poll GET /api/uploadposts/status?request_id=... respecting Upload-Post's 5-10s cache recommendation."""
    query = urllib.parse.urlencode({"request_id": request_id})
    url = f"{status_url}?{query}"
    headers = {"Authorization": f"Apikey {api_key}"}
    deadline = time.monotonic() + max(1.0, timeout_s)
    last_resp: dict[str, Any] = {"request_id": request_id, "status": "pending"}

    while True:
        resp = _http_get(url, headers=headers, timeout=60)
        last_resp = resp
        top_status = str(resp.get("status") or "").lower()
        if top_status in ("completed", "failed", "not_found"):
            return resp
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {**last_resp, "timed_out": True}
        time.sleep(min(interval_s, remaining))


def _summarize_upload_post_results(resp: dict[str, Any]) -> dict[str, Any]:
    """Normalize Upload-Post sync (dict) and async status (list) per-platform results."""
    raw_results = resp.get("results")
    entries: list[tuple[str, dict[str, Any]]] = []
    if isinstance(raw_results, dict):
        for plat, info in raw_results.items():
            if isinstance(info, dict):
                entries.append((str(plat), info))
    elif isinstance(raw_results, list):
        for info in raw_results:
            if isinstance(info, dict):
                plat = str(info.get("platform") or "unknown")
                entries.append((plat, info))

    succeeded: list[str] = []
    skipped: list[str] = []
    failed: dict[str, str] = {}
    platform_urls: dict[str, str] = {}
    warnings: list[str] = []

    for plat, info in entries:
        plat_status = str(info.get("status") or "").lower()
        if info.get("skipped") is True or plat_status == "skipped":
            skipped.append(plat)
            reason = info.get("skip_reason") or "skipped"
            warnings.append(f"{plat}: skipped ({reason})")
            continue

        if isinstance(info.get("warnings"), list):
            for w in info["warnings"]:
                warnings.append(f"{plat}: {w}")
        if info.get("thumbnail_pending"):
            warnings.append(f"{plat}: thumbnail_pending ({info.get('thumbnail_note') or 'applied after processing'})")
        if info.get("fallback_to_inbox"):
            warnings.append(f"{plat}: delivered to TikTok inbox/drafts (daily active-user cap)")

        is_ok = info.get("success") is True or plat_status == "completed"
        if is_ok:
            succeeded.append(plat)
            url = info.get("url") or info.get("post_url")
            if url:
                platform_urls[plat] = str(url)
        else:
            err = info.get("error") or info.get("message") or f"platform status={plat_status or 'failed'}"
            failed[plat] = str(err)

    return {
        "has_platform_results": bool(entries),
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "platform_urls": platform_urls,
        "warnings": warnings,
    }


def _select_cover_file(payload: PublishPayload, jpeg_only: bool = False) -> tuple[Path, str] | None:
    """Pick the best cover file & MIME type for a platform."""
    if payload.cover_jpg_path and payload.cover_jpg_path.is_file():
        return payload.cover_jpg_path, "image/jpeg"
    if jpeg_only:
        if payload.cover_path.suffix.lower() in (".jpg", ".jpeg") and payload.cover_path.is_file():
            return payload.cover_path, "image/jpeg"
        return None
    if payload.cover_path and payload.cover_path.is_file():
        mime = "image/jpeg" if payload.cover_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        return payload.cover_path, mime
    return None


def publish_via_upload_post(payload: PublishPayload) -> dict[str, Any]:
    """Upload-Post.com official v1 multipart binary upload (YouTube Shorts + TikTok + Instagram Reels).

    Implements official spec features from https://docs.upload-post.com/api/upload-video:
      - Automatic profile resolution via GET /api/uploadposts/users (handles 'default' profile automatically)
      - Connected-platform filtering (skips unconnected/reauth platforms cleanly)
      - Platform-specific titles/captions (instagram_title, tiktok_title, youtube_title, youtube_description)
      - Custom covers on all 3 platforms (YouTube thumbnail, Instagram JPEG cover_image, TikTok tiktok_cover_image)
      - YouTube Shorts metadata (categoryId=28 Science & Tech, tags[], BCP-47 languages, AI/COPPA flags, playlist)
      - Native first_comment + Idempotency-Key + external_id + async_upload with Upload Status polling
      - Native scheduled_date / timezone / add_to_queue support (202 Accepted + job_id)
    """
    api_key = (os.environ.get("PUBLISH_API_KEY") or "").strip()
    configured_user = (os.environ.get("UPLOAD_POST_USER") or "").strip()
    if not api_key:
        raise RuntimeError("upload_post requires PUBLISH_API_KEY secret")

    upload_url, users_url, status_url = _upload_post_endpoints()

    # 1. Resolve actual Upload-Post profile username + connected social accounts
    resolved_user, profile, notes = resolve_upload_post_profile(api_key, configured_user, users_url=users_url)

    # 2. Filter requested platforms against actually connected accounts when profile info is available
    effective_platforms = [p.strip().lower() for p in payload.platforms if p.strip()]
    social_accounts = profile.get("social_accounts") if isinstance(profile, dict) else None
    tiktok_caps: set[str] = set()
    if isinstance(social_accounts, dict) and social_accounts:
        filtered: list[str] = []
        for plat in effective_platforms:
            acc_val = social_accounts.get(plat)
            connected, reauth = _is_social_account_connected(acc_val)
            if connected:
                filtered.append(plat)
                if plat == "tiktok" and isinstance(acc_val, dict):
                    tiktok_caps = {str(c) for c in (acc_val.get("capabilities") or [])}
            elif reauth:
                notes.append(
                    f"Skipped {plat!r}: token expired (reauth_required=true). "
                    f"Reconnect in https://app.upload-post.com/manage-users."
                )
            else:
                notes.append(f"Skipped {plat!r}: not connected on Upload-Post profile {resolved_user!r}.")
        if not filtered:
            connected_list = [
                p for p, v in social_accounts.items() if _is_social_account_connected(v)[0]
            ]
            raise RuntimeError(
                f"None of requested platforms {effective_platforms} are connected on Upload-Post profile "
                f"{resolved_user!r}. Connected platforms: {connected_list}. Notes: {notes}"
            )
        effective_platforms = filtered

    # 3. Build common Upload-Post multipart fields
    is_scheduled = bool(payload.scheduled_date)
    is_queued = bool(payload.add_to_queue) and not is_scheduled
    use_async = (not is_scheduled) and (not is_queued) and (os.environ.get("UPLOAD_POST_SYNC", "").strip() != "1")

    client_request_id = f"cts-{payload.slug}-{uuid.uuid4().hex[:10]}"
    ai_flag = "true" if payload.ai_disclosure else "false"
    lang_full = (payload.language or "en-US").strip()
    lang_short = lang_full.split("-")[0] or "en"

    fields: list[tuple[str, str]] = [
        ("user", resolved_user),
        ("title", payload.youtube_title),
        ("external_id", payload.slug),
        ("request_id", client_request_id),
        ("is_ai_generated", ai_flag),
    ]
    for plat in effective_platforms:
        fields.append(("platform[]", plat))

    if payload.pinned_comment.strip():
        fields.append(("first_comment", payload.pinned_comment.strip()))

    if is_scheduled:
        fields.append(("scheduled_date", str(payload.scheduled_date).strip()))
        if payload.timezone:
            fields.append(("timezone", payload.timezone.strip()))
    elif is_queued:
        fields.append(("add_to_queue", "true"))
        if payload.timezone:
            fields.append(("timezone", payload.timezone.strip()))
    elif use_async:
        fields.append(("async_upload", "true"))

    # 4. Build platform-specific fields & binary cover attachments
    files: list[tuple[str, str, str, bytes]] = [
        ("video", payload.mp4_path.name, "video/mp4", payload.mp4_path.read_bytes()),
    ]

    if "youtube" in effective_platforms:
        fields.extend(
            [
                ("youtube_title", payload.youtube_title),
                ("youtube_description", payload.youtube_description),
                ("categoryId", YOUTUBE_SCIENCE_TECH_CATEGORY_ID),
                ("privacyStatus", "public"),
                ("selfDeclaredMadeForKids", "false"),
                ("containsSyntheticMedia", ai_flag),
                ("embeddable", "true"),
                ("publicStatsViewable", "true"),
                ("defaultLanguage", lang_short),
                ("defaultAudioLanguage", lang_full),
            ]
        )
        for tag in payload.youtube_tags():
            fields.append(("tags[]", tag))
        playlist_id = (payload.youtube_playlist_id or os.environ.get("YOUTUBE_PLAYLIST_ID") or "").strip()
        if playlist_id:
            fields.append(("youtube_playlist_id", playlist_id))
        yt_cover = _select_cover_file(payload, jpeg_only=False)
        if yt_cover is not None:
            cpath, cmime = yt_cover
            files.append(("thumbnail", cpath.name, cmime, cpath.read_bytes()))

    if "instagram" in effective_platforms:
        ig_audio_name = (os.environ.get("IG_AUDIO_NAME") or "").strip() or DEFAULT_IG_AUDIO_NAME
        fields.extend(
            [
                ("instagram_title", payload.full_caption[:2200]),
                ("media_type", "REELS"),
                ("share_to_feed", "true"),
                ("audio_name", ig_audio_name),
            ]
        )
        ig_cover = _select_cover_file(payload, jpeg_only=True)
        if ig_cover is not None:
            cpath, cmime = ig_cover
            files.append(("cover_image", cpath.name, cmime, cpath.read_bytes()))
        else:
            notes.append("Instagram cover_image omitted: no JPEG cover.jpg found (Instagram strictly requires JPEG).")

    if "tiktok" in effective_platforms:
        post_mode = (os.environ.get("TIKTOK_POST_MODE") or "").strip() or "DIRECT_POST"
        fields.extend(
            [
                ("tiktok_title", payload.full_caption[:2200]),
                ("post_mode", post_mode),
                ("is_aigc", ai_flag),
            ]
        )
        # Omit privacy_level per official docs so TikTok applies the account's own valid default.
        if (not tiktok_caps) or ("cover_image" in tiktok_caps):
            tt_cover = _select_cover_file(payload, jpeg_only=False)
            if tt_cover is not None:
                cpath, cmime = tt_cover
                files.append(("tiktok_cover_image", cpath.name, cmime, cpath.read_bytes()))

    # 5. Send multipart POST with Idempotency-Key header (prevents duplicate posts on retry/timeout)
    idem_suffix = f"-{payload.scheduled_date}" if is_scheduled else ("-queue" if is_queued else "")
    idempotency_key = f"cts-{payload.slug}-{'-'.join(sorted(effective_platforms))}{idem_suffix}"
    body, content_type = _encode_multipart(fields, files)
    try:
        resp = _http_request(
            upload_url,
            body=body,
            headers={
                "Authorization": f"Apikey {api_key}",
                "Content-Type": content_type,
                "Idempotency-Key": idempotency_key,
            },
            timeout=240,
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "HTTP 403" in msg and "tiktok" in msg.lower():
            raise RuntimeError(
                f"{msg} | Hint: TikTok uploads require a paid Upload-Post plan. "
                f"Run with platforms='youtube,instagram' or set PUBLISH_PLATFORMS=youtube,instagram."
            ) from exc
        raise

    # 6. Handle 202 Accepted (scheduled_date / add_to_queue)
    if resp.get("job_id"):
        return {
            "ok": True,
            "dispatch_state": "scheduled",
            "resolved_user": resolved_user,
            "effective_platforms": effective_platforms,
            "job_id": resp["job_id"],
            "scheduled_date": resp.get("scheduled_date") or payload.scheduled_date,
            "external_id": payload.slug,
            "notes": notes,
            "raw_response": resp,
        }

    # 7. Handle async processing: poll Upload Status until completed/failed (or timeout)
    final_resp = resp
    req_id = resp.get("request_id")
    if req_id and "results" not in resp:
        poll_interval = float(os.environ.get("UPLOAD_POST_POLL_INTERVAL_S") or DEFAULT_POLL_INTERVAL_S)
        poll_timeout = float(os.environ.get("UPLOAD_POST_POLL_TIMEOUT_S") or DEFAULT_POLL_TIMEOUT_S)
        final_resp = _poll_upload_post_status(
            status_url=status_url,
            api_key=api_key,
            request_id=str(req_id),
            timeout_s=poll_timeout,
            interval_s=poll_interval,
        )
        if final_resp.get("timed_out"):
            return {
                "ok": True,
                "dispatch_state": "submitted_async",
                "resolved_user": resolved_user,
                "effective_platforms": effective_platforms,
                "request_id": str(req_id),
                "external_id": payload.slug,
                "notes": notes
                + [
                    f"Upload accepted (request_id={req_id}) and still processing on Upload-Post after "
                    f"{poll_timeout:.0f}s; check GET /api/uploadposts/status?request_id={req_id}."
                ],
                "raw_response": final_resp,
            }

    # 8. Evaluate per-platform outcomes
    summary = _summarize_upload_post_results(final_resp)
    top_status = str(final_resp.get("status") or "").lower()
    explicit_failure = (final_resp.get("success") is False) or (top_status in ("failed", "not_found"))

    if explicit_failure and not summary["succeeded"]:
        err_detail = final_resp.get("message") or final_resp.get("error") or summary["failed"] or final_resp
        raise RuntimeError(f"Upload-Post upload failed for {payload.slug}: {err_detail}")

    if summary["has_platform_results"] and summary["failed"] and not summary["succeeded"]:
        raise RuntimeError(
            f"Upload-Post failed on all attempted platforms for {payload.slug}: {summary['failed']}"
        )

    out: dict[str, Any] = {
        "ok": True,
        "dispatch_state": "published",
        "resolved_user": resolved_user,
        "effective_platforms": effective_platforms,
        "request_id": final_resp.get("request_id") or req_id,
        "external_id": payload.slug,
        "platform_urls": summary["platform_urls"],
        "succeeded_platforms": summary["succeeded"],
        "warnings": summary["warnings"],
        "notes": notes,
        "raw_response": final_resp,
    }
    if summary["failed"]:
        out["partial_failures"] = summary["failed"]
        out["warnings"] = list(summary["warnings"]) + [
            f"Partial failure on {p}: {e}" for p, e in summary["failed"].items()
        ]
    return out


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
    api_key = (os.environ.get("PUBLISH_API_KEY") or "").strip()
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
            "title": payload.full_caption[:2200],
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
    """Universal JSON webhook for Make.com / n8n / Zapier / custom automation workflows."""
    webhook_url = (os.environ.get("PUBLISH_WEBHOOK_URL") or "").strip()
    if not webhook_url:
        raise RuntimeError("webhook provider requires PUBLISH_WEBHOOK_URL secret")

    headers = {"Content-Type": "application/json"}
    api_key = (os.environ.get("PUBLISH_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    plats = [p.strip().lower() for p in payload.platforms if p.strip()]
    yt_tags = payload.youtube_tags()
    size_bytes = payload.mp4_path.stat().st_size
    cover_png_url = payload.cover_url[:-4] + ".png" if payload.cover_url.endswith(".jpg") else payload.cover_url
    ig_audio_name = (os.environ.get("IG_AUDIO_NAME") or "").strip() or DEFAULT_IG_AUDIO_NAME
    playlist_id = (payload.youtube_playlist_id or os.environ.get("YOUTUBE_PLAYLIST_ID") or "").strip() or None

    body = {
        "episode_id": payload.episode_id,
        "slug": payload.slug,
        "platforms": plats,
        "platforms_csv": ",".join(plats),
        "publish_youtube": "youtube" in plats,
        "publish_instagram": "instagram" in plats,
        "publish_tiktok": "tiktok" in plats,
        "scheduled_date": payload.scheduled_date,
        "timezone": payload.timezone,
        "youtube": {
            "title": payload.youtube_title,
            "description": payload.youtube_description,
            "tags": yt_tags,
            "tags_csv": ",".join(yt_tags),
            "category_id": YOUTUBE_SCIENCE_TECH_CATEGORY_ID,
            "privacy_status": "private" if payload.scheduled_date else "public",
            "publish_at": payload.scheduled_date,
            "made_for_kids": False,
            "ai_disclosure": bool(payload.ai_disclosure),
            "language": payload.language,
            "playlist_id": playlist_id,
            "pinned_comment": payload.pinned_comment,
        },
        "instagram_tiktok": {
            "caption": payload.caption,
            "hashtags": payload.hashtags,
            "hashtags_text": " ".join(h for h in payload.hashtags if h.strip()),
            "full_caption": payload.full_caption,
            "audio_name": ig_audio_name,
            "pinned_comment": payload.pinned_comment,
        },
        "media": {
            "video_url": payload.video_url,
            "cover_url": payload.cover_url,
            "cover_jpg_url": payload.cover_url,
            "cover_png_url": cover_png_url,
            "video_filename": payload.mp4_path.name,
            "video_size_bytes": size_bytes,
            "video_size_mb": round(size_bytes / (1024 * 1024), 2),
            "has_cover_jpg": bool(payload.cover_jpg_path and payload.cover_jpg_path.is_file()),
        },
    }
    return _http_request(webhook_url, body=json.dumps(body).encode("utf-8"), headers=headers)


def inspect_publish_account(provider: str | None = None) -> dict[str, Any]:
    """Read-only diagnostic summary for `buffer`, `direct` (YouTube/Instagram), or `upload_post`."""
    from cts_factory.publish.buffer import inspect_buffer_account
    from cts_factory.publish.direct import has_direct_credentials, inspect_direct_account

    prov = (provider or "").strip().lower()
    if not prov or prov == "auto":
        env_prov = (os.environ.get("PUBLISH_PROVIDER") or "").strip().lower()
        if env_prov:
            prov = env_prov
        elif (os.environ.get("BUFFER_API_KEY") or "").strip():
            prov = "buffer"
        elif has_direct_credentials():
            prov = "direct"
        else:
            prov = "upload_post"

    if prov == "buffer":
        return inspect_buffer_account()
    if prov in ("direct", "youtube_direct", "instagram_direct"):
        return inspect_direct_account()
    return inspect_upload_post_account()


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
            "youtube_tags": payload.youtube_tags(),
            "instagram_tiktok_caption": payload.full_caption,
            "first_comment": payload.pinned_comment,
            "has_cover_jpg": bool(payload.cover_jpg_path and payload.cover_jpg_path.is_file()),
            "scheduled_date": payload.scheduled_date,
            "timezone": payload.timezone,
            "add_to_queue": payload.add_to_queue,
            "video_url": payload.video_url,
            "cover_url": payload.cover_url,
            "video_size_bytes": payload.mp4_path.stat().st_size,
        }

    from cts_factory.publish.buffer import publish_via_buffer
    from cts_factory.publish.direct import publish_instagram_direct, publish_via_direct, publish_youtube_direct

    dispatch_map = {
        "buffer": publish_via_buffer,
        "direct": publish_via_direct,
        "youtube_direct": publish_youtube_direct,
        "instagram_direct": publish_instagram_direct,
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
