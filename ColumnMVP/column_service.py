from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .column_store import ColumnStore
from .dynamic_crawler_config import build_crawler_config
from .models import ColumnConfig, SourceConfig, TopicBrief
from .source_discovery import build_search_queries, candidates_from_urls
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

    def __init__(self, store: Optional[ColumnStore] = None):
        self.store = store or ColumnStore()

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
        self.store.save(column, overwrite=overwrite)
        return column

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
        return validate_source(source).to_source_config().to_dict()

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
