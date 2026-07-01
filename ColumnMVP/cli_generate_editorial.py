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
    parser = argparse.ArgumentParser(description="Generate OPC editorial review JSON from an article payload.")
    parser.add_argument("payload_json", help="Path to JSON payload containing article/content fields")
    parser.add_argument("--dry-run", action="store_true", help="Do not call AI; return prompt and normalized article payload")
    parser.add_argument("--no-persist", action="store_true", help="Generate review but do not store it")
    parser.add_argument("--model", default="", help="Optional OpenAI-compatible model override")
    parser.add_argument("--base-url", default="", help="Optional OpenAI-compatible base URL override")
    parser.add_argument("--api-key", default="", help="Optional API key override; prefer env variable in production")
    args = parser.parse_args()

    payload = load_json(args.payload_json)
    if args.dry_run:
        payload["dry_run"] = True
    if args.no_persist:
        payload["persist"] = False
    if args.model:
        payload["model"] = args.model
    if args.base_url:
        payload["base_url"] = args.base_url
    if args.api_key:
        payload["api_key"] = args.api_key

    service = ColumnService()
    print_json(service.generate_editorial_review(payload))


if __name__ == "__main__":
    main()
