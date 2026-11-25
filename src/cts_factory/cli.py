"""Unified CLI for CTS Shorts Factory (FailSafe Lab)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cts_factory.audio.mixer import build_episode_audio
from cts_factory.captions.align import align_episode_captions
from cts_factory.config import AudioTimeline, BrandConfig, CaptionTrack, EpisodeScript
from cts_factory.engine.renderer import render_episode_video
from cts_factory.episodes import get_scene
from cts_factory.packaging.banner import build_channel_banner
from cts_factory.packaging.cover import build_episode_package
from cts_factory.publish import run_publish_batch, sync_publish_queue
from cts_factory.qa.validator import run_episode_qa


def _repo_root() -> Path:
    return Path.cwd()


def _load_brand_and_script(slug: str) -> tuple[BrandConfig, EpisodeScript, Path]:
    root = _repo_root()
    brand = BrandConfig.load(root / "brand.json")
    ep_dir = root / "episodios" / slug
    script = EpisodeScript.load(ep_dir / "script.json")
    return brand, script, ep_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cts_factory", description="FailSafe Lab 2.5D Shorts Factory CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build-banner", help="Generate 2560x1440 YouTube channel banner and preview")
    sub.add_parser("publish-sync", help="Sync publish_queue.json with all QA-passed episodes")

    p_pub = sub.add_parser("publish", help="Auto-publish pending QA-passed episodes via unified connector")
    p_pub.add_argument("--check-account", action="store_true", help="Inspect Upload-Post profiles & connected accounts")
    p_pub.add_argument("--count", type=int, default=1, help="Max episodes to publish in this run (default: 1)")
    p_pub.add_argument("--episode", default=None, help="Optional single episode slug to publish")
    p_pub.add_argument("--batch", default=None, help="Optional batch tag filter (e.g. launch-3, daily)")
    p_pub.add_argument("--platforms", default=None, help="Optional comma-separated platform override")
    p_pub.add_argument("--scheduled-date", default=None, help="Optional ISO-8601 schedule timestamp")
    p_pub.add_argument("--timezone", default=None, help="Optional IANA timezone (e.g. America/Sao_Paulo)")
    p_pub.add_argument("--add-to-queue", action="store_true", help="Schedule in Upload-Post next queue slot")
    p_pub.add_argument("--retry-failed", action="store_true", help="Retry previously failed queue items")
    p_pub.add_argument(
        "--provider",
        default="auto",
        help="Connector: auto | upload_post | postiz | ayrshare | webhook | dry_run",
    )
    p_pub.add_argument("--dry-run", action="store_true", help="Validate & preview payload without calling external API")

    for name in ("build-audio", "align-captions", "package"):
        p = sub.add_parser(name)
        p.add_argument("--episode", required=True, help="Episode slug under episodios/")

    p_render = sub.add_parser("render")
    p_render.add_argument("--episode", required=True)
    p_render.add_argument("--draft", action="store_true")
    p_render.add_argument("--final", action="store_true")

    p_qa = sub.add_parser("qa")
    p_qa.add_argument("--episode", required=True)
    p_qa.add_argument("--with-reel-watch", action="store_true")

    p_all = sub.add_parser("build-all")
    p_all.add_argument("--episode", required=True)
    p_all.add_argument("--draft", action="store_true")
    p_all.add_argument("--final", action="store_true")
    p_all.add_argument("--with-reel-watch", action="store_true")

    args = parser.parse_args(argv)
    root = _repo_root()

    if args.cmd == "build-banner":
        brand = BrandConfig.load(root / "brand.json")
        banner, preview = build_channel_banner(brand, root / "marca", repo_root=root)
        print(json.dumps({"banner": str(banner), "preview": str(preview)}, indent=2))
        return 0

    if args.cmd == "publish-sync":
        queue = sync_publish_queue(root)
        summary = {
            "total": len(queue.items),
            "pending": sum(1 for i in queue.items if i.status == "pending"),
            "published": sum(1 for i in queue.items if i.status == "published"),
            "scheduled": sum(1 for i in queue.items if i.status == "scheduled"),
            "failed": sum(1 for i in queue.items if i.status == "failed"),
            "queue_file": str(root / "publish_queue.json"),
        }
        print(json.dumps(summary, indent=2))
        return 0

    if args.cmd == "publish":
        if args.check_account:
            from cts_factory.publish import inspect_upload_post_account

            info = inspect_upload_post_account()
            print(json.dumps(info, indent=2, ensure_ascii=False))
            return 0 if not info.get("resolution_error") else 2
        platforms_override = [p.strip().lower() for p in (args.platforms or "").split(",") if p.strip()] or None
        res = run_publish_batch(
            repo_root=root,
            count=args.count,
            episode=args.episode or None,
            batch=args.batch or None,
            provider=args.provider,
            dry_run=bool(args.dry_run),
            platforms_override=platforms_override,
            scheduled_date=args.scheduled_date or None,
            tz_name=args.timezone or None,
            add_to_queue=bool(args.add_to_queue),
            retry_failed=bool(args.retry_failed),
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["failures"] == 0 else 2

    brand, script, ep_dir = _load_brand_and_script(args.episode)
    mp4_path = ep_dir / f"{script.slug}.mp4"

    if args.cmd == "build-audio":
        timeline, stats = build_episode_audio(brand, script, ep_dir, repo_root=root)
        print(json.dumps({"duration_s": timeline.total_duration_s, "loudnorm": stats}, indent=2))
        return 0

    if args.cmd == "align-captions":
        timeline = AudioTimeline.load(ep_dir / "narration_timeline.json")
        track = align_episode_captions(brand, script, timeline, ep_dir)
        print(json.dumps({"blocks": len(track.blocks)}, indent=2))
        return 0

    if args.cmd == "render":
        timeline = AudioTimeline.load(ep_dir / "narration_timeline.json")
        captions = CaptionTrack.load(ep_dir / "captions.json")
        scene = get_scene(script.slug)
        info = render_episode_video(
            brand, script, timeline, captions, scene, mp4_path, draft=bool(args.draft and not args.final), repo_root=root
        )
        print(json.dumps(info, indent=2))
        return 0

    if args.cmd == "package":
        scene = get_scene(script.slug)
        out = build_episode_package(brand, script, scene, ep_dir, repo_root=root)
        print(json.dumps({k: str(v) for k, v in out.items()}, indent=2))
        return 0

    if args.cmd == "qa":
        report = run_episode_qa(brand, mp4_path, ep_dir, with_reel_watch=bool(args.with_reel_watch), repo_root=root)
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 2

    if args.cmd == "build-all":
        print(f"=== [1/5] Audio + Gemini TTS ({script.slug}) ===", flush=True)
        timeline, loud_stats = build_episode_audio(brand, script, ep_dir, repo_root=root)
        print(f"Audio ready: {timeline.total_duration_s:.2f}s | loudnorm={loud_stats}", flush=True)

        print(f"=== [2/5] Whisper Caption Alignment ({script.slug}) ===", flush=True)
        captions = align_episode_captions(brand, script, timeline, ep_dir)
        print(f"Captions ready: {len(captions.blocks)} blocks", flush=True)

        print(f"=== [3/5] Rendering 1080x1920 30fps 2.5D Video ({script.slug}) ===", flush=True)
        scene = get_scene(script.slug)
        render_info = render_episode_video(
            brand, script, timeline, captions, scene, mp4_path, draft=bool(args.draft and not args.final), repo_root=root
        )
        print(f"Video rendered: {render_info}", flush=True)

        print(f"=== [4/5] Packaging Cover + Grid Preview + Metadata ({script.slug}) ===", flush=True)
        pkg = build_episode_package(brand, script, scene, ep_dir, repo_root=root)
        print(f"Packaging ready: {list(pkg.keys())}", flush=True)

        print(f"=== [5/5] Mandatory QA Gate ({script.slug}) ===", flush=True)
        report = run_episode_qa(brand, mp4_path, ep_dir, with_reel_watch=bool(args.with_reel_watch), repo_root=root)
        print(json.dumps({k: v for k, v in report.items() if k != "reel_watch_stdout"}, indent=2), flush=True)
        return 0 if report["passed"] else 2

    return 1


if __name__ == "__main__":
    sys.exit(main())
