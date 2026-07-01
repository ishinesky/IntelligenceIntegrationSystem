from __future__ import annotations

from typing import Dict, Optional

from CrawlerServiceEngine import ServiceContext
from Workflow.IntelligenceCrawlFlow import CommonIntelligenceCrawlFlow
from ColumnMVP.column_store import ColumnStore
from ColumnMVP.dynamic_crawler_config import build_crawler_config

NAME = "dynamic_columns"
SERVICE_CONTEXT: Optional[ServiceContext] = None
FLOWS: Dict[str, CommonIntelligenceCrawlFlow] = {}


def module_init(service_context: ServiceContext):
    global SERVICE_CONTEXT
    SERVICE_CONTEXT = service_context


def _flow_name(column_id: str) -> str:
    return f"{NAME}/{column_id}"


def start_task(stop_event):
    if SERVICE_CONTEXT is None:
        return

    store = ColumnStore()
    columns = store.list_columns(enabled_only=True)
    if not columns:
        SERVICE_CONTEXT.logger.info("[dynamic-columns] no enabled columns found.")
        return

    for column in columns:
        if stop_event.is_set():
            break
        if not column.sources:
            SERVICE_CONTEXT.logger.info(f"[dynamic-columns] skip {column.id}: no sources.")
            continue

        flow_name = _flow_name(column.id)
        flow = FLOWS.get(flow_name)
        if flow is None:
            flow = CommonIntelligenceCrawlFlow(flow_name, SERVICE_CONTEXT)
            FLOWS[flow_name] = flow

        crawler_config = build_crawler_config(column)
        if not crawler_config.get("entry_points"):
            SERVICE_CONTEXT.logger.info(f"[dynamic-columns] skip {column.id}: no enabled entry points.")
            continue

        SERVICE_CONTEXT.logger.info(
            f"[dynamic-columns] run column={column.id} sources={len(crawler_config['entry_points'])}"
        )
        flow.run_common_flow(crawler_config, stop_event, global_site=False)
