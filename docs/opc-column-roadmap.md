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

## Next: Source discovery provider

Target flow:

```text
User topic
  -> generated search queries
  -> search provider
  -> candidate URLs
  -> source validation
  -> admin approval
  -> column sources
```

Recommended implementation:

```text
ColumnMVP/source_search_provider.py
ColumnMVP/source_candidate_service.py
ColumnMVP/cli_discover_sources.py
```

Initial provider options:

- manual input provider;
- Bing Web Search API;
- SerpAPI;
- custom RSS/sitemap discovery.

## Later: Editorial publishing

Target flow:

```text
Collected article
  -> existing analysis
  -> OPC editorial review
  -> fact / analysis / AI view / action suggestion
  -> public resource frontend
```

Important rule: never mix AI editorial opinion into fact summary.
