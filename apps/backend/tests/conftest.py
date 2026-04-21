"""Test fixtures. CLAUDE.md §14 — no network; mock Anthropic and market data."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest

os.environ.setdefault("DATABASE_PATH", "data/test-fund.sqlite")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")


@dataclass
class FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 20


@dataclass
class FakeFinalMessage:
    usage: FakeUsage = field(default_factory=FakeUsage)


@dataclass
class FakeStream:
    chunks: list[str]

    @property
    def text_stream(self) -> AsyncIterator[str]:
        async def gen() -> AsyncIterator[str]:
            for c in self.chunks:
                yield c

        return gen()

    async def get_final_message(self) -> FakeFinalMessage:
        return FakeFinalMessage()


class FakeMessages:
    """Returns a stream whose chunks depend on which agent is calling.

    Keys match against the system prompt (agent identity). The backtest
    scorer overrides on the user message: it instructs Haiku to emit the
    structured `SIGNAL: ... / REASON: ...` form, so we special-case it.
    """

    def __init__(self, chunks_for: dict[str, list[str]]) -> None:
        self._by_key = chunks_for

    def stream(self, **kwargs: Any) -> Any:
        system = kwargs.get("system", "")
        messages = kwargs.get("messages") or []
        user = messages[0]["content"] if messages else ""

        if "tactical signal generator" in system:
            # Backtest scorer call — respond in the required format.
            chunks = ["SIGNAL: BUY\n", "REASON: positive momentum."]
        elif "surface the candidates" in user:
            # Ideation call — emit TICKER/THESIS pairs keyed by persona
            # so each speaker produces distinguishable ideas.
            key = _match_key(system, self._by_key) or "default"
            chunks = _IDEATION_CHUNKS.get(key, _IDEATION_CHUNKS["default"])
        else:
            key = _match_key(system, self._by_key) or "default"
            chunks = self._by_key.get(key, ["ok"])

        @asynccontextmanager
        async def cm() -> AsyncIterator[FakeStream]:
            yield FakeStream(chunks=chunks)

        return cm()


def _match_key(system: str, mapping: dict[str, list[str]]) -> str | None:
    for key in mapping:
        if key in system:
            return key
    return None


# Per-persona ideation output. Keys match system-prompt substrings so each
# persona produces distinguishable candidates.
_IDEATION_CHUNKS: dict[str, list[str]] = {
    "mold of Warren Buffett": [
        "TICKER: KO\nTHESIS: durable moat, boring compounder.\n\n",
        "TICKER: MCO\nTHESIS: toll road on credit issuance.\n",
    ],
    "mold of Stanley Druckenmiller": [
        "TICKER: NVDA\nTHESIS: AI capex cycle on the right side of liquidity.\n\n",
        "TICKER: GLD\nTHESIS: real-rate peak sets up the metal.\n",
    ],
    "mold of Michael": [
        "TICKER: CVNA\nTHESIS: covenant risk if used-car comps roll.\n\n",
        "TICKER: DKS\nTHESIS: sandbagging guidance on hard comps.\n",
    ],
    "default": ["TICKER: SPY\nTHESIS: broad-market placeholder.\n"],
}


class FakeAnthropic:
    """Keys are substrings that must be distinctive across all agent prompts.

    Prompts may mention other roles by name (e.g. pm.md references the risk
    officer), so don't use role names as keys — use the opening "You are"
    line each prompt begins with.
    """

    def __init__(self, chunks_for: dict[str, list[str]] | None = None, **_: Any) -> None:
        defaults = {
            "mold of Warren Buffett": ["# Memo\n", "Buy KO. "],
            "mold of Stanley Druckenmiller": ["Macro call. "],
            "mold of Michael": ["Read footnotes. "],
            "You are a valuation analyst": ["Valuation: expensive. "],
            "You are a fundamentals analyst": ["Fundamentals: high quality. "],
            "You are the moderator": ["Committee now in session. "],
            "You are the risk officer on an investment committee":
                ["Risks: concentration. "],
            "You are the portfolio manager": [
                "Thesis.\n",
                "Decision: buy (half). ",
                "Watch next quarter's FCF.",
            ],
        }
        self.messages = FakeMessages(chunks_for=chunks_for or defaults)


@pytest.fixture
def fake_anthropic() -> FakeAnthropic:
    return FakeAnthropic()


@pytest.fixture
def patched_client(
    monkeypatch: pytest.MonkeyPatch, fake_anthropic: FakeAnthropic
) -> Iterator[None]:
    from app.api import jobs as jobs_module

    monkeypatch.setattr(jobs_module, "_make_anthropic_client", lambda: fake_anthropic)
    yield


@pytest.fixture
def patched_market_data(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    async def fake_fetch(ticker: str) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "name": f"{ticker} Corp",
            "price": 100.0,
            "pe_trailing": 20.0,
            "market_cap": 1_000_000_000,
        }

    async def fake_fetch_asof(ticker: str, as_of: Any) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "as_of": str(as_of),
            "close": 100.0,
            "return_52w": 0.12,
            "return_4w": 0.02,
            "high_52w": 110.0,
            "low_52w": 85.0,
        }

    async def fake_forward_return(
        ticker: str, from_date: Any, to_date: Any
    ) -> float | None:
        # Alternate outcomes so BUY signals have a non-trivial hit rate in tests.
        days = (to_date - from_date).days
        return 0.01 * days  # 1% per day of window

    from app.tools import market_data

    monkeypatch.setattr(market_data, "fetch_snapshot", fake_fetch)
    monkeypatch.setattr(market_data, "fetch_snapshot_asof", fake_fetch_asof)
    monkeypatch.setattr(market_data, "fetch_forward_return", fake_forward_return)
    yield


@pytest.fixture(autouse=True)
def fresh_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    db_file = tmp_path / "fund.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))

    from app.config import settings as cfg_settings

    monkeypatch.setattr(cfg_settings, "database_path", str(db_file))

    from app.store import db as db_module

    monkeypatch.setattr(db_module, "_engine", None)
    yield
