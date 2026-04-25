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
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.agents.base import AgentContext, LLMAgent
from app.agents.prompt import contributor_user_message
from app.agents.registry import load_analyst, load_persona
from app.config import (
    ANALYST_BYLINES,
    COMPLIANCE_FOOTER_MD,
    FIRM_NAME,
    PERSONA_BYLINES,
    cost_usd,
)
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

    snapshot_as_of = (
        ctx.snapshot.get("as_of") if ctx.snapshot else None
    )
    snapshot_source = (
        ctx.snapshot.get("data_source", "yfinance") if ctx.snapshot else "yfinance"
    )
    # Parse meta from the persona's raw output BEFORE augmentation —
    # _augment_memo strips the structured **Rating/Target/Style** field
    # lines from the body since the cover and rating banner render them
    # separately. Re-parsing after that strip would lose them.
    memo_md = _augment_memo(
        memo_md,
        ticker=inputs.ticker,
        lead_persona=inputs.persona,
        contributors=list(ctx.persona_views.keys()),
        analysts=list(ctx.analyst_outputs.keys()),
        style=inputs.style,
        price_chart_url=price_chart_url,
        margin_chart_url=margin_chart_url,
        basket_chart_url=basket_chart_url,
        fundamentals_table=fundamentals_table,
        snapshot_as_of=snapshot_as_of,
        snapshot_source=snapshot_source,
    )
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
    ticker: str,
    lead_persona: str,
    contributors: list[str],
    analysts: list[str],
    style: str,
    price_chart_url: str | None,
    margin_chart_url: str | None,
    basket_chart_url: str | None,
    fundamentals_table: str | None,
    snapshot_as_of: str | None,
    snapshot_source: str,
) -> str:
    """Wrap the persona's text in firm chrome.

    Splice order: cover header → persona-stripped body → injected charts +
    financials → basket chart (if any) → compliance footer. A TOC is
    inserted between the cover and the body when the memo has more than
    five top-level (##) sections.
    """
    body = _strip_meta_lines(memo_md)
    figure = _Figure(start=1)

    head_parts: list[str] = []
    if price_chart_url:
        head_parts.append(
            figure.markdown(
                title="Price action — last 52 weeks",
                url=price_chart_url,
                source=snapshot_source,
                as_of=snapshot_as_of,
            )
        )
    if fundamentals_table:
        head_parts.append(fundamentals_table)
    if margin_chart_url:
        head_parts.append(
            figure.markdown(
                title="Margin trajectory — last eight quarters",
                url=margin_chart_url,
                source="financial-datasets.ai",
                as_of=snapshot_as_of,
            )
        )

    body = _splice_before_first_heading(body, head_parts)

    if basket_chart_url:
        body = body.rstrip() + "\n\n" + figure.markdown(
            title="Basket weights — long / short legs",
            url=basket_chart_url,
            source="memo basket block",
            as_of=snapshot_as_of,
        ) + "\n"

    cover = _render_cover(
        ticker=ticker,
        lead_persona=lead_persona,
        contributors=contributors,
        analysts=analysts,
        style=style,
    )
    toc = _render_toc(body)
    footer = COMPLIANCE_FOOTER_MD

    pieces = [cover.rstrip()]
    if toc:
        pieces.append(toc.rstrip())
    pieces.append(body.strip())
    pieces.append(footer.rstrip())
    return "\n\n".join(pieces)


_META_LINE_RE = re.compile(
    r"^\s*\*\*(Style|Anchor|Rating|Base target|Bull target|Bear target|Horizon):\*\*[^\n]*\n",
    re.MULTILINE,
)


def _strip_meta_lines(memo_md: str) -> str:
    """Remove the structured ** field lines** the persona emits at the top.

    They get carried via content_json + the rating banner, so leaving them
    in the markdown makes the rendered memo look duplicative.
    """
    return _META_LINE_RE.sub("", memo_md)


def _splice_before_first_heading(memo_md: str, parts: list[str]) -> str:
    if not parts:
        return memo_md
    addition = "\n\n" + "\n\n".join(parts) + "\n\n"
    lines = memo_md.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            before = "\n".join(lines[:idx]).rstrip()
            after = "\n".join(lines[idx:])
            return f"{before}\n{addition}{after}"
    return memo_md.rstrip() + addition


@dataclass
class _Figure:
    """Counter for figure-numbered captions across one memo."""

    start: int = 1

    def markdown(
        self,
        *,
        title: str,
        url: str,
        source: str,
        as_of: str | None,
    ) -> str:
        n = self.start
        self.start += 1
        as_of_s = f" · as of {as_of}" if as_of else ""
        return (
            f"**Figure {n}. {title}**\n\n"
            f"![Figure {n}]({url})\n\n"
            f"*Source: {source}{as_of_s}*"
        )


_TOC_HEADING_RE = re.compile(r"^##\s+(?!#)([^\n]+?)\s*$", re.MULTILINE)


def _render_toc(body: str) -> str:
    """Build a plain-list TOC when the memo has 6+ ## headings.

    Anchor links would need a markdown plugin in both renderers; the
    list-only form is decorative but renders cleanly everywhere.
    """
    headings = _TOC_HEADING_RE.findall(body)
    if len(headings) < 6:
        return ""
    items = [f"- {heading.strip()}" for heading in headings]
    return "## Contents\n\n" + "\n".join(items)


def _render_cover(
    *,
    ticker: str,
    lead_persona: str,
    contributors: list[str],
    analysts: list[str],
    style: str,
) -> str:
    """The chrome at the top of a memo: firm + doc type + date + bylines."""
    today = datetime.now(UTC).date().isoformat()
    doc_type = "Citrini view" if style == "citrini" else "Initiation"

    lead_card = _byline_card(lead_persona, kind="persona")
    contributor_cards = " · ".join(
        _byline_inline(name, kind="persona") for name in contributors
    ) or "(none)"
    analyst_cards = " · ".join(
        _byline_inline(name, kind="analyst") for name in analysts
    ) or "(none)"

    return (
        f"# {FIRM_NAME} · {doc_type} · {ticker.upper()}\n\n"
        f"**Date:** {today}  ·  **Document:** {doc_type}\n\n"
        f"**Lead author:** {lead_card}\n\n"
        f"**Contributors:** {contributor_cards}\n\n"
        f"**Analyst desk:** {analyst_cards}\n"
    )


def _byline_card(name: str, *, kind: str) -> str:
    """Long-form byline: 'Name · Role · email'."""
    src = PERSONA_BYLINES if kind == "persona" else ANALYST_BYLINES
    info = src.get(name, {"name": name.capitalize(), "email": ""})
    role = info.get("role")
    parts = [info.get("name", name.capitalize())]
    if role:
        parts.append(role)
    if info.get("email"):
        parts.append(info["email"])
    return "  ·  ".join(parts)


def _byline_inline(name: str, *, kind: str) -> str:
    """Short-form byline: 'Name (email)'."""
    src = PERSONA_BYLINES if kind == "persona" else ANALYST_BYLINES
    info = src.get(name, {"name": name.capitalize(), "email": ""})
    label = info.get("name", name.capitalize())
    email = info.get("email")
    return f"{label} ({email})" if email else label


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
