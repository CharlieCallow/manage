"""Job REST + WebSocket routes. CLAUDE.md §6, §7, §9.

- POST /jobs                    create + enqueue a job
- GET  /jobs                    list recent jobs (lightweight)
- GET  /jobs/{id}/artifacts     artifacts produced by a job
- WS   /ws/jobs/{job_id}        stream events (replay on reconnect)

Runner persists every event to job_events so reconnects can replay (§7).
Enforces per-job budget (§9). Never retries on failure (§9, §14).
A bounded asyncio.Semaphore caps concurrent running jobs; additional jobs
sit in status='queued' until a slot frees up.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.agents.base import AgentContext, BudgetTracker
from app.agents.graphs.backtest import run_backtest
from app.agents.graphs.committee import run_committee
from app.agents.graphs.ideation import run_ideation
from app.agents.graphs.research import run_research
from app.config import settings
from app.schemas.events import ErrorEvent, JobDoneEvent, JobEvent, StatusEvent
from app.schemas.jobs import (
    ArtifactRow,
    BacktestInputs,
    CommitteeInputs,
    CreateJobRequest,
    CreateJobResponse,
    IdeationInputs,
    JobDetail,
    JobRow,
    JobSummary,
    ResearchInputs,
)
from app.store import db
from app.store.db import connection

logger = logging.getLogger(__name__)

router = APIRouter()

# Phase 1: fixed concurrency. Roster UI (Phase 2) can surface this later.
_JOB_CONCURRENCY = 2
_job_slot = asyncio.Semaphore(_JOB_CONCURRENCY)


# ---- in-process event bus --------------------------------------------------

_live_queues: dict[str, list[asyncio.Queue[JobEvent | None]]] = {}
_queues_lock = asyncio.Lock()

# Broadcast subscribers see every event across every job (Trading Floor).
_broadcast_queues: list[asyncio.Queue[tuple[str, JobEvent] | None]] = []
_broadcast_lock = asyncio.Lock()

# Per-job locks around persist+publish so seq numbers are strictly increasing
# even when multiple agents stream concurrently.
_event_locks: dict[str, asyncio.Lock] = {}


def _event_lock(job_id: str) -> asyncio.Lock:
    lock = _event_locks.get(job_id)
    if lock is None:
        lock = asyncio.Lock()
        _event_locks[job_id] = lock
    return lock


async def _publish(job_id: str, event: JobEvent) -> None:
    async with _queues_lock:
        queues = list(_live_queues.get(job_id, ()))
    for q in queues:
        await q.put(event)
    async with _broadcast_lock:
        broadcasts = list(_broadcast_queues)
    for b in broadcasts:
        await b.put((job_id, event))


async def _subscribe_broadcast() -> asyncio.Queue[tuple[str, JobEvent] | None]:
    q: asyncio.Queue[tuple[str, JobEvent] | None] = asyncio.Queue()
    async with _broadcast_lock:
        _broadcast_queues.append(q)
    return q


async def _unsubscribe_broadcast(
    q: asyncio.Queue[tuple[str, JobEvent] | None],
) -> None:
    async with _broadcast_lock:
        if q in _broadcast_queues:
            _broadcast_queues.remove(q)


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
    async with _queues_lock:
        queues = list(_live_queues.get(job_id, ()))
    for q in queues:
        await q.put(None)
    _event_locks.pop(job_id, None)


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
    async with _event_lock(job_id):
        _persist_event(job_id, event)
        await _publish(job_id, event)


async def _run_job(job_id: str, req: CreateJobRequest) -> None:
    ctx: AgentContext | None = None
    try:
        async with _job_slot:
            _update_job(job_id, status="running", started_at=_now())

            job = _load_job(job_id)
            if job is None:  # pragma: no cover — defensive
                return

            ctx = AgentContext(
                job=job,
                client=_make_anthropic_client(),
                budget=BudgetTracker(budget_usd=job.budget_usd),
            )

            if req.type == "research":
                stream = run_research(
                    job, ResearchInputs.model_validate(req.inputs), ctx
                )
            elif req.type == "committee":
                stream = run_committee(
                    job, CommitteeInputs.model_validate(req.inputs), ctx
                )
            elif req.type == "backtest":
                stream = run_backtest(
                    job, BacktestInputs.model_validate(req.inputs), ctx
                )
            elif req.type == "ideation":
                stream = run_ideation(
                    job, IdeationInputs.model_validate(req.inputs), ctx
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"job type not implemented: {req.type}",
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
                    await _emit(job_id, JobDoneEvent(cost_usd=ctx.budget.spent_usd))
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
        spent = ctx.budget.spent_usd if ctx else 0.0
        _update_job(
            job_id,
            status="error",
            cost_usd=spent,
            finished_at=_now(),
            error=str(exc),
        )
        await _emit(job_id, ErrorEvent(message=str(exc)))
        # job_done always closes the stream — error path included — so the
        # renderer has a single terminating signal.
        await _emit(job_id, JobDoneEvent(cost_usd=spent))
    finally:
        await _finalize(job_id)


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


# ---- routes ----------------------------------------------------------------


def enqueue_job(req: CreateJobRequest) -> str:
    """Shared path for POST /jobs and internal spawners (e.g. idea approval).

    Runs the same validation + daily-cap + insert + task-spawn dance as the
    public endpoint, minus the HTTP response wrapping. Raises HTTPException
    on validation or budget errors.
    """
    try:
        if req.type == "research":
            ResearchInputs.model_validate(req.inputs)
        elif req.type == "committee":
            CommitteeInputs.model_validate(req.inputs)
        elif req.type == "backtest":
            BacktestInputs.model_validate(req.inputs)
        elif req.type == "ideation":
            IdeationInputs.model_validate(req.inputs)
        else:
            raise HTTPException(
                status_code=400, detail=f"job type not implemented: {req.type}"
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    budget = (
        req.budget_usd
        if req.budget_usd is not None
        else settings.default_job_budget_usd
    )

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
            (job_id, req.type, json.dumps(req.inputs), "queued", budget),
        )

    asyncio.create_task(_run_job(job_id, req))
    return job_id


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(req: CreateJobRequest) -> CreateJobResponse:
    return CreateJobResponse(job_id=enqueue_job(req))


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(limit: int = 50) -> list[JobSummary]:
    rows = db.list_recent_jobs(limit=limit)
    summaries: list[JobSummary] = []
    for row in rows:
        inputs: dict[str, Any] = {}
        with contextlib.suppress(json.JSONDecodeError):
            inputs = json.loads(row.get("inputs_json") or "{}")
        summaries.append(
            JobSummary(
                id=row["id"],
                type=row["type"],
                status=row["status"],
                cost_usd=row["cost_usd"],
                budget_usd=row["budget_usd"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                error=row["error"],
                ticker=inputs.get("ticker"),
                persona=inputs.get("persona"),
            )
        )
    return summaries


@router.get("/jobs/{job_id}/artifacts", response_model=list[ArtifactRow])
async def list_job_artifacts(job_id: str) -> list[ArtifactRow]:
    rows = db.list_artifacts_for_job(job_id)
    return [ArtifactRow(**row) for row in rows]


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(job_id: str) -> JobDetail:
    with connection() as conn:
        cur = conn.execute(
            "SELECT id, type, status, cost_usd, budget_usd, started_at, "
            "finished_at, error, inputs_json FROM jobs WHERE id = ?",
            (job_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    inputs: dict[str, Any] = {}
    with contextlib.suppress(json.JSONDecodeError):
        inputs = json.loads(row["inputs_json"] or "{}")
    return JobDetail(
        id=row["id"],
        type=row["type"],
        status=row["status"],
        cost_usd=row["cost_usd"],
        budget_usd=row["budget_usd"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error=row["error"],
        inputs=inputs,
    )


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

    # Snapshot DB events and subscribe under the same lock _emit uses, so
    # no event can land between read-DB and subscribe — otherwise live
    # events emitted during replay would be lost (they'd go to a queue
    # list that doesn't yet contain ours).
    async with _event_lock(job_id):
        replay = _load_events(job_id)
        queue = await _subscribe(job_id)

    for event in replay:
        await websocket.send_json(event.model_dump())

    if job.status in {"done", "error", "budget_exceeded"}:
        await _unsubscribe(job_id, queue)
        await websocket.close()
        return
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


@router.websocket("/ws/live")
async def stream_live(websocket: WebSocket) -> None:
    """Broadcast of every event on every job. CLAUDE.md §7 — used by the
    Trading Floor to render ambient agent activity."""
    await websocket.accept()
    queue = await _subscribe_broadcast()
    try:
        while True:
            if websocket.application_state != WebSocketState.CONNECTED:
                break
            item = await queue.get()
            if item is None:
                break
            job_id, event = item
            await websocket.send_json(
                {"job_id": job_id, "event": event.model_dump()}
            )
    except WebSocketDisconnect:
        pass
    finally:
        await _unsubscribe_broadcast(queue)
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close()
