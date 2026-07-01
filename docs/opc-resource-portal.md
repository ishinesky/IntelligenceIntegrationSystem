# OPC Resource Portal

This feature turns the dynamic-column/editorial-review backend into a browsable OPC resource portal.

## Scope

The portal is a read-only product layer over existing data:

```text
Columns
  -> Editorial reviews
  -> Feed cards
  -> Column pages
  -> Review detail pages
  -> JSON API
  -> RSS XML
```

It does not mutate original IntelligenceHub articles or editorial review records.

## Routes

### Browser pages

```text
/opc-resource
/opc-resource/columns/<column_id>
/opc-resource/reviews/<review_id>
```

These are registered through the existing `register_opc_column_routes(...)` helper and inherit the configured `login_required` decorator.

### JSON / RSS API

```text
GET /api/opc-resource/columns
GET /api/opc-resource/columns/<column_id>
GET /api/opc-resource/feed
GET /api/opc-resource/reviews/<review_id>
GET /api/opc-resource/rss.xml
```

Feed query parameters:

```text
column_id
keyword
status=published,reviewed
min_quality
min_actionability
limit
```

RSS query parameters:

```text
column_id
keyword
limit
title
```

## CLI

List columns:

```bash
python -m ColumnMVP.cli_public_portal columns
```

List feed:

```bash
python -m ColumnMVP.cli_public_portal feed \
  --column-id jinan-opc-example \
  --min-quality 6 \
  --min-actionability 5
```

Show one review detail:

```bash
python -m ColumnMVP.cli_public_portal review <review_id>
```

Export RSS:

```bash
python -m ColumnMVP.cli_public_portal rss \
  --base-url https://example.com \
  --output opc-feed.xml
```

## Data model

The portal consumes editorial reviews with status:

```text
published
reviewed
```

It displays:

- title;
- source URL;
- fact summary;
- why it matters;
- opportunity;
- risk;
- action suggestion;
- AI editorial view;
- source reliability;
- content quality score;
- actionability score;
- confidence.

## Publishing boundary

For now, `reviewed` and `published` both appear in the feed. To make this public-facing, switch the default status filter to `published` only.

## Security

The pages and API are registered with the same optional `login_required` decorator as the management pages. In the current integration path, they are internal/semipublic unless deployment intentionally registers them without authentication.

## Next step

Add publishing workflow:

```text
draft/reviewed
  -> approve
  -> published
  -> public portal/RSS
```

This should include role checks, audit log, and a clear distinction between internal reviewed content and public published content.
