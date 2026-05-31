"""Order-preserving dedup of CivicItems by id."""
from __future__ import annotations

from digest.models import CivicItem


def dedupe(items: list[CivicItem]) -> list[CivicItem]:
    seen: set[str] = set()
    result: list[CivicItem] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        result.append(item)
    return result
