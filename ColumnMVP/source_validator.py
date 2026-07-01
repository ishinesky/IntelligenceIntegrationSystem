from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .models import SourceConfig, ValidationResult


class _TitleAndLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.feed_links = []
        self.sitemap_links = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "link":
            rel = attrs_dict.get("rel", "")
            href = attrs_dict.get("href", "")
            link_type = attrs_dict.get("type", "")
            if "alternate" in rel and any(x in link_type for x in ["rss", "atom", "xml"]):
                self.feed_links.append(href)
        if tag.lower() == "a":
            href = attrs_dict.get("href", "")
            if "sitemap" in href.lower():
                self.sitemap_links.append(href)

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data.strip())

    @property
    def title(self) -> Optional[str]:
        title = " ".join(part for part in self.title_parts if part).strip()
        return title or None


def _fetch_text(url: str, timeout_s: int = 10) -> tuple[int, str, str]:
    request = Request(url, headers={"User-Agent": "OPCColumnMVP/0.1 (+https://github.com/ishinesky/IntelligenceIntegrationSystem)"})
    with urlopen(request, timeout=timeout_s) as response:
        raw = response.read(512_000)
        charset = response.headers.get_content_charset() or "utf-8"
        return response.status, response.geturl(), raw.decode(charset, errors="replace")


def _looks_like_feed(text: str, url: str) -> bool:
    lower = text[:500].lower()
    return "<rss" in lower or "<feed" in lower or url.lower().endswith((".xml", "/rss", "/feed"))


def validate_source(source: SourceConfig, timeout_s: int = 10) -> ValidationResult:
    notes = []
    try:
        status_code, final_url, text = _fetch_text(source.url, timeout_s=timeout_s)
    except HTTPError as exc:
        return ValidationResult(url=source.url, ok=False, status_code=exc.code, notes=[f"HTTP error: {exc}"])
    except URLError as exc:
        return ValidationResult(url=source.url, ok=False, notes=[f"URL error: {exc}"])
    except Exception as exc:
        return ValidationResult(url=source.url, ok=False, notes=[f"Fetch error: {exc}"])

    parser = _TitleAndLinkParser()
    try:
        parser.feed(text)
    except Exception as exc:
        notes.append(f"HTML parse warning: {exc}")

    has_rss = _looks_like_feed(text, final_url) or bool(parser.feed_links)
    has_sitemap = bool(parser.sitemap_links) or "sitemap" in text[:10_000].lower()
    if has_rss:
        notes.append("RSS/Atom hint found")
    if has_sitemap:
        notes.append("Sitemap hint found")
    if not parser.title and not has_rss:
        notes.append("No HTML title found; manual review recommended")

    ok = 200 <= status_code < 400
    return ValidationResult(
        url=source.url,
        ok=ok,
        status_code=status_code,
        final_url=final_url,
        title=parser.title,
        has_rss_hint=has_rss,
        has_sitemap_hint=has_sitemap,
        robots_allowed_hint=None,
        notes=notes,
    )


def validate_and_update(source: SourceConfig, timeout_s: int = 10) -> SourceConfig:
    result = validate_source(source, timeout_s=timeout_s)
    source.url = result.final_url or source.url
    source.validation_status = "passed" if result.ok else "manual_review"
    source.validation_notes = result.notes
    if result.title and source.name == urlparse(source.url).netloc:
        source.name = result.title
    if result.has_rss_hint:
        source.crawl_method = "rss"
    return source
