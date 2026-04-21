"""Job inputs/outputs. CLAUDE.md §5 and §13."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobType = Literal["research", "committee", "backtest"]
JobStatus = Literal["queued", "running", "done", "error", "budget_exceeded"]


class ResearchInputs(BaseModel):
    """Research job inputs: persona + ticker, plus optional user framing."""

    persona: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=10)
    prompt: str | None = None


class CreateJobRequest(BaseModel):
    type: JobType
    inputs: ResearchInputs
    budget_usd: float | None = None


class CreateJobResponse(BaseModel):
    job_id: str


class JobRow(BaseModel):
    id: str
    type: JobType
    status: JobStatus
    cost_usd: float
    budget_usd: float
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class ArtifactRow(BaseModel):
    id: int
    job_id: str
    kind: str
    content_md: str | None = None
    content_json: str | None = None
    created_at: str


class JobSummary(BaseModel):
    """Light-weight row for list endpoints (does not include inputs_json)."""

    id: str
    type: JobType
    status: JobStatus
    cost_usd: float
    budget_usd: float
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    ticker: str | None = None
    persona: str | None = None
