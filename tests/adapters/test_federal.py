"""Tests for the Federal Register adapter."""
import json
from datetime import date

import pytest
import responses

from digest.adapters.federal import fetch_federal_items
from digest.models import Level


BASE = "https://www.federalregister.gov/api/v1/documents.json"


@pytest.fixture
def page1(fixtures_dir):
    return json.loads((fixtures_dir / "federal_register_page1.json").read_text())


@pytest.fixture
def page2(fixtures_dir):
    return json.loads((fixtures_dir / "federal_register_page2.json").read_text())


@responses.activate
def test_fetch_single_page(page1):
    page1["total_pages"] = 1
    page1.pop("next_page_url", None)
    responses.add(responses.GET, BASE, json=page1, status=200)

    items = fetch_federal_items(date(2026, 5, 22), date(2026, 5, 28))

    assert len(items) == len(page1["results"])
    first = items[0]
    assert first.level is Level.FEDERAL
    assert first.source == "Federal Register"
    assert first.id == f"fr-{page1['results'][0]['document_number']}"
    assert str(first.full_text_url).startswith("https://")


@responses.activate
def test_fetch_paginates_via_next_page_url(page1, page2):
    page1["total_pages"] = 2
    page1["next_page_url"] = BASE + "?page=2"
    page2["total_pages"] = 2
    page2.pop("next_page_url", None)
    responses.add(responses.GET, BASE, json=page1, status=200)
    responses.add(responses.GET, BASE, json=page2, status=200)

    items = fetch_federal_items(date(2026, 5, 22), date(2026, 5, 28))

    assert len(items) == len(page1["results"]) + len(page2["results"])


@responses.activate
def test_fetch_uses_correct_date_params():
    empty = {"count": 0, "total_pages": 1, "results": []}
    responses.add(responses.GET, BASE, json=empty, status=200)

    fetch_federal_items(date(2026, 5, 22), date(2026, 5, 28))

    request = responses.calls[0].request
    assert "conditions[publication_date][gte]=2026-05-22" in request.url
    assert "conditions[publication_date][lte]=2026-05-28" in request.url


@responses.activate
def test_fetch_handles_missing_optional_fields():
    payload = {
        "count": 1,
        "total_pages": 1,
        "results": [
            {
                "title": "T",
                "type": "Notice",
                "document_number": "2026-99",
                "publication_date": "2026-05-22",
                "html_url": "https://example.gov/x",
                "agencies": [],
                # no abstract
            }
        ],
    }
    responses.add(responses.GET, BASE, json=payload, status=200)

    items = fetch_federal_items(date(2026, 5, 22), date(2026, 5, 28))

    assert items[0].abstract is None
    assert items[0].agency is None
