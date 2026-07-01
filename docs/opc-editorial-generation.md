# OPC Editorial Generation

This layer turns the OPC editorial prompt into a callable generation service.

## Goal

Generate article-level editorial review JSON and optionally persist it:

```text
article payload
  -> OPC editorial prompt
  -> AI client
  -> normalized review JSON
  -> EditorialReviewService
  -> reviews.jsonl
```

The generation layer is intentionally outside the crawler execution path. LLM latency or provider failures should not block crawling.

## Environment variables

The built-in adapter supports OpenAI-compatible Chat Completions APIs:

```bash
export OPENAI_COMPAT_API_KEY="..."
export OPENAI_COMPAT_BASE_URL="https://api.openai.com/v1"   # optional
export OPENAI_COMPAT_MODEL="gpt-4o-mini"                    # optional
```

Any provider that exposes a compatible `/chat/completions` endpoint can be used.

## API

### Dry run

Dry run returns the prompt and normalized article payload without calling AI.

```http
POST /api/opc-columns/editorial-reviews/generate
Content-Type: application/json
```

```json
{
  "dry_run": true,
  "column_id": "jinan-opc-example",
  "article_uuid": "article-uuid",
  "title": "济南某政策发布",
  "source_url": "https://example.com/article",
  "content": "文章正文"
}
```

### Generate and persist

```json
{
  "column_id": "jinan-opc-example",
  "article_uuid": "article-uuid",
  "title": "济南某政策发布",
  "source_url": "https://example.com/article",
  "content": "文章正文",
  "status": "reviewed",
  "persist": true
}
```

### Generate without persisting

```json
{
  "column_id": "jinan-opc-example",
  "article_uuid": "article-uuid",
  "title": "济南某政策发布",
  "source_url": "https://example.com/article",
  "content": "文章正文",
  "persist": false
}
```

## CLI

Dry run:

```bash
python -m ColumnMVP.cli_generate_editorial payload.json --dry-run
```

Generate and persist:

```bash
python -m ColumnMVP.cli_generate_editorial payload.json
```

Generate without persisting:

```bash
python -m ColumnMVP.cli_generate_editorial payload.json --no-persist
```

Override model/provider for a single command:

```bash
python -m ColumnMVP.cli_generate_editorial payload.json \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini
```

Prefer environment variables for API keys in production.

## Payload shape

Minimal payload:

```json
{
  "column_id": "jinan-opc-example",
  "title": "文章标题",
  "source_url": "https://example.com/article",
  "content": "文章正文"
}
```

Alternative nested article payload:

```json
{
  "column_id": "jinan-opc-example",
  "article": {
    "UUID": "article-uuid",
    "title": "文章标题",
    "informant": "https://example.com/article",
    "content": "文章正文"
  }
}
```

## Safety boundary

- Generation is not part of crawler execution.
- Dry run allows inspection before any AI call.
- `persist=false` allows previewing generated JSON before saving.
- `FACT_SUMMARY` and `EDITORIAL_VIEW` remain separate fields.
- Generated reviews are internal records until another layer decides to publish them.

## Next step

Add article-store integration so operators can pick an existing collected article by UUID and generate a review without manually pasting article content.
