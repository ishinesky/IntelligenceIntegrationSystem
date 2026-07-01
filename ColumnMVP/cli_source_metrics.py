from __future__ import annotations

import argparse
import json

from .column_service import ColumnService


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Record or summarize runtime metrics for OPC column sources.")
    sub = parser.add_subparsers(dest="command", required=True)

    record_parser = sub.add_parser("record", help="Record one source runtime event")
    record_parser.add_argument("column_id")
    record_parser.add_argument("source_url")
    record_parser.add_argument("event_type", choices=["crawl_success", "crawl_failure", "article", "duplicate", "skipped"])
    record_parser.add_argument("--article-count", type=int, default=0)
    record_parser.add_argument("--duplicate-count", type=int, default=0)
    record_parser.add_argument("--relevance-score", type=float)
    record_parser.add_argument("--quality-score", type=float)
    record_parser.add_argument("--actionability-score", type=float)
    record_parser.add_argument("--latency-ms", type=int)
    record_parser.add_argument("--message", default="")

    summary_parser = sub.add_parser("summary", help="Summarize runtime metrics for a column")
    summary_parser.add_argument("column_id")

    args = parser.parse_args()
    service = ColumnService()

    if args.command == "record":
        payload = {
            "source_url": args.source_url,
            "event_type": args.event_type,
            "article_count": args.article_count,
            "duplicate_count": args.duplicate_count,
            "relevance_score": args.relevance_score,
            "quality_score": args.quality_score,
            "actionability_score": args.actionability_score,
            "latency_ms": args.latency_ms,
            "message": args.message,
        }
        print_json(service.record_source_runtime_metric(args.column_id, payload))
    elif args.command == "summary":
        print_json(service.get_source_runtime_metrics(args.column_id))


if __name__ == "__main__":
    main()
