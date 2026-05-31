"""Adapter for the Texas Register weekly RSS + per-issue TOC.

v1 scope: title + link extraction from the issue TOC HTML. PDF deep-parsing is
deferred (see plan: "Deliberately out of scope for v1").
"""
from __future__ import annotations

import hashlib
import re
from datetime import date as Date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

import feedparser
import requests

from digest.models import CivicItem, Level


FEED_URL = "https://www.sos.state.tx.us/texreg/texreg.xml"
SOURCE = "Texas Register"


def fetch_texas_items(start: Date, end: Date) -> list[CivicItem]:
    """Fetch all items from Texas Register issues published in [start, end]."""
    feed = feedparser.parse(_get(FEED_URL))
    items: list[CivicItem] = []
    for entry in feed.entries:
        pub = _entry_date(entry)
        if pub is None or not (start <= pub <= end):
            continue
        issue_url = entry.get("link")
        if not issue_url:
            continue
        issue_html = _get(issue_url).decode("utf-8", errors="replace")
        for title, link in _extract_toc(issue_html, base_url=issue_url):
            items.append(_to_civicitem(title=title, link=link, pub=pub))
    return items


def _get(url: str) -> bytes:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def _entry_date(entry) -> Date | None:
    # Prefer feedparser's already-parsed struct_time if available.
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is not None:
        try:
            return Date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except (ValueError, AttributeError):
            pass
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %Z").date()
    except ValueError:
        try:
            return datetime.strptime(raw[:16], "%a, %d %b %Y").date()
        except ValueError:
            return None


class _TocExtractor(HTMLParser):
    """Pull (text, href) pairs out of <a href="..."> tags."""
    def __init__(self) -> None:
        super().__init__()
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._current_href = dict(attrs).get("href")
            self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current_href is not None:
            text = re.sub(r"\s+", " ", "".join(self._current_text)).strip()
            if text:
                self.results.append((text, self._current_href))
            self._current_href = None
            self._current_text = []


def _extract_toc(html: str, *, base_url: str) -> list[tuple[str, str]]:
    parser = _TocExtractor()
    parser.feed(html)
    out: list[tuple[str, str]] = []
    for text, href in parser.results:
        if not href:
            continue
        if href.startswith("#"):
            continue
        # Absolutize first, then filter to Texas-Register-content links.
        absolute = _absolutize(href, base_url)
        if "texreg" not in absolute:
            continue
        out.append((text, absolute))
    return out


def _absolutize(href: str, base_url: str) -> str:
    return urljoin(base_url, href)


def _to_civicitem(*, title: str, link: str, pub: Date) -> CivicItem:
    digest = hashlib.sha1(link.encode("utf-8")).hexdigest()[:12]
    return CivicItem(
        id=f"tx-{digest}",
        level=Level.STATE,
        source=SOURCE,
        agency=None,
        type="Texas Register Item",
        title=title,
        abstract=None,
        full_text_url=link,
        date=pub,
    )
