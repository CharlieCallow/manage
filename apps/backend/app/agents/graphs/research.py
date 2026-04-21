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
from datetime import UTC, datetime
from typing import Any

from app.agents.base import AgentContext, LLMAgent
from app.agents.prompt import contributor_user_message
from app.agents.registry import load_analyst, load_persona
from app.config import cost_usd
from app.schemas.events import (
    ArtifactEvent,
    ArtifactPayload,
    JobEvent,
    StatusEvent,
    TokenEvent,
)
from app.schemas.jobs import JobRow, ResearchInputs
from app.store import db
from app.tools import charts, market_data
from app.tools import financial_datasets as fd

# Non-lead personas run on Haiku for their quick takes — CLAUDE.md §8
# "hot-loop calls" pattern. Keeps research total ≤ ~$0.15 on Sonnet.
_CONTRIBUTOR_MODEL = "claude-haiku-4-5"

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

    # 1. Snapshot, then fundamentals series (serial).
    # fd.ai short-circuits if no key is set.
    yield StatusEvent(agent="graph", status="fetching_market_data")
    ctx.snapshot = await market_data.fetch_snapshot(inputs.ticker)
    try:
        fundamentals_series = await fd.fetch_fundamentals_series(
            inputs.ticker, datetime.now(UTC).date()
        )
    except Exception:
        fundamentals_series = None

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

    # 3. Team views — every enabled persona except the lead contributes a
    # short take on Haiku. Their views feed the lead's synthesis.
    contributor_names = _contributor_personas(exclude=inputs.persona)
    if contributor_names:
        async for event in _run_contributor_views(
            contributor_names, job, ctx
        ):
            yield event

    if ctx.budget.exceeded():
        yield StatusEvent(agent="graph", status="budget_exceeded")
        return

    # 4. Lead persona synthesizes the memo, with analyst outputs + team views
    # both available in ctx.
    persona = load_persona(inputs.persona)
    memo_chunks: list[str] = []
    async for event in persona.run(job, ctx):
        if isinstance(event, TokenEvent):
            memo_chunks.append(event.text)
        yield event

    # 4. Chart + table rendering. Basket chart needs the parsed meta, so it
    # happens after synthesis; the rest doesn't depend on the memo.
    price_chart_url = _render_price_chart(job.id, ctx.snapshot)
    margin_chart_url = _render_margin_chart(job.id, fundamentals_series)
    fundamentals_table = _render_fundamentals_table(ctx.snapshot)

    memo_md = "".join(memo_chunks).strip()
    if not memo_md:
        return

    meta = _parse_memo_meta(memo_md)
    basket_chart_url = _render_basket_chart(job.id, meta.get("basket"))

    memo_md = _augment_memo(
        memo_md,
        price_chart_url=price_chart_url,
        margin_chart_url=margin_chart_url,
        basket_chart_url=basket_chart_url,
        fundamentals_table=fundamentals_table,
    )
    # Re-parse AFTER augmentation so the artifact's parsed meta reflects any
    # structure the injected content added (e.g. the basket stays the same
    # since the raw BASKET block is unchanged).
    meta = _parse_memo_meta(memo_md)
    content_json: dict[str, Any] = {
        "ticker": inputs.ticker,
        "persona": inputs.persona,
        "style": inputs.style,
        "analyst_outputs": ctx.analyst_outputs,
        "price_chart_url": price_chart_url,
        "margin_chart_url": margin_chart_url,
        "basket_chart_url": basket_chart_url,
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


def _render_price_chart(
    job_id: str, snapshot: dict[str, Any] | None
) -> str | None:
    if not snapshot:
        return None
    try:
        png = charts.render_price_chart(snapshot)
    except Exception:
        return None
    if not png:
        return None
    try:
        charts.save_chart_png(job_id, "price", png)
    except Exception:
        return None
    return charts.chart_url(job_id, "price")


def _render_margin_chart(
    job_id: str, series: list[dict[str, Any]] | None
) -> str | None:
    if not series:
        return None
    try:
        png = charts.render_margin_trajectory(series)
    except Exception:
        return None
    if not png:
        return None
    try:
        charts.save_chart_png(job_id, "margins", png)
    except Exception:
        return None
    return charts.chart_url(job_id, "margins")


def _render_basket_chart(
    job_id: str, basket: dict[str, list[dict[str, Any]]] | None
) -> str | None:
    if not basket:
        return None
    try:
        png = charts.render_basket_chart(basket)
    except Exception:
        return None
    if not png:
        return None
    try:
        charts.save_chart_png(job_id, "basket", png)
    except Exception:
        return None
    return charts.chart_url(job_id, "basket")


_FUNDAMENTALS_LABELS: list[tuple[str, str, str]] = [
    # (key, label, format spec — "x1" → %, "m" → millions, "n" → number)
    ("pe_ratio", "P/E (TTM)", "n"),
    ("pe_forward", "P/E (forward)", "n"),
    ("price_to_book", "P/B", "n"),
    ("ev_to_ebitda", "EV / EBITDA", "n"),
    ("gross_margin", "Gross margin", "x1"),
    ("operating_margin", "Operating margin", "x1"),
    ("net_margin", "Net margin", "x1"),
    ("return_on_equity", "ROE", "x1"),
    ("revenue_growth", "Revenue growth", "x1"),
    ("free_cash_flow_growth", "FCF growth", "x1"),
    ("revenue", "Revenue (TTM)", "m"),
    ("free_cash_flow", "Free cash flow", "m"),
    ("total_debt", "Total debt", "m"),
    ("cash_and_equivalents", "Cash & equivalents", "m"),
]


def _format_val(value: float | int | None, kind: str) -> str:
    if value is None:
        return "—"
    try:
        if kind == "x1":  # fraction → percent
            return f"{float(value) * 100:+.2f}%"
        if kind == "m":
            v = float(value)
            for unit, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
                if abs(v) >= scale:
                    return f"${v / scale:,.2f}{unit}"
            return f"${v:,.0f}"
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _render_fundamentals_table(snapshot: dict[str, Any] | None) -> str | None:
    if not snapshot:
        return None
    fundamentals = snapshot.get("fundamentals") or {}
    if not fundamentals:
        return None
    rows: list[str] = []
    for key, label, kind in _FUNDAMENTALS_LABELS:
        val = fundamentals.get(key)
        if val is None:
            continue
        rows.append(f"| {label} | {_format_val(val, kind)} |")
    if not rows:
        return None
    report_period = fundamentals.get("report_period")
    header = "| Metric | Value |\n| --- | --- |\n"
    trailing = (
        f"\n\n*As-of report period: {report_period}*"
        if report_period
        else ""
    )
    return "## Point-in-time financials\n\n" + header + "\n".join(rows) + trailing


def _augment_memo(
    memo_md: str,
    *,
    price_chart_url: str | None,
    margin_chart_url: str | None,
    basket_chart_url: str | None,
    fundamentals_table: str | None,
) -> str:
    """Inject charts and the financials table into the memo body.

    Price chart + financials table go at the top (after the header fields,
    before the first ##). Margin trajectory rides just below. Basket chart
    lands at the very end of the memo so it sits next to the basket block.
    """
    head_parts: list[str] = []
    if price_chart_url:
        head_parts.append(f"![Price chart]({price_chart_url})")
    if fundamentals_table:
        head_parts.append(fundamentals_table)
    if margin_chart_url:
        head_parts.append(f"![Margin trajectory]({margin_chart_url})")

    updated = memo_md
    if head_parts:
        addition = "\n\n" + "\n\n".join(head_parts) + "\n\n"
        lines = updated.splitlines()
        spliced = False
        for idx, line in enumerate(lines):
            if line.startswith("## "):
                before = "\n".join(lines[:idx]).rstrip()
                after = "\n".join(lines[idx:])
                updated = f"{before}\n{addition}{after}"
                spliced = True
                break
        if not spliced:
            updated = updated.rstrip() + addition

    if basket_chart_url:
        updated = updated.rstrip() + (
            f"\n\n![Basket weights]({basket_chart_url})\n"
        )
    return updated


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


def _contributor_personas(exclude: str) -> list[str]:
    """Enabled persona names minus the lead."""
    rows = db.list_roster("personas")
    return [
        str(r["name"])
        for r in rows
        if bool(r.get("enabled", 1)) and r["name"] != exclude
    ]


async def _run_contributor_views(
    names: list[str], job: JobRow, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    """Parallel quick-take from every non-lead persona on Haiku.

    Each contributor's streamed tokens surface under its persona name so
    the UI can render a dedicated panel. The final text lands in
    ctx.persona_views for the lead synthesis step to pick up.
    """
    queue: asyncio.Queue[tuple[str, JobEvent] | tuple[str, None]] = asyncio.Queue()
    buffers: dict[str, list[str]] = {n: [] for n in names}

    async def drain(name: str) -> None:
        try:
            async for event in _run_contributor(name, job, ctx):
                if isinstance(event, TokenEvent):
                    buffers[name].append(event.text)
                await queue.put((name, event))
        finally:
            await queue.put((name, None))

    tasks = [asyncio.create_task(drain(n)) for n in names]
    done = 0
    try:
        while done < len(names):
            _, event = await queue.get()
            if event is None:
                done += 1
                continue
            yield event
    finally:
        await asyncio.gather(*tasks, return_exceptions=False)

    for name, chunks in buffers.items():
        ctx.persona_views[name] = "".join(chunks).strip()


async def _run_contributor(
    name: str, job: JobRow, ctx: AgentContext
) -> AsyncIterator[JobEvent]:
    """Run one contributor persona on Haiku and stream tokens + status."""
    row = db.get_persona_by_name(name)
    if row is None:
        return
    if ctx.budget.exceeded():
        yield StatusEvent(agent=name, status="budget_exceeded")
        return

    yield StatusEvent(agent=name, status="thinking")

    user_message = contributor_user_message(
        ticker=ctx.ticker or "(unspecified)",
        snapshot=ctx.snapshot,
        analyst_outputs=ctx.analyst_outputs,
    )

    input_tokens = 0
    output_tokens = 0
    async with ctx.client.messages.stream(
        model=_CONTRIBUTOR_MODEL,
        max_tokens=240,
        system=str(row["prompt_template"]),
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        async for chunk in stream.text_stream:
            if chunk:
                yield TokenEvent(agent=name, text=chunk)
            if ctx.budget.exceeded():
                yield StatusEvent(agent=name, status="budget_exceeded")
                return
        final = await stream.get_final_message()
        input_tokens = final.usage.input_tokens
        output_tokens = final.usage.output_tokens

    call_cost = cost_usd(_CONTRIBUTOR_MODEL, input_tokens, output_tokens)
    ctx.budget.charge(call_cost)
    db.log_api_call(
        job_id=ctx.job.id,
        model=_CONTRIBUTOR_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=call_cost,
    )
    yield StatusEvent(agent=name, status="done")
