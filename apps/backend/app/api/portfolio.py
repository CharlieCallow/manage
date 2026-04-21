"""Portfolio CRUD + daily spend. CLAUDE.md §5, §9."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas.portfolio import (
    DailySpend,
    ModelSpend,
    PortfolioPosition,
    UpsertPosition,
)
from app.store import db

router = APIRouter()


def _row(row: dict[str, Any]) -> PortfolioPosition:
    return PortfolioPosition(
        id=int(row["id"]),
        ticker=str(row["ticker"]).upper(),
        qty=float(row["qty"]),
        avg_price=float(row["avg_price"]),
        updated_at=str(row["updated_at"]),
    )


@router.get("/portfolio", response_model=list[PortfolioPosition])
async def list_portfolio() -> list[PortfolioPosition]:
    return [_row(r) for r in db.list_portfolio()]


@router.put("/portfolio/{ticker}", response_model=PortfolioPosition)
async def upsert_position(ticker: str, body: UpsertPosition) -> PortfolioPosition:
    canonical = ticker.strip().upper()
    if canonical != body.ticker.strip().upper():
        raise HTTPException(
            status_code=400, detail="ticker in path must match body"
        )
    db.upsert_portfolio_position(canonical, body.qty, body.avg_price)
    # Return the up-to-date row.
    for row in db.list_portfolio():
        if row["ticker"].upper() == canonical:
            return _row(row)
    raise HTTPException(status_code=500, detail="failed to load upserted position")


@router.delete("/portfolio/{position_id}")
async def delete_position(position_id: int) -> dict[str, bool]:
    ok = db.delete_portfolio_position(position_id)
    if not ok:
        raise HTTPException(status_code=404, detail="position not found")
    return {"deleted": True}


@router.get("/spend/today", response_model=DailySpend)
async def spend_today() -> DailySpend:
    data = db.daily_spend()
    return DailySpend(
        total_usd=float(data["total_usd"]),
        input_tokens=int(data["input_tokens"]),
        output_tokens=int(data["output_tokens"]),
        by_model=[ModelSpend(**m) for m in data["by_model"]],
        daily_cap_usd=float(settings.daily_budget_usd),
    )
