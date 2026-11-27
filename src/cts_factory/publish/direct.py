"""100% Free Direct Official API Publishers (YouTube Data API v3 + Instagram Graph API).

Zero paid third-party intermediaries, zero monthly SaaS limits, and strictly Python 3.12 stdlib-only.
- YouTube Data API v3: 10,000 free quota units/day (~6 Shorts/day, ~180/month forever), direct binary resumable upload
  (works on PRIVATE GitHub repositories!), custom thumbnail, native scheduled publishAt, first comment, and playlist.
- Instagram Graph API (v21.0): 100% free Reels container + status poll + publish + permalink + first comment
  (requires publicly reachable HTTPS video_url via public repo or PUBLISH_MEDIA_BASE_URL like Cloudflare R2).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cts_factory.publish.connectors import PublishPayload

USER_AGENT = "FailSafeLab-CTS-DirectPublisher/1.0"
YOUTUBE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
YOUTUBE_THUMBNAIL_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_SCIENCE_TECH_CATEGORY_ID = "28"
DEFAULT_IG_GRAPH_VERSION = "v21.0"
DEFAULT_IG_AUDIO_NAME = "FailSafe Lab Original Audio"
DEFAULT_IG_POLL_INTERVAL_S = 5.0
DEFAULT_IG_POLL_TIMEOUT_S = 180.0


def _http_call(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    """Perform an HTTP call using stdlib urllib and return (status_code, lower_headers, parsed_json)."""
    req_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            try:
                parsed = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                parsed = {"body": raw[:500]}
            return resp.status, resp_headers, parsed
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:900]
        raise RuntimeError(f"HTTP {exc.code} {method} {url.split('?')[0]}: {err_body}") from exc


def _youtube_credentials() -> tuple[str, str, str]:
    return (
        (os.environ.get("YOUTUBE_CLIENT_ID") or "").strip(),
        (os.environ.get("YOUTUBE_CLIENT_SECRET") or "").strip(),
        (os.environ.get("YOUTUBE_REFRESH_TOKEN") or "").strip(),
    )


def _instagram_credentials() -> tuple[str, str, str]:
    return (
        (os.environ.get("IG_USER_ID") or "").strip(),
        (os.environ.get("IG_ACCESS_TOKEN") or "").strip(),
        ((os.environ.get("IG_GRAPH_VERSION") or "").strip() or DEFAULT_IG_GRAPH_VERSION),
    )


def has_direct_credentials() -> bool:
    """Return True if either YouTube Data API or Instagram Graph API credentials are configured."""
    yt_id, yt_sec, yt_ref = _youtube_credentials()
    ig_uid, ig_tok, _ = _instagram_credentials()
    return bool((yt_id and yt_sec and yt_ref) or (ig_uid and ig_tok))


def _refresh_youtube_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange permanent OAuth2 refresh_token for a fresh Google API access_token."""
    form = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    _, _, data = _http_call(
        "POST",
        YOUTUBE_OAUTH_TOKEN_URL,
        body=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise RuntimeError(f"Google OAuth token refresh returned no access_token: {data}")
    return token


def publish_youtube_direct(payload: "PublishPayload") -> dict[str, Any]:
    """Upload a Short directly via YouTube Data API v3 (resumable binary upload + thumbnail + first comment + playlist)."""
    client_id, client_secret, refresh_token = _youtube_credentials()
    if not (client_id and client_secret and refresh_token):
        raise RuntimeError(
            "YouTube direct publish requires YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN secrets"
        )

    access_token = _refresh_youtube_access_token(client_id, client_secret, refresh_token)
    video_bytes = payload.mp4_path.read_bytes()

    lang_full = (payload.language or "en-US").strip()
    lang_short = lang_full.split("-")[0] or "en"
    is_scheduled = bool(payload.scheduled_date)

    status_block: dict[str, Any] = {
        "privacyStatus": "private" if is_scheduled else "public",
        "selfDeclaredMadeForKids": False,
        "embeddable": True,
        "publicStatsViewable": True,
        "containsSyntheticMedia": bool(payload.ai_disclosure),
    }
    if is_scheduled:
        status_block["publishAt"] = str(payload.scheduled_date).strip()

    metadata = {
        "snippet": {
            "title": payload.youtube_title[:100],
            "description": payload.youtube_description,
            "tags": payload.youtube_tags(),
            "categoryId": YOUTUBE_SCIENCE_TECH_CATEGORY_ID,
            "defaultLanguage": lang_short,
            "defaultAudioLanguage": lang_full,
        },
        "status": status_block,
    }

    # Step 1: Initiate resumable upload session
    init_url = f"{YOUTUBE_UPLOAD_URL}?uploadType=resumable&part=snippet,status"
    _, init_headers, _ = _http_call(
        "POST",
        init_url,
        body=json.dumps(metadata).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(len(video_bytes)),
            "X-Upload-Content-Type": "video/mp4",
        },
        timeout=60,
    )
    upload_uri = init_headers.get("location")
    if not upload_uri:
        raise RuntimeError("YouTube resumable upload initiation did not return a Location header")

    # Step 2: Upload MP4 binary directly
    _, _, video_resp = _http_call(
        "PUT",
        upload_uri,
        body=video_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(len(video_bytes)),
        },
        timeout=300,
    )
    video_id = str(video_resp.get("id") or "").strip()
    if not video_id:
        raise RuntimeError(f"YouTube upload completed without returning a video id: {video_resp}")

    video_url = f"https://www.youtube.com/shorts/{video_id}"
    warnings: list[str] = []
    thumbnail_set = False
    first_comment_id: str | None = None
    playlists_added: list[str] = []

    # Step 3 (best-effort): Set custom thumbnail (cover.jpg preferred; <= 2 MB YouTube limit)
    thumb_path = payload.cover_jpg_path if (payload.cover_jpg_path and payload.cover_jpg_path.is_file()) else payload.cover_path
    if thumb_path and thumb_path.is_file():
        thumb_mime = "image/jpeg" if thumb_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        thumb_bytes = thumb_path.read_bytes()
        if len(thumb_bytes) <= 2 * 1024 * 1024:
            try:
                thumb_url = f"{YOUTUBE_THUMBNAIL_URL}?{urllib.parse.urlencode({'videoId': video_id, 'uploadType': 'media'})}"
                _http_call(
                    "POST",
                    thumb_url,
                    body=thumb_bytes,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": thumb_mime,
                        "Content-Length": str(len(thumb_bytes)),
                    },
                    timeout=60,
                )
                thumbnail_set = True
            except Exception as exc:
                warnings.append(f"youtube thumbnail skipped (video already published): {exc}")
        else:
            warnings.append(f"youtube thumbnail skipped: {thumb_path.name} exceeds 2 MB limit")

    # Step 4 (best-effort): Post first comment (requires youtube.force-ssl scope; never fails publish)
    if payload.pinned_comment.strip() and not is_scheduled:
        try:
            comment_body = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {"snippet": {"textOriginal": payload.pinned_comment.strip()}},
                }
            }
            _, _, c_resp = _http_call(
                "POST",
                f"{YOUTUBE_API_BASE}/commentThreads?part=snippet",
                body=json.dumps(comment_body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                timeout=30,
            )
            first_comment_id = str(c_resp.get("id") or "") or None
        except Exception as exc:
            warnings.append(f"youtube first_comment skipped (video already published): {exc}")

    # Step 5 (best-effort): Add to playlist(s) if YOUTUBE_PLAYLIST_ID is configured
    raw_playlists = (payload.youtube_playlist_id or os.environ.get("YOUTUBE_PLAYLIST_ID") or "").strip()
    for pid in [p.strip() for p in raw_playlists.split(",") if p.strip()]:
        try:
            pl_body = {
                "snippet": {
                    "playlistId": pid,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            }
            _http_call(
                "POST",
                f"{YOUTUBE_API_BASE}/playlistItems?part=snippet",
                body=json.dumps(pl_body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                timeout=30,
            )
            playlists_added.append(pid)
        except Exception as exc:
            warnings.append(f"youtube playlist {pid} skipped: {exc}")

    return {
        "success": True,
        "platform": "youtube",
        "video_id": video_id,
        "url": video_url,
        "scheduled": is_scheduled,
        "publish_at": payload.scheduled_date if is_scheduled else None,
        "thumbnail_set": thumbnail_set,
        "first_comment_id": first_comment_id,
        "playlists_added": playlists_added,
        "warnings": warnings,
    }


def publish_instagram_direct(payload: "PublishPayload") -> dict[str, Any]:
    """Publish a Reel directly via official Meta Instagram Graph API (container -> poll -> publish -> comment)."""
    ig_user_id, access_token, graph_version = _instagram_credentials()
    if not (ig_user_id and access_token):
        raise RuntimeError("Instagram direct publish requires IG_USER_ID and IG_ACCESS_TOKEN secrets")

    graph_base = f"https://graph.facebook.com/{graph_version}"
    ig_audio_name = (os.environ.get("IG_AUDIO_NAME") or "").strip() or DEFAULT_IG_AUDIO_NAME

    # Step 1: Create REELS container (Meta downloads video_url + cover_url via HTTPS)
    create_params: dict[str, str] = {
        "media_type": "REELS",
        "video_url": payload.video_url,
        "caption": payload.full_caption[:2200],
        "share_to_feed": "true",
        "audio_name": ig_audio_name,
        "access_token": access_token,
    }
    if payload.cover_url:
        create_params["cover_url"] = payload.cover_url

    try:
        _, _, create_resp = _http_call(
            "POST",
            f"{graph_base}/{ig_user_id}/media",
            body=urllib.parse.urlencode(create_params).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60,
        )
    except RuntimeError as exc:
        raise RuntimeError(
            f"{exc} | Hint: Instagram Graph API requires video_url ({payload.video_url}) to be publicly accessible "
            f"via HTTPS (make the repo public or set PUBLISH_MEDIA_BASE_URL to a public R2/S3 bucket)."
        ) from exc

    creation_id = str(create_resp.get("id") or "").strip()
    if not creation_id:
        raise RuntimeError(f"Instagram Graph API did not return a container creation_id: {create_resp}")

    # Step 2: Poll container status until FINISHED
    poll_interval = float(os.environ.get("IG_POLL_INTERVAL_S") or DEFAULT_IG_POLL_INTERVAL_S)
    poll_timeout = float(os.environ.get("IG_POLL_TIMEOUT_S") or DEFAULT_IG_POLL_TIMEOUT_S)
    deadline = time.monotonic() + max(1.0, poll_timeout)
    status_code = "IN_PROGRESS"
    last_status_resp: dict[str, Any] = {}

    while True:
        q = urllib.parse.urlencode({"fields": "status_code,status", "access_token": access_token})
        _, _, st_resp = _http_call("GET", f"{graph_base}/{creation_id}?{q}", timeout=30)
        last_status_resp = st_resp
        status_code = str(st_resp.get("status_code") or "").upper()
        if status_code == "FINISHED":
            break
        if status_code in ("ERROR", "EXPIRED"):
            raise RuntimeError(
                f"Instagram media container {creation_id} failed with status_code={status_code}: {st_resp}. "
                f"Ensure video_url ({payload.video_url}) is publicly reachable via HTTPS."
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(
                f"Instagram media container {creation_id} timed out after {poll_timeout:.0f}s "
                f"(last status: {last_status_resp})"
            )
        time.sleep(min(poll_interval, remaining))

    # Step 3: Publish the finished container
    pub_form = urllib.parse.urlencode({"creation_id": creation_id, "access_token": access_token}).encode("utf-8")
    _, _, pub_resp = _http_call(
        "POST",
        f"{graph_base}/{ig_user_id}/media_publish",
        body=pub_form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
    )
    media_id = str(pub_resp.get("id") or "").strip()
    if not media_id:
        raise RuntimeError(f"Instagram media_publish did not return a media id: {pub_resp}")

    warnings: list[str] = []
    permalink: str | None = None
    first_comment_id: str | None = None

    # Step 4 (best-effort): Fetch Reel permalink
    try:
        pq = urllib.parse.urlencode({"fields": "permalink", "access_token": access_token})
        _, _, p_resp = _http_call("GET", f"{graph_base}/{media_id}?{pq}", timeout=30)
        permalink = str(p_resp.get("permalink") or "") or None
    except Exception as exc:
        warnings.append(f"instagram permalink lookup skipped: {exc}")

    # Step 5 (best-effort): Post first comment
    if payload.pinned_comment.strip():
        try:
            c_form = urllib.parse.urlencode(
                {"message": payload.pinned_comment.strip(), "access_token": access_token}
            ).encode("utf-8")
            _, _, c_resp = _http_call(
                "POST",
                f"{graph_base}/{media_id}/comments",
                body=c_form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            first_comment_id = str(c_resp.get("id") or "") or None
        except Exception as exc:
            warnings.append(f"instagram first_comment skipped (Reel already published): {exc}")

    return {
        "success": True,
        "platform": "instagram",
        "media_id": media_id,
        "creation_id": creation_id,
        "url": permalink or f"https://www.instagram.com/reel/{media_id}/",
        "first_comment_id": first_comment_id,
        "warnings": warnings,
    }


def publish_via_direct(payload: "PublishPayload") -> dict[str, Any]:
    """Dispatch directly to official free platform APIs (YouTube Data API v3 + Instagram Graph API)."""
    yt_id, yt_sec, yt_ref = _youtube_credentials()
    ig_uid, ig_tok, _ = _instagram_credentials()
    yt_ready = bool(yt_id and yt_sec and yt_ref)
    ig_ready = bool(ig_uid and ig_tok)

    requested = [p.strip().lower() for p in payload.platforms if p.strip()]
    notes: list[str] = []
    warnings: list[str] = []
    platform_results: dict[str, Any] = {}
    platform_urls: dict[str, str] = {}
    succeeded: list[str] = []
    failed: dict[str, str] = {}

    runnable: list[str] = []
    for plat in requested:
        if plat == "youtube":
            if yt_ready:
                runnable.append("youtube")
            else:
                notes.append(
                    "Skipped 'youtube': set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN."
                )
        elif plat == "instagram":
            if ig_ready:
                runnable.append("instagram")
            else:
                notes.append("Skipped 'instagram': set IG_USER_ID and IG_ACCESS_TOKEN to enable direct Reels.")
        elif plat == "tiktok":
            notes.append(
                "Skipped 'tiktok': TikTok direct public posting requires TikTok app audit approval "
                "(YouTube + Instagram publish directly for free)."
            )
        else:
            notes.append(f"Skipped unsupported direct platform {plat!r}.")

    if not runnable:
        raise RuntimeError(
            "direct provider has no configured credentials for requested platforms "
            f"{requested}. Configure YouTube (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN) "
            f"and/or Instagram (IG_USER_ID, IG_ACCESS_TOKEN). Notes: {notes}"
        )

    for plat in runnable:
        try:
            if plat == "youtube":
                res = publish_youtube_direct(payload)
            else:
                res = publish_instagram_direct(payload)
            platform_results[plat] = res
            succeeded.append(plat)
            if res.get("url"):
                platform_urls[plat] = str(res["url"])
            for w in res.get("warnings") or []:
                warnings.append(str(w))
        except Exception as exc:
            failed[plat] = str(exc)

    if not succeeded:
        raise RuntimeError(f"Direct publish failed on all attempted platforms for {payload.slug}: {failed}")

    all_scheduled = bool(succeeded) and all(bool(platform_results[p].get("scheduled")) for p in succeeded)
    out: dict[str, Any] = {
        "ok": True,
        "provider": "direct",
        "dispatch_state": "scheduled" if all_scheduled else "published",
        "effective_platforms": runnable,
        "succeeded_platforms": succeeded,
        "platform_urls": platform_urls,
        "warnings": warnings,
        "notes": notes,
        "results": platform_results,
    }
    if failed:
        out["partial_failures"] = failed
        out["warnings"] = list(warnings) + [f"Partial failure on {p}: {e}" for p, e in failed.items()]
    return out


def inspect_direct_account() -> dict[str, Any]:
    """Read-only verification of YouTube Data API v3 & Instagram Graph API credentials (never prints secrets)."""
    yt_id, yt_sec, yt_ref = _youtube_credentials()
    ig_uid, ig_tok, graph_ver = _instagram_credentials()

    youtube_status: dict[str, Any] = {"configured": bool(yt_id and yt_sec and yt_ref)}
    instagram_status: dict[str, Any] = {"configured": bool(ig_uid and ig_tok), "graph_version": graph_ver}
    errors: list[str] = []

    if youtube_status["configured"]:
        try:
            token = _refresh_youtube_access_token(yt_id, yt_sec, yt_ref)
            _, _, ch = _http_call(
                "GET",
                f"{YOUTUBE_API_BASE}/channels?part=snippet&mine=true",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            items = ch.get("items") or []
            if items:
                snip = items[0].get("snippet") or {}
                youtube_status.update(
                    {
                        "connected": True,
                        "channel_id": items[0].get("id"),
                        "channel_title": snip.get("title"),
                        "custom_url": snip.get("customUrl"),
                    }
                )
            else:
                youtube_status["connected"] = False
                youtube_status["error"] = "OAuth token valid, but no YouTube channel found on this Google account."
                errors.append(youtube_status["error"])
        except Exception as exc:
            youtube_status["connected"] = False
            youtube_status["error"] = str(exc)
            errors.append(f"youtube: {exc}")

    if instagram_status["configured"]:
        try:
            q = urllib.parse.urlencode({"fields": "id,username,name", "access_token": ig_tok})
            _, _, ig = _http_call("GET", f"https://graph.facebook.com/{graph_ver}/{ig_uid}?{q}", timeout=30)
            instagram_status.update(
                {
                    "connected": True,
                    "ig_user_id": ig.get("id"),
                    "username": ig.get("username"),
                    "name": ig.get("name"),
                }
            )
        except Exception as exc:
            instagram_status["connected"] = False
            instagram_status["error"] = str(exc)
            errors.append(f"instagram: {exc}")

    if not youtube_status["configured"] and not instagram_status["configured"]:
        errors.append(
            "Neither YouTube (YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET/YOUTUBE_REFRESH_TOKEN) "
            "nor Instagram (IG_USER_ID/IG_ACCESS_TOKEN) secrets are configured."
        )

    return {
        "provider": "direct",
        "youtube": youtube_status,
        "instagram": instagram_status,
        "resolution_error": "; ".join(errors) if errors else None,
    }
