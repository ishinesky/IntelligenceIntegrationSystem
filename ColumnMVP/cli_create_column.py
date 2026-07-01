from __future__ import annotations

import argparse

from .column_store import ColumnStore
from .models import TopicBrief
from .source_discovery import build_search_queries
from .topic_builder import create_column


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a dynamic intelligence column from a topic brief.")
    parser.add_argument("--name", required=True, help="Column name")
    parser.add_argument("--description", required=True, help="Column topic description")
    parser.add_argument("--region", action="append", default=[], help="Region to track; can be repeated")
    parser.add_argument("--keyword", action="append", default=[], help="Keyword to track; can be repeated")
    parser.add_argument("--negative-keyword", action="append", default=[], help="Negative keyword; can be repeated")
    parser.add_argument("--url", action="append", default=[], help="Seed URL; can be repeated")
    parser.add_argument("--no-validate", action="store_true", help="Skip URL validation")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing column JSON")
    parser.add_argument("--print-queries", action="store_true", help="Print suggested discovery queries")
    args = parser.parse_args()

    topic = TopicBrief(
        name=args.name,
        description=args.description,
        regions=args.region,
        keywords=args.keyword,
        negative_keywords=args.negative_keyword,
    )

    if args.print_queries:
        print("Suggested source discovery queries:")
        for query in build_search_queries(topic):
            print(f"- {query}")

    column = create_column(
        topic=topic,
        seed_urls=args.url,
        store=ColumnStore(),
        overwrite=args.overwrite,
        validate_sources=not args.no_validate,
    )
    print(f"Created column: {column.id} ({column.name})")
    print(f"Sources: {len(column.sources)}")


if __name__ == "__main__":
    main()
