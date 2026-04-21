"""Backtest graph. CLAUDE.md §6, §8.

For each as-of date:
  1. Pull a price snapshot as of that date
  2. Score the persona (Haiku, hot-loop) into buy/hold/pass
  3. Measure forward return to the next step
Then write a backtest_report artifact and a persona_performance row.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.agents.base import AgentContext
from app.config import cost_usd
from app.schemas.events import (
    ArtifactEvent,
    ArtifactPayload,
    JobEvent,
    StatusEvent,
    TokenEvent,
)
from app.schemas.jobs import BacktestInputs, JobRow
from app.store import db
from app.tools import market_data

# CLAUDE.md §8 — hot-loop calls use Haiku regardless of the persona row's model.
_SCORER_MODEL = "claude-haiku-4-5"

_SIGNAL_RE = re.compile(r"SIGNAL\s*:\s*(BUY|HOLD|PASS)", re.IGNORECASE)

# Dedicated scorer system prompt. The persona row's prompt is written for a
# memo-producing agent, which produces universal PASSes when handed a single
# Haiku call per step. This prompt instead asks Haiku to emit a tactical
# BUY/HOLD/PASS signal in the persona's style, using whatever the snapshot
# carries — point-in-time fundamentals from financial-datasets.ai when a
# key is configured, else price-only indicators.
_SCORER_SYSTEM = (
    "You are a tactical signal generator inside an equities backtester. For\n"
    "each snapshot you emit exactly one of BUY, HOLD, or PASS.\n\n"
    "Snapshots may include:\n"
    "- price indicators: close, MA20/50/200 distances, drawdown, 52w range,\n"
    "  annualized volatility, 4w/52w returns\n"
    "- a `fundamentals` block (point-in-time): P/E, P/B, EV/EBITDA, margins,\n"
    "  ROE/ROIC, revenue/earnings growth, debt, free cash flow\n\n"
    "Use every block present. If fundamentals are available, weigh them in\n"
    "the persona's style. If only prices are present, score the trend setup.\n"
    "Do not demand data that isn't in the snapshot — work with what's there.\n\n"
    "BUY when the setup is clean in the dimensions you can see.\n"
    "HOLD when signals conflict or the picture is ambiguous.\n"
    "PASS when the trend is breaking or fundamentals/valuation disqualify.\n\n"
    "Lean on the PERSONA_STYLE the user provides — it's a sensibility, not a\n"
    "licence to demand fields that aren't there.\n\n"
    "Respond in this exact format and nothing else:\n"
    "SIGNAL: BUY|HOLD|PASS\n"
    "REASON: <one short sentence grounded in one or two concrete numbers>"
)

# One-liner style hints per persona — used as flavor in the user message so
# different personas produce different signal profiles on the same tape.
_PERSONA_STYLE_HINTS: dict[str, str] = {
    "buffett": (
        "Warren Buffett — prefers durable uptrends with room to compound; "
        "skeptical of frothy breakouts; tolerates sideways tapes."
    ),
    "druckenmiller": (
        "Stanley Druckenmiller — momentum-friendly, bets on clean setups, "
        "cuts fast when the trend breaks, happy to pass on chop."
    ),
    "burry": (
        "Michael Burry — contrarian, favors deep drawdowns with signs of a "
        "floor; skeptical of extended rallies; unafraid to PASS when the "
        "crowd is long."
    ),
}


@dataclass
class _StepResult:
    as_of: str
    close: float | None
    signal: str
    rationale: str
    forward_return: float | None


async def run_backtest(
    job: JobRow, inputs: BacktestInputs, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    ctx.ticker = inputs.ticker

    persona_row = db.get_persona_by_name(inputs.persona)
    if persona_row is None:
        raise KeyError(f"persona row missing: {inputs.persona}")

    yield StatusEvent(agent="backtester", status="starting")

    try:
        start = date.fromisoformat(inputs.start_date)
    except ValueError as exc:
        raise ValueError(f"invalid start_date (want YYYY-MM-DD): {inputs.start_date}") from exc

    step_delta = timedelta(weeks=inputs.step_weeks)
    steps: list[_StepResult] = []

    for i in range(inputs.num_steps):
        if ctx.budget.exceeded():
            yield StatusEvent(agent="backtester", status="budget_exceeded")
            break

        as_of = start + step_delta * i
        next_date = as_of + step_delta

        yield StatusEvent(
            agent="backtester",
            status=f"step {i + 1}/{inputs.num_steps}: fetching {as_of}",
        )
        snapshot = await market_data.fetch_snapshot_asof(inputs.ticker, as_of)
        forward = await market_data.fetch_forward_return(
            inputs.ticker, as_of, next_date
        )

        yield StatusEvent(
            agent="backtester",
            status=f"step {i + 1}/{inputs.num_steps}: scoring {as_of}",
        )
        signal, rationale = await _score(
            persona_name=inputs.persona,
            ticker=inputs.ticker,
            snapshot=snapshot,
            ctx=ctx,
        )
        step = _StepResult(
            as_of=as_of.isoformat(),
            close=snapshot.get("close"),
            signal=signal,
            rationale=rationale,
            forward_return=forward,
        )
        steps.append(step)

        summary = _step_line(step)
        yield TokenEvent(agent="backtester", text=summary + "\n")

    yield StatusEvent(agent="backtester", status="compiling report")
    report = _build_report(inputs, steps)

    # Persist the scoreboard row. `period` is the ticker so repeat runs
    # replace; per §5 uniqueness is (persona_id, period).
    db.upsert_persona_performance(
        persona_id=int(persona_row["id"]),
        period=inputs.ticker,
        trades=int(report["trades"]),
        hit_rate=report["hit_rate"],
        avg_return=report["avg_return"],
    )

    artifact_id = db.insert_artifact(
        job_id=job.id,
        kind="backtest_report",
        content_md=report["markdown"],
        content_json=json.dumps(
            {
                "ticker": inputs.ticker,
                "persona": inputs.persona,
                "start_date": inputs.start_date,
                "num_steps": inputs.num_steps,
                "step_weeks": inputs.step_weeks,
                "trades": report["trades"],
                "hit_rate": report["hit_rate"],
                "avg_return": report["avg_return"],
                "cumulative_return": report["cumulative_return"],
                "steps": [step.__dict__ for step in steps],
            }
        ),
    )
    yield ArtifactEvent(
        artifact=ArtifactPayload(
            id=artifact_id,
            job_id=job.id,
            kind="backtest_report",
            content_md=report["markdown"],
            content_json=None,
        )
    )
    yield StatusEvent(agent="backtester", status="done")


async def _score(
    persona_name: str,
    ticker: str,
    snapshot: dict[str, Any],
    ctx: AgentContext,
) -> tuple[str, str]:
    """Call Haiku with the dedicated scorer system prompt."""
    # Strip the heavy weekly-closes list from the user message — Haiku needs
    # the headline numbers, not 52 bars of price history.
    lite = {k: v for k, v in snapshot.items() if k != "weekly_closes_52w"}
    style = _PERSONA_STYLE_HINTS.get(persona_name, persona_name)
    user = (
        f"Ticker: {ticker}\n"
        f"As of: {snapshot.get('as_of')}\n"
        f"PERSONA_STYLE: {style}\n\n"
        f"Snapshot (price-based indicators only):\n"
        f"{json.dumps(lite, indent=2, default=str)}"
    )

    text_parts: list[str] = []
    input_tokens = 0
    output_tokens = 0

    async with ctx.client.messages.stream(
        model=_SCORER_MODEL,
        max_tokens=120,
        system=_SCORER_SYSTEM,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        async for chunk in stream.text_stream:
            if chunk:
                text_parts.append(chunk)
        final = await stream.get_final_message()
        input_tokens = final.usage.input_tokens
        output_tokens = final.usage.output_tokens

    call_cost = cost_usd(_SCORER_MODEL, input_tokens, output_tokens)
    ctx.budget.charge(call_cost)
    db.log_api_call(
        job_id=ctx.job.id,
        model=_SCORER_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=call_cost,
    )

    full = "".join(text_parts)
    signal = "HOLD"
    match = _SIGNAL_RE.search(full)
    if match:
        signal = match.group(1).upper()
    reason = ""
    for line in full.splitlines():
        if line.lower().startswith("reason:"):
            reason = line.split(":", 1)[1].strip()
            break
    return signal, reason


def _step_line(s: _StepResult) -> str:
    close = f"{s.close:.2f}" if s.close is not None else "—"
    fwd = f"{s.forward_return * 100:+.2f}%" if s.forward_return is not None else "—"
    reason = s.rationale or ""
    return f"{s.as_of}  close {close}  {s.signal:<4}  fwd {fwd:>8}  · {reason}"


def _build_report(
    inputs: BacktestInputs, steps: list[_StepResult]
) -> dict[str, Any]:
    trades = [s for s in steps if s.signal == "BUY" and s.forward_return is not None]
    returns = [s.forward_return for s in trades if s.forward_return is not None]
    hits = [r for r in returns if r > 0]
    hit_rate = (len(hits) / len(returns)) if returns else None
    avg_return = (sum(returns) / len(returns)) if returns else None

    # Cumulative return on the BUY-only strategy (flat otherwise).
    cum = 1.0
    for s in steps:
        if s.signal == "BUY" and s.forward_return is not None:
            cum *= 1.0 + s.forward_return
    cumulative = cum - 1.0 if returns else None

    rows = [
        f"| {s.as_of} | "
        f"{(f'{s.close:.2f}' if s.close is not None else '—')} | "
        f"{s.signal} | "
        f"{(f'{s.forward_return * 100:+.2f}%' if s.forward_return is not None else '—')} |"
        for s in steps
    ]
    md = "\n".join(
        [
            f"# Backtest · {inputs.persona.capitalize()} on {inputs.ticker}",
            "",
            f"- Start: {inputs.start_date}",
            f"- Steps: {inputs.num_steps} × {inputs.step_weeks}w",
            f"- Trades (BUY signals): {len(returns)}",
            f"- Hit rate: {(f'{hit_rate * 100:.1f}%' if hit_rate is not None else '—')}",
            f"- Avg return per trade: "
            f"{(f'{avg_return * 100:+.2f}%' if avg_return is not None else '—')}",
            f"- Cumulative BUY-only return: "
            f"{(f'{cumulative * 100:+.2f}%' if cumulative is not None else '—')}",
            "",
            "| Date | Close | Signal | Fwd return |",
            "| --- | --- | --- | --- |",
            *rows,
        ]
    )

    return {
        "trades": len(returns),
        "hit_rate": hit_rate,
        "avg_return": avg_return,
        "cumulative_return": cumulative,
        "markdown": md,
    }
