from __future__ import annotations

from typing import Iterable, List

from .column_store import ColumnStore
from .models import ColumnConfig, SourceConfig, TopicBrief
from .source_discovery import candidates_from_urls
from .source_validator import validate_and_update


def build_column_from_topic(
    topic: TopicBrief,
    seed_urls: Iterable[str] = (),
    validate_sources: bool = True,
) -> ColumnConfig:
    sources: List[SourceConfig] = candidates_from_urls(seed_urls)
    if validate_sources:
        sources = [validate_and_update(source) for source in sources]
    return ColumnConfig.from_topic(topic, sources=sources)


def create_column(
    topic: TopicBrief,
    seed_urls: Iterable[str] = (),
    store: ColumnStore | None = None,
    overwrite: bool = False,
    validate_sources: bool = True,
) -> ColumnConfig:
    store = store or ColumnStore()
    column = build_column_from_topic(
        topic=topic,
        seed_urls=seed_urls,
        validate_sources=validate_sources,
    )
    store.save(column, overwrite=overwrite)
    return column
