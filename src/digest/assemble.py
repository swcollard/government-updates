"""Render the digest as markdown."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date

from digest.models import BriefedItem, Level, TriagedItem


@dataclass
class SourceStatus:
    name: str
    ok: bool
    error: str | None = None


@dataclass
class DigestInput:
    start: Date
    end: Date
    briefed: list[BriefedItem]
    borderline: list[TriagedItem]
    sources: list[SourceStatus]


_LEVEL_ORDER: list[Level] = [Level.FEDERAL, Level.STATE, Level.LOCAL]
_LEVEL_LABEL = {Level.FEDERAL: "Federal", Level.STATE: "Texas", Level.LOCAL: "Austin"}


def assemble_digest(d: DigestInput) -> str:
    parts: list[str] = []
    parts.append(_header(d))
    parts.append(_main_section(d.briefed))
    parts.append(_borderline_section(d.borderline))
    parts.append(_footer(d.sources))
    return "\n\n".join(p for p in parts if p)


def _header(d: DigestInput) -> str:
    counts = {lvl: 0 for lvl in _LEVEL_ORDER}
    for b in d.briefed:
        counts[b.triaged.item.level] += 1
    for t in d.borderline:
        counts[t.item.level] += 1
    line = " \u00b7 ".join(f"{_LEVEL_LABEL[l]}: {counts[l]}" for l in _LEVEL_ORDER)
    return f"# Weekly Civic Digest\n\n**{d.start.isoformat()} \u2192 {d.end.isoformat()}**\n\n{line}"


def _main_section(briefed: list[BriefedItem]) -> str:
    if not briefed:
        return "_No relevant items this week._"
    sections: list[str] = []
    for level in _LEVEL_ORDER:
        in_level = [b for b in briefed if b.triaged.item.level is level]
        if not in_level:
            continue
        rows = [f"## {_LEVEL_LABEL[level]}"]
        for b in in_level:
            item = b.triaged.item
            rows.append(
                f"### [{item.title}]({item.full_text_url})\n"
                f"_{item.source} \u00b7 {item.type} \u00b7 {item.date.isoformat()}_\n\n"
                f"**What it is.** {b.what_it_is}\n\n"
                f"**Why it matters to you.** {b.why_it_matters}\n\n"
                f"**What you could do.** {b.what_you_could_do}"
            )
        sections.append("\n\n".join(rows))
    return "\n\n".join(sections)


def _borderline_section(borderline: list[TriagedItem]) -> str:
    if not borderline:
        return ""
    lines = ["## Maybe worth a look"]
    for t in borderline:
        item = t.item
        lines.append(f"- [{item.title}]({item.full_text_url}) \u2014 {t.reason}")
    return "\n".join(lines)


def _footer(sources: list[SourceStatus]) -> str:
    if not sources:
        return ""
    lines = ["---", "**Sources checked:**"]
    for s in sources:
        if s.ok:
            lines.append(f"- {s.name}: ok")
        else:
            lines.append(f"- {s.name}: FAILED ({s.error or 'unknown'})")
    return "\n".join(lines)
