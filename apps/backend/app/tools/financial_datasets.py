"""financial-datasets.ai client.

CLAUDE.md §4 — agents never touch this module directly; it's used only by
`app/tools/market_data.py` as the preferred backend when a key is set.

Every public function here is null-safe: if no key, if the API errors, or
if a field is absent, we return `None` so the orchestrator can fall back to
yfinance cleanly.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.financialdatasets.ai"
_TIMEOUT = httpx.Timeout(15.0)


def is_enabled() -> bool:
    return bool(settings.financial_datasets_api_key.strip())


def _headers() -> dict[str, str]:
    return {"X-API-KEY": settings.financial_datasets_api_key.strip()}


async def _get(path: str, params: dict[str, Any]) -> dict[str, Any] | None:
    if not is_enabled():
        return None
    url = f"{_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(url, params=params, headers=_headers())
        if r.status_code != 200:
            logger.warning(
                "financial-datasets %s -> %s: %s",
                path,
                r.status_code,
                r.text[:200],
            )
            return None
        data: dict[str, Any] = r.json()
        return data
    except Exception as exc:
        logger.warning("financial-datasets %s failed: %s", path, exc)
        return None


async def fetch_daily_closes(
    ticker: str, start: date, end: date
) -> list[tuple[date, float]] | None:
    """Return daily closes in [start, end]. None if fd.ai is disabled or errors."""
    data = await _get(
        "/prices",
        {
            "ticker": ticker,
            "interval": "day",
            "interval_multiplier": 1,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    if not data:
        return None
    prices = data.get("prices") or []
    closes: list[tuple[date, float]] = []
    for row in prices:
        when = row.get("time") or row.get("date") or row.get("report_period")
        close = row.get("close")
        if not when or close is None:
            continue
        try:
            d = date.fromisoformat(str(when)[:10])
            closes.append((d, float(close)))
        except (TypeError, ValueError):
            continue
    return closes or None


async def fetch_fundamentals_asof(
    ticker: str, as_of: date
) -> dict[str, Any] | None:
    """Point-in-time fundamentals: latest TTM-like figures reported on or before `as_of`.

    Returns a compact dict suitable for pasting into the agent user message.
    None if fd.ai is disabled or no data is available.
    """
    if not is_enabled():
        return None

    # We ask for the latest few quarters up to `as_of` and combine them.
    metrics = await _get(
        "/financial-metrics",
        {
            "ticker": ticker,
            "period": "ttm",
            "limit": 1,
            "report_period_lte": as_of.isoformat(),
        },
    )
    income = await _get(
        "/financials/income-statements",
        {
            "ticker": ticker,
            "period": "ttm",
            "limit": 1,
            "report_period_lte": as_of.isoformat(),
        },
    )
    balance = await _get(
        "/financials/balance-sheets",
        {
            "ticker": ticker,
            "period": "quarterly",
            "limit": 1,
            "report_period_lte": as_of.isoformat(),
        },
    )
    cashflow = await _get(
        "/financials/cash-flow-statements",
        {
            "ticker": ticker,
            "period": "ttm",
            "limit": 1,
            "report_period_lte": as_of.isoformat(),
        },
    )

    m = _first(metrics, "financial_metrics")
    inc = _first(income, "income_statements")
    bal = _first(balance, "balance_sheets")
    cf = _first(cashflow, "cash_flow_statements")

    if not any([m, inc, bal, cf]):
        return None

    return _compact(
        {
            "report_period": _pick(m, inc, bal, cf, key="report_period"),
            # Valuation
            "pe_ratio": _get_num(m, "price_to_earnings_ratio"),
            "pe_forward": _get_num(m, "forward_price_to_earnings_ratio"),
            "price_to_book": _get_num(m, "price_to_book_ratio"),
            "price_to_sales": _get_num(m, "price_to_sales_ratio"),
            "ev_to_ebitda": _get_num(m, "enterprise_value_to_ebitda_ratio"),
            "ev_to_revenue": _get_num(m, "enterprise_value_to_revenue_ratio"),
            "dividend_yield": _get_num(m, "dividend_yield"),
            # Profitability / quality
            "gross_margin": _get_num(m, "gross_margin"),
            "operating_margin": _get_num(m, "operating_margin"),
            "net_margin": _get_num(m, "net_margin"),
            "return_on_equity": _get_num(m, "return_on_equity"),
            "return_on_invested_capital": _get_num(m, "return_on_invested_capital"),
            # Growth
            "revenue_growth": _get_num(m, "revenue_growth"),
            "earnings_growth": _get_num(m, "earnings_growth"),
            "free_cash_flow_growth": _get_num(m, "free_cash_flow_growth"),
            # Income statement highlights
            "revenue": _get_num(inc, "revenue"),
            "operating_income": _get_num(inc, "operating_income"),
            "net_income": _get_num(inc, "net_income"),
            # Balance sheet
            "total_assets": _get_num(bal, "total_assets"),
            "total_liabilities": _get_num(bal, "total_liabilities"),
            "total_debt": _get_num(bal, "total_debt"),
            "cash_and_equivalents": _get_num(bal, "cash_and_equivalents"),
            "shareholders_equity": _get_num(bal, "shareholders_equity"),
            # Cash flow
            "operating_cash_flow": _get_num(cf, "net_cash_flow_from_operations"),
            "capital_expenditure": _get_num(cf, "capital_expenditure"),
            "free_cash_flow": _get_num(cf, "free_cash_flow"),
        }
    )


async def fetch_fundamentals_live(ticker: str) -> dict[str, Any] | None:
    """Most recent-available fundamentals (same shape as asof, but no date bound)."""
    # As-of today covers the "live" case too.
    return await fetch_fundamentals_asof(ticker, date.today() + timedelta(days=1))


async def fetch_fundamentals_series(
    ticker: str, as_of: date, periods: int = 8
) -> list[dict[str, Any]] | None:
    """Pull the last `periods` quarterly metrics rows on/before as_of.

    Each row is shaped { report_period, revenue, gross_margin,
    operating_margin, net_margin, revenue_growth, free_cash_flow_growth }.
    Ordered oldest → newest so callers can plot left-to-right.
    """
    if not is_enabled():
        return None
    data = await _get(
        "/financial-metrics",
        {
            "ticker": ticker,
            "period": "quarterly",
            "limit": max(1, min(periods, 40)),
            "report_period_lte": as_of.isoformat(),
        },
    )
    if not data:
        return None
    rows = data.get("financial_metrics") or []
    if not isinstance(rows, list) or not rows:
        return None

    series: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        compact = _compact(
            {
                "report_period": raw.get("report_period"),
                "revenue": _get_num(raw, "revenue"),
                "gross_margin": _get_num(raw, "gross_margin"),
                "operating_margin": _get_num(raw, "operating_margin"),
                "net_margin": _get_num(raw, "net_margin"),
                "revenue_growth": _get_num(raw, "revenue_growth"),
                "free_cash_flow_growth": _get_num(raw, "free_cash_flow_growth"),
            }
        )
        if compact.get("report_period"):
            series.append(compact)
    if not series:
        return None
    # ISO date strings sort correctly: oldest → newest.
    series.sort(key=lambda r: str(r.get("report_period") or ""))
    return series


# ---- helpers ---------------------------------------------------------------


def _first(data: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    if not data:
        return None
    arr = data.get(key)
    if isinstance(arr, list) and arr:
        row = arr[0]
        if isinstance(row, dict):
            return row
    return None


def _get_num(row: dict[str, Any] | None, key: str) -> float | None:
    if not row:
        return None
    val = row.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pick(*rows: dict[str, Any] | None, key: str) -> str | None:
    for row in rows:
        if row and row.get(key):
            return str(row[key])
    return None


def _compact(d: dict[str, Any]) -> dict[str, Any]:
    """Drop None-valued keys so the prompt stays short."""
    return {k: v for k, v in d.items() if v is not None}
