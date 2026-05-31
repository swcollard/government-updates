"""Tests for the markdown digest assembler."""
from datetime import date

from digest.assemble import DigestInput, SourceStatus, assemble_digest
from digest.models import BriefedItem, Bucket, CivicItem, Level, TriagedItem


def _civic(id_: str, level: Level, title: str) -> CivicItem:
    return CivicItem(
        id=id_,
        level=level,
        source={Level.FEDERAL: "Federal Register", Level.STATE: "Texas Register", Level.LOCAL: "Austin Council"}[level],
        type="Notice",
        title=title,
        full_text_url=f"https://example.gov/{id_}",
        date=date(2026, 5, 22),
    )


def _briefed(id_: str, level: Level, title: str) -> BriefedItem:
    triaged = TriagedItem(
        item=_civic(id_, level, title),
        score=90, bucket=Bucket.RELEVANT, reason="matches",
    )
    return BriefedItem(
        triaged=triaged,
        what_it_is="WHAT", why_it_matters="WHY", what_you_could_do="DO",
    )


def _borderline(id_: str, level: Level, title: str) -> TriagedItem:
    return TriagedItem(
        item=_civic(id_, level, title),
        score=50, bucket=Bucket.BORDERLINE, reason="tangential",
    )


def test_assemble_renders_header_with_date_range_and_counts():
    digest = assemble_digest(DigestInput(
        start=date(2026, 5, 22),
        end=date(2026, 5, 28),
        briefed=[_briefed("a", Level.FEDERAL, "Federal thing")],
        borderline=[],
        sources=[SourceStatus(name="Federal Register", ok=True)],
    ))
    assert "2026-05-22" in digest
    assert "2026-05-28" in digest
    assert "Federal: 1" in digest


def test_assemble_groups_by_level_in_main_section():
    digest = assemble_digest(DigestInput(
        start=date(2026, 5, 22),
        end=date(2026, 5, 28),
        briefed=[
            _briefed("f", Level.FEDERAL, "Fed thing"),
            _briefed("a", Level.LOCAL, "Austin thing"),
            _briefed("t", Level.STATE, "Texas thing"),
        ],
        borderline=[],
        sources=[],
    ))
    fed = digest.index("Fed thing")
    tex = digest.index("Texas thing")
    aus = digest.index("Austin thing")
    assert fed < tex < aus  # federal -> state -> local order


def test_assemble_includes_brief_fields_per_relevant_item():
    digest = assemble_digest(DigestInput(
        start=date(2026, 5, 22), end=date(2026, 5, 28),
        briefed=[_briefed("a", Level.FEDERAL, "T")],
        borderline=[], sources=[],
    ))
    assert "WHAT" in digest and "WHY" in digest and "DO" in digest


def test_assemble_borderline_section_is_compact():
    digest = assemble_digest(DigestInput(
        start=date(2026, 5, 22), end=date(2026, 5, 28),
        briefed=[],
        borderline=[_borderline("x", Level.STATE, "Maybe")],
        sources=[],
    ))
    assert "Maybe worth a look" in digest
    assert "Maybe" in digest
    assert "tangential" in digest


def test_assemble_footer_lists_sources_and_failures():
    digest = assemble_digest(DigestInput(
        start=date(2026, 5, 22), end=date(2026, 5, 28),
        briefed=[], borderline=[],
        sources=[
            SourceStatus(name="Federal Register", ok=True),
            SourceStatus(name="Texas Register", ok=False, error="HTTP 500"),
        ],
    ))
    assert "Federal Register" in digest
    assert "Texas Register" in digest
    assert "HTTP 500" in digest
