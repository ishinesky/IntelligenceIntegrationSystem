from __future__ import annotations

import argparse
import json
from pathlib import Path

from .column_service import ColumnService


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or export the OPC resource portal read model.")
    sub = parser.add_subparsers(dest="command", required=True)

    columns = sub.add_parser("columns", help="List portal columns")
    columns.add_argument("--include-disabled", action="store_true")

    feed = sub.add_parser("feed", help="List feed items")
    feed.add_argument("--column-id", default="")
    feed.add_argument("--keyword", default="")
    feed.add_argument("--min-quality", type=float, default=0)
    feed.add_argument("--min-actionability", type=float, default=0)
    feed.add_argument("--limit", type=int, default=50)

    review = sub.add_parser("review", help="Show one review detail")
    review.add_argument("review_id")

    rss = sub.add_parser("rss", help="Export RSS XML")
    rss.add_argument("--column-id", default="")
    rss.add_argument("--keyword", default="")
    rss.add_argument("--limit", type=int, default=30)
    rss.add_argument("--base-url", default="")
    rss.add_argument("--title", default="OPC Resource Feed")
    rss.add_argument("--output", default="")

    args = parser.parse_args()
    service = ColumnService()

    if args.command == "columns":
        print_json(service.public_columns(include_disabled=args.include_disabled))
    elif args.command == "feed":
        print_json(service.public_feed({
            "column_id": args.column_id,
            "keyword": args.keyword,
            "min_quality": args.min_quality,
            "min_actionability": args.min_actionability,
            "limit": args.limit,
        }))
    elif args.command == "review":
        print_json(service.public_review_detail(args.review_id))
    elif args.command == "rss":
        xml = service.public_rss({
            "column_id": args.column_id,
            "keyword": args.keyword,
            "limit": args.limit,
            "base_url": args.base_url,
            "title": args.title,
        })
        if args.output:
            Path(args.output).write_text(xml, encoding="utf-8")
            print(args.output)
        else:
            print(xml)


if __name__ == "__main__":
    main()
