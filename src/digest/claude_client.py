"""Thin Anthropic SDK wrapper that downstream modules use for all Claude calls.

Tests inject a fake `sdk` (a stand-in for `anthropic.Anthropic()`).
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_TRIAGE_MODEL = "claude-haiku-4-5"
DEFAULT_BRIEF_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4000


class ClaudeClient:
    def __init__(self, sdk: Any, model: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> None:
        self._sdk = sdk
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, *, system: str, user: str) -> str:
        response = self._sdk.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content)


def build_default(model: str) -> ClaudeClient:
    """Construct a real ClaudeClient using the ANTHROPIC_API_KEY env var."""
    from anthropic import Anthropic  # imported lazily so unit tests don't need the key

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return ClaudeClient(sdk=Anthropic(api_key=api_key), model=model)
