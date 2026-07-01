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
    parser = argparse.ArgumentParser(description="Lookup or import articles for OPC editorial generation.")
    sub = parser.add_subparsers(dest="command", required=True)

    lookup_parser = sub.add_parser("lookup", help="Lookup one article by UUID or source URL")
    lookup_parser.add_argument("--uuid", default="")
    lookup_parser.add_argument("--url", default="")

    import_parser = sub.add_parser("import", help="Import one article JSON into the local JSONL mirror")
    import_parser.add_argument("payload_json")

    generate_parser = sub.add_parser("generate", help="Lookup article and generate editorial review")
    generate_parser.add_argument("--uuid", default="")
    generate_parser.add_argument("--url", default="")
    generate_parser.add_argument("--column-id", default="")
    generate_parser.add_argument("--dry-run", action="store_true")
    generate_parser.add_argument("--no-persist", action="store_true")

    args = parser.parse_args()
    service = ColumnService()

    if args.command == "lookup":
        print_json(service.lookup_article({"article_uuid": args.uuid, "source_url": args.url}))
    elif args.command == "import":
        print_json(service.import_article(load_json(args.payload_json)))
    elif args.command == "generate":
        payload = {
            "article_uuid": args.uuid,
            "source_url": args.url,
            "column_id": args.column_id,
        }
        if args.dry_run:
            payload["dry_run"] = True
        if args.no_persist:
            payload["persist"] = False
        print_json(service.generate_editorial_review_from_article(payload))


if __name__ == "__main__":
    main()
