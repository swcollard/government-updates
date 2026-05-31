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
