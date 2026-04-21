"""Test fixtures. CLAUDE.md §14 — no network calls; mock the Anthropic client."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest

# Force an isolated DB per test process, before any app import.
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
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    def stream(self, **_kwargs: Any) -> Any:
        chunks = self._chunks

        @asynccontextmanager
        async def cm() -> AsyncIterator[FakeStream]:
            yield FakeStream(chunks=chunks)

        return cm()


class FakeAnthropic:
    def __init__(self, chunks: list[str] | None = None, **_: Any) -> None:
        self.messages = FakeMessages(chunks or ["Hello ", "from ", "Buffett."])


@pytest.fixture
def fake_anthropic_chunks() -> list[str]:
    return ["Hello ", "from ", "Buffett."]


@pytest.fixture
def patched_client(
    monkeypatch: pytest.MonkeyPatch, fake_anthropic_chunks: list[str]
) -> Iterator[None]:
    from app.api import jobs as jobs_module

    def factory() -> FakeAnthropic:
        return FakeAnthropic(chunks=fake_anthropic_chunks)

    monkeypatch.setattr(jobs_module, "_make_anthropic_client", factory)
    yield


@pytest.fixture(autouse=True)
def fresh_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Redirect the DB to a per-test temp file.
    db_file = tmp_path / "fund.sqlite"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))

    from app.config import settings as cfg_settings

    monkeypatch.setattr(cfg_settings, "database_path", str(db_file))

    # Reset the cached engine so a new one picks up the new path.
    from app.store import db as db_module

    monkeypatch.setattr(db_module, "_engine", None)
    yield
