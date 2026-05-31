"""Tests for the thin Anthropic wrapper."""
from unittest.mock import MagicMock

from digest.claude_client import ClaudeClient


def test_complete_returns_message_text():
    fake_sdk = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="hello world")]
    fake_sdk.messages.create.return_value = fake_response

    client = ClaudeClient(sdk=fake_sdk, model="claude-haiku-4-5")
    out = client.complete(system="you are X", user="say hi")

    assert out == "hello world"
    fake_sdk.messages.create.assert_called_once()
    kwargs = fake_sdk.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["system"] == "you are X"
    assert kwargs["messages"] == [{"role": "user", "content": "say hi"}]


def test_complete_joins_multiple_content_blocks():
    fake_sdk = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="part one "), MagicMock(text="part two")]
    fake_sdk.messages.create.return_value = fake_response

    client = ClaudeClient(sdk=fake_sdk, model="claude-haiku-4-5")
    out = client.complete(system="s", user="u")

    assert out == "part one part two"
