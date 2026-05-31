"""End-to-end orchestration: fetch -> normalize -> triage -> brief -> assemble."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date as Date, timedelta
from pathlib import Path
from typing import Callable

from digest.assemble import DigestInput, SourceStatus, assemble_digest
from digest.brief import brief_items
from digest.claude_client import ClaudeClient, DEFAULT_BRIEF_MODEL, DEFAULT_TRIAGE_MODEL, build_default
from digest.deliver import build_default_config, deliver_github_issue
from digest.models import Bucket, CivicItem
from digest.normalize import dedupe
from digest.triage import triage_items


Fetcher = Callable[[Date, Date], list[CivicItem]]
NamedFetcher = tuple[str, Fetcher]


@dataclass
class PipelineConfig:
    relevant_cutoff: int = 70
    borderline_cutoff: int = 40
    batch_size: int = 25


@dataclass
class PipelineResult:
    digest_markdown: str
    sources: list[SourceStatus] = field(default_factory=list)


def run_pipeline(
    *,
    start: Date,
    end: Date,
    profile: str,
    fetchers: list[NamedFetcher],
    triage_client: ClaudeClient,
    brief_client: ClaudeClient,
    config: PipelineConfig,
) -> PipelineResult:
    all_items: list[CivicItem] = []
    sources: list[SourceStatus] = []
    for name, fetch in fetchers:
        try:
            fetched = fetch(start, end)
            all_items.extend(fetched)
            sources.append(SourceStatus(name=name, ok=True))
        except Exception as exc:  # adapter failures must not break the digest
            sources.append(SourceStatus(name=name, ok=False, error=str(exc)))

    items = dedupe(all_items)

    triaged = triage_items(
        items,
        profile=profile,
        client=triage_client,
        relevant_cutoff=config.relevant_cutoff,
        borderline_cutoff=config.borderline_cutoff,
        batch_size=config.batch_size,
    )
    relevant = [t for t in triaged if t.bucket is Bucket.RELEVANT]
    borderline = [t for t in triaged if t.bucket is Bucket.BORDERLINE]

    briefed = brief_items(relevant, profile=profile, client=brief_client)

    digest = assemble_digest(DigestInput(
        start=start, end=end,
        briefed=briefed,
        borderline=borderline,
        sources=sources,
    ))
    return PipelineResult(digest_markdown=digest, sources=sources)


def main() -> None:
    """CLI entrypoint used by the GitHub Action."""
    from digest.adapters.federal import fetch_federal_items

    end = Date.today()
    start = end - timedelta(days=7)

    profile_path = Path(os.environ.get("PROFILE_PATH", "profile.md"))
    profile = profile_path.read_text()

    fetchers: list[NamedFetcher] = [("Federal Register", fetch_federal_items)]
    # Texas + Austin adapters are added by their tasks; import them here once shipped.
    try:
        from digest.adapters.texas import fetch_texas_items  # noqa: F401
        fetchers.append(("Texas Register", fetch_texas_items))
    except ImportError:
        pass
    try:
        from digest.adapters.austin import fetch_austin_items  # noqa: F401
        fetchers.append(("Austin Council", fetch_austin_items))
    except ImportError:
        pass

    triage_client = build_default(DEFAULT_TRIAGE_MODEL)
    brief_client = build_default(DEFAULT_BRIEF_MODEL)

    result = run_pipeline(
        start=start, end=end, profile=profile,
        fetchers=fetchers,
        triage_client=triage_client, brief_client=brief_client,
        config=PipelineConfig(),
    )

    title = f"Weekly Civic Digest — {end.isoformat()}"
    url = deliver_github_issue(result.digest_markdown, config=build_default_config(title))
    print(f"Delivered: {url}")


if __name__ == "__main__":
    main()
