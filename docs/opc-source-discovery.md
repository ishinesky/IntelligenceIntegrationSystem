# OPC Source Discovery

This layer adds candidate-source discovery for dynamic OPC columns.

## Goal

The system now supports this flow:

```text
Column topic
  -> generated search queries
  -> source search provider
  -> candidate URLs
  -> validation / scoring
  -> admin review
  -> selected URLs are added to the column
```

Discovery does **not** automatically insert sources into a column. Candidates must be approved by an operator through the admin page, API, or CLI.

## Providers

Provider selection is controlled by the `provider` field.

### `manual`

Uses explicitly supplied `seed_urls` as candidates. This is the safest provider and requires no external service.

### `bing`

Uses Bing Web Search API.

Environment variables:

```bash
export BING_SEARCH_API_KEY="..."
export BING_SEARCH_ENDPOINT="https://api.bing.microsoft.com/v7.0/search"  # optional
export BING_SEARCH_MARKET="zh-CN"                                         # optional
```

### `auto`

Default provider.

Behavior:

```text
BING_SEARCH_API_KEY exists -> use bing
seed_urls provided         -> use manual
otherwise                  -> use null
```

### `null`

Returns no results. Useful for testing endpoint wiring.

## API

### Discover from topic payload

```http
POST /api/opc-columns/discover-sources
Content-Type: application/json
```

```json
{
  "name": "济南 OPC 政策与社区动态",
  "description": "跟踪济南 OPC 政策、社区、补贴、活动",
  "regions": ["济南", "山东"],
  "keywords": ["OPC", "一人公司", "算力券"],
  "provider": "auto",
  "seed_urls": ["https://www.jinan.gov.cn/"],
  "max_queries": 8,
  "results_per_query": 5,
  "validate_sources": true
}
```

### Discover for an existing column

```http
POST /api/opc-columns/<column_id>/discover-sources
Content-Type: application/json
```

```json
{
  "provider": "manual",
  "seed_urls": ["https://www.jinan.gov.cn/"],
  "max_queries": 8,
  "results_per_query": 5,
  "validate_sources": true
}
```

### Add approved candidates

Use the existing source-add endpoint:

```http
POST /api/opc-columns/<column_id>/sources
Content-Type: application/json
```

```json
{
  "urls": ["https://www.jinan.gov.cn/"],
  "validate_sources": true
}
```

## CLI

Discover from topic:

```bash
python -m ColumnMVP.cli_discover_sources topic \
  --name "济南 OPC 政策与社区动态" \
  --description "跟踪济南 OPC 政策、社区、补贴、活动" \
  --region 济南 \
  --keyword OPC \
  --keyword 算力券 \
  --provider manual \
  --seed-url https://www.jinan.gov.cn/
```

Discover for existing column:

```bash
python -m ColumnMVP.cli_discover_sources column jinan-opc-example \
  --provider manual \
  --seed-url https://www.jinan.gov.cn/
```

## Admin page

Open:

```text
/opc-columns/admin
```

Use the **发现候选数据源** section:

1. Enter a column ID.
2. Choose provider.
3. Add seed URLs if using `manual` or fallback `auto`.
4. Click **发现候选源**.
5. Review score and validation result.
6. Tick candidates and click **将勾选候选源加入栏目**.

## Candidate scoring

The MVP scoring is intentionally simple:

- keyword match increases score;
- region match increases score;
- negative keyword match decreases score;
- `.gov.cn` sources get a trust boost;
- known media-like hostnames get a small boost;
- successful validation adds a small boost.

This is not final ranking logic. It is a lightweight triage score for admin review.

## Safety boundary

- Discovery produces candidates only.
- Operators approve before sources are persisted.
- Runtime still consumes reviewed JSON column config.
- AI-generated executable crawler code is not allowed.
- Closed/social platforms are not automatically scraped.
