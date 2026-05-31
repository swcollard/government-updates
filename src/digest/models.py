"""Common data model shared by every adapter and every downstream module."""
from __future__ import annotations

from datetime import date as Date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Level(str, Enum):
    FEDERAL = "federal"
    STATE = "state"
    LOCAL = "local"


class Bucket(str, Enum):
    RELEVANT = "relevant"
    BORDERLINE = "borderline"
    DROP = "drop"


class CivicItem(BaseModel):
    """One normalized government action: rule, notice, agenda item, etc."""

    model_config = ConfigDict(frozen=False)

    id: str
    level: Level
    source: str
    agency: str | None = None
    type: str
    title: str
    abstract: str | None = None
    full_text_url: HttpUrl
    date: Date
    raw: dict[str, Any] | None = None


class TriagedItem(BaseModel):
    item: CivicItem
    score: int = Field(ge=0, le=100)
    bucket: Bucket
    reason: str


class BriefedItem(BaseModel):
    triaged: TriagedItem
    what_it_is: str
    why_it_matters: str
    what_you_could_do: str
