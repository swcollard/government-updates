"""Adapter for the Federal Register JSON API."""
from __future__ import annotations

from datetime import date as Date
from typing import Any

import requests

from digest.models import CivicItem, Level


API_URL = "https://www.federalregister.gov/api/v1/documents.json"
SOURCE = "Federal Register"


def fetch_federal_items(start: Date, end: Date) -> list[CivicItem]:
    """Fetch all Federal Register documents published in [start, end] inclusive."""
    items: list[CivicItem] = []
    query = (
        f"conditions[publication_date][gte]={start.isoformat()}"
        f"&conditions[publication_date][lte]={end.isoformat()}"
        f"&per_page=100"
    )
    url: str | None = API_URL
    params: str | None = query
    while url:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        for raw in payload.get("results", []):
            items.append(_to_civicitem(raw))
        url = payload.get("next_page_url")
        params = None
    return items


def _to_civicitem(raw: dict[str, Any]) -> CivicItem:
    agencies = raw.get("agencies") or []
    agency_name = agencies[0].get("name") if agencies else None
    return CivicItem(
        id=f"fr-{raw['document_number']}",
        level=Level.FEDERAL,
        source=SOURCE,
        agency=agency_name,
        type=raw.get("type") or "Document",
        title=raw["title"],
        abstract=raw.get("abstract"),
        full_text_url=raw["html_url"],
        date=Date.fromisoformat(raw["publication_date"]),
        raw=raw,
    )
