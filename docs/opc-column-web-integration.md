# OPC Column Web Integration

This step connects the dynamic OPC column API to the existing Flask web service with minimal risk.

## Preferred integration

Open `IntelligenceHubWebService.py` and add this import near the other imports:

```python
from ColumnMVP.web_service_integration import register_opc_column_routes
```

Inside `IntelligenceHubWebService.register_routers`, after `app.json_encoder = CustomJSONEncoder`, add:

```python
register_opc_column_routes(
    app,
    login_required=WebServiceAccessManager.login_required,
)
```

This registers the private management API at:

```text
/api/opc-columns
```

The API remains protected by the existing session login decorator.

## Opt-in monkey patch integration

For deployments that do not want to edit `IntelligenceHubWebService.py` directly, call this once before the web service instance registers routes:

```python
from ColumnMVP.web_service_integration import patch_intelligence_hub_web_service

patch_intelligence_hub_web_service()
```

The patch wraps `IntelligenceHubWebService.register_routers` and registers the column API after the original routes are mounted.

Prefer the explicit registration approach for production. The monkey patch is meant for local evaluation or transitional deployment.

## Verify endpoints

After startup and login, check:

```http
GET /api/opc-columns
```

Create a column:

```http
POST /api/opc-columns
Content-Type: application/json
```

```json
{
  "name": "济南 OPC 政策与社区动态",
  "description": "跟踪济南及山东范围内与 OPC、一人公司、AI创业社区、算力券、Token券、人才补贴、园区入驻相关的公开信息",
  "regions": ["济南", "山东"],
  "keywords": ["OPC", "一人公司", "中国算谷", "算力券"],
  "seed_urls": ["https://www.jinan.gov.cn/"],
  "validate_sources": true
}
```

Preview the crawler config:

```http
GET /api/opc-columns/<column_id>/crawler-config
```

## Why this is separate from the large web-service file

`IntelligenceHubWebService.py` is a large central file with many routes and service concerns. Keeping the integration wrapper in `ColumnMVP/web_service_integration.py` makes the change small, reviewable, and reversible.

The dynamic column system still keeps the safety boundary:

- no AI-generated Python crawler code is executed;
- only reviewed JSON column/source config is consumed;
- closed social platforms are not automatically scraped;
- facts, analysis, AI editorial view, and action suggestions stay separated.
