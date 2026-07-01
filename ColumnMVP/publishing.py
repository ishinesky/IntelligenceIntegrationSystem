from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .editorial_review import EditorialReviewRecord, EditorialReviewService, EditorialReviewStore, utc_now_iso

PUBLISHABLE_STATUSES = {"draft", "reviewed", "published", "rejected"}


@dataclass
class PublicationAuditRecord:
    audit_id: str
    review_id: str
    previous_status: str
    next_status: str
    operator: str = "system"
    reason: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PublicationAuditStore:
    def __init__(self, path: str | Path = "ColumnMVP/editorial_reviews/publication_audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: PublicationAuditRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def list_records(self, *, review_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if review_id and item.get("review_id") != review_id:
                    continue
                records.append(item)
        records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return records[:max(1, limit)]


class EditorialPublishingService:
    """Append-only publication workflow for editorial reviews.

    Status updates append a new review version with the same `review_id` and an
    audit record. The latest record wins for read models that call `store.get`.
    """

    def __init__(
        self,
        *,
        editorial_service: Optional[EditorialReviewService] = None,
        review_store: Optional[EditorialReviewStore] = None,
        audit_store: Optional[PublicationAuditStore] = None,
    ):
        self.review_store = review_store or EditorialReviewStore()
        self.editorial_service = editorial_service or EditorialReviewService(self.review_store)
        self.audit_store = audit_store or PublicationAuditStore()

    def set_status(
        self,
        review_id: str,
        next_status: str,
        *,
        operator: str = "system",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        next_status = str(next_status or "").strip()
        if next_status not in PUBLISHABLE_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(PUBLISHABLE_STATUSES))}")

        current = self.review_store.get(review_id)
        if not current:
            raise FileNotFoundError("review not found")

        previous_status = current.status
        updated = EditorialReviewRecord.from_dict(current.to_dict())
        updated.status = next_status
        updated.created_at = utc_now_iso()
        updated.metadata = dict(updated.metadata or {})
        updated.metadata.setdefault("publication_history", [])
        updated.metadata["last_publication_change"] = {
            "previous_status": previous_status,
            "next_status": next_status,
            "operator": operator,
            "reason": reason,
            "created_at": updated.created_at,
        }
        if metadata:
            updated.metadata["publication_metadata"] = metadata

        self.review_store.append(updated)
        audit = PublicationAuditRecord(
            audit_id=f"audit-{updated.created_at}-{review_id}",
            review_id=review_id,
            previous_status=previous_status,
            next_status=next_status,
            operator=operator or "system",
            reason=reason,
            metadata=metadata or {},
        )
        self.audit_store.append(audit)
        return {
            "review": updated.to_dict(),
            "audit": audit.to_dict(),
        }

    def publish(self, review_id: str, *, operator: str = "system", reason: str = "") -> Dict[str, Any]:
        return self.set_status(review_id, "published", operator=operator, reason=reason)

    def unpublish(self, review_id: str, *, operator: str = "system", reason: str = "") -> Dict[str, Any]:
        return self.set_status(review_id, "reviewed", operator=operator, reason=reason)

    def reject(self, review_id: str, *, operator: str = "system", reason: str = "") -> Dict[str, Any]:
        return self.set_status(review_id, "rejected", operator=operator, reason=reason)

    def audit(self, *, review_id: str = "", limit: int = 100) -> Dict[str, Any]:
        records = self.audit_store.list_records(review_id=review_id, limit=limit)
        return {
            "count": len(records),
            "records": records,
        }
