# OPC Runtime Metrics

This layer adds a runtime metrics store for dynamic OPC column sources.

## Goal

The previous source-quality layer was metadata and validation based. Runtime metrics add observed operational signals:

```text
crawl success rate
crawl failures
article count
duplicate count
average relevance
average quality
actionability
latency
latest success time
```

The first implementation uses a JSONL store so it can be used without knowing the exact internal structure of the crawler governance database.

## Storage

Default path:

```text
ColumnMVP/runtime_metrics/source_metrics.jsonl
```

Each line is one event record.

## Event types

```text
crawl_success
crawl_failure
article
duplicate
skipped
```

## Automatic crawler hooks

Dynamic column crawlers now emit runtime metrics automatically.

The hook only activates for flow names matching:

```text
dynamic_columns/<column_id>
```

Existing fixed crawler tasks are ignored.

Currently recorded automatically:

```text
successful collected-data submission -> article event with article_count=1
commit/submission error              -> crawl_failure
ProcessSkip / ProcessIgnore          -> skipped
fetch_error / unexpected exception   -> crawl_failure
pipeline exception handler error     -> crawl_failure
```

## API

### Record one event

```http
POST /api/opc-columns/<column_id>/source-runtime-metrics
Content-Type: application/json
```

```json
{
  "source_url": "https://www.jinan.gov.cn/",
  "event_type": "crawl_success",
  "article_count": 8,
  "duplicate_count": 1,
  "relevance_score": 0.82,
  "quality_score": 0.76,
  "actionability_score": 0.66,
  "latency_ms": 1200,
  "message": "manual test event"
}
```

### Summarize one column

```http
GET /api/opc-columns/<column_id>/source-runtime-metrics
```

The summary includes:

- `success_rate`
- `article_count`
- `duplicate_ratio`
- `latest_success`
- `avg_relevance`
- `avg_quality`
- `avg_actionability`
- `runtime_score`
- `recommendation`

## CLI

Record one event:

```bash
python -m ColumnMVP.cli_source_metrics record jinan-opc-example https://www.jinan.gov.cn/ crawl_success \
  --article-count 8 \
  --duplicate-count 1 \
  --relevance-score 0.82 \
  --quality-score 0.76 \
  --actionability-score 0.66 \
  --latency-ms 1200 \
  --message "manual test event"
```

Summarize:

```bash
python -m ColumnMVP.cli_source_metrics summary jinan-opc-example
```

## Admin page

Open:

```text
/opc-columns/runtime-metrics
```

The page supports:

- recording a source runtime event;
- loading a runtime metrics summary;
- viewing source-level runtime score and recommendation;
- inspecting raw JSON.

## Runtime recommendations

The first runtime recommendation is derived from:

- success rate;
- article count;
- duplicate ratio;
- average relevance;
- average quality;
- average actionability;
- latest success existence.

Recommendations:

```text
promote
keep
review
disable
```

## Safety boundary

This layer does not automatically mutate sources. It only records and summarizes runtime observations. Operators still decide whether to promote, keep, review, or disable a source.

Metric recording is best-effort. If recording fails, crawling continues.

## Next integration

A later adapter can add deeper runtime signals from:

```text
DATA_PATH/spider_governance.db
IntelligenceCrawler.CrawlPipeline internals
Mongo article archives
AI analysis scores
```

Potential future metrics:

```text
discovered count
fetched count
extracted count
batch elapsed time
per-source duplicate rate
topic relevance from analyzed articles
```
