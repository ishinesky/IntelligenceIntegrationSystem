from __future__ import annotations

import argparse
import json

from .column_service import ColumnService


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover candidate source URLs for OPC columns.")
    sub = parser.add_subparsers(dest="command", required=True)

    topic_parser = sub.add_parser("topic", help="Discover candidates from a topic payload")
    topic_parser.add_argument("--name", required=True)
    topic_parser.add_argument("--description", required=True)
    topic_parser.add_argument("--region", action="append", default=[])
    topic_parser.add_argument("--keyword", action="append", default=[])
    topic_parser.add_argument("--negative-keyword", action="append", default=[])
    topic_parser.add_argument("--seed-url", action="append", default=[])
    topic_parser.add_argument("--provider", default="auto", choices=["auto", "manual", "bing", "null"])
    topic_parser.add_argument("--max-queries", type=int, default=8)
    topic_parser.add_argument("--results-per-query", type=int, default=5)
    topic_parser.add_argument("--no-validate", action="store_true")

    column_parser = sub.add_parser("column", help="Discover candidates for an existing column")
    column_parser.add_argument("column_id")
    column_parser.add_argument("--seed-url", action="append", default=[])
    column_parser.add_argument("--provider", default="auto", choices=["auto", "manual", "bing", "null"])
    column_parser.add_argument("--max-queries", type=int, default=8)
    column_parser.add_argument("--results-per-query", type=int, default=5)
    column_parser.add_argument("--no-validate", action="store_true")

    args = parser.parse_args()
    service = ColumnService()

    if args.command == "topic":
        payload = {
            "name": args.name,
            "description": args.description,
            "regions": args.region,
            "keywords": args.keyword,
            "negative_keywords": args.negative_keyword,
            "seed_urls": args.seed_url,
            "provider": args.provider,
            "max_queries": args.max_queries,
            "results_per_query": args.results_per_query,
            "validate_sources": not args.no_validate,
        }
        print_json(service.discover_sources_from_payload(payload))
    elif args.command == "column":
        payload = {
            "seed_urls": args.seed_url,
            "provider": args.provider,
            "max_queries": args.max_queries,
            "results_per_query": args.results_per_query,
            "validate_sources": not args.no_validate,
        }
        print_json(service.discover_sources_for_column(args.column_id, payload))


if __name__ == "__main__":
    main()
