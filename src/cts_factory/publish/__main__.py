"""Zero-dependency stdlib CLI entrypoint for cloud GitHub Actions: `python -m cts_factory.publish`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cts_factory.publish.connectors import inspect_publish_account
from cts_factory.publish.queue import sync_publish_queue
from cts_factory.publish.runner import run_publish_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cts_factory.publish",
        description="FailSafe Lab zero-dependency multi-platform auto-publisher (YouTube + TikTok + Reels)",
    )
    parser.add_argument("--sync-only", action="store_true", help="Only sync publish_queue.json without publishing")
    parser.add_argument(
        "--check-account",
        action="store_true",
        help="Read-only diagnostic: inspect configured direct (YouTube/Instagram) or Upload-Post accounts",
    )
    parser.add_argument("--count", type=int, default=1, help="Max episodes to publish in this run (default: 1)")
    parser.add_argument("--episode", default=None, help="Optional single episode slug to publish")
    parser.add_argument("--batch", default=None, help="Optional batch filter (e.g. launch-3, daily)")
    parser.add_argument(
        "--platforms",
        default=None,
        help="Optional comma-separated platform override (e.g. youtube,instagram or youtube,tiktok,instagram)",
    )
    parser.add_argument(
        "--scheduled-date",
        default=None,
        help="Optional ISO-8601 future timestamp for native scheduling (e.g. 2026-11-26T15:00:00Z)",
    )
    parser.add_argument(
        "--timezone",
        default=None,
        help="Optional IANA timezone for scheduled_date/add_to_queue (e.g. America/Sao_Paulo)",
    )
    parser.add_argument(
        "--add-to-queue",
        action="store_true",
        help="Add post to Upload-Post's next available queue slot (cannot be combined with --scheduled-date)",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Include previously failed queue items when selecting episodes to publish",
    )
    parser.add_argument(
        "--provider",
        default="auto",
        help="Connector: auto | direct | upload_post | postiz | ayrshare | webhook | dry_run",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate & preview payload without calling external API")
    args = parser.parse_args(argv)
    root = Path.cwd()

    if args.check_account:
        info = inspect_publish_account(provider=args.provider)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0 if not info.get("resolution_error") else 2

    if args.sync_only:
        queue = sync_publish_queue(root)
        print(
            json.dumps(
                {
                    "total": len(queue.items),
                    "pending": sum(1 for i in queue.items if i.status == "pending"),
                    "published": sum(1 for i in queue.items if i.status == "published"),
                    "scheduled": sum(1 for i in queue.items if i.status == "scheduled"),
                    "failed": sum(1 for i in queue.items if i.status == "failed"),
                    "queue_file": str(root / "publish_queue.json"),
                },
                indent=2,
            )
        )
        return 0

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


if __name__ == "__main__":
    sys.exit(main())
