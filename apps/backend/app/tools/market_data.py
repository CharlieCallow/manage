"""Market data tool.

CLAUDE.md §4 — abstract financial-datasets.ai + yfinance behind this module;
agents must never call either library directly. Phase 1 ships a yfinance
backend only; the financial-datasets.ai path lands in a later phase.

CLAUDE.md §13 — "Stub in tests — never hit a live market data provider in
tests." Tests monkey-patch `fetch_snapshot` in this module.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def fetch_snapshot(ticker: str) -> dict[str, Any]:
    """Return a compact dict of the numbers analysts care about.

    Never raises on data-provider failure — returns a snapshot with an
    `error` field so the graph can continue and the agents can acknowledge
    missing data rather than invent it.
    """
    ticker = ticker.strip().upper()
    try:
        raw = await asyncio.to_thread(_yfinance_snapshot, ticker)
    except Exception as exc:  # never let data failures kill a job
        logger.warning("market_data fetch failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "error": f"snapshot unavailable: {exc}"}
    return raw


def _yfinance_snapshot(ticker: str) -> dict[str, Any]:
    import yfinance  # local import so tests and non-data flows don't pay the cost

    t = yfinance.Ticker(ticker)
    info = t.info or {}
    fast = getattr(t, "fast_info", {}) or {}

    def pick(*keys: str) -> Any:
        for k in keys:
            v = info.get(k)
            if v not in (None, ""):
                return v
        return None

    return {
        "ticker": ticker,
        "name": pick("longName", "shortName"),
        "sector": pick("sector"),
        "industry": pick("industry"),
        "price": fast.get("last_price") or pick("currentPrice", "regularMarketPrice"),
        "market_cap": fast.get("market_cap") or pick("marketCap"),
        "pe_trailing": pick("trailingPE"),
        "pe_forward": pick("forwardPE"),
        "ev_to_ebitda": pick("enterpriseToEbitda"),
        "price_to_book": pick("priceToBook"),
        "dividend_yield": pick("dividendYield"),
        "profit_margin": pick("profitMargins"),
        "operating_margin": pick("operatingMargins"),
        "gross_margin": pick("grossMargins"),
        "revenue": pick("totalRevenue"),
        "revenue_growth": pick("revenueGrowth"),
        "earnings_growth": pick("earningsGrowth"),
        "return_on_equity": pick("returnOnEquity"),
        "total_cash": pick("totalCash"),
        "total_debt": pick("totalDebt"),
        "free_cash_flow": pick("freeCashflow"),
        "52w_high": pick("fiftyTwoWeekHigh"),
        "52w_low": pick("fiftyTwoWeekLow"),
        "beta": pick("beta"),
    }
