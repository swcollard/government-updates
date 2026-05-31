"""Tests for the Austin Socrata adapter."""
import json
from datetime import date

import responses

from digest.adapters.austin import DATASET_ID, fetch_austin_items
from digest.models import Level


BASE = f"https://data.austintexas.gov/resource/{DATASET_ID}.json"


@responses.activate
def test_fetch_returns_civicitems_with_local_level(fixtures_dir):
    payload = json.loads((fixtures_dir / "austin_socrata.json").read_text())
    responses.add(responses.GET, BASE, json=payload, status=200)

    items = fetch_austin_items(date(2026, 5, 22), date(2026, 5, 28))

    assert items, "fixture should yield at least one item"
    assert all(i.level is Level.LOCAL for i in items)
    assert all(i.source == "Austin Council" for i in items)
    assert all(i.id.startswith("austin-") for i in items)


@responses.activate
def test_fetch_passes_date_window_to_where_clause():
    responses.add(responses.GET, BASE, json=[], status=200)

    fetch_austin_items(date(2026, 5, 22), date(2026, 5, 28))

    request_url = responses.calls[0].request.url
    assert "2026-05-22" in request_url
    assert "2026-05-28" in request_url
