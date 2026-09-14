"""Tests for the Texas Register adapter."""
from datetime import date

import responses

from digest.adapters.texas import fetch_texas_items
from digest.models import Level


FEED_URL = "https://www.sos.state.tx.us/texreg/texreg.xml"
ISSUE_URL = "https://www.sos.state.tx.us/texreg/archive/May262026/index.shtml"


# Minimal hand-authored RSS pinning one issue inside the test window.
_FEED_XML = f"""<?xml version='1.0'?>
<rss version='2.0'><channel>
  <item>
    <title>May 26, 2026 issue</title>
    <link>{ISSUE_URL}</link>
    <pubDate>Tue, 26 May 2026 00:00:00 GMT</pubDate>
  </item>
</channel></rss>""".encode()


# Minimal TOC HTML with two real-looking items.
_ISSUE_HTML = b"""<html><body>
  <h2>Proposed Rules</h2>
  <ul>
    <li><a href="proprule/1234.html">Texas Water Development Board - Pricing Rule</a></li>
    <li><a href="proprule/1235.html">TCEQ - Air Quality Standards</a></li>
  </ul>
</body></html>"""


@responses.activate
def test_fetch_inside_window_yields_items_from_toc():
    responses.add(responses.GET, FEED_URL, body=_FEED_XML, status=200,
                  content_type="application/rss+xml")
    responses.add(responses.GET, ISSUE_URL, body=_ISSUE_HTML, status=200,
                  content_type="text/html")

    items = fetch_texas_items(date(2026, 5, 22), date(2026, 5, 28))

    assert len(items) == 2
    assert all(i.level is Level.STATE for i in items)
    assert all(i.source == "Texas Register" for i in items)
    assert all(i.id.startswith("tx-") for i in items)
    titles = {i.title for i in items}
    assert "Texas Water Development Board - Pricing Rule" in titles


@responses.activate
def test_fetch_skips_issues_outside_window():
    feed_xml = b"""<?xml version='1.0'?><rss version='2.0'><channel>
      <item>
        <title>Old issue</title>
        <link>https://www.sos.state.tx.us/texreg/archive/old.shtml</link>
        <pubDate>Fri, 03 Jan 2020 00:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""
    responses.add(responses.GET, FEED_URL, body=feed_xml, status=200,
                  content_type="application/rss+xml")

    items = fetch_texas_items(date(2026, 5, 22), date(2026, 5, 28))

    assert items == []


# This mirrors the shape of the live feed as of 2026-08-23: no <pubDate> or
# <updated> on any item, the issue date only spelled out in <description>,
# and the same issue listed three ways (HTML TOC, PDF viewer, historical
# archive link). This is the exact shape that produced 0 items every week
# in production even though the feed and the issue page were both live.
_LIVE_SHAPE_FEED_XML = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
<title>Current Issue of the Texas Register</title>
<link>http://www.sos.state.tx.us/texreg/index.shtml</link>
<description>This feed contains information published in the weekly Texas Register for May 26, 2026 in html and pdf format.</description>
<item>
<title>HTML format</title>
<link>{ISSUE_URL}</link>
<description>Texas Register issue for May 26, 2026 in html format</description>
</item>
<item>
<title>PDF format</title>
<link>https://www.sos.state.tx.us/texreg/pdf/backview/0526/index.shtml</link>
<description>Texas Register issue for May 26, 2026 in pdf format</description>
</item>
<item>
<title>All Texas Register issues available electronically</title>
<link>http://texashistory.unt.edu/explore/collections/TR/</link>
<description>All Texas Register issues beginning with Volume 1, Number 1 are available through The Portal to Texas History.</description>
</item>
</channel>
</rss>""".encode()


@responses.activate
def test_fetch_falls_back_to_description_date_when_no_pubdate():
    """The bug found in production: with no <pubDate>/<updated> anywhere in
    the feed, every entry used to be skipped and fetch_texas_items always
    returned []. The date is recoverable from the description text."""
    responses.add(responses.GET, FEED_URL, body=_LIVE_SHAPE_FEED_XML, status=200,
                  content_type="application/rss+xml")
    responses.add(responses.GET, ISSUE_URL, body=_ISSUE_HTML, status=200,
                  content_type="text/html")

    items = fetch_texas_items(date(2026, 5, 22), date(2026, 5, 28))

    assert len(items) == 2
    titles = {i.title for i in items}
    assert "Texas Water Development Board - Pricing Rule" in titles


@responses.activate
def test_fetch_ignores_pdf_and_archive_entries_in_live_feed_shape():
    """Only the HTML-format entry should ever be fetched as a TOC page. If
    the adapter regresses and tries the PDF-viewer or historical-archive
    link instead, this test fails with a connection error because no mock
    is registered for those URLs."""
    responses.add(responses.GET, FEED_URL, body=_LIVE_SHAPE_FEED_XML, status=200,
                  content_type="application/rss+xml")
    responses.add(responses.GET, ISSUE_URL, body=_ISSUE_HTML, status=200,
                  content_type="text/html")

    items = fetch_texas_items(date(2026, 5, 22), date(2026, 5, 28))

    assert len(items) == 2
    fetched_urls = {call.request.url for call in responses.calls}
    assert ISSUE_URL in fetched_urls
    assert not any("pdf/backview" in u for u in fetched_urls)
    assert not any("texashistory" in u for u in fetched_urls)
