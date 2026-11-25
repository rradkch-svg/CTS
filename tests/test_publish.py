"""Unit tests for cloud multi-platform automated publishing (queue, QA gate, all 4 connectors, CLI)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cts_factory.publish.connectors import PublishPayload, dispatch_publish
from cts_factory.publish.queue import PublishQueue, sync_publish_queue, validate_episode_ready_to_publish
from cts_factory.publish.runner import run_publish_batch

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_sync_publish_queue_discovers_all_10_qa_passed_episodes(tmp_path: Path) -> None:
    qpath = tmp_path / "publish_queue.json"
    queue = sync_publish_queue(REPO_ROOT, queue_path=qpath)
    assert len(queue.items) >= 10
    assert [it.batch for it in queue.items[:3]] == ["launch-3", "launch-3", "launch-3"]
    assert all(it.status == "pending" for it in queue.items)
    assert qpath.is_file()


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
    # Queue remains pending after dry run
    reloaded = PublishQueue.load(qpath)
    assert all(it.status == "pending" for it in reloaded.items[:3])


def _sample_payload(tmp_path: Path) -> PublishPayload:
    mp4 = tmp_path / "ep01.mp4"
    cov = tmp_path / "cover.png"
    mp4.write_bytes(b"MP4DATA")
    cov.write_bytes(b"PNGDATA")
    return PublishPayload(
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
        video_url="https://raw.githubusercontent.com/rradkch-svg/CTS/main/episodios/ep01/ep01.mp4",
        cover_url="https://raw.githubusercontent.com/rradkch-svg/CTS/main/episodios/ep01/cover.png",
    )


def test_connectors_build_valid_http_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _sample_payload(tmp_path)
    calls: list[tuple[str, bytes, dict[str, str]]] = []

    def _fake_http(url: str, body: bytes, headers: dict[str, str], timeout: int = 180) -> dict:
        calls.append((url, body, headers))
        if "postiz" in url and url.endswith("/upload"):
            return {"id": "media_123", "path": "https://cdn.postiz.local/video.mp4"}
        return {"ok": True, "id": "post_999"}

    with patch("cts_factory.publish.connectors._http_request", side_effect=_fake_http):
        # 1. upload_post (multipart binary + empty UPLOAD_POST_BASE_URL like GitHub Actions unset secret!)
        monkeypatch.setenv("PUBLISH_API_KEY", "k_test")
        monkeypatch.setenv("UPLOAD_POST_USER", "failsafelab")
        monkeypatch.setenv("UPLOAD_POST_BASE_URL", "")
        out = dispatch_publish("upload_post", payload)
        assert out["ok"] is True
        assert calls[-1][0] == "https://api.upload-post.com/api/upload"
        assert b"MP4DATA" in calls[-1][1]
        assert calls[-1][2]["Authorization"] == "Apikey k_test"

        # 2. postiz (2-step binary upload + empty POSTIZ_BASE_URL fallback!)
        monkeypatch.setenv("POSTIZ_BASE_URL", "")
        monkeypatch.setenv("POSTIZ_INTEGRATION_IDS", "yt_1,tt_2,ig_3")
        out = dispatch_publish("postiz", payload)
        assert out["ok"] is True
        assert calls[-2][0] == "https://api.postiz.com/public/v1/upload"
        post_json = json.loads(calls[-1][1].decode("utf-8"))
        assert len(post_json["posts"]) == 3

        # 3. ayrshare
        out = dispatch_publish("ayrshare", payload)
        assert out["ok"] is True
        ayr_json = json.loads(calls[-1][1].decode("utf-8"))
        assert ayr_json["platforms"] == ["youtube", "tiktok", "instagram"]
        assert ayr_json["youTubeOptions"]["shorts"] is True

        # 4. webhook (n8n / Make / Zapier)
        monkeypatch.setenv("PUBLISH_WEBHOOK_URL", "https://hooks.example.test/cts")
        out = dispatch_publish("webhook", payload)
        assert out["ok"] is True
        wh_json = json.loads(calls[-1][1].decode("utf-8"))
        assert wh_json["episode_id"] == "ep01"
        assert wh_json["media"]["video_size_bytes"] == 7


def test_real_publish_marks_item_published_idempotently(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qpath = tmp_path / "publish_queue.json"
    monkeypatch.setenv("PUBLISH_WEBHOOK_URL", "https://hooks.example.test/cts")
    with patch("cts_factory.publish.connectors._http_request", return_value={"id": "wh_001"}):
        res1 = run_publish_batch(REPO_ROOT, count=1, provider="webhook", queue_path=qpath)
        assert res1["selected"] == 1 and res1["failures"] == 0
        assert res1["results"][0]["slug"] == "ep01_elevator_safety_brake"

        # Second run MUST pick ep02 (never re-post ep01!)
        res2 = run_publish_batch(REPO_ROOT, count=1, provider="webhook", queue_path=qpath)
        assert res2["selected"] == 1 and res2["failures"] == 0
        assert res2["results"][0]["slug"] == "ep02_submersible_implosion_physics"
