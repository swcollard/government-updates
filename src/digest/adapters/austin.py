"""Adapter for the Austin Socrata SODA API council-agenda dataset.

VERIFY DATASET_ID and DATE_COLUMN against the live API before relying on
this adapter. Both are recorded during the build-time verification step.

Verified 2026-05-29: dataset ``3c89-i35a`` ("City of Austin Council Voting
Record") is the current, queryable Austin council dataset. The originally
specified ``g9iv-xdsg`` and ``2pje-cg27`` candidates both return HTTP 404
from the Socrata resource endpoint. ``3c89-i35a`` exposes one row per voter
per agenda item; downstream dedup in the normalizer collapses duplicates.
"""
from __future__ import annotations

import hashlib
from datetime import date as Date
from typing import Any

import requests

from digest.models import CivicItem, Level


# Verified live against https://data.austintexas.gov on 2026-05-29.
DATASET_ID = "3c89-i35a"
# Verified date column name for dataset 3c89-i35a.
DATE_COLUMN = "meeting_date"
SOURCE = "Austin Council"


def fetch_austin_items(start: Date, end: Date) -> list[CivicItem]:
    url = f"https://data.austintexas.gov/resource/{DATASET_ID}.json"
    where = f"{DATE_COLUMN} between '{start.isoformat()}' and '{end.isoformat()}'"
    params = {
        "$where": where,
        "$limit": 1000,
        "$order": f"{DATE_COLUMN} DESC",
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return [_to_civicitem(row) for row in response.json()]


def _to_civicitem(row: dict[str, Any]) -> CivicItem:
    # Field names below are best-effort defaults that cover the verified
    # 3c89-i35a schema first, then fall back to other plausible Socrata
    # agenda-dataset shapes so the adapter remains resilient.
    title = (
        row.get("item_description")
        or row.get("description")
        or row.get("title")
        or "(no title)"
    )
    item_no = (
        row.get("meeting_item_number")
        or row.get("item_no")
        or row.get("agenda_item_number")
        or ""
    )
    meeting_date = row.get(DATE_COLUMN) or row.get("date")
    try:
        parsed_date = Date.fromisoformat(meeting_date[:10]) if meeting_date else Date.today()
    except (ValueError, TypeError):
        parsed_date = Date.today()
    raw_id = f"{item_no}-{meeting_date}-{title}"
    short_id = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:12]
    sponsor = (
        row.get("sponsors")
        or row.get("sponsor")
        or row.get("meeting_type")
    )
    url = (
        row.get("backup_url")
        or row.get("url")
        or f"https://data.austintexas.gov/resource/{DATASET_ID}.json"
    )
    return CivicItem(
        id=f"austin-{short_id}",
        level=Level.LOCAL,
        source=SOURCE,
        agency=sponsor,
        type="Agenda Item",
        title=str(title)[:300],
        abstract=None,
        full_text_url=url,
        date=parsed_date,
        raw=row,
    )
