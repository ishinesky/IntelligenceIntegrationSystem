from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


EDITORIAL_FIELDS = [
    "FACT_SUMMARY",
    "WHY_IT_MATTERS",
    "OPPORTUNITY",
    "RISK",
    "WHO_SHOULD_CARE",
    "ACTION_SUGGESTION",
    "EDITORIAL_VIEW",
    "SOURCE_RELIABILITY",
    "CONTENT_QUALITY_SCORE",
    "ACTIONABILITY_SCORE",
    "CONFIDENCE",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EditorialReviewRecord:
    """One OPC editorial review record.

    A record is intentionally tied to both the original article UUID and optional
    column metadata so it can be rendered independently from the original article
    store.
    """

    review_id: str
    article_uuid: str
    column_id: str = ""
    source_url: str = ""
    title: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    status: str = "draft"  # draft | reviewed | published | rejected
    review: Dict[str, Any] = field(default_factory=dict)
    article: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EditorialReviewRecord":
        payload = dict(data)
        payload.setdefault("review_id", str(uuid.uuid4()))
        payload.setdefault("article_uuid", "")
        payload.setdefault("column_id", "")
        payload.setdefault("source_url", "")
        payload.setdefault("title", "")
        payload.setdefault("created_at", utc_now_iso())
        payload.setdefault("status", "draft")
        payload.setdefault("review", {})
        payload.setdefault("article", {})
        payload.setdefault("metadata", {})
        return cls(**payload)


class EditorialReviewStore:
    """JSONL-backed editorial review store."""

    def __init__(self, path: str | Path = "ColumnMVP/editorial_reviews/reviews.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: EditorialReviewRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def iter_records(self) -> List[EditorialReviewRecord]:
        if not self.path.exists():
            return []
        records: List[EditorialReviewRecord] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(EditorialReviewRecord.from_dict(json.loads(line)))
                except Exception:
                    continue
        return records

    def latest_records(self) -> List[EditorialReviewRecord]:
        latest: Dict[str, EditorialReviewRecord] = {}
        for record in self.iter_records():
            current = latest.get(record.review_id)
            if current is None or str(record.created_at) >= str(current.created_at):
                latest[record.review_id] = record
        return list(latest.values())

    def list_records(
        self,
        *,
        column_id: str = "",
        article_uuid: str = "",
        status: str = "",
        limit: int = 50,
    ) -> List[EditorialReviewRecord]:
        records = self.latest_records()
        if column_id:
            records = [record for record in records if record.column_id == column_id]
        if article_uuid:
            records = [record for record in records if record.article_uuid == article_uuid]
        if status:
            allowed = {item.strip() for item in status.split(',') if item.strip()}
            records = [record for record in records if record.status in allowed]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[:max(1, limit)]

    def get(self, review_id: str) -> Optional[EditorialReviewRecord]:
        for record in reversed(self.iter_records()):
            if record.review_id == review_id:
                return record
        return None


class EditorialReviewService:
    """Application service for OPC editorial reviews.

    The v1 service stores review payloads and can build normalized records. It does
    not require an AI client. Automatic AI generation can call the existing
    `ColumnMVP.ai_editorial.build_editorial_review` and then pass the resulting
    JSON into `create_review`.
    """

    def __init__(self, store: Optional[EditorialReviewStore] = None):
        self.store = store or EditorialReviewStore()

    def normalize_review(self, review: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {}
        for field_name in EDITORIAL_FIELDS:
            normalized[field_name] = review.get(field_name, [] if field_name == "WHO_SHOULD_CARE" else "")

        normalized["CONTENT_QUALITY_SCORE"] = _bounded_number(normalized.get("CONTENT_QUALITY_SCORE"), 0, 10)
        normalized["ACTIONABILITY_SCORE"] = _bounded_number(normalized.get("ACTIONABILITY_SCORE"), 0, 10)
        normalized["CONFIDENCE"] = _bounded_number(normalized.get("CONFIDENCE"), 0, 1)
        if not isinstance(normalized.get("WHO_SHOULD_CARE"), list):
            normalized["WHO_SHOULD_CARE"] = [str(normalized.get("WHO_SHOULD_CARE", ""))]
        return normalized

    def create_review(self, payload: Dict[str, Any]) -> EditorialReviewRecord:
        review_payload = payload.get("review") or {}
        if not isinstance(review_payload, dict):
            raise ValueError("review must be an object")

        article = payload.get("article") if isinstance(payload.get("article"), dict) else {}
        article_uuid = str(payload.get("article_uuid") or article.get("UUID") or article.get("uuid") or "").strip()
        if not article_uuid:
            article_uuid = str(uuid.uuid4())

        record = EditorialReviewRecord(
            review_id=str(payload.get("review_id") or uuid.uuid4()),
            article_uuid=article_uuid,
            column_id=str(payload.get("column_id", "")).strip(),
            source_url=str(payload.get("source_url") or article.get("informant") or article.get("INFORMANT") or "").strip(),
            title=str(payload.get("title") or article.get("title") or article.get("EVENT_TITLE") or "").strip(),
            status=str(payload.get("status", "reviewed")),
            review=self.normalize_review(review_payload),
            article=article,
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.store.append(record)
        return record

    def list_reviews(
        self,
        *,
        column_id: str = "",
        article_uuid: str = "",
        status: str = "",
        limit: int = 50,
    ) -> Dict[str, Any]:
        records = self.store.list_records(
            column_id=column_id,
            article_uuid=article_uuid,
            status=status,
            limit=limit,
        )
        return {
            "count": len(records),
            "reviews": [record.to_dict() for record in records],
        }

    def get_review(self, review_id: str) -> Dict[str, Any]:
        record = self.store.get(review_id)
        if not record:
            raise FileNotFoundError("review not found")
        return record.to_dict()


def _bounded_number(value: Any, min_value: float, max_value: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = min_value
    return max(min_value, min(max_value, number))
