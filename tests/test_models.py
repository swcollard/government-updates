"""Tests for CivicItem and the bucketed triage/brief result models."""
from datetime import date

import pytest
from pydantic import ValidationError

from digest.models import (
    Bucket,
    BriefedItem,
    CivicItem,
    Level,
    TriagedItem,
)


def test_civicitem_minimum_fields():
    item = CivicItem(
        id="fr-2026-12345",
        level=Level.FEDERAL,
        source="Federal Register",
        type="Proposed Rule",
        title="Some rule",
        full_text_url="https://example.gov/x",
        date=date(2026, 5, 28),
    )
    assert item.agency is None
    assert item.abstract is None


def test_civicitem_rejects_bad_level():
    with pytest.raises(ValidationError):
        CivicItem(
            id="x",
            level="planetary",  # type: ignore[arg-type]
            source="s",
            type="t",
            title="t",
            full_text_url="https://example.gov/x",
            date=date(2026, 5, 28),
        )


def test_triaged_item_carries_score_and_reason():
    base = CivicItem(
        id="x",
        level=Level.LOCAL,
        source="Austin Council",
        type="Agenda Item",
        title="Zoning case",
        full_text_url="https://example.gov/x",
        date=date(2026, 5, 28),
    )
    t = TriagedItem(item=base, score=87, bucket=Bucket.RELEVANT, reason="zoning in district")
    assert t.bucket is Bucket.RELEVANT
    assert t.item.id == "x"


def test_briefed_item_extends_triaged_with_brief_fields():
    base = CivicItem(
        id="x",
        level=Level.STATE,
        source="Texas Register",
        type="Proposed Rule",
        title="Water rule",
        full_text_url="https://example.gov/x",
        date=date(2026, 5, 28),
    )
    triaged = TriagedItem(item=base, score=90, bucket=Bucket.RELEVANT, reason="water")
    briefed = BriefedItem(
        triaged=triaged,
        what_it_is="A new water rule.",
        why_it_matters="Affects rates.",
        what_you_could_do="Comment by June 30.",
    )
    assert briefed.triaged.item.title == "Water rule"
