from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .article_lookup import ArticleLookupService
from .column_store import ColumnStore
from .dynamic_crawler_config import build_crawler_config
from .editorial_generation import EditorialGenerationService
from .editorial_review import EditorialReviewService
from .models import ColumnConfig, SourceConfig, TopicBrief
from .public_portal import OPCPublicPortalService
from .source_candidate_service import SourceCandidateService
from .source_discovery import build_search_queries, candidates_from_urls
from .source_quality import SourceQualityService
from .source_runtime_metrics import SourceRuntimeMetricService
from .source_validator import validate_and_update, validate_source
from .topic_builder import build_column_from_topic


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()] if str(value).strip() else []


class ColumnService:
    """Application-level service for dynamic columns.

    This class is intentionally independent from Flask so it can be used by CLI,
    web routes, dialogue agents, and future background jobs.
    """

    def __init__(
        self,
        store: Optional[ColumnStore] = None,
        candidate_service: Optional[SourceCandidateService] = None,
        quality_service: Optional[SourceQualityService] = None,
        runtime_metric_service: Optional[SourceRuntimeMetricService] = None,
        editorial_service: Optional[EditorialReviewService] = None,
        editorial_generation_service: Optional[EditorialGenerationService] = None,
        article_lookup_service: Optional[ArticleLookupService] = None,
        public_portal_service: Optional[OPCPublicPortalService] = None,
    ):
        self.store = store or ColumnStore()
        self.candidate_service = candidate_service or SourceCandidateService()
        self.quality_service = quality_service or SourceQualityService()
        self.runtime_metric_service = runtime_metric_service or SourceRuntimeMetricService()
        self.editorial_service = editorial_service or EditorialReviewService()
        self.editorial_generation_service = editorial_generation_service or EditorialGenerationService(self.editorial_service)
        self.article_lookup_service = article_lookup_service or ArticleLookupService()
        self.public_portal_service = public_portal_service or OPCPublicPortalService(
            column_store=self.store,
            editorial_service=self.editorial_service,
        )

    # ------------------------------ topic / creation ------------------------------

    @staticmethod
    def topic_from_payload(payload: Dict[str, Any]) -> TopicBrief:
        name = str(payload.get("name", "")).strip()
        description = str(payload.get("description", payload.get("topic", ""))).strip()
        if not name:
            raise ValueError("name is required")
        if not description:
            raise ValueError("description or topic is required")

        return TopicBrief(
            name=name,
            description=description,
            regions=_ensure_list(payload.get("regions", payload.get("region"))),
            keywords=_ensure_list(payload.get("keywords", payload.get("keyword"))),
            negative_keywords=_ensure_list(payload.get("negative_keywords", payload.get("negative_keyword"))),
            source_policy=str(payload.get("source_policy", "official_first")),
            update_frequency=str(payload.get("update_frequency", "daily")),
            publish_style=str(payload.get("publish_style", "fact_summary_ai_analysis_editorial_action")),
        )

    def suggest_queries(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        topic = self.topic_from_payload(payload)
        return {
            "topic": topic.to_dict(),
            "queries": build_search_queries(topic),
        }

    def create_column_from_payload(
        self,
        payload: Dict[str, Any],
        *,
        overwrite: bool = False,
        validate_sources: bool = True,
    ) -> ColumnConfig:
        topic = self.topic_from_payload(payload)
        seed_urls = _ensure_list(payload.get("seed_urls", payload.get("urls", payload.get("url"))))
        column = build_column_from_topic(
            topic=topic,
            seed_urls=seed_urls,
            validate_sources=validate_sources,
        )
        if topic.regions:
            column.metadata["regions"] = topic.regions
        self.store.save(column, overwrite=overwrite)
        return column

    # ------------------------------ discovery ------------------------------

    def discover_sources_from_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        topic = self.topic_from_payload(payload)
        return self.candidate_service.discover_for_topic(
            topic,
            provider_name=str(payload.get("provider", "auto")),
            seed_urls=_ensure_list(payload.get("seed_urls", payload.get("urls", payload.get("url")))),
            max_queries=int(payload.get("max_queries", 8)),
            results_per_query=int(payload.get("results_per_query", 5)),
            validate=bool(payload.get("validate_sources", True)),
        )

    def discover_sources_for_column(self, column_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        column = self.store.load(column_id)
        return self.candidate_service.discover_for_column(
            column,
            provider_name=str(payload.get("provider", "auto")),
            seed_urls=_ensure_list(payload.get("seed_urls", payload.get("urls", payload.get("url")))),
            max_queries=int(payload.get("max_queries", 8)),
            results_per_query=int(payload.get("results_per_query", 5)),
            validate=bool(payload.get("validate_sources", True)),
        )

    # ------------------------------ read / update ------------------------------

    def list_columns(self, *, enabled_only: bool = False) -> List[Dict[str, Any]]:
        return [column.to_dict() for column in self.store.list_columns(enabled_only=enabled_only)]

    def get_column(self, column_id: str) -> ColumnConfig:
        return self.store.load(column_id)

    def set_enabled(self, column_id: str, enabled: bool) -> ColumnConfig:
        column = self.store.load(column_id)
        column.enabled = bool(enabled)
        self.store.save(column, overwrite=True)
        return column

    def update_column_metadata(self, column_id: str, payload: Dict[str, Any]) -> ColumnConfig:
        column = self.store.load(column_id)
        for field_name in [
            "name",
            "description",
            "topic_scope",
            "source_policy",
            "update_frequency",
            "publish_style",
        ]:
            if field_name in payload:
                setattr(column, field_name, payload[field_name])

        if "keywords" in payload:
            column.keywords = _ensure_list(payload["keywords"])
        if "negative_keywords" in payload:
            column.negative_keywords = _ensure_list(payload["negative_keywords"])
        if "regions" in payload:
            column.metadata["regions"] = _ensure_list(payload["regions"])
        if "enabled" in payload:
            column.enabled = bool(payload["enabled"])
        if "metadata" in payload and isinstance(payload["metadata"], dict):
            column.metadata.update(payload["metadata"])

        self.store.save(column, overwrite=True)
        return column

    # ------------------------------ sources ------------------------------

    def add_sources(
        self,
        column_id: str,
        urls: Iterable[str],
        *,
        validate_sources: bool = True,
    ) -> ColumnConfig:
        column = self.store.load(column_id)
        existing = {source.url for source in column.sources}
        new_sources = []
        for source in candidates_from_urls(urls):
            if source.url in existing:
                continue
            if validate_sources:
                source = validate_and_update(source)
            new_sources.append(source)
            existing.add(source.url)

        column.sources.extend(new_sources)
        self.store.save(column, overwrite=True)
        return column

    def validate_source_url(self, url: str) -> Dict[str, Any]:
        source = SourceConfig(name=url, url=url)
        result = validate_source(source)
        return {
            "url": result.url,
            "ok": result.ok,
            "status_code": result.status_code,
            "final_url": result.final_url,
            "title": result.title,
            "has_rss_hint": result.has_rss_hint,
            "has_sitemap_hint": result.has_sitemap_hint,
            "robots_allowed_hint": result.robots_allowed_hint,
            "notes": result.notes,
            "source_config": result.to_source_config().to_dict(),
        }

    def audit_source_quality(self, column_id: str, *, live_validate: bool = True) -> Dict[str, Any]:
        column = self.store.load(column_id)
        return self.quality_service.audit_column_sources(column, live_validate=live_validate)

    # ------------------------------ runtime metrics ------------------------------

    def record_source_runtime_metric(self, column_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_payload = dict(payload)
        event_payload["column_id"] = column_id
        return self.runtime_metric_service.record_event(event_payload)

    def get_source_runtime_metrics(self, column_id: str) -> Dict[str, Any]:
        column = self.store.load(column_id)
        return self.runtime_metric_service.summarize_column(column)

    # ------------------------------ editorial reviews ------------------------------

    def create_editorial_review(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.editorial_service.create_review(payload).to_dict()

    def list_editorial_reviews(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        return self.editorial_service.list_reviews(
            column_id=str(payload.get("column_id", "")),
            article_uuid=str(payload.get("article_uuid", "")),
            status=str(payload.get("status", "")),
            limit=int(payload.get("limit", 50)),
        )

    def get_editorial_review(self, review_id: str) -> Dict[str, Any]:
        return self.editorial_service.get_review(review_id)

    def generate_editorial_review(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.editorial_generation_service.generate(payload)

    # ------------------------------ article lookup ------------------------------

    def lookup_article(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.article_lookup_service.resolve(payload)

    def import_article(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        article = payload.get("article") if isinstance(payload.get("article"), dict) else payload
        return self.article_lookup_service.import_article(article)

    def generate_editorial_review_from_article(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        generation_payload = self.article_lookup_service.build_generation_payload(payload)
        return self.generate_editorial_review(generation_payload)

    # ------------------------------ public portal ------------------------------

    def public_columns(self, *, include_disabled: bool = False) -> Dict[str, Any]:
        return self.public_portal_service.list_columns(include_disabled=include_disabled)

    def public_feed(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        return self.public_portal_service.list_feed(
            column_id=str(payload.get("column_id", "")),
            keyword=str(payload.get("keyword", "")),
            status=str(payload.get("status", "published,reviewed")),
            min_quality=float(payload.get("min_quality", 0) or 0),
            min_actionability=float(payload.get("min_actionability", 0) or 0),
            limit=int(payload.get("limit", 50) or 50),
        )

    def public_column_detail(self, column_id: str) -> Dict[str, Any]:
        return self.public_portal_service.get_column(column_id)

    def public_review_detail(self, review_id: str) -> Dict[str, Any]:
        return self.public_portal_service.get_review_detail(review_id)

    def public_rss(self, payload: Optional[Dict[str, Any]] = None) -> str:
        payload = payload or {}
        return self.public_portal_service.build_rss(
            base_url=str(payload.get("base_url", "")),
            column_id=str(payload.get("column_id", "")),
            keyword=str(payload.get("keyword", "")),
            limit=int(payload.get("limit", 30) or 30),
            title=str(payload.get("title", "OPC Resource Feed")),
        )

    # ------------------------------ crawl preview ------------------------------

    def get_crawler_config_preview(self, column_id: str) -> Dict[str, Any]:
        column = self.store.load(column_id)
        config = build_crawler_config(column)
        return {
            "column": {
                "id": column.id,
                "name": column.name,
                "enabled": column.enabled,
            },
            "entry_points": config.get("entry_points", {}),
            "config": config,
        }
