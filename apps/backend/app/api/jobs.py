"""Job REST + WebSocket routes. CLAUDE.md §6, §7, §9.

- POST /jobs            create + enqueue a job
- WS  /ws/jobs/{job_id} stream events (with replay on reconnect)

Runner persists every event to job_events so reconnects can replay (§7).
Enforces per-job budget (§9). Never retries on failure (§9, §14).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.agents.base import AgentContext, BudgetTracker
from app.agents.graphs.research import run_research
from app.config import settings
from app.schemas.events import ErrorEvent, JobDoneEvent, JobEvent, StatusEvent
from app.schemas.jobs import CreateJobRequest, CreateJobResponse, JobRow
from app.store.db import connection

logger = logging.getLogger(__name__)

router = APIRouter()


# ---- in-process event bus --------------------------------------------------

# One queue per active job. Dropped after the job completes.
_live_queues: dict[str, list[asyncio.Queue[JobEvent | None]]] = {}
_queues_lock = asyncio.Lock()


async def _publish(job_id: str, event: JobEvent) -> None:
    async with _queues_lock:
        queues = list(_live_queues.get(job_id, ()))
    for q in queues:
        await q.put(event)


async def _subscribe(job_id: str) -> asyncio.Queue[JobEvent | None]:
    q: asyncio.Queue[JobEvent | None] = asyncio.Queue()
    async with _queues_lock:
        _live_queues.setdefault(job_id, []).append(q)
    return q


async def _unsubscribe(job_id: str, q: asyncio.Queue[JobEvent | None]) -> None:
    async with _queues_lock:
        queues = _live_queues.get(job_id, [])
        if q in queues:
            queues.remove(q)
        if not queues:
            _live_queues.pop(job_id, None)


async def _finalize(job_id: str) -> None:
    """Tell every live subscriber the stream is done."""
    async with _queues_lock:
        queues = list(_live_queues.get(job_id, ()))
    for q in queues:
        await q.put(None)


# ---- persistence -----------------------------------------------------------


def _persist_event(job_id: str, event: JobEvent) -> None:
    payload = event.model_dump_json()
    with connection() as conn:
        cur = conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM job_events WHERE job_id = ?",
            (job_id,),
        )
        seq = int(cur.fetchone()[0])
        conn.execute(
            "INSERT INTO job_events (job_id, seq, payload) VALUES (?, ?, ?)",
            (job_id, seq, payload),
        )


def _load_events(job_id: str) -> list[JobEvent]:
    from app.schemas.events import EventEnvelope

    with connection() as conn:
        cur = conn.execute(
            "SELECT payload FROM job_events WHERE job_id = ? ORDER BY seq",
            (job_id,),
        )
        rows = cur.fetchall()
    events: list[JobEvent] = []
    for row in rows:
        env = EventEnvelope.model_validate({"event": json.loads(row[0])})
        events.append(env.event)
    return events


def _load_job(job_id: str) -> JobRow | None:
    with connection() as conn:
        cur = conn.execute(
            "SELECT id, type, status, cost_usd, budget_usd, started_at, "
            "finished_at, error FROM jobs WHERE id = ?",
            (job_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return JobRow(
        id=row["id"],
        type=row["type"],
        status=row["status"],
        cost_usd=row["cost_usd"],
        budget_usd=row["budget_usd"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error=row["error"],
    )


_JOB_UPDATABLE_COLS: frozenset[str] = frozenset(
    {"status", "cost_usd", "started_at", "finished_at", "error"}
)


def _update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    bad = set(fields) - _JOB_UPDATABLE_COLS
    if bad:
        raise ValueError(f"refusing to update unknown job columns: {sorted(bad)}")
    cols = ", ".join(f"{k} = ?" for k in fields)
    sql = f"UPDATE jobs SET {cols} WHERE id = ?"  # noqa: S608 — keys validated above
    with connection() as conn:
        conn.execute(sql, (*fields.values(), job_id))


# ---- runner ----------------------------------------------------------------


def _make_anthropic_client() -> AsyncAnthropic:
    """Split out so tests can monkey-patch the factory."""
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


async def _emit(job_id: str, event: JobEvent) -> None:
    _persist_event(job_id, event)
    await _publish(job_id, event)


async def _run_job(job_id: str, req: CreateJobRequest) -> None:
    _update_job(job_id, status="running", started_at=_now())

    job = _load_job(job_id)
    if job is None:  # pragma: no cover — defensive
        return

    ctx = AgentContext(
        job=job,
        client=_make_anthropic_client(),
        budget=BudgetTracker(budget_usd=job.budget_usd),
    )

    try:
        if req.type == "research":
            stream = run_research(job, req.inputs, ctx)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"job type not implemented in Phase 0: {req.type}",
            )

        async for event in stream:
            await _emit(job_id, event)
            if isinstance(event, StatusEvent) and event.status == "budget_exceeded":
                _update_job(
                    job_id,
                    status="budget_exceeded",
                    cost_usd=ctx.budget.spent_usd,
                    finished_at=_now(),
                )
                await _emit(
                    job_id, JobDoneEvent(cost_usd=ctx.budget.spent_usd)
                )
                return

        _update_job(
            job_id,
            status="done",
            cost_usd=ctx.budget.spent_usd,
            finished_at=_now(),
        )
        await _emit(job_id, JobDoneEvent(cost_usd=ctx.budget.spent_usd))

    except Exception as exc:  # surface to user (§11)
        logger.exception("job %s failed", job_id)
        _update_job(
            job_id,
            status="error",
            cost_usd=ctx.budget.spent_usd,
            finished_at=_now(),
            error=str(exc),
        )
        await _emit(job_id, ErrorEvent(message=str(exc)))
    finally:
        await _finalize(job_id)


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


# ---- routes ----------------------------------------------------------------


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(req: CreateJobRequest) -> CreateJobResponse:
    # Explicit None-check: 0.0 is a legitimate budget (zero-budget test/gate).
    budget = (
        req.budget_usd
        if req.budget_usd is not None
        else settings.default_job_budget_usd
    )

    # Daily cap check (§9).
    with connection() as conn:
        cur = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM jobs "
            "WHERE date(started_at) = date('now')"
        )
        spent_today = float(cur.fetchone()[0])
    if spent_today + budget > settings.daily_budget_usd:
        raise HTTPException(
            status_code=429,
            detail=(
                f"daily budget would be exceeded: spent={spent_today:.2f} "
                f"+ budget={budget:.2f} > cap={settings.daily_budget_usd:.2f}"
            ),
        )

    job_id = str(uuid.uuid4())
    with connection() as conn:
        conn.execute(
            "INSERT INTO jobs (id, type, inputs_json, status, budget_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                job_id,
                req.type,
                req.inputs.model_dump_json(),
                "queued",
                budget,
            ),
        )

    asyncio.create_task(_run_job(job_id, req))
    return CreateJobResponse(job_id=job_id)


@router.websocket("/ws/jobs/{job_id}")
async def stream_job(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()

    job = _load_job(job_id)
    if job is None:
        await websocket.send_json(
            ErrorEvent(message=f"unknown job: {job_id}").model_dump()
        )
        await websocket.close()
        return

    # Replay persisted events so reconnects resume cleanly (§7).
    replay = _load_events(job_id)
    for event in replay:
        await websocket.send_json(event.model_dump())

    # If the job is already terminal, we're done.
    if job.status in {"done", "error", "budget_exceeded"}:
        await websocket.close()
        return

    queue = await _subscribe(job_id)
    try:
        async for event in _drain(queue):
            if websocket.application_state != WebSocketState.CONNECTED:
                break
            await websocket.send_json(event.model_dump())
    except WebSocketDisconnect:
        pass
    finally:
        await _unsubscribe(job_id, queue)
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close()


async def _drain(queue: asyncio.Queue[JobEvent | None]) -> AsyncIterator[JobEvent]:
    while True:
        item = await queue.get()
        if item is None:
            return
        yield item
