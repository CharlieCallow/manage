"""Job inputs/outputs. CLAUDE.md §5 and §13."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobType = Literal["research", "committee", "backtest"]
JobStatus = Literal["queued", "running", "done", "error", "budget_exceeded"]


class ResearchInputs(BaseModel):
    """Phase 0: just a persona + free-form prompt. Phase 1 adds ticker, analysts."""

    persona: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


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
