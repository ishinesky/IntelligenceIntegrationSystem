# OPC Column MVP

This MVP turns the fixed-source crawler model into a safer topic-driven column workflow.

## Goal

Create a durable column from a user-selected topic:

```text
User topic
  -> TopicBrief
  -> candidate source URLs
  -> validation
  -> ColumnMVP/columns/*.json
  -> CrawlTasks/task_dynamic_columns.py
  -> CommonIntelligenceCrawlFlow
  -> IntelligenceHub
```

The first version deliberately does **not** let AI generate and execute Python crawler code. AI can propose topics, keywords, source candidates, and editorial reviews; the runtime only consumes JSON configuration.

## Why this fits the existing project

The original crawler service loads Python tasks from `CrawlTasks` via the plugin mechanism. Existing tasks usually import a fixed crawler config and call `CommonIntelligenceCrawlFlow`. This MVP keeps that contract and adds a single dynamic task:

```text
CrawlTasks/task_dynamic_columns.py
```

The task reads JSON column definitions and converts each column into the existing crawler config shape.

## Create a column

Example:

```bash
python -m ColumnMVP.cli_create_column \
  --name "济南 OPC 政策与社区动态" \
  --description "跟踪济南及山东范围内与 OPC、一人公司、AI创业社区、算力券、Token券、人才补贴、园区入驻相关的公开信息" \
  --region 济南 \
  --region 山东 \
  --keyword OPC \
  --keyword 一人公司 \
  --keyword 中国算谷 \
  --keyword 算力券 \
  --url https://www.jinan.gov.cn/ \
  --overwrite
```

Print discovery queries without creating sources:

```bash
python -m ColumnMVP.cli_create_column \
  --name "济南 OPC 政策与社区动态" \
  --description "跟踪济南 OPC 政策、社区、补贴、活动" \
  --region 济南 \
  --keyword OPC \
  --keyword 算力券 \
  --print-queries \
  --no-validate \
  --overwrite
```

Generated files are stored under:

```text
ColumnMVP/columns/*.json
```

## Run dynamic columns

Start the existing crawler service normally. It scans `CrawlTasks` and should load:

```text
CrawlTasks/task_dynamic_columns.py
```

The task will process every enabled column with at least one source.

## Editorial review layer

`ColumnMVP/ai_editorial.py` adds a dedicated OPC editorial prompt. It returns strict JSON with separated fields:

- `FACT_SUMMARY`
- `WHY_IT_MATTERS`
- `OPPORTUNITY`
- `RISK`
- `WHO_SHOULD_CARE`
- `ACTION_SUGGESTION`
- `EDITORIAL_VIEW`
- `SOURCE_RELIABILITY`
- `CONTENT_QUALITY_SCORE`
- `ACTIONABILITY_SCORE`
- `CONFIDENCE`

Important UI rule: display facts, analysis, and AI editorial view as separate blocks. Do not mix AI opinion into the factual summary.

## Next steps

1. Add a UI/API endpoint for topic dialogue and column creation.
2. Connect a search provider to `source_discovery.build_search_queries`.
3. Add source quality scoring and automatic source retirement.
4. Persist columns in MongoDB instead of JSON once the schema stabilizes.
5. Attach `ai_editorial.build_editorial_review` after article analysis and expose it on the public page.
