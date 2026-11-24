"""Zero-dependency stdlib CLI entrypoint for cloud GitHub Actions: `python -m cts_factory.publish`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cts_factory.publish.queue import sync_publish_queue
from cts_factory.publish.runner import run_publish_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cts_factory.publish",
        description="FailSafe Lab zero-dependency multi-platform auto-publisher (YouTube + TikTok + Reels)",
    )
    parser.add_argument("--sync-only", action="store_true", help="Only sync publish_queue.json without publishing")
    parser.add_argument("--count", type=int, default=1, help="Max episodes to publish in this run (default: 1)")
    parser.add_argument("--episode", default=None, help="Optional single episode slug to publish")
    parser.add_argument("--batch", default=None, help="Optional batch filter (e.g. launch-3, daily)")
    parser.add_argument(
        "--provider",
        default="auto",
        help="Connector: auto | upload_post | postiz | ayrshare | webhook | dry_run",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate & preview payload without calling external API")
    args = parser.parse_args(argv)
    root = Path.cwd()

    if args.sync_only:
        queue = sync_publish_queue(root)
        print(
            json.dumps(
                {
                    "total": len(queue.items),
                    "pending": sum(1 for i in queue.items if i.status == "pending"),
                    "published": sum(1 for i in queue.items if i.status == "published"),
                    "queue_file": str(root / "publish_queue.json"),
                },
                indent=2,
            )
        )
        return 0

    res = run_publish_batch(
        repo_root=root,
        count=args.count,
        episode=args.episode or None,
        batch=args.batch or None,
        provider=args.provider,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res["failures"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
