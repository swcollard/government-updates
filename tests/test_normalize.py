"""Tests for the normalizer (dedup-by-id pass)."""
from datetime import date

from digest.models import CivicItem, Level
from digest.normalize import dedupe


def _item(id_: str) -> CivicItem:
    return CivicItem(
        id=id_,
        level=Level.FEDERAL,
        source="Federal Register",
        type="Notice",
        title=f"Title {id_}",
        full_text_url="https://example.gov/x",
        date=date(2026, 5, 22),
    )


def test_dedupe_keeps_first_occurrence_of_each_id():
    items = [_item("a"), _item("b"), _item("a"), _item("c")]
    result = dedupe(items)
    assert [i.id for i in result] == ["a", "b", "c"]


def test_dedupe_preserves_order():
    items = [_item("c"), _item("a"), _item("b")]
    result = dedupe(items)
    assert [i.id for i in result] == ["c", "a", "b"]


def test_dedupe_empty_returns_empty():
    assert dedupe([]) == []
