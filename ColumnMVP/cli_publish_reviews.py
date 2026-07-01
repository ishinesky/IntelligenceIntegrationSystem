from __future__ import annotations

import argparse
import json

from .publishing import EditorialPublishingService


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish, unpublish, reject, or audit OPC editorial reviews.")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ["publish", "unpublish", "reject"]:
        p = sub.add_parser(command)
        p.add_argument("review_id")
        p.add_argument("--operator", default="cli")
        p.add_argument("--reason", default="")

    status = sub.add_parser("status")
    status.add_argument("review_id")
    status.add_argument("status")
    status.add_argument("--operator", default="cli")
    status.add_argument("--reason", default="")

    audit = sub.add_parser("audit")
    audit.add_argument("--review-id", default="")
    audit.add_argument("--limit", type=int, default=100)

    args = parser.parse_args()
    service = EditorialPublishingService()

    if args.command == "publish":
        print_json(service.publish(args.review_id, operator=args.operator, reason=args.reason))
    elif args.command == "unpublish":
        print_json(service.unpublish(args.review_id, operator=args.operator, reason=args.reason))
    elif args.command == "reject":
        print_json(service.reject(args.review_id, operator=args.operator, reason=args.reason))
    elif args.command == "status":
        print_json(service.set_status(args.review_id, args.status, operator=args.operator, reason=args.reason))
    elif args.command == "audit":
        print_json(service.audit(review_id=args.review_id, limit=args.limit))


if __name__ == "__main__":
    main()
