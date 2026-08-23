"""Adapter for the Texas Register weekly RSS + per-issue TOC.

v1 scope: title + link extraction from the issue TOC HTML. PDF deep-parsing is
deferred (see plan: "Deliberately out of scope for v1").

Re-verified 2026-08-23, after 10 straight weekly runs each reported "Texas
Register: ok" with 0 items: the live feed at FEED_URL is up and does carry
real content, but it is shaped differently than this file assumed. It only
ever lists the CURRENT issue, three ways -- an HTML table of contents, a PDF
viewer, and a link to the historical archive site -- and none of its <item>
elements carry <pubDate> or <updated>. ``_entry_date`` required one of those
to exist, so every entry was skipped and ``fetch_texas_items`` silently
returned an empty list every single week, regardless of whether that week's
issue was actually in range. The date is present, just as plain text inside
each item's <description> (e.g. "...for August 21, 2026..."); ``_entry_date``
now falls back to parsing it from there. ``_is_html_issue_entry`` also skips
the PDF-viewer and archive-site entries, which aren't TOC pages and would
otherwise be scraped as if they were.

Known limitation this fix does not solve: because the feed only ever exposes
the current issue, a week where this pipeline doesn't run (or runs before
that week's issue posts) has no way to be backfilled later -- there is no
historical index in this feed. Out of scope for this pass; flagging for a
follow-up if backfill turns out to matter.
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

# Matches the issue date embedded in each entry's <description>, e.g.
# "Texas Register issue for August 21, 2026 in html format".
_DESCRIPTION_DATE_RE = re.compile(r"for ([A-Z][a-z]+ \d{1,2}, \d{4})")


def fetch_texas_items(start: Date, end: Date) -> list[CivicItem]:
    """Fetch all items from Texas Register issues published in [start, end]."""
    feed = feedparser.parse(_get(FEED_URL))
    items: list[CivicItem] = []
    for entry in feed.entries:
        if not _is_html_issue_entry(entry):
            continue
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


def _is_html_issue_entry(entry) -> bool:
    """The live feed lists the same issue three ways: an HTML table of
    contents, a PDF viewer, and a link to the historical archive site. Only
    the first is a page this adapter can scrape for links -- fetching the
    other two as if they were a TOC would either error or pull in unrelated
    navigation links."""
    title = (entry.get("title") or "").strip().lower()
    if title == "html format":
        return True
    link = entry.get("link") or ""
    return "/texreg/archive/" in link


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
    if raw:
        try:
            return datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %Z").date()
        except ValueError:
            try:
                return datetime.strptime(raw[:16], "%a, %d %b %Y").date()
            except ValueError:
                pass
    # The live feed carries no <pubDate>/<updated> at all -- fall back to the
    # date spelled out in the entry's description text.
    description = entry.get("description") or entry.get("summary") or ""
    match = _DESCRIPTION_DATE_RE.search(description)
    if match:
        try:
            return datetime.strptime(match.group(1), "%B %d, %Y").date()
        except ValueError:
            return None
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
