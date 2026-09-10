"""Adapter for the Austin Socrata SODA API council-agenda dataset.

VERIFY DATASET_ID and DATE_COLUMN against the live API before relying on
this adapter. Both are recorded during the build-time verification step.

Verified 2026-05-29: dataset ``3c89-i35a`` ("City of Austin Council Voting
Record") is the current, queryable Austin council dataset. The originally
specified ``g9iv-xdsg`` and ``2pje-cg27`` candidates both return HTTP 404
from the Socrata resource endpoint. ``3c89-i35a`` exposes one row per voter
per agenda item; downstream dedup in the normalizer collapses duplicates.

Re-verified 2026-08-23, after 10 straight weekly runs each reported "Austin
Council: ok" with 0 items: the query and schema are both still fine, but
``3c89-i35a`` itself has not received a new row since 2026-05-28 -- the
whole dataset is a single meeting's worth of votes, predating this
pipeline's very first run (2026-06-08). ``_check_freshness`` below turns a
dead dataset into a loud pipeline failure instead of a silent zero.

Replaced 2026-09-09: swapped in ``sich-49ay`` ("City of Austin Council
Agenda Items Updates, Feb 2024-Present"), confirmed live with rows through
2026-08-27 (vs. ``3c89-i35a``'s last row on 2026-05-28). Found via the
Socrata catalog API (``api.us.socrata.com/api/catalog/v1?domains=data.austintexas.gov``)
since the dataset's own "Last Updated" metadata field is not a reliable
freshness signal -- it read 2026-09-09 for the dead ``3c89-i35a`` dataset
too. This dataset tracks one row per agenda item (resolutions, ordinances,
budget riders) rather than one row per council-member vote, so item counts
will look different from before. It also contains a single permanent
placeholder/training row (``item_number == "test"``, ``agenda_date`` in
2050) that both queries below explicitly exclude -- left in unfiltered, it
would have permanently defeated the freshness check by always sorting first
as the "most recent" row.
"""
from __future__ import annotations

import hashlib
from datetime import date as Date, timedelta
from typing import Any

import requests

from digest.models import CivicItem, Level


# Verified live against https://data.austintexas.gov on 2026-09-09.
DATASET_ID = "sich-49ay"
# Verified date column name for dataset sich-49ay.
DATE_COLUMN = "agenda_date"
SOURCE = "Austin Council"

# The dataset carries one permanent placeholder row (item_number == "test",
# agenda_date far in the future) that must be excluded from every query --
# otherwise it would always sort first in the freshness probe and mask a
# genuinely dead dataset forever.
_EXCLUDE_TEST_ROW = "item_number != 'test'"

# If the windowed query comes back empty, double-check the dataset's most
# recent row before trusting that it was just a quiet week. Austin Council
# goes quiet around holidays and its summer recess, but not for more than a
# couple of weeks -- if the newest row on file is older than this relative
# to the window's end date, treat the dataset itself as stale and fail loudly
# rather than reporting "ok" with 0 items again.
STALE_AFTER_DAYS = 14


def fetch_austin_items(start: Date, end: Date) -> list[CivicItem]:
    url = f"https://data.austintexas.gov/resource/{DATASET_ID}.json"
    where = (
        f"{DATE_COLUMN} between '{start.isoformat()}' and '{end.isoformat()}'"
        f" AND {_EXCLUDE_TEST_ROW}"
    )
    params = {
        "$where": where,
        "$limit": 1000,
        "$order": f"{DATE_COLUMN} DESC",
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    rows = response.json()
    if not rows:
        _check_freshness(url=url, end=end)
    return [_to_civicitem(row) for row in rows]


def _check_freshness(*, url: str, end: Date) -> None:
    """Raise if the dataset's newest row is older than STALE_AFTER_DAYS.

    A quiet week with no votes in [start, end] is normal and should stay
    silent. A dataset that has stopped receiving new rows entirely is not,
    and previously looked identical from the digest's point of view --
    "Austin Council: ok" with 0 items, week after week. This tells the two
    apart with one cheap extra request, only when the primary query found
    nothing.
    """
    response = requests.get(
        url,
        params={
            "$where": _EXCLUDE_TEST_ROW,
            "$limit": 1,
            "$order": f"{DATE_COLUMN} DESC",
        },
        timeout=30,
    )
    response.raise_for_status()
    rows = response.json()
    if not rows:
        raise RuntimeError(
            f"Austin Socrata dataset {DATASET_ID} returned no rows at all -- "
            "it may have been removed or renamed. Check "
            "https://data.austintexas.gov for a replacement council dataset."
        )
    latest_raw = rows[0].get(DATE_COLUMN)
    try:
        latest = Date.fromisoformat(str(latest_raw)[:10])
    except (TypeError, ValueError):
        return  # unparseable -- don't block the digest over a format change
    staleness = end - latest
    if staleness > timedelta(days=STALE_AFTER_DAYS):
        raise RuntimeError(
            f"Austin Socrata dataset {DATASET_ID} has not been updated since "
            f"{latest.isoformat()} ({staleness.days} days before this "
            "digest's window ended). It looks abandoned, not just quiet -- "
            "verify the dataset is still current at "
            "https://data.austintexas.gov and swap DATASET_ID/DATE_COLUMN in "
            "this file if a replacement has taken its place."
        )


def _to_civicitem(row: dict[str, Any]) -> CivicItem:
    # Field names below are best-effort defaults that cover the verified
    # sich-49ay schema first, then fall back to other plausible Socrata
    # agenda-dataset shapes so the adapter remains resilient.
    title = (
        row.get("posting_language")
        or row.get("item_description")
        or row.get("description")
        or row.get("title")
        or "(no title)"
    )
    item_no = (
        row.get("item_number")
        or row.get("meeting_item_number")
        or row.get("item_no")
        or row.get("agenda_item_number")
        or ""
    )
    item_date = row.get(DATE_COLUMN) or row.get("date")
    try:
        parsed_date = Date.fromisoformat(item_date[:10]) if item_date else Date.today()
    except (ValueError, TypeError):
        parsed_date = Date.today()
    raw_id = row.get("request_number") or f"{item_no}-{item_date}-{title}"
    short_id = hashlib.sha1(str(raw_id).encode("utf-8")).hexdigest()[:12]
    sponsor = (
        row.get("sponsor")
        or row.get("sponsors")
        or row.get("meeting_type")
    )
    attachments = row.get("attachments")
    url = (
        (attachments.get("url") if isinstance(attachments, dict) else None)
        or row.get("backup_url")
        or row.get("url")
        or f"https://data.austintexas.gov/resource/{DATASET_ID}.json"
    )
    return CivicItem(
        id=f"austin-{short_id}",
        level=Level.LOCAL,
        source=SOURCE,
        agency=sponsor,
        type=row.get("request_type") or "Agenda Item",
        title=str(title)[:300],
        abstract=None,
        full_text_url=url,
        date=parsed_date,
        raw=row,
    )
