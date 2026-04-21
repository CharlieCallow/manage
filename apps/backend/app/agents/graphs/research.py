"""Research graph. CLAUDE.md §6.

chosen persona ← analyst stack (parallel) ← market snapshot

Emits all intermediate events (token, status) tagged by agent, then a
final ArtifactEvent containing the persona's memo.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from app.agents.base import AgentContext, LLMAgent
from app.agents.registry import load_analyst, load_persona
from app.schemas.events import (
    ArtifactEvent,
    ArtifactPayload,
    JobEvent,
    StatusEvent,
    TokenEvent,
)
from app.schemas.jobs import JobRow, ResearchInputs
from app.store import db
from app.tools import market_data

# Phase 1: two analysts. Phase 3+ expands the stack and/or makes this
# per-persona configurable.
DEFAULT_ANALYSTS = ("valuation", "fundamentals")


async def run_research(
    job: JobRow, inputs: ResearchInputs, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    ctx.ticker = inputs.ticker
    ctx.user_prompt = inputs.prompt

    # 1. Snapshot
    yield StatusEvent(agent="graph", status="fetching_market_data")
    ctx.snapshot = await market_data.fetch_snapshot(inputs.ticker)

    if ctx.budget.exceeded():
        yield StatusEvent(agent="graph", status="budget_exceeded")
        return

    # 2. Parallel analysts
    analysts = [load_analyst(name) for name in DEFAULT_ANALYSTS]
    async for event in _run_parallel(analysts, job, ctx):
        yield event

    if ctx.budget.exceeded():
        yield StatusEvent(agent="graph", status="budget_exceeded")
        return

    # 3. Persona synthesis — memo collected via TokenEvent buffer
    persona = load_persona(inputs.persona)
    memo_chunks: list[str] = []
    async for event in persona.run(job, ctx):
        if isinstance(event, TokenEvent):
            memo_chunks.append(event.text)
        yield event

    # 4. Memo artifact
    memo_md = "".join(memo_chunks).strip()
    if memo_md:
        artifact_id = db.insert_artifact(
            job_id=job.id,
            kind="memo",
            content_md=memo_md,
            content_json=json.dumps(
                {
                    "ticker": inputs.ticker,
                    "persona": inputs.persona,
                    "analyst_outputs": ctx.analyst_outputs,
                }
            ),
        )
        yield ArtifactEvent(
            artifact=ArtifactPayload(
                id=artifact_id,
                job_id=job.id,
                kind="memo",
                content_md=memo_md,
                content_json=None,
            )
        )


async def _run_parallel(
    agents: list[LLMAgent], job: JobRow, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    """Run agents concurrently; merge their events into one stream.

    Accumulates each agent's streamed text into ctx.analyst_outputs so the
    persona synthesis step can read it.
    """
    queue: asyncio.Queue[tuple[str, JobEvent] | tuple[str, None]] = asyncio.Queue()
    buffers: dict[str, list[str]] = {a.name: [] for a in agents}

    async def drain(agent: LLMAgent) -> None:
        try:
            async for event in agent.run(job, ctx):
                if isinstance(event, TokenEvent):
                    buffers[agent.name].append(event.text)
                await queue.put((agent.name, event))
        finally:
            await queue.put((agent.name, None))

    tasks = [asyncio.create_task(drain(a)) for a in agents]
    done = 0
    try:
        while done < len(agents):
            _, event = await queue.get()
            if event is None:
                done += 1
                continue
            yield event
    finally:
        # Surface any agent-task exceptions; don't swallow (§11).
        await asyncio.gather(*tasks, return_exceptions=False)

    for name, chunks in buffers.items():
        ctx.analyst_outputs[name] = "".join(chunks).strip()
