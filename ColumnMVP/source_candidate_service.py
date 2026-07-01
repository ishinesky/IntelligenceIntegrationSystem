from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from .models import ColumnConfig, SourceConfig, TopicBrief
from .source_discovery import build_search_queries
from .source_search_provider import SourceSearchCandidate, get_source_search_provider
from .source_validator import validate_source


def _dedupe_candidates(candidates: Iterable[SourceSearchCandidate]) -> List[SourceSearchCandidate]:
    seen = set()
    deduped: List[SourceSearchCandidate] = []
    for candidate in candidates:
        parsed = urlparse(candidate.url)
        key = (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/'))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _score_candidate(candidate: SourceSearchCandidate, topic: TopicBrief) -> float:
    text = f"{candidate.title}\n{candidate.snippet}\n{candidate.url}".lower()
    score = candidate.score or 0.0

    for keyword in topic.keywords:
        if keyword.lower() in text:
            score += 0.15
    for region in topic.regions:
        if region.lower() in text:
            score += 0.1
    for negative in topic.negative_keywords:
        if negative.lower() in text:
            score -= 0.25

    host = urlparse(candidate.url).netloc.lower()
    if host.endswith("gov.cn") or ".gov.cn" in host:
        score += 0.25
    if any(token in host for token in ["news", "people", "xinhuanet", "chinanews"]):
        score += 0.1

    return max(0.0, min(1.0, score))


class SourceCandidateService:
    """Discover candidate source URLs for a topic or column.

    Discovery is intentionally separated from approval. A candidate only becomes
    a `ColumnSource` after an operator explicitly adds its URL to a column.
    """

    def discover_for_topic(
        self,
        topic: TopicBrief,
        *,
        provider_name: str = "auto",
        seed_urls: Optional[Iterable[str]] = None,
        max_queries: int = 8,
        results_per_query: int = 5,
        validate: bool = True,
    ) -> Dict[str, Any]:
        queries = build_search_queries(topic)[:max_queries]
        provider = get_source_search_provider(provider_name, seed_urls=seed_urls)

        raw_candidates: List[SourceSearchCandidate] = []
        warnings: List[str] = []
        for query in queries or [topic.name]:
            try:
                raw_candidates.extend(provider.search(query, limit=results_per_query))
            except Exception as exc:
                warnings.append(f"{provider.name} query failed: {query} - {exc}")

        candidates = _dedupe_candidates(raw_candidates)
        enriched = []
        for candidate in candidates:
            candidate.score = _score_candidate(candidate, topic)
            candidate_data = candidate.to_dict()
            if validate:
                try:
                    validation = validate_source(SourceConfig(name=candidate.title, url=candidate.url))
                    candidate_data["validation"] = {
                        "ok": validation.ok,
                        "status_code": validation.status_code,
                        "final_url": validation.final_url,
                        "title": validation.title,
                        "has_rss_hint": validation.has_rss_hint,
                        "has_sitemap_hint": validation.has_sitemap_hint,
                        "notes": validation.notes,
                    }
                    if validation.title and candidate_data["title"] == candidate.url:
                        candidate_data["title"] = validation.title
                    if validation.ok:
                        candidate_data["score"] = min(1.0, candidate_data["score"] + 0.1)
                except Exception as exc:
                    candidate_data["validation"] = {
                        "ok": False,
                        "notes": [f"validation failed: {exc}"],
                    }
            enriched.append(candidate_data)

        enriched.sort(key=lambda item: item.get("score", 0), reverse=True)
        return {
            "provider": provider.name,
            "queries": queries,
            "warnings": warnings,
            "candidates": enriched,
        }

    def discover_for_column(
        self,
        column: ColumnConfig,
        *,
        provider_name: str = "auto",
        seed_urls: Optional[Iterable[str]] = None,
        max_queries: int = 8,
        results_per_query: int = 5,
        validate: bool = True,
    ) -> Dict[str, Any]:
        topic = TopicBrief(
            name=column.name,
            description=column.description or column.topic_scope,
            regions=list(column.metadata.get("regions", [])) if isinstance(column.metadata, dict) else [],
            keywords=column.keywords,
            negative_keywords=column.negative_keywords,
            source_policy=column.source_policy,
            update_frequency=column.update_frequency,
            publish_style=column.publish_style,
        )
        result = self.discover_for_topic(
            topic,
            provider_name=provider_name,
            seed_urls=seed_urls,
            max_queries=max_queries,
            results_per_query=results_per_query,
            validate=validate,
        )

        existing_urls = {source.url for source in column.sources}
        for candidate in result["candidates"]:
            candidate["already_in_column"] = candidate.get("url") in existing_urls
        return result
