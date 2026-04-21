"""Research graph. CLAUDE.md §6.

chosen persona ← analyst stack (parallel) ← market snapshot

Emits all intermediate events (token, status) tagged by agent, then a
final ArtifactEvent containing the persona's memo.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

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

# Post-Step-3: four analysts fan out in parallel for the full report.
# Each one's output lands in ctx.analyst_outputs and feeds the persona's
# synthesis.
DEFAULT_ANALYSTS = ("valuation", "fundamentals", "macro", "technicals")

_RATING_RE = re.compile(
    r"\*\*Rating:\*\*\s*([A-Z][A-Z ]+)",
)
_TARGET_RE_TEMPLATE = r"\*\*{label} target:\*\*\s*\$?([\-0-9.,]+)"

# Citrini basket block: a fenced block bracketed by BASKET / lines of
# LONG|SHORT: TICKER weight%
_BASKET_BLOCK_RE = re.compile(r"BASKET\s*\n([\s\S]+?)(?:\n\s*```|$)")
_BASKET_LINE_RE = re.compile(
    r"^\s*(LONG|SHORT)\s*:\s*([A-Z][A-Z0-9.\-]{0,6})\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


async def run_research(
    job: JobRow, inputs: ResearchInputs, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    ctx.ticker = inputs.ticker
    ctx.user_prompt = inputs.prompt
    ctx.style = inputs.style

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

    # 4. Memo artifact (with parsed rating + targets)
    memo_md = "".join(memo_chunks).strip()
    if memo_md:
        meta = _parse_memo_meta(memo_md)
        content_json: dict[str, Any] = {
            "ticker": inputs.ticker,
            "persona": inputs.persona,
            "style": inputs.style,
            "analyst_outputs": ctx.analyst_outputs,
            **meta,
        }
        artifact_id = db.insert_artifact(
            job_id=job.id,
            kind="memo",
            content_md=memo_md,
            content_json=json.dumps(content_json),
        )
        yield ArtifactEvent(
            artifact=ArtifactPayload(
                id=artifact_id,
                job_id=job.id,
                kind="memo",
                content_md=memo_md,
                content_json=content_json,
            )
        )


def _parse_memo_meta(memo_md: str) -> dict[str, Any]:
    """Pull rating + bull/base/bear targets + Citrini basket from the memo."""
    rating_match = _RATING_RE.search(memo_md)
    rating = rating_match.group(1).strip() if rating_match else None

    def target(label: str) -> float | None:
        match = re.search(_TARGET_RE_TEMPLATE.format(label=label), memo_md)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    return {
        "rating": rating,
        "targets": {
            "bull": target("Bull"),
            "base": target("Base"),
            "bear": target("Bear"),
        },
        "basket": _parse_basket(memo_md),
    }


def _parse_basket(memo_md: str) -> dict[str, list[dict[str, Any]]] | None:
    """Pull the Citrini basket block if present."""
    block_match = _BASKET_BLOCK_RE.search(memo_md)
    if not block_match:
        return None
    block = block_match.group(1)
    longs: list[dict[str, Any]] = []
    shorts: list[dict[str, Any]] = []
    for match in _BASKET_LINE_RE.finditer(block):
        side = match.group(1).upper()
        ticker = match.group(2).upper()
        try:
            weight = float(match.group(3))
        except ValueError:
            continue
        entry = {"ticker": ticker, "weight": weight}
        if side == "LONG":
            longs.append(entry)
        else:
            shorts.append(entry)
    if not longs and not shorts:
        return None
    return {"long": longs, "short": shorts}


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
