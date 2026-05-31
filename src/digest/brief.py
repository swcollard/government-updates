"""Rich per-item briefs for the `relevant` bucket only."""
from __future__ import annotations

import json
import re

from digest.claude_client import ClaudeClient
from digest.models import Bucket, BriefedItem, TriagedItem


SYSTEM_PROMPT = """You are a civic-affairs briefer.

Given the reader's profile and a single government item, write a brief with
exactly three plain-language fields:

  what_it_is        — describe the action in human terms, 1-3 sentences.
  why_it_matters    — connect explicitly to the reader's profile, 1-3 sentences.
  what_you_could_do — concrete next step: comment period, meeting to attend,
                      who to contact, or "nothing actionable, just be aware".

Return ONLY a JSON object with those three keys. No commentary, no fencing."""


def brief_items(
    triaged: list[TriagedItem],
    *,
    profile: str,
    client: ClaudeClient,
) -> list[BriefedItem]:
    out: list[BriefedItem] = []
    for t in triaged:
        if t.bucket is not Bucket.RELEVANT:
            continue
        text = client.complete(system=SYSTEM_PROMPT, user=_build_user_prompt(t, profile=profile))
        data = _parse_json_object(text)
        out.append(
            BriefedItem(
                triaged=t,
                what_it_is=data.get("what_it_is", ""),
                why_it_matters=data.get("why_it_matters", ""),
                what_you_could_do=data.get("what_you_could_do", ""),
            )
        )
    return out


def _build_user_prompt(t: TriagedItem, *, profile: str) -> str:
    item = t.item
    payload = {
        "level": item.level.value,
        "source": item.source,
        "agency": item.agency,
        "type": item.type,
        "title": item.title,
        "abstract": item.abstract,
        "url": str(item.full_text_url),
        "date": item.date.isoformat(),
        "triage_reason": t.reason,
    }
    return (
        f"## Reader profile\n\n{profile}\n\n"
        f"## Item\n\n{json.dumps(payload, indent=2)}\n\n"
        "Return the JSON object now."
    )


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_object(text: str) -> dict:
    match = _JSON_OBJECT_RE.search(text)
    if not match:
        return {}
    return json.loads(match.group(0))
