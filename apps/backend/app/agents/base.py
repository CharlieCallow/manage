"""Agent protocol and runtime context. CLAUDE.md §6."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from anthropic import AsyncAnthropic

from app.schemas.events import JobEvent
from app.schemas.jobs import JobRow


@dataclass
class BudgetTracker:
    """Per-job cost accounting. See CLAUDE.md §9.

    Every agent must call `charge` after each model call. If `exceeded()` is
    true, the agent must stop cleanly (emit status=budget_exceeded and return).
    """

    budget_usd: float
    spent_usd: float = 0.0

    def charge(self, amount_usd: float) -> None:
        self.spent_usd += amount_usd

    def exceeded(self) -> bool:
        return self.spent_usd >= self.budget_usd


@dataclass
class AgentContext:
    job: JobRow
    client: AsyncAnthropic
    budget: BudgetTracker


@runtime_checkable
class Agent(Protocol):
    name: str
    model: str  # per-persona model, loaded from personas.model (§8)

    # Implemented as an async generator (`async def run` with `yield`). The
    # Protocol signature uses a plain `def` so the return type is the iterator
    # itself, not a coroutine.
    def run(
        self, job: JobRow, ctx: AgentContext
    ) -> AsyncIterator[JobEvent]: ...
