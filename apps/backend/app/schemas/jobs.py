"""Job inputs/outputs. CLAUDE.md §5 and §13."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

JobType = Literal["research", "committee", "backtest", "ideation"]
JobStatus = Literal["queued", "running", "done", "error", "budget_exceeded"]
ReportStyle = Literal["classic", "citrini"]


class ResearchInputs(BaseModel):
    """Research job inputs: persona + ticker, plus optional user framing.

    `style` picks the memo format. `classic` is the full sell-side report
    (rating, bull/base/bear targets, exec summary, thesis pillars, business,
    valuation triangulation, risks). `citrini` is a thematic long/short
    write-up — falls back to classic until Step 3 lands.
    """

    persona: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=10)
    prompt: str | None = None
    style: ReportStyle = "classic"


class CommitteeInputs(BaseModel):
    """Committee job inputs: ticker and optional user framing.

    Phase 3 always includes all three personas in the debate. Phase 4+ may
    surface a subset selector; for now keep the UI simple.
    """

    ticker: str = Field(min_length=1, max_length=10)
    prompt: str | None = None
    personas: list[str] | None = None


class IdeationInputs(BaseModel):
    """Ideation job inputs.

    Each enabled persona (or the explicit subset) is asked to surface
    `num_per_persona` tickers worth a deeper look, with one-sentence
    theses. Candidates land in the `ideas` table as `pending`.
    """

    framing: str | None = None
    personas: list[str] | None = None
    num_per_persona: int = Field(default=3, ge=1, le=6)


class BacktestInputs(BaseModel):
    """Backtest job inputs. CLAUDE.md §6, §8.

    Runs a single persona across `num_steps` weekly windows starting at
    `start_date`. Each step the persona (running on Haiku, per §8) emits a
    signal on the as-of snapshot; the forward return is then measured.
    """

    persona: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=10)
    start_date: str = Field(
        description="ISO date (YYYY-MM-DD) for the first step's as-of anchor"
    )
    num_steps: int = Field(default=12, ge=1, le=52)
    step_weeks: int = Field(default=1, ge=1, le=8)


class CreateJobRequest(BaseModel):
    """Boundary schema. `inputs` is a raw dict so each job type can validate
    into its own Pydantic model inside the runner."""

    type: JobType
    inputs: dict[str, Any]
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
