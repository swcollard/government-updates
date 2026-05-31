"""Batched Claude triage scoring CivicItems against the profile."""
from __future__ import annotations

import json
import re

from digest.claude_client import ClaudeClient
from digest.models import Bucket, CivicItem, TriagedItem


DEFAULT_BATCH_SIZE = 25
DEFAULT_RELEVANT_CUTOFF = 70
DEFAULT_BORDERLINE_CUTOFF = 40

SYSTEM_PROMPT = """You are a civic-affairs triage assistant.

You are given the reader's personal interest profile and a list of government
items (rules, notices, agenda items). For each item, return a relevance score
from 0 to 100 and a one-line reason.

Return ONLY a JSON array. Each element must have: id (string, exactly matching
the input id), score (integer 0-100), reason (short string).

Do not include any commentary. Do not wrap the array in any other object."""


def triage_items(
    items: list[CivicItem],
    *,
    profile: str,
    client: ClaudeClient,
    relevant_cutoff: int = DEFAULT_RELEVANT_CUTOFF,
    borderline_cutoff: int = DEFAULT_BORDERLINE_CUTOFF,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[TriagedItem]:
    results: list[TriagedItem] = []
    for batch_start in range(0, len(items), batch_size):
        batch = items[batch_start : batch_start + batch_size]
        scored = _score_one_batch(batch, profile=profile, client=client)
        by_id = {row["id"]: row for row in scored}
        for item in batch:
            row = by_id.get(item.id)
            if row is None:
                continue
            score = int(row["score"])
            results.append(
                TriagedItem(
                    item=item,
                    score=score,
                    bucket=_bucket(score, relevant_cutoff, borderline_cutoff),
                    reason=row.get("reason", ""),
                )
            )
    return results


def _bucket(score: int, relevant: int, borderline: int) -> Bucket:
    if score >= relevant:
        return Bucket.RELEVANT
    if score >= borderline:
        return Bucket.BORDERLINE
    return Bucket.DROP


def _score_one_batch(
    batch: list[CivicItem], *, profile: str, client: ClaudeClient
) -> list[dict]:
    user_prompt = _build_user_prompt(batch, profile=profile)
    text = client.complete(system=SYSTEM_PROMPT, user=user_prompt)
    return _parse_json_array(text)


def _build_user_prompt(batch: list[CivicItem], *, profile: str) -> str:
    payload = [
        {
            "id": item.id,
            "level": item.level.value,
            "source": item.source,
            "agency": item.agency,
            "type": item.type,
            "title": item.title,
            "abstract": item.abstract,
        }
        for item in batch
    ]
    return (
        f"## Reader profile\n\n{profile}\n\n"
        f"## Items to score (JSON)\n\n{json.dumps(payload, indent=2)}\n\n"
        "Return the JSON array now."
    )


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _parse_json_array(text: str) -> list[dict]:
    match = _JSON_ARRAY_RE.search(text)
    if not match:
        return []
    return json.loads(match.group(0))
