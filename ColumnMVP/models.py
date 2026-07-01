from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    """Create a conservative filesystem-friendly slug."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "column"


@dataclass
class TopicBrief:
    """A user-facing topic brief captured from dialogue or CLI input."""

    name: str
    description: str
    regions: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)
    source_policy: str = "official_first"
    update_frequency: str = "daily"
    publish_style: str = "fact_summary_ai_analysis_editorial_action"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceConfig:
    """A fixed source that belongs to a column after validation/approval."""

    name: str
    url: str
    source_type: str = "unknown"  # government | media | industry | rss | sitemap | manual
    crawl_method: str = "list_page"  # list_page | rss | sitemap
    trust_level: str = "B"  # S | A | B | C
    enabled: bool = True
    validation_status: str = "pending"  # pending | passed | failed | manual_review
    validation_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    url: str
    ok: bool
    status_code: Optional[int] = None
    final_url: Optional[str] = None
    title: Optional[str] = None
    has_rss_hint: bool = False
    has_sitemap_hint: bool = False
    robots_allowed_hint: Optional[bool] = None
    notes: List[str] = field(default_factory=list)

    def to_source_config(self, name: Optional[str] = None) -> SourceConfig:
        source_name = name or self.title or self.url
        trust_level = "A" if self.ok else "C"
        validation_status = "passed" if self.ok else "manual_review"
        return SourceConfig(
            name=source_name,
            url=self.final_url or self.url,
            source_type="manual",
            crawl_method="rss" if self.has_rss_hint else "list_page",
            trust_level=trust_level,
            validation_status=validation_status,
            validation_notes=self.notes,
        )


@dataclass
class ColumnConfig:
    """A durable dynamic column definition."""

    id: str
    name: str
    description: str
    topic_scope: str
    keywords: List[str] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)
    source_policy: str = "official_first"
    update_frequency: str = "daily"
    publish_style: str = "fact_summary_ai_analysis_editorial_action"
    sources: List[SourceConfig] = field(default_factory=list)
    enabled: bool = True
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_topic(cls, topic: TopicBrief, sources: Optional[List[SourceConfig]] = None) -> "ColumnConfig":
        parts = [topic.description]
        if topic.regions:
            parts.append("关注区域：" + "、".join(topic.regions))
        if topic.keywords:
            parts.append("关键词：" + "、".join(topic.keywords))
        return cls(
            id=slugify(topic.name),
            name=topic.name,
            description=topic.description,
            topic_scope="\n".join(parts),
            keywords=topic.keywords,
            negative_keywords=topic.negative_keywords,
            source_policy=topic.source_policy,
            update_frequency=topic.update_frequency,
            publish_style=topic.publish_style,
            sources=sources or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["sources"] = [source.to_dict() for source in self.sources]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColumnConfig":
        source_items = data.get("sources", [])
        sources = [SourceConfig(**item) for item in source_items]
        payload = dict(data)
        payload["sources"] = sources
        return cls(**payload)
