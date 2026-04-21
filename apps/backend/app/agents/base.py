"""Agent protocol, runtime context, and a shared streaming helper.

CLAUDE.md §6 for the contract, §8 for model selection, §9 for budget.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from anthropic import AsyncAnthropic

from app.config import cost_usd
from app.schemas.events import JobEvent, StatusEvent, TokenEvent
from app.schemas.jobs import JobRow


@dataclass
class BudgetTracker:
    """Per-job cost accounting. See CLAUDE.md §9."""

    budget_usd: float
    spent_usd: float = 0.0

    def charge(self, amount_usd: float) -> None:
        self.spent_usd += amount_usd

    def exceeded(self) -> bool:
        return self.spent_usd >= self.budget_usd


@dataclass
class TranscriptTurn:
    role: str  # "moderator" | "buffett" | "druckenmiller" | "burry" | "risk" | "pm"
    text: str


@dataclass
class AgentContext:
    """Per-job mutable state shared across nodes in a graph."""

    job: JobRow
    client: AsyncAnthropic
    budget: BudgetTracker
    snapshot: dict[str, Any] | None = None
    analyst_outputs: dict[str, str] = field(default_factory=dict)
    transcript: list[TranscriptTurn] = field(default_factory=list)
    user_prompt: str | None = None
    ticker: str | None = None


@runtime_checkable
class Agent(Protocol):
    name: str
    model: str

    def run(self, job: JobRow, ctx: AgentContext) -> AsyncIterator[JobEvent]: ...


class LLMAgent(ABC):
    """Concrete base for personas and analysts.

    Subclasses override `build_user_message`; all streaming, budget, and
    event emission is shared here. CLAUDE.md §8: always stream.
    """

    name: str
    model: str
    prompt_template: str

    def __init__(self, name: str, model: str, prompt_template: str) -> None:
        self.name = name
        self.model = model
        self.prompt_template = prompt_template

    @abstractmethod
    def build_user_message(self, ctx: AgentContext) -> str: ...

    async def run(
        self, _job: JobRow, ctx: AgentContext
    ) -> AsyncIterator[JobEvent]:
        if ctx.budget.exceeded():
            yield StatusEvent(agent=self.name, status="budget_exceeded")
            return

        yield StatusEvent(agent=self.name, status="thinking")

        user_message = self.build_user_message(ctx)
        input_tokens = 0
        output_tokens = 0

        async with ctx.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=self.prompt_template,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for chunk in stream.text_stream:
                if chunk:
                    yield TokenEvent(agent=self.name, text=chunk)
                if ctx.budget.exceeded():
                    yield StatusEvent(agent=self.name, status="budget_exceeded")
                    return

            final = await stream.get_final_message()
            input_tokens = final.usage.input_tokens
            output_tokens = final.usage.output_tokens

        ctx.budget.charge(cost_usd(self.model, input_tokens, output_tokens))
        yield StatusEvent(agent=self.name, status="done")
