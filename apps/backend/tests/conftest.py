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

    We key on the system prompt: every persona/analyst prompt file starts
    with a distinctive first word, which lets tests assert per-agent output.
    """

    def __init__(self, chunks_for: dict[str, list[str]]) -> None:
        self._by_key = chunks_for

    def stream(self, **kwargs: Any) -> Any:
        system = kwargs.get("system", "")
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

    from app.tools import market_data

    monkeypatch.setattr(market_data, "fetch_snapshot", fake_fetch)
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
