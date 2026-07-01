from __future__ import annotations

import datetime
import email.utils
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from .column_store import ColumnStore
from .editorial_review import EditorialReviewRecord, EditorialReviewService


def _safe_number(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _shorten(value: str, limit: int = 220) -> str:
    value = (value or '').strip()
    if len(value) <= limit:
        return value
    return value[:limit - 1].rstrip() + '…'


def _parse_time(value: str) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def _rss_date(value: str) -> str:
    dt = _parse_time(value) or datetime.datetime.now(datetime.timezone.utc)
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return email.utils.format_datetime(dt)


class OPCPublicPortalService:
    """Read-model service for the OPC resource portal.

    The portal is based on column definitions and editorial review records. It is
    deliberately read-only: publishing decisions remain controlled by the review
    status and filters.
    """

    def __init__(
        self,
        *,
        column_store: Optional[ColumnStore] = None,
        editorial_service: Optional[EditorialReviewService] = None,
    ):
        self.column_store = column_store or ColumnStore()
        self.editorial_service = editorial_service or EditorialReviewService()

    def list_columns(self, *, include_disabled: bool = False) -> Dict[str, Any]:
        columns = self.column_store.list_columns(enabled_only=not include_disabled)
        reviews = self.editorial_service.store.iter_records()
        count_by_column: Dict[str, int] = {}
        for review in reviews:
            if review.status in {'reviewed', 'published'}:
                count_by_column[review.column_id] = count_by_column.get(review.column_id, 0) + 1

        return {
            'columns': [
                {
                    'id': column.id,
                    'name': column.name,
                    'description': column.description,
                    'enabled': column.enabled,
                    'keywords': column.keywords,
                    'source_count': len(column.sources),
                    'review_count': count_by_column.get(column.id, 0),
                    'updated_at': column.updated_at,
                }
                for column in columns
            ],
            'total': len(columns),
        }

    def get_column(self, column_id: str) -> Dict[str, Any]:
        column = self.column_store.load(column_id)
        feed = self.list_feed(column_id=column_id, limit=50)
        return {
            'column': column.to_dict(),
            'feed': feed,
        }

    def list_feed(
        self,
        *,
        column_id: str = '',
        keyword: str = '',
        status: str = 'published,reviewed',
        min_quality: float = 0,
        min_actionability: float = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        allowed_status = {item.strip() for item in status.split(',') if item.strip()}
        records = self.editorial_service.store.iter_records()
        cards: List[Dict[str, Any]] = []
        for record in records:
            if allowed_status and record.status not in allowed_status:
                continue
            if column_id and record.column_id != column_id:
                continue
            card = self._record_to_card(record)
            review = card.get('review', {})
            if _safe_number(review.get('CONTENT_QUALITY_SCORE')) < min_quality:
                continue
            if _safe_number(review.get('ACTIONABILITY_SCORE')) < min_actionability:
                continue
            if keyword:
                haystack = ' '.join([
                    card.get('title', ''),
                    card.get('source_url', ''),
                    review.get('FACT_SUMMARY', ''),
                    review.get('WHY_IT_MATTERS', ''),
                    review.get('OPPORTUNITY', ''),
                    review.get('RISK', ''),
                    review.get('ACTION_SUGGESTION', ''),
                    review.get('EDITORIAL_VIEW', ''),
                ]).lower()
                if keyword.lower() not in haystack:
                    continue
            cards.append(card)

        cards.sort(key=lambda item: item.get('created_at', ''), reverse=True)
        return {
            'items': cards[:max(1, min(limit, 200))],
            'total': len(cards),
            'filters': {
                'column_id': column_id,
                'keyword': keyword,
                'status': status,
                'min_quality': min_quality,
                'min_actionability': min_actionability,
                'limit': limit,
            },
        }

    def get_review_detail(self, review_id: str) -> Dict[str, Any]:
        record = self.editorial_service.store.get(review_id)
        if not record:
            raise FileNotFoundError('review not found')
        return self._record_to_card(record, include_article=True)

    def build_rss(
        self,
        *,
        base_url: str = '',
        column_id: str = '',
        keyword: str = '',
        limit: int = 30,
        title: str = 'OPC Resource Feed',
    ) -> str:
        feed = self.list_feed(column_id=column_id, keyword=keyword, status='published,reviewed', limit=limit)
        base_url = (base_url or '').rstrip('/')
        channel_link = f'{base_url}/opc-resource' if base_url else '/opc-resource'
        items_xml = []
        for item in feed['items']:
            link = f"{base_url}/opc-resource/reviews/{item['review_id']}" if base_url else f"/opc-resource/reviews/{item['review_id']}"
            review = item.get('review', {})
            description = '\n'.join([
                f"事实摘要：{review.get('FACT_SUMMARY', '')}",
                f"为什么重要：{review.get('WHY_IT_MATTERS', '')}",
                f"行动建议：{review.get('ACTION_SUGGESTION', '')}",
                f"AI观点：{review.get('EDITORIAL_VIEW', '')}",
            ])
            items_xml.append(f"""
            <item>
              <title>{escape(item.get('title') or item.get('review_id'))}</title>
              <link>{escape(link)}</link>
              <guid>{escape(item.get('review_id'))}</guid>
              <pubDate>{escape(_rss_date(item.get('created_at', '')))}</pubDate>
              <description>{escape(description)}</description>
            </item>""")
        return f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>{escape(title)}</title>
    <link>{escape(channel_link)}</link>
    <description>{escape('Curated OPC intelligence with AI editorial reviews')}</description>
    <lastBuildDate>{escape(_rss_date(datetime.datetime.now(datetime.timezone.utc).isoformat()))}</lastBuildDate>
    {''.join(items_xml)}
  </channel>
</rss>
"""

    def _record_to_card(self, record: EditorialReviewRecord, *, include_article: bool = False) -> Dict[str, Any]:
        review = record.review or {}
        card = {
            'review_id': record.review_id,
            'article_uuid': record.article_uuid,
            'column_id': record.column_id,
            'source_url': record.source_url,
            'title': record.title or record.article_uuid,
            'created_at': record.created_at,
            'status': record.status,
            'summary': _shorten(review.get('FACT_SUMMARY', ''), 260),
            'why_it_matters': _shorten(review.get('WHY_IT_MATTERS', ''), 220),
            'opportunity': _shorten(review.get('OPPORTUNITY', ''), 220),
            'risk': _shorten(review.get('RISK', ''), 220),
            'action_suggestion': _shorten(review.get('ACTION_SUGGESTION', ''), 220),
            'editorial_view': _shorten(review.get('EDITORIAL_VIEW', ''), 220),
            'quality_score': _safe_number(review.get('CONTENT_QUALITY_SCORE')),
            'actionability_score': _safe_number(review.get('ACTIONABILITY_SCORE')),
            'confidence': _safe_number(review.get('CONFIDENCE')),
            'source_reliability': review.get('SOURCE_RELIABILITY', ''),
            'who_should_care': review.get('WHO_SHOULD_CARE', []),
            'review': review,
        }
        if include_article:
            card['article'] = record.article
            card['metadata'] = record.metadata
        return card
