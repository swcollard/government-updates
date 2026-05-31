"""Tests for the per-item brief pass."""
import json
from datetime import date
from unittest.mock import MagicMock

from digest.brief import brief_items
from digest.claude_client import ClaudeClient
from digest.models import Bucket, CivicItem, Level, TriagedItem


def _triaged(id_: str, bucket: Bucket = Bucket.RELEVANT) -> TriagedItem:
    item = CivicItem(
        id=id_,
        level=Level.FEDERAL,
        source="Federal Register",
        agency="ED",
        type="Proposed Rule",
        title="Student loan repayment plan changes",
        abstract="Changes to income-driven repayment.",
        full_text_url="https://example.gov/x",
        date=date(2026, 5, 22),
    )
    return TriagedItem(item=item, score=90, bucket=bucket, reason="loans")


def _client_returning(payload: dict) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(payload))]
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-6")


def test_brief_only_runs_on_relevant_bucket():
    triaged = [
        _triaged("a", Bucket.RELEVANT),
        _triaged("b", Bucket.BORDERLINE),
        _triaged("c", Bucket.DROP),
    ]
    fake_sdk = MagicMock()
    fake_sdk.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps({
            "what_it_is": "x", "why_it_matters": "y", "what_you_could_do": "z"
        }))]
    )
    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-6")

    result = brief_items(triaged, profile="p", client=client)

    assert len(result) == 1
    assert result[0].triaged.item.id == "a"
    assert fake_sdk.messages.create.call_count == 1


def test_brief_populates_three_fields():
    triaged = [_triaged("a")]
    client = _client_returning({
        "what_it_is": "A rule lowering payments.",
        "why_it_matters": "You qualify.",
        "what_you_could_do": "Comment by June 30.",
    })

    result = brief_items(triaged, profile="p", client=client)

    assert result[0].what_it_is == "A rule lowering payments."
    assert result[0].why_it_matters == "You qualify."
    assert result[0].what_you_could_do == "Comment by June 30."


def test_brief_tolerates_code_fenced_json():
    triaged = [_triaged("a")]
    fake_sdk = MagicMock()
    fake_sdk.messages.create.return_value = MagicMock(
        content=[MagicMock(text='```json\n{"what_it_is":"x","why_it_matters":"y","what_you_could_do":"z"}\n```')]
    )
    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-6")

    result = brief_items(triaged, profile="p", client=client)

    assert len(result) == 1
    assert result[0].what_it_is == "x"
