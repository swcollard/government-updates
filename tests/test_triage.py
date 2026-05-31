"""Tests for the batched Claude triage pass."""
import json
from datetime import date
from unittest.mock import MagicMock

from digest.claude_client import ClaudeClient
from digest.models import Bucket, CivicItem, Level
from digest.triage import triage_items


def _item(id_: str, title: str = "T", abstract: str | None = "A") -> CivicItem:
    return CivicItem(
        id=id_,
        level=Level.FEDERAL,
        source="Federal Register",
        agency="EPA",
        type="Proposed Rule",
        title=title,
        abstract=abstract,
        full_text_url="https://example.gov/x",
        date=date(2026, 5, 22),
    )


def _client_returning(json_payload: list[dict]) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps(json_payload))]
    fake_sdk.messages.create.return_value = fake_response
    return ClaudeClient(sdk=fake_sdk, model="claude-haiku-4-5")


def test_triage_assigns_buckets_using_thresholds():
    items = [_item("a"), _item("b"), _item("c")]
    client = _client_returning([
        {"id": "a", "score": 90, "reason": "matches housing"},
        {"id": "b", "score": 55, "reason": "tangential"},
        {"id": "c", "score": 10, "reason": "irrelevant"},
    ])

    result = triage_items(
        items, profile="my profile", client=client,
        relevant_cutoff=70, borderline_cutoff=40,
    )

    by_id = {t.item.id: t for t in result}
    assert by_id["a"].bucket is Bucket.RELEVANT
    assert by_id["b"].bucket is Bucket.BORDERLINE
    assert by_id["c"].bucket is Bucket.DROP
    assert by_id["a"].reason == "matches housing"


def test_triage_batches_large_inputs():
    items = [_item(str(i)) for i in range(30)]
    fake_sdk = MagicMock()
    # Two responses, since batch size defaults to 25.
    fake_sdk.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=json.dumps(
            [{"id": str(i), "score": 80, "reason": "r"} for i in range(25)]
        ))]),
        MagicMock(content=[MagicMock(text=json.dumps(
            [{"id": str(i), "score": 80, "reason": "r"} for i in range(25, 30)]
        ))]),
    ]
    client = ClaudeClient(sdk=fake_sdk, model="claude-haiku-4-5")

    result = triage_items(
        items, profile="p", client=client,
        relevant_cutoff=70, borderline_cutoff=40, batch_size=25,
    )

    assert len(result) == 30
    assert fake_sdk.messages.create.call_count == 2


def test_triage_tolerates_extra_whitespace_or_code_fence_around_json():
    items = [_item("a")]
    client = _client_returning_text(
        "```json\n[{\"id\": \"a\", \"score\": 88, \"reason\": \"x\"}]\n```"
    )

    result = triage_items(items, profile="p", client=client, relevant_cutoff=70, borderline_cutoff=40)

    assert len(result) == 1
    assert result[0].score == 88


def test_triage_drops_items_the_model_did_not_score():
    items = [_item("a"), _item("b")]
    client = _client_returning([{"id": "a", "score": 80, "reason": "r"}])

    result = triage_items(items, profile="p", client=client, relevant_cutoff=70, borderline_cutoff=40)

    assert len(result) == 1
    assert result[0].item.id == "a"


def _client_returning_text(text: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=text)]
    fake_sdk.messages.create.return_value = fake_response
    return ClaudeClient(sdk=fake_sdk, model="claude-haiku-4-5")
