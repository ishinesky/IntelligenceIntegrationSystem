from __future__ import annotations

from urllib.parse import urlparse
from typing import Iterable, List

from .models import SourceConfig, TopicBrief


def build_search_queries(topic: TopicBrief) -> List[str]:
    """Generate search queries for a human or external search API.

    This MVP does not call a search engine directly. A later service can pass these
    queries to Bing/Google/SerpAPI and feed discovered URLs back into the validator.
    """
    regions = topic.regions or [""]
    keywords = topic.keywords or [topic.name]
    queries: List[str] = []

    for region in regions:
        region_prefix = f"{region} " if region else ""
        for keyword in keywords:
            queries.extend([
                f"{region_prefix}{keyword} 政策 官网",
                f"{region_prefix}{keyword} 通知 公告",
                f"{region_prefix}{keyword} 园区 社区 入驻",
                f"{region_prefix}{keyword} 算力券 人才补贴",
            ])

    seen = set()
    deduped = []
    for query in queries:
        normalized = " ".join(query.split())
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def guess_source_type(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if ".gov.cn" in host or host.endswith("gov.cn"):
        return "government"
    if any(token in host for token in ["news", "people", "xinhuanet", "chinanews"]):
        return "media"
    if "rss" in url.lower() or "feed" in url.lower():
        return "rss"
    return "manual"


def guess_source_name(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or url


def candidates_from_urls(urls: Iterable[str]) -> List[SourceConfig]:
    sources: List[SourceConfig] = []
    seen = set()
    for url in urls:
        normalized = url.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        source_type = guess_source_type(normalized)
        sources.append(SourceConfig(
            name=guess_source_name(normalized),
            url=normalized,
            source_type=source_type,
            crawl_method="rss" if source_type == "rss" else "list_page",
            trust_level="S" if source_type == "government" else "B",
            validation_status="pending",
        ))
    return sources
