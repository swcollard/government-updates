"""End-to-end pipeline test using fake fetchers and a fake Claude client."""
import json
from datetime import date
from unittest.mock import MagicMock

from digest.claude_client import ClaudeClient
from digest.models import CivicItem, Level
from digest.pipeline import PipelineConfig, run_pipeline


def _item(level: Level, id_: str, title: str) -> CivicItem:
    return CivicItem(
        id=id_, level=level,
        source={Level.FEDERAL: "Federal Register", Level.STATE: "Texas Register", Level.LOCAL: "Austin Council"}[level],
        type="Notice", title=title,
        full_text_url=f"https://example.gov/{id_}",
        date=date(2026, 5, 22),
    )


def _fake_client_sequence(texts: list[str]) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=t)]) for t in texts
    ]
    return ClaudeClient(sdk=fake_sdk, model="m")


def test_run_pipeline_full_flow():
    federal_items = [_item(Level.FEDERAL, "f1", "Housing rule")]
    state_items = [_item(Level.STATE, "s1", "Random unrelated rule")]

    triage_response = json.dumps([
        {"id": "f1", "score": 90, "reason": "housing match"},
        {"id": "s1", "score": 10, "reason": "irrelevant"},
    ])
    brief_response = json.dumps({
        "what_it_is": "x", "why_it_matters": "y", "what_you_could_do": "z",
    })

    client = _fake_client_sequence([triage_response, brief_response])

    result = run_pipeline(
        start=date(2026, 5, 22),
        end=date(2026, 5, 28),
        profile="my profile",
        fetchers=[
            ("Federal Register", lambda s, e: federal_items),
            ("Texas Register", lambda s, e: state_items),
        ],
        triage_client=client,
        brief_client=client,
        config=PipelineConfig(relevant_cutoff=70, borderline_cutoff=40),
    )

    assert "Housing rule" in result.digest_markdown
    assert "Random unrelated rule" not in result.digest_markdown
    assert all(s.ok for s in result.sources)


def test_run_pipeline_records_fetcher_failures():
    def failing_fetcher(start, end):
        raise RuntimeError("HTTP 500")

    client = _fake_client_sequence([json.dumps([])])

    result = run_pipeline(
        start=date(2026, 5, 22),
        end=date(2026, 5, 28),
        profile="p",
        fetchers=[("Texas Register", failing_fetcher)],
        triage_client=client,
        brief_client=client,
        config=PipelineConfig(relevant_cutoff=70, borderline_cutoff=40),
    )

    assert "FAILED" in result.digest_markdown
    failed = [s for s in result.sources if not s.ok]
    assert len(failed) == 1
    assert "HTTP 500" in failed[0].error
