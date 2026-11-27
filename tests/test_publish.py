"""Unit tests for cloud multi-platform automated publishing (Upload-Post official spec, queue, QA gate, connectors)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cts_factory.publish.connectors import (
    PublishPayload,
    dispatch_publish,
    inspect_upload_post_account,
    resolve_upload_post_profile,
)
from cts_factory.publish.queue import PublishQueue, sync_publish_queue, validate_episode_ready_to_publish
from cts_factory.publish.runner import run_publish_batch

REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_profiles_response(
    profiles: list[dict] | None = None,
    plan: str = "default",
) -> dict:
    if profiles is None:
        profiles = [
            {
                "username": "default",
                "display_name": "FailSafe Lab",
                "social_accounts": {
                    "youtube": {"display_name": "FailSafe Lab", "handle": "@FailSafeLab", "reauth_required": False},
                    "instagram": {"display_name": "FailSafe Lab", "handle": "failsafelab", "reauth_required": False},
                    "tiktok": {
                        "display_name": "FailSafe Lab",
                        "handle": "failsafelab",
                        "reauth_required": False,
                        "capabilities": ["cover_image", "comments", "profile_analytics"],
                    },
                },
            }
        ]
    return {"success": True, "plan": plan, "limit": 10, "profiles": profiles}


def _sample_payload(tmp_path: Path, **overrides) -> PublishPayload:
    mp4 = tmp_path / "ep01.mp4"
    cov = tmp_path / "cover.png"
    cov_jpg = tmp_path / "cover.jpg"
    mp4.write_bytes(b"MP4DATA")
    cov.write_bytes(b"PNGDATA")
    cov_jpg.write_bytes(b"\xff\xd8\xffJPGDATA")
    kwargs = dict(
        episode_id="ep01",
        slug="ep01_elevator_safety_brake",
        platforms=["youtube", "tiktok", "instagram"],
        youtube_title="How Elevators STOP When Every Cable Snaps",
        youtube_description="",
        caption="Gravity vs 1853 mechanical trap.",
        hashtags=["#engineering", "#failsafelab"],
        pinned_comment="Comment YES or NO",
        mp4_path=mp4,
        cover_path=cov,
        cover_jpg_path=cov_jpg,
        video_url="https://raw.githubusercontent.com/rradkch-svg/CTS/main/episodios/ep01/ep01.mp4",
        cover_url="https://raw.githubusercontent.com/rradkch-svg/CTS/main/episodios/ep01/cover.jpg",
        ai_disclosure=False,
        language="en-US",
    )
    kwargs.update(overrides)
    return PublishPayload(**kwargs)


def test_sync_publish_queue_discovers_all_10_qa_passed_episodes_with_cover_jpg(tmp_path: Path) -> None:
    qpath = tmp_path / "publish_queue.json"
    queue = sync_publish_queue(REPO_ROOT, queue_path=qpath)
    assert len(queue.items) >= 10
    assert [it.batch for it in queue.items[:3]] == ["launch-3", "launch-3", "launch-3"]
    assert all(it.status == "pending" for it in queue.items)
    assert qpath.is_file()
    # Every episode has a native RGB JPEG cover.jpg <= 8 MB for Instagram Reels cover_image
    for it in queue.items:
        ready, _, info = validate_episode_ready_to_publish(REPO_ROOT, it.slug)
        assert ready is True
        cjpg = info["cover_jpg_path"]
        assert cjpg is not None and cjpg.is_file()
        assert cjpg.read_bytes()[:2] == b"\xff\xd8"
        assert cjpg.stat().st_size < 8 * 1024 * 1024


def test_qa_gate_blocks_unpublished_or_failed_episode(tmp_path: Path) -> None:
    ep_dir = tmp_path / "episodios" / "ep99_broken"
    ep_dir.mkdir(parents=True)
    (ep_dir / "ep99_broken.mp4").write_bytes(b"fake")
    (ep_dir / "cover.png").write_bytes(b"fake")
    (ep_dir / "publish_meta.json").write_text(json.dumps({"youtube_title": "Test"}), encoding="utf-8")
    (ep_dir / "qa_report.json").write_text(json.dumps({"passed": False, "violations": ["bad audio"]}), encoding="utf-8")

    ready, reason, _ = validate_episode_ready_to_publish(tmp_path, "ep99_broken")
    assert ready is False
    assert "QA gate failed" in reason


def test_dry_run_launch_3_batch_never_mutates_queue_status(tmp_path: Path) -> None:
    qpath = tmp_path / "publish_queue.json"
    res = run_publish_batch(
        repo_root=REPO_ROOT,
        count=3,
        batch="launch-3",
        provider="dry_run",
        dry_run=True,
        queue_path=qpath,
    )
    assert res["dry_run"] is True
    assert res["selected"] == 3
    assert res["failures"] == 0
    assert [r["slug"] for r in res["results"]] == [
        "ep01_elevator_safety_brake",
        "ep02_submersible_implosion_physics",
        "ep03_bank_vault_lock",
    ]
    assert res["results"][0]["response"]["has_cover_jpg"] is True
    assert "Shorts" in res["results"][0]["response"]["youtube_tags"]
    # Queue remains pending after dry run
    reloaded = PublishQueue.load(qpath)
    assert all(it.status == "pending" for it in reloaded.items[:3])


def test_upload_post_profile_auto_discovery_handles_wrong_handle_and_blank_user() -> None:
    single = _fake_profiles_response(
        profiles=[
            {
                "username": "default",
                "display_name": None,
                "social_accounts": {
                    "youtube": {"display_name": "My Channel", "handle": "@MyChannel"},
                    "instagram": {"display_name": "My IG", "handle": "myig"},
                    "tiktok": "",
                },
            }
        ]
    )
    with patch("cts_factory.publish.connectors._http_get", return_value=single):
        # Exact Run #2 scenario: user configured a social handle instead of 'default'
        uname, prof, notes = resolve_upload_post_profile("k_test", "@WrongSocialHandle")
        assert uname == "default"
        assert prof is not None
        assert any("Auto-selected sole Upload-Post profile 'default'" in n for n in notes)

        # Blank UPLOAD_POST_USER also resolves cleanly to 'default'
        uname2, _, notes2 = resolve_upload_post_profile("k_test", "")
        assert uname2 == "default"
        assert notes2

    # Multi-profile account: resolves via connected social handle or fails clearly listing available profiles
    multi = _fake_profiles_response(
        profiles=[
            {
                "username": "brand_a",
                "display_name": "Brand A",
                "social_accounts": {"youtube": {"handle": "@BrandA"}},
            },
            {
                "username": "brand_b",
                "display_name": "FailSafe Lab",
                "social_accounts": {"instagram": {"handle": "failsafelab"}},
            },
        ]
    )
    with patch("cts_factory.publish.connectors._http_get", return_value=multi):
        uname3, _, _ = resolve_upload_post_profile("k_test", "@failsafelab")
        assert uname3 == "brand_b"

        with pytest.raises(RuntimeError, match="Available profile usernames: \\['brand_a', 'brand_b'\\]"):
            resolve_upload_post_profile("k_test", "nonexistent_user")


def test_upload_post_full_official_spec_multipart_and_async_polling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _sample_payload(tmp_path)
    post_calls: list[tuple[str, bytes, dict[str, str]]] = []
    get_calls: list[str] = []
    status_poll_count = {"n": 0}

    def _fake_get(url: str, headers: dict[str, str], timeout: int = 60) -> dict:
        get_calls.append(url)
        if url.endswith("/api/uploadposts/users"):
            return _fake_profiles_response()
        if "/api/uploadposts/status?" in url:
            status_poll_count["n"] += 1
            if status_poll_count["n"] == 1:
                return {"request_id": "req_abc", "status": "in_progress", "completed": 1, "total": 3, "results": []}
            return {
                "request_id": "req_abc",
                "external_id": payload.slug,
                "status": "completed",
                "completed": 3,
                "total": 3,
                "results": [
                    {
                        "platform": "youtube",
                        "success": True,
                        "url": "https://youtube.com/shorts/abc123",
                        "thumbnail_pending": True,
                        "thumbnail_note": "Will apply after Shorts processing",
                    },
                    {"platform": "instagram", "success": True, "url": "https://instagram.com/reel/xyz"},
                    {"platform": "tiktok", "success": True, "post_url": "https://tiktok.com/@failsafelab/video/999"},
                ],
            }
        raise AssertionError(f"Unexpected GET {url}")

    def _fake_post(url: str, body: bytes, headers: dict[str, str], timeout: int = 180) -> dict:
        post_calls.append((url, body, headers))
        return {"success": True, "message": "Upload initiated successfully in background.", "request_id": "req_abc"}

    monkeypatch.setenv("PUBLISH_API_KEY", "k_test")
    monkeypatch.setenv("UPLOAD_POST_USER", "@FailSafeLab")
    monkeypatch.setenv("UPLOAD_POST_BASE_URL", "")
    monkeypatch.setenv("YOUTUBE_PLAYLIST_ID", "PLfailsafe123")
    monkeypatch.setenv("UPLOAD_POST_POLL_INTERVAL_S", "0.01")

    with (
        patch("cts_factory.publish.connectors._http_get", side_effect=_fake_get),
        patch("cts_factory.publish.connectors._http_request", side_effect=_fake_post),
    ):
        out = dispatch_publish("upload_post", payload)

    assert out["ok"] is True
    assert out["dispatch_state"] == "published"
    assert out["resolved_user"] == "default"
    assert out["request_id"] == "req_abc"
    assert out["platform_urls"]["youtube"] == "https://youtube.com/shorts/abc123"
    assert out["platform_urls"]["instagram"] == "https://instagram.com/reel/xyz"
    assert out["platform_urls"]["tiktok"] == "https://tiktok.com/@failsafelab/video/999"
    assert any("thumbnail_pending" in w for w in out["warnings"])
    assert status_poll_count["n"] == 2

    url, body, headers = post_calls[0]
    assert url == "https://api.upload-post.com/api/upload"
    assert headers["Authorization"] == "Apikey k_test"
    assert headers["Idempotency-Key"] == "cts-ep01_elevator_safety_brake-instagram-tiktok-youtube"

    # Verify every official Upload-Post parameter & cover attachment on the wire
    for expected in (
        b'name="user"\r\n\r\ndefault\r\n',
        b'name="external_id"\r\n\r\nep01_elevator_safety_brake\r\n',
        b'name="async_upload"\r\n\r\ntrue\r\n',
        b'name="first_comment"\r\n\r\nComment YES or NO\r\n',
        b'name="youtube_title"\r\n\r\nHow Elevators STOP When Every Cable Snaps\r\n',
        b'name="categoryId"\r\n\r\n28\r\n',
        b'name="selfDeclaredMadeForKids"\r\n\r\nfalse\r\n',
        b'name="containsSyntheticMedia"\r\n\r\nfalse\r\n',
        b'name="defaultLanguage"\r\n\r\nen\r\n',
        b'name="defaultAudioLanguage"\r\n\r\nen-US\r\n',
        b'name="youtube_playlist_id"\r\n\r\nPLfailsafe123\r\n',
        b'name="tags[]"\r\n\r\nShorts\r\n',
        b'name="instagram_title"\r\n\r\nGravity vs 1853 mechanical trap.\n\n#engineering #failsafelab\r\n',
        b'name="media_type"\r\n\r\nREELS\r\n',
        b'name="share_to_feed"\r\n\r\ntrue\r\n',
        b'name="tiktok_title"\r\n\r\nGravity vs 1853 mechanical trap.\n\n#engineering #failsafelab\r\n',
        b'name="post_mode"\r\n\r\nDIRECT_POST\r\n',
        b'name="thumbnail"; filename="cover.jpg"',
        b'name="cover_image"; filename="cover.jpg"',
        b'name="tiktok_cover_image"; filename="cover.jpg"',
        b"MP4DATA",
    ):
        assert expected in body, f"Missing expected multipart chunk: {expected!r}"
    # Official spec: omit privacy_level on TikTok & do not send global description
    assert b'name="privacy_level"' not in body
    assert b'name="description"' not in body


def test_upload_post_filters_unconnected_platforms_and_handles_scheduled_202(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _sample_payload(
        tmp_path,
        scheduled_date="2026-12-01T15:00:00Z",
        timezone="America/Sao_Paulo",
    )
    only_yt_ig = _fake_profiles_response(
        profiles=[
            {
                "username": "default",
                "display_name": "FailSafe Lab",
                "social_accounts": {
                    "youtube": {"handle": "@FailSafeLab", "reauth_required": False},
                    "instagram": {"handle": "failsafelab", "reauth_required": False},
                    "tiktok": "",  # unconnected!
                },
            }
        ]
    )
    captured_body: list[bytes] = []

    def _fake_post(url: str, body: bytes, headers: dict[str, str], timeout: int = 180) -> dict:
        captured_body.append(body)
        return {"success": True, "job_id": "job_sched_42", "scheduled_date": "2026-12-01T15:00:00Z"}

    monkeypatch.setenv("PUBLISH_API_KEY", "k_test")
    monkeypatch.setenv("UPLOAD_POST_USER", "default")
    with (
        patch("cts_factory.publish.connectors._http_get", return_value=only_yt_ig),
        patch("cts_factory.publish.connectors._http_request", side_effect=_fake_post),
    ):
        out = dispatch_publish("upload_post", payload)

    assert out["dispatch_state"] == "scheduled"
    assert out["job_id"] == "job_sched_42"
    assert out["effective_platforms"] == ["youtube", "instagram"]
    assert b'name="platform[]"\r\n\r\ntiktok\r\n' not in captured_body[0]
    assert b'name="scheduled_date"\r\n\r\n2026-12-01T15:00:00Z\r\n' in captured_body[0]
    assert b'name="timezone"\r\n\r\nAmerica/Sao_Paulo\r\n' in captured_body[0]
    assert b'name="async_upload"' not in captured_body[0]


def test_inspect_upload_post_account_is_read_only_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLISH_API_KEY", "SUPER_SECRET_KEY_12345")
    monkeypatch.setenv("UPLOAD_POST_USER", "@FailSafeLab")
    with patch("cts_factory.publish.connectors._http_get", return_value=_fake_profiles_response()):
        info = inspect_upload_post_account()
    serialized = json.dumps(info)
    assert "SUPER_SECRET_KEY_12345" not in serialized
    assert info["resolved_user"] == "default"
    assert info["profiles"][0]["social_accounts"]["youtube"]["connected"] is True


def test_other_connectors_build_valid_http_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _sample_payload(tmp_path)
    calls: list[tuple[str, bytes, dict[str, str]]] = []

    def _fake_http(url: str, body: bytes, headers: dict[str, str], timeout: int = 180) -> dict:
        calls.append((url, body, headers))
        if "postiz" in url and url.endswith("/upload"):
            return {"id": "media_123", "path": "https://cdn.postiz.local/video.mp4"}
        return {"ok": True, "id": "post_999"}

    with patch("cts_factory.publish.connectors._http_request", side_effect=_fake_http):
        monkeypatch.setenv("PUBLISH_API_KEY", "k_test")
        # 1. postiz (2-step binary upload + empty POSTIZ_BASE_URL fallback!)
        monkeypatch.setenv("POSTIZ_BASE_URL", "")
        monkeypatch.setenv("POSTIZ_INTEGRATION_IDS", "yt_1,tt_2,ig_3")
        out = dispatch_publish("postiz", payload)
        assert out["ok"] is True
        assert calls[-2][0] == "https://api.postiz.com/public/v1/upload"
        post_json = json.loads(calls[-1][1].decode("utf-8"))
        assert len(post_json["posts"]) == 3

        # 2. ayrshare
        out = dispatch_publish("ayrshare", payload)
        assert out["ok"] is True
        ayr_json = json.loads(calls[-1][1].decode("utf-8"))
        assert ayr_json["platforms"] == ["youtube", "tiktok", "instagram"]
        assert ayr_json["youTubeOptions"]["shorts"] is True

        # 3. webhook (Make.com / n8n / Zapier)
        monkeypatch.setenv("PUBLISH_WEBHOOK_URL", "https://hooks.example.test/cts")
        out = dispatch_publish("webhook", payload)
        assert out["ok"] is True
        wh_json = json.loads(calls[-1][1].decode("utf-8"))
        assert wh_json["episode_id"] == "ep01"
        assert wh_json["publish_youtube"] is True
        assert wh_json["publish_instagram"] is True
        assert wh_json["youtube"]["privacy_status"] == "public"
        assert "Shorts" in wh_json["youtube"]["tags_csv"]
        assert wh_json["media"]["video_size_bytes"] == 7
        assert wh_json["media"]["has_cover_jpg"] is True
        assert wh_json["media"]["cover_jpg_url"].endswith("cover.jpg")
        assert wh_json["media"]["cover_png_url"].endswith("cover.png")

    # Verify Make.com blueprint JSON parses cleanly and references expected webhook fields
    bp_path = REPO_ROOT / "automation" / "make_com_blueprint.json"
    bp = json.loads(bp_path.read_text(encoding="utf-8"))
    assert bp["flow"][0]["module"] == "gateway:CustomWebHook"
    bp_text = bp_path.read_text(encoding="utf-8")
    assert "{{1.media.video_url}}" in bp_text
    assert "{{1.instagram_tiktok.full_caption}}" in bp_text
    assert "{{1.youtube.title}}" in bp_text


def test_partial_batch_failure_persists_success_and_retry_failed_resumes_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qpath = tmp_path / "publish_queue.json"
    monkeypatch.setenv("PUBLISH_WEBHOOK_URL", "https://hooks.example.test/cts")
    attempt = {"n": 0}

    def _flaky_http(url: str, body: bytes, headers: dict[str, str], timeout: int = 180) -> dict:
        attempt["n"] += 1
        if attempt["n"] == 2:
            raise RuntimeError("HTTP 429 rate limit")
        return {"id": f"wh_{attempt['n']}"}

    with patch("cts_factory.publish.connectors._http_request", side_effect=_flaky_http):
        res1 = run_publish_batch(REPO_ROOT, count=2, provider="webhook", queue_path=qpath)
        assert res1["selected"] == 2
        assert res1["failures"] == 1
        assert res1["results"][0]["status"] == "published"
        assert res1["results"][1]["status"] == "failed"

        # Persisted queue MUST already have ep01=published and ep02=failed
        q_mid = PublishQueue.load(qpath)
        assert q_mid.get_by_slug("ep01_elevator_safety_brake").status == "published"
        assert q_mid.get_by_slug("ep02_submersible_implosion_physics").status == "failed"

        # Retry with retry_failed=True MUST pick ep02 (NEVER re-post ep01!)
        res2 = run_publish_batch(REPO_ROOT, count=1, provider="webhook", queue_path=qpath, retry_failed=True)
        assert res2["selected"] == 1
        assert res2["failures"] == 0
        assert res2["results"][0]["slug"] == "ep02_submersible_implosion_physics"
        assert PublishQueue.load(qpath).get_by_slug("ep02_submersible_implosion_physics").status == "published"


def test_scheduled_run_marks_queue_item_scheduled_and_never_reuploads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qpath = tmp_path / "publish_queue.json"
    monkeypatch.setenv("PUBLISH_API_KEY", "k_test")
    monkeypatch.setenv("UPLOAD_POST_USER", "default")
    with (
        patch("cts_factory.publish.connectors._http_get", return_value=_fake_profiles_response()),
        patch(
            "cts_factory.publish.connectors._http_request",
            return_value={"success": True, "job_id": "job_999", "scheduled_date": "2026-12-01T15:00:00Z"},
        ),
    ):
        res = run_publish_batch(
            REPO_ROOT,
            count=1,
            provider="upload_post",
            queue_path=qpath,
            scheduled_date="2026-12-01T15:00:00Z",
            tz_name="America/Sao_Paulo",
        )
    assert res["failures"] == 0
    assert res["results"][0]["status"] == "scheduled"
    q_after = PublishQueue.load(qpath)
    ep01 = q_after.get_by_slug("ep01_elevator_safety_brake")
    assert ep01 is not None and ep01.status == "scheduled"
    assert ep01.external_ids["job_id"] == "job_999"


def test_direct_publisher_youtube_and_instagram_full_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _sample_payload(tmp_path)
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "yt_cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "yt_csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "yt_ref")
    monkeypatch.setenv("YOUTUBE_PLAYLIST_ID", "PLdirect1")
    monkeypatch.setenv("IG_USER_ID", "17841400001")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "IG_SECRET_TOKEN")
    monkeypatch.setenv("IG_POLL_INTERVAL_S", "0.01")

    http_log: list[tuple[str, str]] = []
    ig_poll = {"n": 0}

    def _fake_http_call(method: str, url: str, *, body=None, headers=None, timeout=120):
        http_log.append((method, url))
        if "oauth2.googleapis.com/token" in url:
            return 200, {}, {"access_token": "yt_access_tok"}
        if "upload/youtube/v3/videos" in url and method == "POST":
            meta = json.loads(body.decode("utf-8"))
            assert meta["snippet"]["categoryId"] == "28"
            assert meta["status"]["privacyStatus"] == "public"
            assert meta["status"]["selfDeclaredMadeForKids"] is False
            assert "Shorts" in meta["snippet"]["tags"]
            return 200, {"location": "https://upload.youtube.local/session/1"}, {}
        if url == "https://upload.youtube.local/session/1" and method == "PUT":
            assert body == b"MP4DATA"
            return 200, {}, {"id": "YT_VID_001"}
        if "thumbnails/set" in url:
            assert body == b"\xff\xd8\xffJPGDATA"
            return 200, {}, {"items": [{}]}
        if "youtube/v3/commentThreads" in url:
            return 200, {}, {"id": "yt_cmt_1"}
        if "youtube/v3/playlistItems" in url:
            return 200, {}, {"id": "yt_pl_item_1"}
        if "/17841400001/media" in url and not url.endswith("/media_publish"):
            form_text = body.decode("utf-8")
            assert "media_type=REELS" in form_text
            assert "share_to_feed=true" in form_text
            return 200, {}, {"id": "ig_container_1"}
        if "/ig_container_1?" in url:
            ig_poll["n"] += 1
            return 200, {}, {"status_code": "IN_PROGRESS" if ig_poll["n"] == 1 else "FINISHED"}
        if "/17841400001/media_publish" in url:
            return 200, {}, {"id": "ig_media_99"}
        if "/ig_media_99?" in url:
            return 200, {}, {"permalink": "https://www.instagram.com/reel/DIRECT99/"}
        if "/ig_media_99/comments" in url:
            return 200, {}, {"id": "ig_cmt_99"}
        raise AssertionError(f"Unexpected call: {method} {url}")

    with patch("cts_factory.publish.direct._http_call", side_effect=_fake_http_call):
        out = dispatch_publish("direct", payload)

    assert out["ok"] is True
    assert out["provider"] == "direct"
    assert out["dispatch_state"] == "published"
    assert out["succeeded_platforms"] == ["youtube", "instagram"]
    assert out["platform_urls"]["youtube"] == "https://www.youtube.com/shorts/YT_VID_001"
    assert out["platform_urls"]["instagram"] == "https://www.instagram.com/reel/DIRECT99/"
    assert out["results"]["youtube"]["thumbnail_set"] is True
    assert out["results"]["youtube"]["first_comment_id"] == "yt_cmt_1"
    assert out["results"]["youtube"]["playlists_added"] == ["PLdirect1"]
    assert out["results"]["instagram"]["first_comment_id"] == "ig_cmt_99"
    assert any("tiktok" in n.lower() for n in out["notes"])


def test_direct_publisher_youtube_only_scheduled_and_partial_failure_safety(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only YouTube configured + scheduled_date -> publishes/schedules YouTube cleanly without requiring IG secrets
    payload = _sample_payload(tmp_path, scheduled_date="2026-12-05T15:00:00Z")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "yt_cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "yt_csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "yt_ref")
    monkeypatch.delenv("IG_USER_ID", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)

    def _fake_yt_only(method: str, url: str, *, body=None, headers=None, timeout=120):
        if "oauth2.googleapis.com/token" in url:
            return 200, {}, {"access_token": "yt_tok"}
        if "upload/youtube/v3/videos" in url:
            meta = json.loads(body.decode("utf-8"))
            assert meta["status"]["privacyStatus"] == "private"
            assert meta["status"]["publishAt"] == "2026-12-05T15:00:00Z"
            return 200, {"location": "https://upload.youtube.local/sched"}, {}
        if url == "https://upload.youtube.local/sched":
            return 200, {}, {"id": "YT_SCHED_77"}
        if "thumbnails/set" in url:
            return 200, {}, {}
        raise AssertionError(f"Unexpected call: {method} {url}")

    with patch("cts_factory.publish.direct._http_call", side_effect=_fake_yt_only):
        out = dispatch_publish("direct", payload)

    assert out["dispatch_state"] == "scheduled"
    assert out["succeeded_platforms"] == ["youtube"]
    assert any("instagram" in n.lower() for n in out["notes"])


def test_direct_check_account_verifies_channels_without_leaking_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cts_factory.publish.connectors import inspect_publish_account

    monkeypatch.setenv("PUBLISH_PROVIDER", "direct")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid_123")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "ULTRA_SECRET_YT_KEY")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "ULTRA_SECRET_REFRESH")
    monkeypatch.setenv("IG_USER_ID", "17841400001")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "ULTRA_SECRET_IG_TOKEN")

    def _fake_check(method: str, url: str, *, body=None, headers=None, timeout=120):
        if "oauth2.googleapis.com/token" in url:
            return 200, {}, {"access_token": "temp_tok"}
        if "youtube/v3/channels" in url:
            return 200, {}, {"items": [{"id": "UCfailsafe", "snippet": {"title": "FailSafe Lab", "customUrl": "@FailSafeLab"}}]}
        if "graph.facebook.com" in url:
            return 200, {}, {"id": "17841400001", "username": "failsafelab", "name": "FailSafe Lab"}
        raise AssertionError(f"Unexpected {url}")

    with patch("cts_factory.publish.direct._http_call", side_effect=_fake_check):
        info = inspect_publish_account()

    serialized = json.dumps(info)
    for secret in ("ULTRA_SECRET_YT_KEY", "ULTRA_SECRET_REFRESH", "ULTRA_SECRET_IG_TOKEN"):
        assert secret not in serialized
    assert info["provider"] == "direct"
    assert info["resolution_error"] is None
    assert info["youtube"]["channel_title"] == "FailSafe Lab"
    assert info["instagram"]["username"] == "failsafelab"


def test_buffer_graphql_publishes_youtube_tiktok_and_instagram_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _sample_payload(tmp_path)
    monkeypatch.setenv("PUBLISH_API_KEY", "BUFFER_SUPER_SECRET_KEY")
    created_inputs: list[dict] = []

    def _fake_gql(api_key: str, query: str, variables=None, timeout=90):
        assert api_key == "BUFFER_SUPER_SECRET_KEY"
        if "GetOrganizations" in query:
            return {"account": {"organizations": [{"id": "org_1", "name": "FailSafe Lab"}]}}
        if "GetChannels" in query:
            return {
                "channels": [
                    {"id": "ch_yt", "name": "FailSafe Lab", "displayName": "FailSafe Lab YT", "service": "youtube"},
                    {"id": "ch_tt", "name": "failsafelab", "displayName": "FailSafe Lab TT", "service": "tiktok"},
                    {"id": "ch_ig", "name": "failsafelab", "displayName": "FailSafe Lab IG", "service": "instagram"},
                ]
            }
        if "CreatePost" in query:
            inp = variables["input"]
            created_inputs.append(inp)
            return {"createPost": {"post": {"id": f"post_{inp['channelId']}", "status": "buffer", "dueAt": None}}}
        raise AssertionError(f"Unexpected GraphQL query: {query}")

    with patch("cts_factory.publish.buffer._buffer_graphql", side_effect=_fake_gql):
        out = dispatch_publish("buffer", payload)

    assert out["ok"] is True
    assert out["provider"] == "buffer"
    assert out["dispatch_state"] == "published"
    assert out["succeeded_platforms"] == ["youtube", "tiktok", "instagram"]
    assert len(created_inputs) == 3

    yt_inp = next(i for i in created_inputs if i["channelId"] == "ch_yt")
    assert yt_inp["mode"] == "shareNow"
    assert yt_inp["schedulingType"] == "automatic"
    assert yt_inp["assets"][0]["video"]["url"] == payload.video_url
    assert yt_inp["metadata"]["youtube"]["categoryId"] == "28"
    assert yt_inp["metadata"]["youtube"]["title"] == payload.youtube_title
    assert yt_inp["metadata"]["youtube"]["privacy"] == "public"
    assert yt_inp["metadata"]["youtube"]["madeForKids"] is False

    tt_inp = next(i for i in created_inputs if i["channelId"] == "ch_tt")
    assert tt_inp["text"] == payload.full_caption
    assert tt_inp["metadata"]["tiktok"]["isAiGenerated"] is False

    ig_inp = next(i for i in created_inputs if i["channelId"] == "ch_ig")
    assert ig_inp["metadata"]["instagram"]["type"] == "reel"
    assert ig_inp["metadata"]["instagram"]["shouldShareToFeed"] is True
    assert "firstComment" not in ig_inp["metadata"]["instagram"]


def test_buffer_instagram_retries_without_first_comment_when_paid_feature_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _sample_payload(tmp_path, platforms=["instagram"])
    monkeypatch.setenv("PUBLISH_API_KEY", "k_free")
    monkeypatch.setenv("BUFFER_ENABLE_FIRST_COMMENT", "1")
    calls = {"create": 0}

    def _fake_gql(api_key: str, query: str, variables=None, timeout=90):
        if "GetOrganizations" in query:
            return {"account": {"organizations": [{"id": "org_1", "name": "FailSafe Lab"}]}}
        if "GetChannels" in query:
            return {"channels": [{"id": "ch_ig", "displayName": "FailSafe Lab IG", "service": "instagram"}]}
        calls["create"] += 1
        ig_meta = variables["input"]["metadata"]["instagram"]
        if "firstComment" in ig_meta:
            return {"createPost": {"message": "Invalid post: First comment requires a paid plan."}}
        return {"createPost": {"post": {"id": "post_ig_ok", "status": "sending", "dueAt": None}}}

    with patch("cts_factory.publish.buffer._buffer_graphql", side_effect=_fake_gql):
        out = dispatch_publish("buffer", payload)

    assert out["ok"] is True
    assert out["succeeded_platforms"] == ["instagram"]
    assert calls["create"] == 2
    assert any("firstComment omitted" in w for w in out["warnings"])


def test_buffer_check_account_redacts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from cts_factory.publish.connectors import inspect_publish_account

    monkeypatch.setenv("PUBLISH_PROVIDER", "buffer")
    monkeypatch.setenv("PUBLISH_API_KEY", "BUFFER_KEY_DO_NOT_LEAK")

    def _fake_gql(api_key: str, query: str, variables=None, timeout=90):
        if "GetOrganizations" in query:
            return {"account": {"organizations": [{"id": "org_1", "name": "FailSafe Lab"}]}}
        return {
            "channels": [
                {"id": "ch_yt", "displayName": "FailSafe Lab", "service": "youtube", "isQueuePaused": False},
                {"id": "ch_tt", "displayName": "@failsafelab", "service": "tiktok", "isQueuePaused": False},
                {"id": "ch_ig", "displayName": "@failsafelab", "service": "instagram", "isQueuePaused": False},
            ]
        }

    with patch("cts_factory.publish.buffer._buffer_graphql", side_effect=_fake_gql):
        info = inspect_publish_account()

    assert "BUFFER_KEY_DO_NOT_LEAK" not in json.dumps(info)
    assert info["provider"] == "buffer"
    assert info["connected_services"] == ["instagram", "tiktok", "youtube"]
    assert info["resolution_error"] is None


