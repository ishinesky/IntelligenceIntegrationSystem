from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .models import ColumnConfig, SourceConfig
from .source_validator import validate_source


@dataclass
class SourceQualityReport:
    name: str
    url: str
    enabled: bool
    source_type: str
    trust_level: str
    validation_status: str
    score: float
    recommendation: str
    reasons: List[str] = field(default_factory=list)
    validation: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _contains_any(text: str, keywords: List[str]) -> bool:
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords if keyword)


def _audit_one_source(
    column: ColumnConfig,
    source: SourceConfig,
    *,
    live_validate: bool = True,
) -> SourceQualityReport:
    score = 0.5
    reasons: List[str] = []
    validation_data: Dict[str, Any] = {}

    if source.enabled:
        score += 0.1
        reasons.append("source is enabled")
    else:
        score -= 0.1
        reasons.append("source is disabled")

    trust_boost = {"S": 0.25, "A": 0.18, "B": 0.08, "C": -0.05}.get(source.trust_level, 0)
    score += trust_boost
    reasons.append(f"trust level {source.trust_level}")

    host = urlparse(source.url).netloc.lower()
    if host.endswith("gov.cn") or ".gov.cn" in host:
        score += 0.18
        reasons.append("official .gov.cn source")
    elif any(token in host for token in ["news", "people", "xinhuanet", "chinanews"]):
        score += 0.08
        reasons.append("media-like source host")

    topic_text = f"{source.name}\n{source.url}\n{' '.join(source.validation_notes)}"
    if column.keywords and _contains_any(topic_text, column.keywords):
        score += 0.12
        reasons.append("matches column keywords")
    elif column.keywords:
        score -= 0.08
        reasons.append("does not clearly match column keywords")

    if column.negative_keywords and _contains_any(topic_text, column.negative_keywords):
        score -= 0.2
        reasons.append("matches negative keywords")

    if source.validation_status == "passed":
        score += 0.08
        reasons.append("stored validation passed")
    elif source.validation_status == "failed":
        score -= 0.2
        reasons.append("stored validation failed")
    elif source.validation_status == "manual_review":
        score -= 0.02
        reasons.append("manual review status")

    if source.crawl_method == "rss":
        score += 0.08
        reasons.append("rss crawl method")

    if live_validate:
        validation = validate_source(source)
        validation_data = {
            "ok": validation.ok,
            "status_code": validation.status_code,
            "final_url": validation.final_url,
            "title": validation.title,
            "has_rss_hint": validation.has_rss_hint,
            "has_sitemap_hint": validation.has_sitemap_hint,
            "notes": validation.notes,
        }
        if validation.ok:
            score += 0.12
            reasons.append("live validation ok")
        else:
            score -= 0.25
            reasons.append("live validation failed")
        if validation.has_rss_hint:
            score += 0.06
            reasons.append("rss hint found")
        if validation.has_sitemap_hint:
            score += 0.04
            reasons.append("sitemap hint found")

    score = max(0.0, min(1.0, score))
    if score >= 0.75:
        recommendation = "promote"
    elif score >= 0.5:
        recommendation = "keep"
    elif score >= 0.3:
        recommendation = "review"
    else:
        recommendation = "disable"

    return SourceQualityReport(
        name=source.name,
        url=source.url,
        enabled=source.enabled,
        source_type=source.source_type,
        trust_level=source.trust_level,
        validation_status=source.validation_status,
        score=round(score, 4),
        recommendation=recommendation,
        reasons=reasons,
        validation=validation_data,
    )


class SourceQualityService:
    """Audit source quality for dynamic columns.

    The first version is deliberately source-local: it uses source metadata,
    topic relevance, trust heuristics, and optional live validation. A later
    version can add crawler governance history such as success rate, freshness,
    duplicate rate, and relevance of fetched articles.
    """

    def audit_column_sources(
        self,
        column: ColumnConfig,
        *,
        live_validate: bool = True,
    ) -> Dict[str, Any]:
        reports = [
            _audit_one_source(column, source, live_validate=live_validate).to_dict()
            for source in column.sources
        ]
        reports.sort(key=lambda item: item.get("score", 0), reverse=True)

        recommendation_counts: Dict[str, int] = {}
        for report in reports:
            recommendation = report.get("recommendation", "unknown")
            recommendation_counts[recommendation] = recommendation_counts.get(recommendation, 0) + 1

        return {
            "column": {
                "id": column.id,
                "name": column.name,
                "source_count": len(column.sources),
            },
            "live_validate": live_validate,
            "recommendation_counts": recommendation_counts,
            "sources": reports,
        }
