from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class SourceSearchCandidate:
    """A candidate URL discovered before it is accepted into a column."""

    title: str
    url: str
    snippet: str = ""
    provider: str = "manual"
    query: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceSearchProvider(Protocol):
    name: str

    def search(self, query: str, *, limit: int = 10) -> List[SourceSearchCandidate]:
        ...


class ManualSourceSearchProvider:
    """Provider that converts explicitly supplied URLs into candidates.

    This is useful for offline/local deployments and keeps the discovery pipeline
    testable without a paid search API.
    """

    name = "manual"

    def __init__(self, urls: Optional[Iterable[str]] = None):
        self.urls = [url.strip() for url in (urls or []) if url and url.strip()]

    def search(self, query: str, *, limit: int = 10) -> List[SourceSearchCandidate]:
        candidates: List[SourceSearchCandidate] = []
        for url in self.urls[:limit]:
            candidates.append(SourceSearchCandidate(
                title=url,
                url=url,
                snippet="Manual seed URL",
                provider=self.name,
                query=query,
                score=0.5,
            ))
        return candidates


class BingWebSearchProvider:
    """Minimal Bing Web Search provider using urllib only.

    Configure with environment variables:

    - `BING_SEARCH_API_KEY`
    - `BING_SEARCH_ENDPOINT` optional, defaults to Bing v7 endpoint
    - `BING_SEARCH_MARKET` optional, defaults to `zh-CN`
    """

    name = "bing"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        market: Optional[str] = None,
        timeout_s: int = 10,
    ):
        self.api_key = api_key or os.getenv("BING_SEARCH_API_KEY", "")
        self.endpoint = endpoint or os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
        self.market = market or os.getenv("BING_SEARCH_MARKET", "zh-CN")
        self.timeout_s = timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, *, limit: int = 10) -> List[SourceSearchCandidate]:
        if not self.enabled:
            return []

        params = urlencode({
            "q": query,
            "mkt": self.market,
            "count": min(max(limit, 1), 50),
            "responseFilter": "Webpages",
            "textDecorations": "false",
            "textFormat": "Raw",
        })
        url = f"{self.endpoint}?{params}"
        request = Request(url, headers={
            "Ocp-Apim-Subscription-Key": self.api_key,
            "User-Agent": "OPCColumnMVP/0.1",
        })
        with urlopen(request, timeout=self.timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))

        values = payload.get("webPages", {}).get("value", [])
        candidates: List[SourceSearchCandidate] = []
        for item in values[:limit]:
            target_url = item.get("url", "")
            if not target_url:
                continue
            candidates.append(SourceSearchCandidate(
                title=item.get("name", target_url),
                url=target_url,
                snippet=item.get("snippet", ""),
                provider=self.name,
                query=query,
                score=0.7,
                metadata={
                    "display_url": item.get("displayUrl", ""),
                    "date_last_crawled": item.get("dateLastCrawled", ""),
                },
            ))
        return candidates


class NullSourceSearchProvider:
    """Provider used when no external search provider is configured."""

    name = "null"

    def search(self, query: str, *, limit: int = 10) -> List[SourceSearchCandidate]:
        return []


def get_source_search_provider(name: str = "auto", *, seed_urls: Optional[Iterable[str]] = None) -> SourceSearchProvider:
    normalized = (name or "auto").strip().lower()

    if normalized == "manual":
        return ManualSourceSearchProvider(seed_urls)
    if normalized == "bing":
        return BingWebSearchProvider()
    if normalized == "null":
        return NullSourceSearchProvider()

    if normalized == "auto":
        bing = BingWebSearchProvider()
        if bing.enabled:
            return bing
        if seed_urls:
            return ManualSourceSearchProvider(seed_urls)
        return NullSourceSearchProvider()

    raise ValueError(f"Unsupported source search provider: {name}")
