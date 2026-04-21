"""Ideas CRUD + approval-spawns-research. See the ideation graph for how
candidates land in the `ideas` table; this module manages their lifecycle.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.jobs import enqueue_job
from app.schemas.ideas import ApproveResult, Idea, IdeaDecision, IdeaStatus
from app.schemas.jobs import CreateJobRequest
from app.store import db

router = APIRouter()


def _to_model(row: dict[str, Any]) -> Idea:
    status = str(row["status"])
    if status not in ("pending", "approved", "dismissed"):
        raise ValueError(f"unexpected idea status in DB: {status}")
    return Idea(
        id=int(row["id"]),
        ideation_job_id=str(row["ideation_job_id"]),
        persona=str(row["persona"]),
        ticker=str(row["ticker"]),
        thesis=str(row["thesis"]),
        status=status,
        research_job_id=(
            str(row["research_job_id"]) if row.get("research_job_id") else None
        ),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


@router.get("/ideas", response_model=list[Idea])
async def list_ideas(
    status: IdeaStatus | None = None,
    ideation_job_id: str | None = None,
    limit: int = 200,
) -> list[Idea]:
    rows = db.list_ideas(
        status=status, ideation_job_id=ideation_job_id, limit=limit
    )
    return [_to_model(r) for r in rows]


@router.patch("/ideas/{idea_id}", response_model=ApproveResult)
async def decide_idea(idea_id: int, body: IdeaDecision) -> ApproveResult:
    row = db.get_idea(idea_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"idea {idea_id} not found")
    if row["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"idea {idea_id} already {row['status']}",
        )

    research_job_id: str | None = None
    if body.status == "approved":
        # Spawn a research job using the persona + ticker + thesis (as framing).
        req = CreateJobRequest(
            type="research",
            inputs={
                "persona": row["persona"],
                "ticker": row["ticker"],
                "prompt": row["thesis"],
            },
        )
        research_job_id = enqueue_job(req)

    db.update_idea_status(idea_id, body.status, research_job_id)
    updated = db.get_idea(idea_id)
    assert updated is not None  # we just updated it
    return ApproveResult(idea=_to_model(updated), research_job_id=research_job_id)
