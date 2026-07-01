from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .column_service import ColumnService


def load_json(path: str) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage OPC editorial review records.")
    sub = parser.add_subparsers(dest="command", required=True)

    create_parser = sub.add_parser("create", help="Create one editorial review from a JSON payload")
    create_parser.add_argument("payload_json", help="Path to JSON payload containing article/review fields")

    list_parser = sub.add_parser("list", help="List editorial reviews")
    list_parser.add_argument("--column-id", default="")
    list_parser.add_argument("--article-uuid", default="")
    list_parser.add_argument("--status", default="")
    list_parser.add_argument("--limit", type=int, default=50)

    show_parser = sub.add_parser("show", help="Show one editorial review")
    show_parser.add_argument("review_id")

    args = parser.parse_args()
    service = ColumnService()

    if args.command == "create":
        print_json(service.create_editorial_review(load_json(args.payload_json)))
    elif args.command == "list":
        print_json(service.list_editorial_reviews({
            "column_id": args.column_id,
            "article_uuid": args.article_uuid,
            "status": args.status,
            "limit": args.limit,
        }))
    elif args.command == "show":
        print_json(service.get_editorial_review(args.review_id))


if __name__ == "__main__":
    main()
