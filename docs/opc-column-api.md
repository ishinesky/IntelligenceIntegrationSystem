# OPC Column API

This document describes the second MVP layer for dynamic OPC columns: a service layer, Flask Blueprint, and management CLI.

## Files

```text
ColumnMVP/column_service.py       # application service used by CLI/API/dialogue agents
ColumnMVP/web_api.py              # Flask Blueprint for column management
ColumnMVP/cli_manage_columns.py   # local management CLI
```

## Register the Flask Blueprint

The API is intentionally implemented as a Blueprint so it can be wired into the existing `IntelligenceHubWebService` without changing the crawler flow.

Inside `IntelligenceHubWebService.register_routers`, after `app` is initialized and before public pages, add:

```python
from ColumnMVP.web_api import register_column_routes

register_column_routes(
    app,
    login_required=WebServiceAccessManager.login_required,
)
```

This keeps the endpoints private behind the existing session login decorator.

## Endpoints

Default prefix:

```text
/api/opc-columns
```

### List columns

```http
GET /api/opc-columns
GET /api/opc-columns?enabled_only=true
```

### Create column

```http
POST /api/opc-columns
Content-Type: application/json
```

Body:

```json
{
  "name": "济南 OPC 政策与社区动态",
  "description": "跟踪济南及山东范围内与 OPC、一人公司、AI创业社区、算力券、Token券、人才补贴、园区入驻相关的公开信息",
  "regions": ["济南", "山东"],
  "keywords": ["OPC", "一人公司", "中国算谷", "算力券"],
  "negative_keywords": ["普通招聘", "无关招商广告"],
  "seed_urls": ["https://www.jinan.gov.cn/"],
  "validate_sources": true,
  "overwrite": false
}
```

### Suggest source discovery queries

```http
POST /api/opc-columns/suggest-queries
Content-Type: application/json
```

Body accepts the same topic fields as create-column. This does not call a search engine; it returns query strings for a future search provider.

### Validate one source

```http
POST /api/opc-columns/validate-source
Content-Type: application/json
```

```json
{
  "url": "https://www.jinan.gov.cn/"
}
```

### Get / update column

```http
GET /api/opc-columns/<column_id>
PATCH /api/opc-columns/<column_id>
```

Patch body can include:

```json
{
  "enabled": true,
  "keywords": ["OPC", "AI创业"],
  "metadata": {
    "owner": "opc-resource"
  }
}
```

### Enable / disable

```http
POST /api/opc-columns/<column_id>/enable
POST /api/opc-columns/<column_id>/disable
```

### Add sources

```http
POST /api/opc-columns/<column_id>/sources
Content-Type: application/json
```

```json
{
  "urls": [
    "https://www.jinan.gov.cn/"
  ],
  "validate_sources": true
}
```

### Preview generated crawler config

```http
GET /api/opc-columns/<column_id>/crawler-config
```

This returns the existing `CommonIntelligenceCrawlFlow` crawler config shape, including `entry_points`.

## CLI

List columns:

```bash
python -m ColumnMVP.cli_manage_columns list
```

Show one column:

```bash
python -m ColumnMVP.cli_manage_columns show jinan-opc-example
```

Enable / disable:

```bash
python -m ColumnMVP.cli_manage_columns enable jinan-opc-example
python -m ColumnMVP.cli_manage_columns disable jinan-opc-example
```

Add source:

```bash
python -m ColumnMVP.cli_manage_columns add-source jinan-opc-example https://www.jinan.gov.cn/
```

Preview crawler config:

```bash
python -m ColumnMVP.cli_manage_columns preview-crawler jinan-opc-example
```

## Design boundary

This layer still does not allow AI-generated Python code execution. It accepts structured topic/source configuration only. This is the intended boundary for a public resource site where data-source governance and legal risk matter.
