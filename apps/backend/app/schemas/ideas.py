"""Ideation wire types."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IdeaStatus = Literal["pending", "approved", "dismissed"]


class Idea(BaseModel):
    id: int
    ideation_job_id: str
    persona: str
    ticker: str
    thesis: str
    status: IdeaStatus
    research_job_id: str | None = None
    created_at: str
    updated_at: str


class IdeaDecision(BaseModel):
    """PATCH body to approve or dismiss an idea."""

    status: Literal["approved", "dismissed"]


class ApproveResult(BaseModel):
    idea: Idea
    research_job_id: str | None = None


class IdeationOutcome(BaseModel):
    """Returned as the artifact's content_json for an ideation run."""

    framing: str | None
    personas: list[str]
    num_per_persona: int
    idea_ids: list[int] = Field(default_factory=list)
