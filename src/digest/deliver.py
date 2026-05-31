"""Delivery module: opens a GitHub Issue containing the digest markdown.

This is the v1 delivery target — chosen because GitHub itself emails
notifications, removing the need for any third-party email provider.

To swap delivery later (e.g. Brevo, Resend, SMTP), implement a new function
with the same signature `deliver(digest_markdown) -> url` and update
`pipeline.py` to call it instead.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass
class DeliveryConfig:
    repo: str          # "owner/repo"
    token: str
    title: str


def deliver_github_issue(digest_markdown: str, *, config: DeliveryConfig) -> str:
    """Open a GitHub Issue. Returns the issue URL."""
    url = f"https://api.github.com/repos/{config.repo}/issues"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {config.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": config.title, "body": digest_markdown},
        timeout=30,
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"GitHub API error {response.status_code}: {response.text}"
        )
    return response.json()["html_url"]


def build_default_config(title: str) -> DeliveryConfig:
    """Read repo + token from the env vars GitHub Actions injects."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN must be set")
    return DeliveryConfig(repo=repo, token=token, title=title)
