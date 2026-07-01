# OPC Column Admin Page

This page provides a lightweight browser UI for managing dynamic OPC columns.

## Route

After registering the OPC column integration helper, open:

```text
/opc-columns/admin
```

A short alias also exists:

```text
/opc-columns
```

It redirects to `/opc-columns/admin`.

## Capabilities

The page calls the existing `/api/opc-columns` endpoints and supports:

- list columns;
- create a topic-driven column;
- generate discovery search queries;
- enable / disable columns;
- copy column ID into source/preview forms;
- append source URLs;
- validate one source URL;
- preview generated crawler config.

## Files

```text
ColumnMVP/web_pages.py
ColumnMVP/web_service_integration.py
templates/opc_column_admin.html
```

## How it is registered

`ColumnMVP.web_service_integration.register_opc_column_routes` now registers both:

```text
/api/opc-columns       # JSON management API
/opc-columns/admin     # browser admin page
```

Use the integration helper inside `IntelligenceHubWebService.register_routers`:

```python
from ColumnMVP.web_service_integration import register_opc_column_routes

register_opc_column_routes(
    app,
    login_required=WebServiceAccessManager.login_required,
)
```

## Security

When `login_required=WebServiceAccessManager.login_required` is passed, both the API and page are protected by the existing session login.

The page itself does not bypass any backend validation. It only submits JSON to the same endpoints used by CLI/API consumers.

## Operational notes

- The page uses plain HTML, CSS, and vanilla JavaScript.
- It does not introduce frontend build tooling.
- It uses `credentials: 'same-origin'`, so it relies on the existing Flask session cookie.
- Source validation may be slow for sites with slow network responses.
- The page is intended as an internal/admin tool, not a public OPC resource frontend.

## Next step

The next meaningful layer is automatic source discovery:

```text
Topic payload
  -> generate search queries
  -> call a search provider
  -> collect candidate URLs
  -> validate sources
  -> present candidates for approval
  -> add approved sources to column
```
