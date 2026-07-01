from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def normalize_article(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize different IntelligenceHub/article shapes for editorial generation."""
    article = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    appendix = article.get("APPENDIX") if isinstance(article.get("APPENDIX"), dict) else {}
    return {
        "UUID": article.get("UUID") or article.get("uuid") or article.get("id") or "",
        "title": article.get("title") or article.get("EVENT_TITLE") or article.get("TITLE") or "",
        "content": article.get("content") or article.get("CONTENT") or article.get("BODY") or article.get("markdown_content") or article.get("SUMMARY") or article.get("EVENT_DESCRIPTION") or "",
        "pub_time": article.get("pub_time") or article.get("PUB_TIME") or article.get("time") or article.get("TIME") or article.get("archived_time") or appendix.get("archived_time") or "",
        "informant": article.get("informant") or article.get("INFORMANT") or article.get("url") or article.get("URL") or "",
        "raw": article,
    }


class LocalJsonlArticleLookup:
    """Lookup articles from local JSONL mirror files.

    Each line can be either a raw article object or an API-style object with a
    `data` field. This is useful for offline review and batch testing.
    """

    def __init__(self, path: str | Path = "ColumnMVP/article_store/articles.jsonl"):
        self.path = Path(path)

    def get(self, *, article_uuid: str = "", source_url: str = "") -> Optional[Dict[str, Any]]:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    article = normalize_article(json.loads(line))
                except Exception:
                    continue
                if article_uuid and article.get("UUID") == article_uuid:
                    return article
                if source_url and article.get("informant") == source_url:
                    return article
        return None

    def append(self, article: Dict[str, Any]) -> Dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        normalized = normalize_article(article)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
        return normalized


class RemoteIntelligenceHubArticleLookup:
    """Lookup articles from an IntelligenceHub HTTP endpoint.

    Uses the existing endpoint:

        GET /api/intelligence/<uuid>

    Configure with:

    - `INTELLIGENCE_HUB_BASE_URL`, e.g. `http://127.0.0.1:8080`
    """

    def __init__(self, base_url: Optional[str] = None, timeout_s: int = 15):
        self.base_url = (base_url or os.getenv("INTELLIGENCE_HUB_BASE_URL", "")).rstrip("/")
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def get(self, *, article_uuid: str = "", source_url: str = "") -> Optional[Dict[str, Any]]:
        if not self.enabled or not article_uuid:
            return None
        url = f"{self.base_url}/api/intelligence/{quote(article_uuid)}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "OPCColumnMVP/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise RuntimeError(f"IntelligenceHub HTTP error {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"IntelligenceHub URL error: {exc}") from exc
        return normalize_article(payload)


class ArticleLookupService:
    """Resolve article payloads for editorial generation."""

    def __init__(
        self,
        *,
        local_lookup: Optional[LocalJsonlArticleLookup] = None,
        remote_lookup: Optional[RemoteIntelligenceHubArticleLookup] = None,
    ):
        self.local_lookup = local_lookup or LocalJsonlArticleLookup()
        self.remote_lookup = remote_lookup or RemoteIntelligenceHubArticleLookup()

    def resolve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        inline_article = payload.get("article") if isinstance(payload.get("article"), dict) else None
        if inline_article:
            return normalize_article(inline_article)

        article_uuid = str(payload.get("article_uuid") or payload.get("uuid") or "").strip()
        source_url = str(payload.get("source_url") or payload.get("url") or "").strip()

        article = self.local_lookup.get(article_uuid=article_uuid, source_url=source_url)
        if article:
            return article

        article = self.remote_lookup.get(article_uuid=article_uuid, source_url=source_url)
        if article:
            return article

        raise FileNotFoundError("article not found")

    def import_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        return self.local_lookup.append(article)

    def build_generation_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        article = self.resolve(payload)
        generation_payload = dict(payload)
        generation_payload["article"] = article
        generation_payload.setdefault("article_uuid", article.get("UUID", ""))
        generation_payload.setdefault("title", article.get("title", ""))
        generation_payload.setdefault("source_url", article.get("informant", ""))
        generation_payload.setdefault("content", article.get("content", ""))
        return generation_payload
