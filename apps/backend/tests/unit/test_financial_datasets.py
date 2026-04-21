"""Unit tests for the financial-datasets.ai client. CLAUDE.md §4, §13.

Stubs httpx so no network is hit. Covers:
- Disabled path (no API key) returns None.
- Happy-path asof fundamentals parsing.
- Daily closes parsing.
- Non-200 response returns None (so market_data can fall back).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest


class _FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, by_path: dict[str, _FakeResponse]) -> None:
        self._by_path = by_path
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def get(
        self, url: str, params: dict[str, Any], headers: dict[str, str]
    ) -> _FakeResponse:
        # Map by path suffix so callers can look up /prices etc.
        self.calls.append((url, params))
        for suffix, resp in self._by_path.items():
            if url.endswith(suffix):
                return resp
        return _FakeResponse(404, {})


@pytest.fixture
def fd_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "financial_datasets_api_key", "fd-test")


async def test_is_enabled_toggles_on_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings
    from app.tools import financial_datasets as fd

    monkeypatch.setattr(settings, "financial_datasets_api_key", "")
    assert fd.is_enabled() is False
    monkeypatch.setattr(settings, "financial_datasets_api_key", "fd-test")
    assert fd.is_enabled() is True


async def test_returns_none_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings
    from app.tools import financial_datasets as fd

    monkeypatch.setattr(settings, "financial_datasets_api_key", "")
    assert await fd.fetch_daily_closes("NVDA", date(2024, 1, 1), date(2024, 2, 1)) is None
    assert await fd.fetch_fundamentals_asof("NVDA", date(2024, 1, 1)) is None


async def test_fetch_daily_closes_parses_prices(
    fd_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tools import financial_datasets as fd

    fake = _FakeClient(
        {
            "/prices": _FakeResponse(
                200,
                {
                    "prices": [
                        {"time": "2024-01-02", "close": 100.0},
                        {"time": "2024-01-03", "close": 101.5},
                        {"time": "2024-01-04", "close": None},  # skipped
                    ]
                },
            )
        }
    )
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: fake  # type: ignore[misc]
    )

    result = await fd.fetch_daily_closes("NVDA", date(2024, 1, 1), date(2024, 1, 5))
    assert result == [
        (date(2024, 1, 2), 100.0),
        (date(2024, 1, 3), 101.5),
    ]


async def test_fetch_fundamentals_asof_merges_endpoints(
    fd_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tools import financial_datasets as fd

    fake = _FakeClient(
        {
            "/financial-metrics": _FakeResponse(
                200,
                {
                    "financial_metrics": [
                        {
                            "report_period": "2023-12-31",
                            "price_to_earnings_ratio": 18.5,
                            "price_to_book_ratio": 3.1,
                            "gross_margin": 0.65,
                            "return_on_equity": 0.22,
                        }
                    ]
                },
            ),
            "/financials/income-statements": _FakeResponse(
                200,
                {
                    "income_statements": [
                        {"revenue": 1_000_000_000, "net_income": 150_000_000}
                    ]
                },
            ),
            "/financials/balance-sheets": _FakeResponse(
                200,
                {
                    "balance_sheets": [
                        {"total_debt": 200_000_000, "cash_and_equivalents": 400_000_000}
                    ]
                },
            ),
            "/financials/cash-flow-statements": _FakeResponse(
                200,
                {
                    "cash_flow_statements": [
                        {"free_cash_flow": 180_000_000}
                    ]
                },
            ),
        }
    )
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: fake  # type: ignore[misc]
    )

    result = await fd.fetch_fundamentals_asof("NVDA", date(2024, 1, 1))
    assert result is not None
    assert result["pe_ratio"] == 18.5
    assert result["price_to_book"] == 3.1
    assert result["gross_margin"] == 0.65
    assert result["return_on_equity"] == 0.22
    assert result["revenue"] == 1_000_000_000
    assert result["total_debt"] == 200_000_000
    assert result["free_cash_flow"] == 180_000_000
    assert result["report_period"] == "2023-12-31"


async def test_non_200_returns_none(
    fd_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tools import financial_datasets as fd

    fake = _FakeClient({"/prices": _FakeResponse(500, {"detail": "oops"})})
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: fake  # type: ignore[misc]
    )
    assert await fd.fetch_daily_closes("NVDA", date(2024, 1, 1), date(2024, 1, 5)) is None


async def test_fetch_fundamentals_series_orders_oldest_to_newest(
    fd_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tools import financial_datasets as fd

    fake = _FakeClient(
        {
            "/financial-metrics": _FakeResponse(
                200,
                {
                    "financial_metrics": [
                        {
                            "report_period": "2024-03-31",
                            "gross_margin": 0.66,
                            "operating_margin": 0.33,
                            "net_margin": 0.24,
                        },
                        {
                            "report_period": "2023-09-30",
                            "gross_margin": 0.60,
                            "operating_margin": 0.31,
                            "net_margin": 0.22,
                        },
                        {
                            "report_period": "2023-12-31",
                            "gross_margin": 0.63,
                            "operating_margin": 0.32,
                            "net_margin": 0.23,
                        },
                    ]
                },
            )
        }
    )
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: fake  # type: ignore[misc]
    )

    series = await fd.fetch_fundamentals_series("NVDA", date(2024, 4, 1), periods=8)
    assert series is not None
    assert [row["report_period"] for row in series] == [
        "2023-09-30",
        "2023-12-31",
        "2024-03-31",
    ]
    assert series[-1]["gross_margin"] == 0.66


async def test_fetch_fundamentals_series_disabled_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings
    from app.tools import financial_datasets as fd

    monkeypatch.setattr(settings, "financial_datasets_api_key", "")
    assert (
        await fd.fetch_fundamentals_series("NVDA", date(2024, 1, 1), periods=4)
        is None
    )
