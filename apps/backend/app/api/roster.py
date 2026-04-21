"""Roster CRUD routes. CLAUDE.md §8, §13.

Personas and analysts share the same schema (§5), so one helper backs the
four routes below. Only prompt_template, model, and enabled are PATCHable.
Renaming either requires a migration (§14).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.roster import PerformanceRow, RosterRow, RosterUpdate
from app.store import db

router = APIRouter()


def _row_to_model(row: dict[str, Any]) -> RosterRow:
    return RosterRow(
        id=int(row["id"]),
        name=str(row["name"]),
        prompt_template=str(row["prompt_template"]),
        model=str(row["model"]),
        enabled=bool(row["enabled"]),
        created_at=str(row["created_at"]),
    )


async def _list(table: str) -> list[RosterRow]:
    return [_row_to_model(r) for r in db.list_roster(table)]


async def _get(table: str, name: str) -> RosterRow:
    row = db.get_roster_row(table, name)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"{table[:-1]} '{name}' not found"
        )
    return _row_to_model(row)


async def _patch(table: str, name: str, body: RosterUpdate) -> RosterRow:
    # model_fields_set excludes defaults — a missing field never writes None.
    fields = {k: getattr(body, k) for k in body.model_fields_set}
    ok = db.update_roster_row(table, name, fields)
    if not ok:
        raise HTTPException(
            status_code=404, detail=f"{table[:-1]} '{name}' not found"
        )
    row = db.get_roster_row(table, name)
    assert row is not None  # we just updated it
    return _row_to_model(row)


@router.get("/personas", response_model=list[RosterRow])
async def list_personas() -> list[RosterRow]:
    return await _list("personas")


@router.get("/personas/{name}", response_model=RosterRow)
async def get_persona(name: str) -> RosterRow:
    return await _get("personas", name)


@router.patch("/personas/{name}", response_model=RosterRow)
async def patch_persona(name: str, body: RosterUpdate) -> RosterRow:
    return await _patch("personas", name, body)


@router.get("/analysts", response_model=list[RosterRow])
async def list_analysts() -> list[RosterRow]:
    return await _list("analysts")


@router.get("/analysts/{name}", response_model=RosterRow)
async def get_analyst(name: str) -> RosterRow:
    return await _get("analysts", name)


@router.patch("/analysts/{name}", response_model=RosterRow)
async def patch_analyst(name: str, body: RosterUpdate) -> RosterRow:
    return await _patch("analysts", name, body)


@router.get("/personas/{name}/performance", response_model=list[PerformanceRow])
async def list_persona_performance(name: str) -> list[PerformanceRow]:
    row = db.get_roster_row("personas", name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"persona '{name}' not found")
    rows = db.list_performance_for_persona(int(row["id"]))
    return [PerformanceRow(**r) for r in rows]
