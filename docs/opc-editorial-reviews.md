# OPC Editorial Reviews

This layer adds storage and display for article-level OPC editorial reviews.

## Goal

The original analysis pipeline classifies and summarizes intelligence. OPC editorial review adds a product-facing editorial layer:

```text
article
  -> fact summary
  -> why it matters
  -> opportunity
  -> risk
  -> who should care
  -> action suggestion
  -> AI editorial view
  -> quality/actionability/confidence scores
```

Important rule: facts, analysis, and AI opinion must stay separated.

## Storage

Default path:

```text
ColumnMVP/editorial_reviews/reviews.jsonl
```

Each line is one editorial review record.

## Fields

The normalized review object contains:

```text
FACT_SUMMARY
WHY_IT_MATTERS
OPPORTUNITY
RISK
WHO_SHOULD_CARE
ACTION_SUGGESTION
EDITORIAL_VIEW
SOURCE_RELIABILITY
CONTENT_QUALITY_SCORE
ACTIONABILITY_SCORE
CONFIDENCE
```

## API

### Create a review

```http
POST /api/opc-columns/editorial-reviews
Content-Type: application/json
```

```json
{
  "column_id": "jinan-opc-example",
  "article_uuid": "article-uuid",
  "title": "济南某政策发布",
  "source_url": "https://example.com/article",
  "status": "reviewed",
  "review": {
    "FACT_SUMMARY": "基于原文的事实摘要",
    "WHY_IT_MATTERS": "为什么重要",
    "OPPORTUNITY": "机会点",
    "RISK": "风险点",
    "WHO_SHOULD_CARE": ["OPC创业者", "AI应用开发者"],
    "ACTION_SUGGESTION": "下一步行动建议",
    "EDITORIAL_VIEW": "明确标注为 AI 编辑观点的评论态度",
    "SOURCE_RELIABILITY": "A",
    "CONTENT_QUALITY_SCORE": 8,
    "ACTIONABILITY_SCORE": 7,
    "CONFIDENCE": 0.82
  }
}
```

### List reviews

```http
GET /api/opc-columns/editorial-reviews
GET /api/opc-columns/editorial-reviews?column_id=jinan-opc-example
GET /api/opc-columns/editorial-reviews?article_uuid=article-uuid
GET /api/opc-columns/editorial-reviews?status=published
```

### Get one review

```http
GET /api/opc-columns/editorial-reviews/<review_id>
```

## CLI

Create from JSON payload:

```bash
python -m ColumnMVP.cli_editorial_reviews create payload.json
```

List:

```bash
python -m ColumnMVP.cli_editorial_reviews list --column-id jinan-opc-example --limit 20
```

Show:

```bash
python -m ColumnMVP.cli_editorial_reviews show <review_id>
```

## Admin page

Open:

```text
/opc-columns/editorial-reviews
```

The page supports:

- creating a review record;
- listing reviews;
- filtering by column ID and status;
- displaying fact summary, importance, opportunity, risk, action suggestion, and AI view separately.

## AI generation path

`ColumnMVP.ai_editorial.build_editorial_review()` already wraps the OPC editorial prompt and can generate review JSON from an AI client.

The safe integration path is:

```text
article JSON
  -> build_editorial_review(ai_client, article)
  -> POST /api/opc-columns/editorial-reviews
  -> editorial review store
```

This PR does not force automatic AI generation inside the crawler flow. That remains a separate step so the crawler cannot be blocked by LLM latency or failures.

## Safety boundary

- Editorial reviews are not facts.
- `FACT_SUMMARY` must be based on the source article.
- `EDITORIAL_VIEW` must be shown as AI/editorial opinion.
- The review store does not mutate the original article record.
- This layer does not auto-publish public content.
