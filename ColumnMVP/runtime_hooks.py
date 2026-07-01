from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .source_runtime_metrics import SourceRuntimeMetricService

logger = logging.getLogger(__name__)

DYNAMIC_COLUMN_FLOW_PREFIX = "dynamic_columns/"


def extract_column_id(flow_name: str) -> Optional[str]:
    """Extract the dynamic column id from a flow name.

    Dynamic column flows are named like:

        dynamic_columns/<column_id>

    Non-dynamic flows return None so existing crawlers are not affected.
    """
    if not flow_name or not flow_name.startswith(DYNAMIC_COLUMN_FLOW_PREFIX):
        return None
    rest = flow_name[len(DYNAMIC_COLUMN_FLOW_PREFIX):]
    column_id = rest.split("/", 1)[0].strip()
    return column_id or None


def build_group_source_map(flow_name: str, entry_points: Dict[str, str] | None) -> Dict[str, str]:
    """Build a best-effort mapping from crawler group labels to source URLs."""
    mapping: Dict[str, str] = {}
    for source_name, source_url in (entry_points or {}).items():
        if not source_name or not source_url:
            continue
        mapping[str(source_name)] = str(source_url)
        mapping[f"{flow_name}/{source_name}"] = str(source_url)
        mapping[str(source_url)] = str(source_url)
    return mapping


def configure_context_for_runtime_metrics(context: Any, entry_points: Dict[str, str] | None) -> None:
    """Attach dynamic-column runtime metadata to a CrawlContext-like object."""
    column_id = extract_column_id(getattr(context, "flow_name", ""))
    setattr(context, "runtime_metrics_column_id", column_id)
    setattr(context, "runtime_metrics_source_map", build_group_source_map(getattr(context, "flow_name", ""), entry_points))
    if column_id:
        logger.info("Runtime metrics enabled for dynamic column: %s", column_id)


def resolve_source_url(context: Any, group: str, fallback_url: str = "") -> str:
    mapping = getattr(context, "runtime_metrics_source_map", {}) or {}
    if group in mapping:
        return mapping[group]

    tail = str(group or "").rsplit("/", 1)[-1]
    if tail in mapping:
        return mapping[tail]

    if fallback_url in mapping:
        return mapping[fallback_url]

    return fallback_url or str(group or "")


def record_runtime_metric(
    context: Any,
    *,
    group: str,
    source_url: str = "",
    event_type: str,
    article_count: int = 0,
    duplicate_count: int = 0,
    latency_ms: Optional[int] = None,
    message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Best-effort metric recording.

    This function must never break crawling. All exceptions are swallowed and
    written to logs because metrics are observational, not part of crawl success.
    """
    column_id = getattr(context, "runtime_metrics_column_id", None)
    if not column_id:
        return

    resolved_source_url = resolve_source_url(context, group, source_url)
    if not resolved_source_url:
        return

    try:
        SourceRuntimeMetricService().record_event({
            "column_id": column_id,
            "source_url": resolved_source_url,
            "event_type": event_type,
            "article_count": article_count,
            "duplicate_count": duplicate_count,
            "latency_ms": latency_ms,
            "message": message,
            "metadata": {
                "group": group,
                "raw_source_url": source_url,
                **(metadata or {}),
            },
        })
    except Exception as exc:
        logger.warning("Failed to record runtime metric: %s", exc)
