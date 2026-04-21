"""Ideation graph.

Each enabled persona is asked to surface `num_per_persona` tickers worth a
deeper look, with a one-sentence thesis. Personas run in parallel, streaming
tokens under their own agent name, and their candidates land in the `ideas`
table as `pending`.

The Research Desk flow (Phase 1+) is reused when the user approves a
candidate — see `api/ideas.py`.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator

from app.agents.base import AgentContext
from app.config import cost_usd
from app.schemas.events import (
    ArtifactEvent,
    ArtifactPayload,
    JobEvent,
    StatusEvent,
    TokenEvent,
)
from app.schemas.jobs import IdeationInputs, JobRow
from app.store import db

_MAX_TOKENS = 320

_TICKER_RE = re.compile(r"^\s*TICKER\s*:\s*([A-Z][A-Z0-9.\-]{0,6})\s*$", re.IGNORECASE)
_THESIS_RE = re.compile(r"^\s*THESIS\s*:\s*(.+?)\s*$", re.IGNORECASE)

# Obvious non-ticker tokens we sometimes see from LLM output.
_TICKER_BLOCKLIST = {"NONE", "N/A", "NA", "TICKER", "TBD"}


async def run_ideation(
    job: JobRow, inputs: IdeationInputs, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    personas = inputs.personas or _default_enabled_personas()
    if not personas:
        raise RuntimeError("no enabled personas to ideate with")

    yield StatusEvent(agent="graph", status="ideating")

    queue: asyncio.Queue[tuple[str, JobEvent] | tuple[str, None]] = asyncio.Queue()
    buffers: dict[str, list[str]] = {p: [] for p in personas}

    async def drain(persona: str) -> None:
        try:
            async for event in _run_persona(
                persona=persona,
                framing=inputs.framing,
                num=inputs.num_per_persona,
                ctx=ctx,
            ):
                if isinstance(event, TokenEvent):
                    buffers[persona].append(event.text)
                await queue.put((persona, event))
        finally:
            await queue.put((persona, None))

    tasks = [asyncio.create_task(drain(p)) for p in personas]
    done = 0
    try:
        while done < len(personas):
            _, event = await queue.get()
            if event is None:
                done += 1
                continue
            yield event
    finally:
        await asyncio.gather(*tasks, return_exceptions=False)

    idea_ids: list[int] = []
    for persona, chunks in buffers.items():
        raw = "".join(chunks).strip()
        for ticker, thesis in _parse_candidates(raw):
            if _is_plausible_ticker(ticker):
                idea_id = db.insert_idea(
                    ideation_job_id=job.id,
                    persona=persona,
                    ticker=ticker,
                    thesis=thesis,
                )
                idea_ids.append(idea_id)

    meta = {
        "framing": inputs.framing,
        "personas": personas,
        "num_per_persona": inputs.num_per_persona,
        "idea_ids": idea_ids,
    }
    artifact_id = db.insert_artifact(
        job_id=job.id,
        kind="ideation_outcome",
        content_md=_render_markdown(personas, idea_ids),
        content_json=json.dumps(meta),
    )
    yield ArtifactEvent(
        artifact=ArtifactPayload(
            id=artifact_id,
            job_id=job.id,
            kind="ideation_outcome",
            content_md=None,
            content_json=meta,
        )
    )


async def _run_persona(
    persona: str,
    framing: str | None,
    num: int,
    ctx: AgentContext,
) -> AsyncIterator[JobEvent]:
    row = db.get_persona_by_name(persona)
    if row is None:
        raise KeyError(f"persona row missing: {persona}")
    model = str(row["model"])
    system_prompt = str(row["prompt_template"])

    if ctx.budget.exceeded():
        yield StatusEvent(agent=persona, status="budget_exceeded")
        return

    yield StatusEvent(agent=persona, status="thinking")

    user_message = _build_user_message(persona, framing, num)

    input_tokens = 0
    output_tokens = 0

    async with ctx.client.messages.stream(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        async for chunk in stream.text_stream:
            if chunk:
                yield TokenEvent(agent=persona, text=chunk)
            if ctx.budget.exceeded():
                yield StatusEvent(agent=persona, status="budget_exceeded")
                return

        final = await stream.get_final_message()
        input_tokens = final.usage.input_tokens
        output_tokens = final.usage.output_tokens

    call_cost = cost_usd(model, input_tokens, output_tokens)
    ctx.budget.charge(call_cost)
    db.log_api_call(
        job_id=ctx.job.id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=call_cost,
    )
    yield StatusEvent(agent=persona, status="done")


def _build_user_message(persona: str, framing: str | None, num: int) -> str:
    framing_line = framing.strip() if framing else ""
    ask = (
        f"A PM is asking for {num} tickers you'd flag as worth a deeper look\n"
        "right now. Think in your own style — don't justify at length, just\n"
        "surface the candidates.\n\n"
    )
    if framing_line:
        ask += f"Framing from the PM: {framing_line}\n\n"
    ask += (
        "Respond in EXACTLY this format and nothing else — no preamble, no\n"
        "conclusion, no numbering:\n\n"
        "TICKER: <symbol>\n"
        "THESIS: <one sentence, ≤25 words, the single reason this is worth\n"
        "  deeper research right now>\n\n"
        "(blank line between each pair)"
    )
    _ = persona  # the persona name is already reflected in the system prompt
    return ask


def _parse_candidates(raw: str) -> list[tuple[str, str]]:
    """Pull (ticker, thesis) pairs out of a free-form response."""
    pairs: list[tuple[str, str]] = []
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    pending_ticker: str | None = None
    for line in lines:
        ticker_match = _TICKER_RE.match(line)
        if ticker_match:
            pending_ticker = ticker_match.group(1).upper()
            continue
        thesis_match = _THESIS_RE.match(line)
        if thesis_match and pending_ticker:
            pairs.append((pending_ticker, thesis_match.group(1).strip()))
            pending_ticker = None
    return pairs


def _is_plausible_ticker(ticker: str) -> bool:
    if not ticker or ticker.upper() in _TICKER_BLOCKLIST:
        return False
    return bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,6}", ticker))


def _default_enabled_personas() -> list[str]:
    rows = db.list_roster("personas")
    return [str(r["name"]) for r in rows if bool(r.get("enabled", 1))]


def _render_markdown(personas: list[str], idea_ids: list[int]) -> str:
    return (
        f"# Ideation run\n\n"
        f"Personas: {', '.join(personas)}\n\n"
        f"Produced {len(idea_ids)} candidate idea(s). Approve or dismiss them\n"
        f"from the Ideas room."
    )
