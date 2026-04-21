"""Roster wire types: personas, analysts, performance rows. CLAUDE.md §5, §8."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import ModelId


class RosterRow(BaseModel):
    """Shared shape for persona + analyst rows."""

    id: int
    name: str
    prompt_template: str
    model: str
    enabled: bool
    created_at: str


class RosterUpdate(BaseModel):
    """PATCH body. Every field is optional — only provided fields get written."""

    prompt_template: str | None = Field(default=None, min_length=1)
    model: ModelId | None = None
    enabled: bool | None = None


class PerformanceRow(BaseModel):
    id: int
    persona_id: int
    period: str
    trades: int
    hit_rate: float | None = None
    avg_return: float | None = None
