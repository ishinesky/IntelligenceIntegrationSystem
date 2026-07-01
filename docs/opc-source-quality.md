# OPC Source Quality

This layer adds source-quality governance for dynamic OPC columns.

## Goal

The system can now audit the sources attached to a column and return a quality score plus an operational recommendation.

```text
Column sources
  -> metadata heuristics
  -> topic relevance
  -> trust-level checks
  -> optional live validation
  -> score
  -> recommendation
```

## Recommendations

The first version returns one of four recommendations:

```text
promote   strong source, likely worth prioritizing
keep      usable source, keep enabled
review    questionable source, review manually
disable   weak or failing source, consider disabling
```

## Signals used in v1

The first audit version is intentionally local and lightweight. It uses:

- source enabled/disabled state;
- stored `trust_level`;
- `.gov.cn` and media-like hostname hints;
- keyword relevance against the column keywords;
- negative keyword penalty;
- stored validation status;
- crawl method, especially RSS;
- optional live HTTP validation;
- RSS/sitemap hints from live validation.

It does **not** yet use historical crawler success rate, article relevance, duplicate rate, or freshness from the crawler governance DB. Those should be added in the next iteration.

## API

```http
GET /api/opc-columns/<column_id>/source-quality
GET /api/opc-columns/<column_id>/source-quality?live_validate=false
```

Response shape:

```json
{
  "success": true,
  "data": {
    "column": {
      "id": "jinan-opc-example",
      "name": "济南 OPC 政策与社区动态示例",
      "source_count": 1
    },
    "live_validate": true,
    "recommendation_counts": {
      "promote": 1
    },
    "sources": [
      {
        "name": "济南市人民政府",
        "url": "https://www.jinan.gov.cn/",
        "enabled": true,
        "source_type": "government",
        "trust_level": "S",
        "validation_status": "manual_review",
        "score": 0.82,
        "recommendation": "promote",
        "reasons": ["official .gov.cn source"],
        "validation": {
          "ok": true,
          "status_code": 200
        }
      }
    ]
  }
}
```

## CLI

```bash
python -m ColumnMVP.cli_audit_sources jinan-opc-example
python -m ColumnMVP.cli_audit_sources jinan-opc-example --no-live-validate
```

## Admin page

Open:

```text
/opc-columns/source-quality
```

Enter a column ID and choose whether to run live validation.

## Safety boundary

This audit does not automatically disable or modify any source. It only returns recommendations. Operators still decide whether to disable, keep, or promote a source.

## Next step

Add historical quality signals from crawler runtime data:

```text
crawl success rate
last successful crawl time
article count in last N days
duplicate ratio
topic relevance of fetched articles
average AI quality / actionability score
```
