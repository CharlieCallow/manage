"""Committee graph. CLAUDE.md §6.

moderator → round-robin persona turns → risk → pm → transcript + verdict.

Each speaker streams tokens tagged by their agent name (per §7 the renderer
demultiplexes on `agent`). The accumulated transcript is passed into the
next speaker's user message.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from app.agents.base import AgentContext, LLMAgent, TranscriptTurn
from app.agents.registry import load_analyst, load_persona
from app.schemas.events import (
    ArtifactEvent,
    ArtifactPayload,
    JobEvent,
    StatusEvent,
    TokenEvent,
)
from app.schemas.jobs import CommitteeInputs, JobRow
from app.store import db
from app.tools import market_data

DEFAULT_PERSONAS: tuple[str, ...] = ("buffett", "druckenmiller", "burry")

_VERDICT_RE = re.compile(
    r"^decision:\s*(buy|add|hold|trim|pass|short)\b",
    re.IGNORECASE | re.MULTILINE,
)


async def run_committee(
    job: JobRow, inputs: CommitteeInputs, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    ctx.ticker = inputs.ticker
    ctx.user_prompt = inputs.prompt
    ctx.transcript = []

    yield StatusEvent(agent="graph", status="fetching_market_data")
    ctx.snapshot = await market_data.fetch_snapshot(inputs.ticker)

    if ctx.budget.exceeded():
        yield StatusEvent(agent="graph", status="budget_exceeded")
        return

    personas = inputs.personas or list(DEFAULT_PERSONAS)

    # Speaking order: moderator, then personas round-robin, then risk, then pm.
    speakers: list[LLMAgent] = [load_analyst("moderator")]
    speakers.extend(load_persona(p) for p in personas)
    speakers.append(load_analyst("risk"))
    speakers.append(load_analyst("pm"))

    for speaker in speakers:
        if ctx.budget.exceeded():
            yield StatusEvent(agent="graph", status="budget_exceeded")
            return
        buffer: list[str] = []
        async for event in speaker.run(job, ctx):
            if isinstance(event, TokenEvent):
                buffer.append(event.text)
            yield event
        ctx.transcript.append(
            TranscriptTurn(role=speaker.name, text="".join(buffer).strip())
        )

    verdict = _extract_verdict(ctx.transcript)
    transcript_md = _render_markdown(inputs.ticker, ctx.transcript)
    meta = {
        "ticker": inputs.ticker,
        "participants": [t.role for t in ctx.transcript],
        "verdict": verdict,
    }
    artifact_id = db.insert_artifact(
        job_id=job.id,
        kind="transcript",
        content_md=transcript_md,
        content_json=json.dumps(meta),
    )
    yield ArtifactEvent(
        artifact=ArtifactPayload(
            id=artifact_id,
            job_id=job.id,
            kind="transcript",
            content_md=transcript_md,
            content_json=meta,
        )
    )


def _extract_verdict(turns: list[TranscriptTurn]) -> str | None:
    for turn in reversed(turns):
        if turn.role != "pm":
            continue
        match = _VERDICT_RE.search(turn.text)
        if match:
            return match.group(1).lower()
    return None


_TITLE_BY_ROLE: dict[str, str] = {
    "moderator": "Moderator",
    "buffett": "Buffett",
    "druckenmiller": "Druckenmiller",
    "burry": "Burry",
    "risk": "Risk officer",
    "pm": "PM decision",
}


def _render_markdown(ticker: str, turns: list[TranscriptTurn]) -> str:
    parts = [f"# Committee · {ticker}\n"]
    for turn in turns:
        title = _TITLE_BY_ROLE.get(turn.role, turn.role.capitalize())
        parts.append(f"## {title}\n\n{turn.text.strip()}\n")
    return "\n".join(parts).strip()
