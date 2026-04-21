"""Market data tool.

CLAUDE.md §4 — abstract financial-datasets.ai + yfinance behind this module;
agents must never call either library directly. When
`FINANCIAL_DATASETS_API_KEY` is set the orchestrator prefers fd.ai for both
prices and (crucially) point-in-time fundamentals, and falls back to
yfinance for prices when fd.ai is disabled or errors.

CLAUDE.md §13 — "Stub in tests — never hit a live market data provider in
tests." Tests monkey-patch `fetch_snapshot` / `fetch_snapshot_asof` /
`fetch_forward_return` in this module.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from app.tools import financial_datasets as fd

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
        raw = {"ticker": ticker, "error": f"snapshot unavailable: {exc}"}

    fundamentals = await fd.fetch_fundamentals_live(ticker)
    if fundamentals:
        raw["fundamentals"] = fundamentals
        raw["data_source"] = "financial-datasets.ai+yfinance"
    else:
        raw["data_source"] = "yfinance"
    return raw


async def fetch_snapshot_asof(ticker: str, as_of: date) -> dict[str, Any]:
    """Return a price-based snapshot of `ticker` as of `as_of`, augmented
    with point-in-time fundamentals when fd.ai is configured.
    """
    ticker = ticker.strip().upper()

    # Prices: try fd.ai daily closes; fall back to yfinance. Either way we
    # run `_build_asof_snapshot` on a uniform list of (date, float) pairs.
    try:
        closes = await fd.fetch_daily_closes(
            ticker, as_of - timedelta(days=400), as_of
        )
    except Exception as exc:
        logger.warning("fd.ai prices failed for %s @ %s: %s", ticker, as_of, exc)
        closes = None
    source_prices = "fd.ai"
    if not closes:
        try:
            closes = await asyncio.to_thread(
                _yfinance_history_closes, ticker, as_of - timedelta(days=400), as_of
            )
            source_prices = "yfinance"
        except Exception as exc:
            logger.warning(
                "market_data asof prices failed for %s @ %s: %s", ticker, as_of, exc
            )
            return {
                "ticker": ticker,
                "as_of": as_of.isoformat(),
                "error": f"snapshot unavailable: {exc}",
            }

    snapshot = _build_asof_snapshot(ticker, as_of, closes)

    fundamentals = await fd.fetch_fundamentals_asof(ticker, as_of)
    if fundamentals:
        snapshot["fundamentals"] = fundamentals
        snapshot["data_source"] = f"{source_prices}+fd.ai"
    else:
        snapshot["data_source"] = source_prices
    return snapshot


async def fetch_forward_return(
    ticker: str, from_date: date, to_date: date
) -> float | None:
    """Simple return from last close <= from_date to last close <= to_date.

    Prefers fd.ai for prices; falls back to yfinance.
    """
    ticker = ticker.strip().upper()
    window_start = from_date - timedelta(days=10)
    window_end = to_date + timedelta(days=10)

    closes = None
    try:
        closes = await fd.fetch_daily_closes(ticker, window_start, window_end)
    except Exception as exc:
        logger.warning("fd.ai forward prices failed: %s", exc)
    if not closes:
        try:
            closes = await asyncio.to_thread(
                _yfinance_history_closes, ticker, window_start, window_end
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

    if not closes:
        return None
    start = _last_close_on_or_before(closes, from_date)
    end = _last_close_on_or_before(closes, to_date)
    if start is None or end is None or start[1] == 0:
        return None
    return end[1] / start[1] - 1.0


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


def _build_asof_snapshot(
    ticker: str, as_of: date, closes: list[tuple[date, float]]
) -> dict[str, Any]:
    """Source-agnostic: builds the price-derived snapshot from a bar series.

    `closes` should cover at least the past year ending on/near as_of.
    """
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

    def avg(series: list[float]) -> float | None:
        return sum(series) / len(series) if series else None

    def stdev(series: list[float]) -> float | None:
        if len(series) < 2:
            return None
        m = sum(series) / len(series)
        var = sum((x - m) ** 2 for x in series) / (len(series) - 1)
        return float(var**0.5)

    # Price and daily returns for derived metrics.
    sorted_asc = sorted(closes, key=lambda x: x[0])
    close_series = [c for _, c in sorted_asc]
    daily_returns = [
        close_series[i] / close_series[i - 1] - 1.0
        for i in range(1, len(close_series))
        if close_series[i - 1] > 0
    ]

    last_20 = close_series[-20:] if len(close_series) >= 2 else []
    last_50 = close_series[-50:] if len(close_series) >= 2 else []
    last_200 = close_series[-200:] if len(close_series) >= 2 else []
    recent_returns = daily_returns[-63:]  # ~3 months of trading days

    ma20 = avg(last_20)
    ma50 = avg(last_50)
    ma200 = avg(last_200)
    vol = stdev(recent_returns)
    annualized_vol = vol * (252**0.5) if vol is not None else None

    high_52w = max(year_back) if year_back else None
    low_52w = min(year_back) if year_back else None

    def pct_from(base: float | None) -> float | None:
        if base is None or base == 0:
            return None
        return anchor_close / base - 1.0

    return {
        "ticker": ticker,
        "as_of": anchor_date.isoformat(),
        "close": anchor_close,
        "return_52w": pct_return(year_back),
        "return_4w": pct_return(month_back),
        "high_52w": high_52w,
        "low_52w": low_52w,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "pct_vs_ma20": pct_from(ma20),
        "pct_vs_ma50": pct_from(ma50),
        "pct_vs_ma200": pct_from(ma200),
        "drawdown_from_52w_high": pct_from(high_52w),
        "distance_above_52w_low": pct_from(low_52w),
        "annualized_vol_3m": annualized_vol,
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


