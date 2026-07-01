from __future__ import annotations

import argparse
import json
from typing import Any

from .column_service import ColumnService


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage dynamic OPC columns.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List columns")
    list_parser.add_argument("--enabled-only", action="store_true")

    show_parser = sub.add_parser("show", help="Show one column")
    show_parser.add_argument("column_id")

    enable_parser = sub.add_parser("enable", help="Enable a column")
    enable_parser.add_argument("column_id")

    disable_parser = sub.add_parser("disable", help="Disable a column")
    disable_parser.add_argument("column_id")

    add_source_parser = sub.add_parser("add-source", help="Add source URLs to a column")
    add_source_parser.add_argument("column_id")
    add_source_parser.add_argument("url", nargs="+")
    add_source_parser.add_argument("--no-validate", action="store_true")

    validate_parser = sub.add_parser("validate-source", help="Validate a single source URL")
    validate_parser.add_argument("url")

    preview_parser = sub.add_parser("preview-crawler", help="Preview generated crawler config")
    preview_parser.add_argument("column_id")

    args = parser.parse_args()
    service = ColumnService()

    if args.command == "list":
        print_json(service.list_columns(enabled_only=args.enabled_only))
    elif args.command == "show":
        print_json(service.get_column(args.column_id).to_dict())
    elif args.command == "enable":
        print_json(service.set_enabled(args.column_id, True).to_dict())
    elif args.command == "disable":
        print_json(service.set_enabled(args.column_id, False).to_dict())
    elif args.command == "add-source":
        print_json(service.add_sources(
            args.column_id,
            args.url,
            validate_sources=not args.no_validate,
        ).to_dict())
    elif args.command == "validate-source":
        print_json(service.validate_source_url(args.url))
    elif args.command == "preview-crawler":
        print_json(service.get_crawler_config_preview(args.column_id))


if __name__ == "__main__":
    main()
