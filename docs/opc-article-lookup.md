# OPC Article Lookup

This layer connects editorial generation to existing or mirrored article records.

## Goal

Before this layer, operators had to paste article text manually. This layer supports:

```text
article UUID / source URL
  -> local JSONL mirror lookup
  -> optional remote IntelligenceHub lookup
  -> normalized article payload
  -> OPC editorial generation
  -> editorial review store
```

## Existing IntelligenceHub endpoint

The main web service already exposes:

```http
GET /api/intelligence/<uuid>
```

This endpoint calls `self.intelligence_hub.get_intelligence(uuid)` and returns API JSON.

## Lookup sources

### 1. Inline article payload

If the request includes `article`, it is used directly.

### 2. Local JSONL mirror

Default path:

```text
ColumnMVP/article_store/articles.jsonl
```

Each line can be either a raw article object or an API object with `data`.

### 3. Remote IntelligenceHub

Set:

```bash
export INTELLIGENCE_HUB_BASE_URL="http://127.0.0.1:8080"
```

Then lookup by UUID will call:

```text
{INTELLIGENCE_HUB_BASE_URL}/api/intelligence/<uuid>
```

## API

### Lookup article

```http
GET /api/opc-columns/articles/lookup?article_uuid=<uuid>
GET /api/opc-columns/articles/lookup?source_url=https://example.com/article
```

### Import one local article mirror

```http
POST /api/opc-columns/articles/import
Content-Type: application/json
```

```json
{
  "article": {
    "UUID": "article-uuid",
    "title": "文章标题",
    "content": "文章正文",
    "informant": "https://example.com/article"
  }
}
```

### Generate editorial review from article lookup

```http
POST /api/opc-columns/editorial-reviews/generate-from-article
Content-Type: application/json
```

```json
{
  "column_id": "jinan-opc-example",
  "article_uuid": "article-uuid",
  "dry_run": true,
  "persist": true
}
```

Use `dry_run=true` to inspect the prompt/payload before calling AI.

## CLI

Lookup:

```bash
python -m ColumnMVP.cli_article_lookup lookup --uuid article-uuid
```

Import local mirror:

```bash
python -m ColumnMVP.cli_article_lookup import article.json
```

Lookup and generate:

```bash
python -m ColumnMVP.cli_article_lookup generate \
  --uuid article-uuid \
  --column-id jinan-opc-example \
  --dry-run
```

Generate and persist:

```bash
python -m ColumnMVP.cli_article_lookup generate \
  --uuid article-uuid \
  --column-id jinan-opc-example
```

## Admin page

Open:

```text
/opc-columns/article-lookup
```

The page supports:

- lookup by article UUID or URL;
- importing one local article JSON into the JSONL mirror;
- lookup + dry-run editorial generation;
- lookup + generate and persist.

## Normalized article shape

The service normalizes different upstream shapes into:

```json
{
  "UUID": "...",
  "title": "...",
  "content": "...",
  "pub_time": "...",
  "informant": "...",
  "raw": {}
}
```

## Safety boundary

- Lookup does not mutate original IntelligenceHub records.
- Import only appends to the local JSONL mirror.
- Generation still supports dry-run and `persist=false`.
- Editorial views remain separate from factual summaries.
