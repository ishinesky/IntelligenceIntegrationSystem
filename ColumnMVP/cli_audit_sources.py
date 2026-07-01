from __future__ import annotations

import argparse
import json

from .column_service import ColumnService


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit source quality for a dynamic OPC column.")
    parser.add_argument("column_id", help="Column ID to audit")
    parser.add_argument("--no-live-validate", action="store_true", help="Skip live HTTP validation")
    args = parser.parse_args()

    service = ColumnService()
    print_json(service.audit_source_quality(
        args.column_id,
        live_validate=not args.no_live_validate,
    ))


if __name__ == "__main__":
    main()
