"""Buffett persona. CLAUDE.md §6, §8, §13.

Reads prompt_template from the persona row (§8: never hard-code a model
inside an agent file). Streams tokens via anthropic.AsyncAnthropic.messages.stream.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from app.agents.base import AgentContext
from app.config import cost_usd
from app.schemas.events import JobEvent, StatusEvent, TokenEvent
from app.schemas.jobs import JobRow
from app.store.db import connection

PROMPT_PATH = Path(__file__).with_suffix(".md")


def default_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


@dataclass
class BuffettAgent:
    model: str
    prompt_template: str
    name: str = "buffett"

    async def run(
        self, job: JobRow, ctx: AgentContext
    ) -> AsyncIterator[JobEvent]:
        user_prompt = _extract_user_prompt(job.id)

        if ctx.budget.exceeded():
            yield StatusEvent(agent=self.name, status="budget_exceeded")
            return

        yield StatusEvent(agent=self.name, status="thinking")

        async with ctx.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=self.prompt_template,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield TokenEvent(agent=self.name, text=text)
                if ctx.budget.exceeded():
                    yield StatusEvent(agent=self.name, status="budget_exceeded")
                    return

            final = await stream.get_final_message()
            input_tokens = final.usage.input_tokens
            output_tokens = final.usage.output_tokens

        ctx.budget.charge(cost_usd(self.model, input_tokens, output_tokens))
        yield StatusEvent(agent=self.name, status="done")


def _extract_user_prompt(job_id: str) -> str:
    # Phase 0 — ResearchInputs.prompt is the single user turn.
    # Phase 1+: synthesize from ticker + analyst outputs.
    with connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT inputs_json FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"job not found: {job_id}")
    inputs = json.loads(row["inputs_json"])
    return str(inputs["prompt"])
