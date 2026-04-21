"""Market data tool.

CLAUDE.md §4 — abstract financial-datasets.ai + yfinance behind this module;
agents must never call either library directly. Phase 1 ships a yfinance
backend only; the financial-datasets.ai path lands in a later phase.

CLAUDE.md §13 — "Stub in tests — never hit a live market data provider in
tests." Tests monkey-patch `fetch_snapshot` / `fetch_snapshot_asof` /
`fetch_forward_return` in this module.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
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


async def fetch_snapshot_asof(ticker: str, as_of: date) -> dict[str, Any]:
    """Return a price-based snapshot of `ticker` as of `as_of`.

    Only price data is historical — yfinance doesn't expose point-in-time
    fundamentals, so this snapshot is deliberately narrower than the live
    one in `fetch_snapshot`.
    """
    ticker = ticker.strip().upper()
    try:
        return await asyncio.to_thread(_yfinance_snapshot_asof, ticker, as_of)
    except Exception as exc:
        logger.warning("market_data asof fetch failed for %s @ %s: %s", ticker, as_of, exc)
        return {
            "ticker": ticker,
            "as_of": as_of.isoformat(),
            "error": f"snapshot unavailable: {exc}",
        }


async def fetch_forward_return(
    ticker: str, from_date: date, to_date: date
) -> float | None:
    """Simple return from last close <= from_date to last close <= to_date."""
    ticker = ticker.strip().upper()
    try:
        return await asyncio.to_thread(
            _yfinance_forward_return, ticker, from_date, to_date
        )
    except Exception as exc:
        logger.warning(
            "market_data forward-return failed for %s %s→%s: %s",
            ticker,
            from_date,
            to_date,
            exc,
        )
        return None


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


def _yfinance_history_closes(ticker: str, start: date, end: date) -> list[tuple[date, float]]:
    import yfinance

    t = yfinance.Ticker(ticker)
    # auto_adjust=True so splits/dividends don't skew forward returns.
    hist = t.history(start=start, end=end + timedelta(days=1), auto_adjust=True)
    closes: list[tuple[date, float]] = []
    for idx, row in hist.iterrows():
        d = idx.date() if hasattr(idx, "date") else idx
        closes.append((d, float(row["Close"])))
    return closes


def _last_close_on_or_before(
    closes: list[tuple[date, float]], target: date
) -> tuple[date, float] | None:
    best: tuple[date, float] | None = None
    for d, c in closes:
        if d <= target and (best is None or d > best[0]):
            best = (d, c)
    return best


def _yfinance_snapshot_asof(ticker: str, as_of: date) -> dict[str, Any]:
    # Pull a year's worth of bars ending at as_of so we can compute the
    # rolling window indicators. One extra day of headroom covers weekends.
    window_start = as_of - timedelta(days=400)
    closes = _yfinance_history_closes(ticker, window_start, as_of)
    if not closes:
        return {
            "ticker": ticker,
            "as_of": as_of.isoformat(),
            "error": "no price history in window",
        }

    anchor = _last_close_on_or_before(closes, as_of)
    if anchor is None:
        return {
            "ticker": ticker,
            "as_of": as_of.isoformat(),
            "error": "no bar on or before as_of",
        }
    anchor_date, anchor_close = anchor

    year_back = [c for d, c in closes if (anchor_date - d).days <= 365]
    month_back = [c for d, c in closes if (anchor_date - d).days <= 28]

    def pct_return(series: list[float]) -> float | None:
        if len(series) < 2:
            return None
        return series[-1] / series[0] - 1.0

    return {
        "ticker": ticker,
        "as_of": anchor_date.isoformat(),
        "close": anchor_close,
        "return_52w": pct_return(year_back),
        "return_4w": pct_return(month_back),
        "high_52w": max(year_back) if year_back else None,
        "low_52w": min(year_back) if year_back else None,
        "weekly_closes_52w": _downsample_weekly(
            [(d, c) for d, c in closes if (anchor_date - d).days <= 365]
        ),
    }


def _downsample_weekly(
    closes: list[tuple[date, float]],
) -> list[dict[str, Any]]:
    if not closes:
        return []
    closes = sorted(closes, key=lambda x: x[0])
    by_week: dict[tuple[int, int], tuple[date, float]] = {}
    for d, c in closes:
        key = d.isocalendar()[:2]  # (iso_year, iso_week)
        by_week[key] = (d, c)
    return [
        {"date": d.isoformat(), "close": round(c, 4)}
        for d, c in sorted(by_week.values(), key=lambda x: x[0])
    ]


def _yfinance_forward_return(
    ticker: str, from_date: date, to_date: date
) -> float | None:
    # Pull an inclusive window that covers both anchors.
    closes = _yfinance_history_closes(
        ticker, from_date - timedelta(days=10), to_date + timedelta(days=10)
    )
    if not closes:
        return None
    start = _last_close_on_or_before(closes, from_date)
    end = _last_close_on_or_before(closes, to_date)
    if start is None or end is None or start[1] == 0:
        return None
    return end[1] / start[1] - 1.0
