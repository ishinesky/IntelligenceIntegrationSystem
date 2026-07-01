# OPC Runtime Hooks

This layer connects dynamic OPC column crawls to the runtime metrics system.

## Goal

Before this change, runtime metrics could be recorded manually through API/CLI. This layer records metrics automatically from the crawler flow for dynamic columns.

```text
dynamic_columns/<column_id>
  -> CommonIntelligenceCrawlFlow
  -> CrawlContext
  -> SourceRuntimeMetricService
  -> ColumnMVP/runtime_metrics/source_metrics.jsonl
```

## Files changed

```text
ColumnMVP/runtime_hooks.py
Workflow/CommonFlowUtility.py
Workflow/IntelligenceCrawlFlow.py
ColumnMVP/__init__.py
```

## How dynamic columns are detected

Only flow names matching this prefix are enabled for automatic runtime metrics:

```text
dynamic_columns/<column_id>
```

Fixed-source crawlers are ignored.

## Source URL mapping

`CommonIntelligenceCrawlFlow.run_common_flow()` reads the crawler config `entry_points` and builds a source map:

```python
{
  "source name": "source url",
  "dynamic_columns/<column_id>/source name": "source url",
  "source url": "source url"
}
```

This allows article-level callbacks to resolve a crawler group back to its original column source URL.

## Recorded events

### Article submission

When `CrawlContext.submit_collected_data()` successfully submits one collected article, it records:

```json
{
  "event_type": "article",
  "article_count": 1
}
```

### Commit/submission failure

If submitting to IntelligenceHub fails and the article is cached, it records:

```json
{
  "event_type": "crawl_failure",
  "message": "commit_error"
}
```

### Process exceptions

`CrawlContext.handle_process_exception()` records:

```text
ProcessSkip      -> skipped
ProcessIgnore    -> skipped
fetch_error      -> crawl_failure
commit_error     -> crawl_failure
other exceptions -> crawl_failure
```

### Pipeline exception handler

`IntelligenceCrawlFlow.intelligence_crawler_exception_handler()` records crawl failures reported by the pipeline exception handler.

## Safety boundary

Runtime metrics are best-effort only. They must never break crawling.

If metric recording fails, the exception is swallowed and logged as a warning. The crawler continues.

## Current limitation

This PR records article and failure events at stable existing flow boundaries. It does not yet record full batch-level metrics such as exact discovered count, duplicate count from the pipeline internals, or per-source elapsed duration. Those require deeper integration with `IntelligenceCrawler.CrawlPipeline` internals.

## Verify

Run a dynamic column crawl and then check:

```bash
python -m ColumnMVP.cli_source_metrics summary <column_id>
```

Or open:

```text
/opc-columns/runtime-metrics
```

The JSONL file should appear at:

```text
ColumnMVP/runtime_metrics/source_metrics.jsonl
```
