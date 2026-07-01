# OPC Publishing Workflow

This feature hardens the OPC resource portal by adding an explicit publishing workflow.

## Goal

Separate internal review from public publication:

```text
draft / reviewed
  -> publish
  -> published
  -> public portal + RSS
```

Public feed and RSS now default to `published` only.

## Review statuses

```text
draft       generated or manually created, not reviewed
reviewed    internally reviewed, not public by default
published   visible in public portal/feed/RSS
rejected    not suitable for publishing
```

## Append-only model

Publishing does not overwrite the existing JSONL line. It appends a new review record with the same `review_id` and updated `status`.

The latest version wins for portal read models.

## Audit log

Publication changes are written to:

```text
ColumnMVP/editorial_reviews/publication_audit.jsonl
```

Each audit entry includes:

```text
audit_id
review_id
previous_status
next_status
operator
reason
created_at
metadata
```

## API

```text
POST /api/opc-publishing/reviews/<review_id>/publish
POST /api/opc-publishing/reviews/<review_id>/unpublish
POST /api/opc-publishing/reviews/<review_id>/reject
POST /api/opc-publishing/reviews/<review_id>/status
GET  /api/opc-publishing/reviews/<review_id>/audit
GET  /api/opc-publishing/audit
```

### Publish

```http
POST /api/opc-publishing/reviews/<review_id>/publish
Content-Type: application/json
```

```json
{
  "operator": "jaime",
  "reason": "适合公开发布"
}
```

### Custom status

```json
{
  "status": "reviewed",
  "operator": "jaime",
  "reason": "撤回公开，等待复核"
}
```

## CLI

```bash
python -m ColumnMVP.cli_publish_reviews publish <review_id> --operator jaime --reason "公开发布"
python -m ColumnMVP.cli_publish_reviews unpublish <review_id> --operator jaime --reason "撤回复核"
python -m ColumnMVP.cli_publish_reviews reject <review_id> --operator jaime --reason "来源不可靠"
python -m ColumnMVP.cli_publish_reviews status <review_id> reviewed --operator jaime
python -m ColumnMVP.cli_publish_reviews audit --review-id <review_id>
```

## Admin page

Open:

```text
/opc-columns/publishing
```

The page supports:

- listing recent reviews by status;
- selecting a review ID;
- publishing;
- unpublishing;
- rejecting;
- viewing audit logs.

## Public hardening

The portal now defaults to `published` only:

```text
/opc-resource
/api/opc-resource/feed
/api/opc-resource/rss.xml
```

To inspect internal reviewed content, use editorial review management pages/API instead of public feed.

## Security note

The publishing API is registered through the same integration helper as the existing OPC admin APIs and inherits the configured `login_required` decorator. For public deployment, add role-level checks before exposing publish/unpublish actions to multiple users.
