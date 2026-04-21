"""Portfolio + spend wire types. CLAUDE.md §5, §9."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PortfolioPosition(BaseModel):
    id: int
    ticker: str
    qty: float
    avg_price: float
    updated_at: str


class UpsertPosition(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    qty: float
    avg_price: float = Field(ge=0)


class ModelSpend(BaseModel):
    model: str
    cost: float
    input_tokens: int
    output_tokens: int
    calls: int


class DailySpend(BaseModel):
    total_usd: float
    input_tokens: int
    output_tokens: int
    by_model: list[ModelSpend]
    daily_cap_usd: float
