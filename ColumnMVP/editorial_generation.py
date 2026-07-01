from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .ai_editorial import OPC_EDITORIAL_PROMPT, build_editorial_review
from .editorial_review import EditorialReviewService


class OpenAICompatibleChatClient:
    """Minimal OpenAI-compatible chat client.

    This adapter is intentionally tiny and dependency-free. It only implements
    the `.chat(messages=..., temperature=..., max_tokens=...)` method expected by
    `ServiceComponent.IntelligenceAnalyzerProxy.analyze_with_ai`.

    Environment variables:

    - `OPENAI_COMPAT_API_KEY`
    - `OPENAI_COMPAT_BASE_URL`, default `https://api.openai.com/v1`
    - `OPENAI_COMPAT_MODEL`, default `gpt-4o-mini`
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: int = 60,
    ):
        self.api_key = api_key or os.getenv("OPENAI_COMPAT_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("OPENAI_COMPAT_MODEL", "gpt-4o-mini")
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def chat(self, *, messages, temperature: float = 0, max_tokens: int = 8192):
        if not self.enabled:
            raise RuntimeError("OPENAI_COMPAT_API_KEY is not configured")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "OPCColumnMVP/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(f"AI provider HTTP error {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"AI provider URL error: {exc}") from exc

        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def build_article_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize API/CLI payload into the article shape consumed by ai_editorial."""
    article = payload.get("article") if isinstance(payload.get("article"), dict) else {}
    return {
        "UUID": payload.get("article_uuid") or article.get("UUID") or article.get("uuid") or "",
        "title": payload.get("title") or article.get("title") or article.get("EVENT_TITLE") or "",
        "content": payload.get("content") or article.get("content") or article.get("BODY") or article.get("markdown_content") or "",
        "pub_time": payload.get("pub_time") or article.get("pub_time") or article.get("date") or "",
        "informant": payload.get("source_url") or article.get("informant") or article.get("url") or "",
        "metadata": article.get("metadata", {}) if isinstance(article.get("metadata"), dict) else {},
    }


class EditorialGenerationService:
    """Generate and optionally persist OPC editorial reviews."""

    def __init__(self, editorial_service: Optional[EditorialReviewService] = None):
        self.editorial_service = editorial_service or EditorialReviewService()

    def build_generation_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        article = build_article_payload(payload)
        return {
            "prompt": payload.get("prompt") or OPC_EDITORIAL_PROMPT,
            "article": article,
            "column_id": payload.get("column_id", ""),
            "status": payload.get("status", "reviewed"),
            "persist": bool(payload.get("persist", True)),
        }

    def generate(
        self,
        payload: Dict[str, Any],
        *,
        ai_client=None,
    ) -> Dict[str, Any]:
        generation_payload = self.build_generation_payload(payload)
        article = generation_payload["article"]
        if not article.get("content"):
            raise ValueError("article content is required")

        dry_run = bool(payload.get("dry_run", False))
        if dry_run:
            return {
                "dry_run": True,
                "generation_payload": generation_payload,
            }

        if ai_client is None:
            ai_client = OpenAICompatibleChatClient(
                api_key=payload.get("api_key") or None,
                base_url=payload.get("base_url") or None,
                model=payload.get("model") or None,
            )
        if not getattr(ai_client, "enabled", True):
            raise RuntimeError("No AI client configured. Set OPENAI_COMPAT_API_KEY or pass dry_run=true.")

        review = build_editorial_review(
            ai_client,
            article,
            prompt=generation_payload["prompt"],
        )

        review_payload = {
            "column_id": generation_payload.get("column_id", ""),
            "article_uuid": article.get("UUID", ""),
            "source_url": article.get("informant", ""),
            "title": article.get("title", ""),
            "status": generation_payload.get("status", "reviewed"),
            "review": review,
            "article": article,
            "metadata": {
                "generated_by": "EditorialGenerationService",
                "model": payload.get("model") or os.getenv("OPENAI_COMPAT_MODEL", ""),
            },
        }
        if not generation_payload.get("persist", True):
            return {
                "persisted": False,
                "review_payload": review_payload,
            }

        record = self.editorial_service.create_review(review_payload)
        return {
            "persisted": True,
            "review": record.to_dict(),
        }
