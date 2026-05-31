"""Tests for delivery (v1: GitHub Issue)."""
import json

import pytest
import responses

from digest.deliver import DeliveryConfig, deliver_github_issue


@responses.activate
def test_deliver_posts_issue_to_correct_endpoint():
    responses.add(
        responses.POST,
        "https://api.github.com/repos/owner/repo/issues",
        json={"html_url": "https://github.com/owner/repo/issues/42", "number": 42},
        status=201,
    )

    url = deliver_github_issue(
        "# digest body",
        config=DeliveryConfig(repo="owner/repo", token="abc", title="Weekly digest 2026-05-29"),
    )

    assert url == "https://github.com/owner/repo/issues/42"
    request = responses.calls[0].request
    body = json.loads(request.body)
    assert body["title"] == "Weekly digest 2026-05-29"
    assert body["body"] == "# digest body"
    assert request.headers["Authorization"] == "Bearer abc"
    assert request.headers["Accept"] == "application/vnd.github+json"


@responses.activate
def test_deliver_raises_on_http_error():
    responses.add(
        responses.POST,
        "https://api.github.com/repos/owner/repo/issues",
        json={"message": "Bad credentials"},
        status=401,
    )

    with pytest.raises(RuntimeError, match="GitHub API error"):
        deliver_github_issue(
            "x",
            config=DeliveryConfig(repo="owner/repo", token="bad", title="t"),
        )
