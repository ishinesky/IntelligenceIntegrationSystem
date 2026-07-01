# OPC Column MVP Roadmap

The current implementation is intentionally staged to keep the crawler safe and reviewable.

## Completed

### PR #1: Dynamic column MVP

- File-backed dynamic columns.
- Safe JSON configuration model.
- Dynamic crawler task that reuses `CommonIntelligenceCrawlFlow`.
- OPC editorial prompt wrapper.

### PR #2: Management API and CLI

- Reusable `ColumnService`.
- Flask Blueprint API under `/api/opc-columns`.
- CLI for local management.

### PR #3: Web-service integration helper

- Explicit helper for registering the API.
- Optional monkey patch for local/transitional deployment.

### PR #4: Admin page

- Browser UI for creating and managing columns.
- No frontend build stack.
- Uses existing session-authenticated API.

### PR #5: Source discovery provider

- Provider abstraction for candidate URL discovery.
- Manual seed URL provider.
- Bing Web Search provider through environment variables.
- Candidate validation and triage scoring.
- API and CLI discovery entrypoints.
- Admin page support for candidate review and approval.

### PR #6: Source quality governance

- Source quality audit service.
- CLI source audit command.
- API endpoint for `/source-quality`.
- Browser page for reviewing source quality.
- Initial promote / keep / review / disable recommendations.

### PR #7: Runtime quality signals

- JSONL-backed runtime metric store.
- CLI for recording and summarizing source runtime events.
- API endpoint for `/source-runtime-metrics`.
- Browser page for runtime metrics.
- Runtime score and recommendation based on observed events.

### PR #8: Runtime integration hooks

- Dynamic-column runtime hook helpers.
- Runtime source mapping from crawler config entry points.
- Automatic article metric recording on successful submission.
- Automatic failure/skipped metric recording on process exceptions.
- Metrics are best-effort and never break crawling.

### PR #9: Editorial reviews

- Editorial review JSONL store.
- API endpoint for creating/listing/retrieving editorial reviews.
- CLI for editorial review management.
- Browser page for creating and reviewing AI editorial output.
- Facts, analysis, AI opinion, and action suggestions stay separated.

### PR #10: Editorial generation

- Editorial generation service.
- OpenAI-compatible chat adapter.
- Dry-run mode for prompt/article inspection.
- API endpoint for generating editorial reviews.
- CLI for generating and optionally persisting reviews.

## Next: Article-store integration

Target flow:

```text
Collected article UUID
  -> fetch article from IntelligenceHub / local store
  -> generate OPC editorial review
  -> review store
  -> article detail editorial block
```

Recommended implementation:

```text
ColumnMVP/article_lookup.py
/api/opc-columns/articles/<uuid>/generate-editorial-review
Article detail page editorial block
```

## Later: Public OPC resource frontend

Target flow:

```text
Column
  -> curated articles
  -> editorial reviews
  -> public list/detail pages
  -> RSS / email / API subscription
```

Important rule: never mix AI editorial opinion into fact summary.
