"""Tests for the Austin Socrata adapter."""
import json
from datetime import date, timedelta

import pytest
import responses

from digest.adapters.austin import DATASET_ID, STALE_AFTER_DAYS, fetch_austin_items
from digest.models import Level


BASE = f"https://data.austintexas.gov/resource/{DATASET_ID}.json"


@responses.activate
def test_fetch_returns_civicitems_with_local_level(fixtures_dir):
    payload = json.loads((fixtures_dir / "austin_socrata.json").read_text())
    responses.add(responses.GET, BASE, json=payload, status=200)

    items = fetch_austin_items(date(2026, 8, 25), date(2026, 8, 28))

    assert items, "fixture should yield at least one item"
    assert all(i.level is Level.LOCAL for i in items)
    assert all(i.source == "Austin Council" for i in items)
    assert all(i.id.startswith("austin-") for i in items)
    assert all(str(i.full_text_url).startswith("https://www.austintexas.gov/") for i in items)


@responses.activate
def test_fetch_passes_date_window_to_where_clause():
    # First call: the windowed query, empty. Second call: the freshness
    # probe fetch_austin_items makes when the windowed query is empty --
    # give it a recent-enough row so it doesn't raise for this test.
    responses.add(responses.GET, BASE, json=[], status=200)
    responses.add(
        responses.GET, BASE,
        json=[{"agenda_date": "2026-05-27T00:00:00.000"}], status=200,
    )

    fetch_austin_items(date(2026, 5, 22), date(2026, 5, 28))

    request_url = responses.calls[0].request.url
    assert "2026-05-22" in request_url
    assert "2026-05-28" in request_url


@responses.activate
def test_fetch_excludes_the_permanent_placeholder_test_row():
    """sich-49ay carries a permanent placeholder row (item_number == "test",
    agenda_date far in the future). Both the windowed query and the
    freshness probe must exclude it -- left in, it would always sort first
    in the freshness probe and permanently mask a genuinely dead dataset."""
    responses.add(responses.GET, BASE, json=[], status=200)
    responses.add(
        responses.GET, BASE,
        json=[{"agenda_date": "2026-05-27T00:00:00.000"}], status=200,
    )

    fetch_austin_items(date(2026, 5, 22), date(2026, 5, 28))

    for call in responses.calls:
        assert "item_number" in call.request.url
        assert "test" in call.request.url  # part of the exclusion clause


@responses.activate
def test_fetch_returns_empty_list_when_window_is_quiet_but_dataset_is_fresh():
    """A week with no items is normal and must not raise, as long as the
    dataset has been updated recently relative to the window."""
    responses.add(responses.GET, BASE, json=[], status=200)
    responses.add(
        responses.GET, BASE,
        json=[{"agenda_date": "2026-06-10T00:00:00.000"}], status=200,
    )

    items = fetch_austin_items(date(2026, 6, 8), date(2026, 6, 15))

    assert items == []


@responses.activate
def test_fetch_raises_when_dataset_has_gone_stale():
    """This is the bug found in production: the previously configured
    dataset stopped receiving new rows, and every windowed query since had
    returned [] while the digest reported "Austin Council: ok". A stale
    dataset must now surface as a loud failure instead of a silent empty
    list."""
    responses.add(responses.GET, BASE, json=[], status=200)
    responses.add(
        responses.GET, BASE,
        json=[{"agenda_date": "2026-05-28T00:00:00.000"}], status=200,
    )

    end = date(2026, 5, 28) + timedelta(days=STALE_AFTER_DAYS + 1)
    with pytest.raises(RuntimeError, match="has not been updated since"):
        fetch_austin_items(end - timedelta(days=7), end)


@responses.activate
def test_fetch_raises_when_dataset_is_completely_empty():
    responses.add(responses.GET, BASE, json=[], status=200)
    responses.add(responses.GET, BASE, json=[], status=200)

    with pytest.raises(RuntimeError, match="no rows at all"):
        fetch_austin_items(date(2026, 6, 8), date(2026, 6, 15))
