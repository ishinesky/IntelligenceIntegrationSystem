from __future__ import annotations

from typing import Dict

from .models import ColumnConfig


def build_entry_points(column: ColumnConfig) -> Dict[str, str]:
    entry_points: Dict[str, str] = {}
    for source in column.sources:
        if not source.enabled:
            continue
        if source.validation_status not in {"passed", "manual_review", "pending"}:
            continue
        key = source.name.strip() or source.url
        entry_points[key] = source.url
    return entry_points


def build_crawler_config(column: ColumnConfig) -> dict:
    """Translate a ColumnConfig into the existing IntelligenceCrawler config shape."""
    entry_points = build_entry_points(column)
    return {
        "d_fetcher_name": "RequestsFetcher",
        "d_fetcher_init_param": {"log_callback": print, "proxy": None, "timeout_s": 10},
        "e_fetcher_name": "RequestsFetcher",
        "e_fetcher_init_param": {"log_callback": print, "proxy": None, "timeout_s": 20},
        "discoverer_name": "ListPageDiscoverer",
        "discoverer_init_param": {
            "verbose": True,
            "manual_specified_signature": None,
            "scope_selector": None,
        },
        "extractor_name": "Trafilatura",
        "extractor_init_param": {"verbose": True},
        "entry_points": entry_points,
        "period_filter": (None, None),
        "channel_filter": None,
        "d_fetcher_kwargs": {
            "wait_until": "networkidle",
            "wait_for_selector": None,
            "wait_for_timeout_s": 10,
            "scroll_pages": 0,
        },
        "e_fetcher_kwargs": {
            "wait_until": "networkidle",
            "wait_for_selector": None,
            "wait_for_timeout_s": 20,
            "scroll_pages": 0,
        },
        "extractor_kwargs": {},
        "article_filter": None,
        "content_handler": None,
        "exception_handler": None,
    }
