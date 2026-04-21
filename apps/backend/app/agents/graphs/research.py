"""Research graph. CLAUDE.md §6.

Phase 0: persona-only. Phase 1 adds analyst stack (parallel) → synthesis
and produces a memo artifact. This file evolves; the public entrypoint
`run_research` is the stable contract callers depend on.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.agents.base import AgentContext
from app.agents.registry import load_persona
from app.schemas.events import JobEvent
from app.schemas.jobs import JobRow, ResearchInputs


async def run_research(
    job: JobRow, inputs: ResearchInputs, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    persona = load_persona(inputs.persona)
    async for event in persona.run(job, ctx):
        yield event
