from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import ColumnConfig


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


@dataclass
class SourceRuntimeMetricRecord:
    """One runtime event associated with a column source."""

    column_id: str
    source_url: str
    event_type: str  # crawl_success | crawl_failure | article | duplicate | skipped
    timestamp: str = field(default_factory=utc_now_iso)
    article_count: int = 0
    duplicate_count: int = 0
    relevance_score: Optional[float] = None
    quality_score: Optional[float] = None
    actionability_score: Optional[float] = None
    latency_ms: Optional[int] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceRuntimeMetricRecord":
        payload = dict(data)
        payload.setdefault("timestamp", utc_now_iso())
        payload.setdefault("article_count", 0)
        payload.setdefault("duplicate_count", 0)
        payload.setdefault("metadata", {})
        return cls(**payload)


class SourceRuntimeMetricStore:
    """JSONL-backed runtime metric store.

    This v1 store avoids coupling to crawler governance internals. Later versions
    can add adapters for `spider_governance.db`, MongoDB, or article archives.
    """

    def __init__(self, path: str | Path = "ColumnMVP/runtime_metrics/source_metrics.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: SourceRuntimeMetricRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def iter_records(self) -> Iterable[SourceRuntimeMetricRecord]:
        if not self.path.exists():
            return []
        records: List[SourceRuntimeMetricRecord] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(SourceRuntimeMetricRecord.from_dict(json.loads(line)))
                except Exception:
                    continue
        return records

    def query(self, *, column_id: Optional[str] = None, source_url: Optional[str] = None) -> List[SourceRuntimeMetricRecord]:
        records = list(self.iter_records())
        if column_id:
            records = [record for record in records if record.column_id == column_id]
        if source_url:
            records = [record for record in records if record.source_url == source_url]
        return records


class SourceRuntimeMetricService:
    def __init__(self, store: Optional[SourceRuntimeMetricStore] = None):
        self.store = store or SourceRuntimeMetricStore()

    def record_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = SourceRuntimeMetricRecord(
            column_id=str(payload.get("column_id", "")).strip(),
            source_url=str(payload.get("source_url", payload.get("url", ""))).strip(),
            event_type=str(payload.get("event_type", "")).strip(),
            timestamp=str(payload.get("timestamp") or utc_now_iso()),
            article_count=int(payload.get("article_count", 0) or 0),
            duplicate_count=int(payload.get("duplicate_count", 0) or 0),
            relevance_score=_optional_float(payload.get("relevance_score")),
            quality_score=_optional_float(payload.get("quality_score")),
            actionability_score=_optional_float(payload.get("actionability_score")),
            latency_ms=_optional_int(payload.get("latency_ms")),
            message=str(payload.get("message", "")),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        if not record.column_id:
            raise ValueError("column_id is required")
        if not record.source_url:
            raise ValueError("source_url is required")
        if record.event_type not in {"crawl_success", "crawl_failure", "article", "duplicate", "skipped"}:
            raise ValueError("event_type must be crawl_success, crawl_failure, article, duplicate, or skipped")
        self.store.append(record)
        return record.to_dict()

    def summarize_column(self, column: ColumnConfig) -> Dict[str, Any]:
        records = self.store.query(column_id=column.id)
        by_url: Dict[str, List[SourceRuntimeMetricRecord]] = {}
        for record in records:
            by_url.setdefault(record.source_url, []).append(record)

        source_summaries = []
        for source in column.sources:
            source_records = by_url.get(source.url, [])
            source_summaries.append(_summarize_source(source.url, source.name, source_records))

        known_urls = {source.url for source in column.sources}
        orphan_summaries = [
            _summarize_source(url, url, source_records, attached=False)
            for url, source_records in by_url.items()
            if url not in known_urls
        ]

        source_summaries.sort(key=lambda item: item.get("runtime_score", 0), reverse=True)
        return {
            "column": {
                "id": column.id,
                "name": column.name,
                "source_count": len(column.sources),
            },
            "record_count": len(records),
            "sources": source_summaries,
            "orphan_sources": orphan_summaries,
        }


def _optional_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _optional_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _avg(values: Iterable[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _summarize_source(
    source_url: str,
    source_name: str,
    records: List[SourceRuntimeMetricRecord],
    *,
    attached: bool = True,
) -> Dict[str, Any]:
    success_count = sum(1 for r in records if r.event_type == "crawl_success")
    failure_count = sum(1 for r in records if r.event_type == "crawl_failure")
    skipped_count = sum(1 for r in records if r.event_type == "skipped")
    article_count = sum(max(0, int(r.article_count or 0)) for r in records)
    duplicate_count = sum(max(0, int(r.duplicate_count or 0)) for r in records)
    article_event_count = sum(1 for r in records if r.event_type == "article")
    duplicate_event_count = sum(1 for r in records if r.event_type == "duplicate")
    attempts = success_count + failure_count
    success_rate = (success_count / attempts) if attempts else None
    duplicate_ratio = duplicate_count / max(article_count + duplicate_count, 1)

    latest_success = _latest_timestamp([r.timestamp for r in records if r.event_type == "crawl_success"])
    latest_record = _latest_timestamp([r.timestamp for r in records])
    avg_relevance = _avg(r.relevance_score for r in records)
    avg_quality = _avg(r.quality_score for r in records)
    avg_actionability = _avg(r.actionability_score for r in records)
    avg_latency_ms = _avg(float(r.latency_ms) for r in records if r.latency_ms is not None)

    runtime_score = _runtime_score(
        success_rate=success_rate,
        article_count=article_count + article_event_count,
        duplicate_ratio=duplicate_ratio,
        avg_relevance=avg_relevance,
        avg_quality=avg_quality,
        avg_actionability=avg_actionability,
        latest_success=latest_success,
    )

    return {
        "source_url": source_url,
        "source_name": source_name,
        "attached": attached,
        "record_count": len(records),
        "success_count": success_count,
        "failure_count": failure_count,
        "skipped_count": skipped_count,
        "article_count": article_count,
        "article_event_count": article_event_count,
        "duplicate_count": duplicate_count,
        "duplicate_event_count": duplicate_event_count,
        "success_rate": success_rate,
        "duplicate_ratio": duplicate_ratio,
        "latest_success": latest_success,
        "latest_record": latest_record,
        "avg_relevance": avg_relevance,
        "avg_quality": avg_quality,
        "avg_actionability": avg_actionability,
        "avg_latency_ms": avg_latency_ms,
        "runtime_score": runtime_score,
        "recommendation": _runtime_recommendation(runtime_score, success_rate, latest_success),
    }


def _latest_timestamp(values: Iterable[str]) -> Optional[str]:
    parsed = []
    for value in values:
        dt = _parse_dt(value)
        if dt:
            parsed.append(dt)
    if not parsed:
        return None
    return max(parsed).isoformat()


def _runtime_score(
    *,
    success_rate: Optional[float],
    article_count: int,
    duplicate_ratio: float,
    avg_relevance: Optional[float],
    avg_quality: Optional[float],
    avg_actionability: Optional[float],
    latest_success: Optional[str],
) -> float:
    score = 0.35
    if success_rate is not None:
        score += 0.25 * success_rate
    if article_count > 0:
        score += min(0.15, article_count * 0.01)
    score -= min(0.15, duplicate_ratio * 0.15)
    if avg_relevance is not None:
        score += 0.12 * max(0.0, min(1.0, avg_relevance))
    if avg_quality is not None:
        score += 0.08 * max(0.0, min(1.0, avg_quality))
    if avg_actionability is not None:
        score += 0.05 * max(0.0, min(1.0, avg_actionability))
    if latest_success:
        score += 0.08
    return round(max(0.0, min(1.0, score)), 4)


def _runtime_recommendation(runtime_score: float, success_rate: Optional[float], latest_success: Optional[str]) -> str:
    if success_rate == 0 and latest_success is None:
        return "disable"
    if runtime_score >= 0.75:
        return "promote"
    if runtime_score >= 0.55:
        return "keep"
    if runtime_score >= 0.35:
        return "review"
    return "disable"
