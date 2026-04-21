"""End-to-end test for the research job type. CLAUDE.md §11.

Drives POST /jobs + WebSocket + artifacts GET, with mocked Anthropic and
market data (no network, no spend).
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("patched_client", "patched_market_data")


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_research_streams_parallel_analysts_then_memo(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "buffett", "ticker": "NVDA"},
            },
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]

        events: list[dict[str, Any]] = []
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event = ws.receive_json()
                events.append(event)
                if event["type"] == "job_done":
                    break

        agents_seen = {
            e.get("agent") for e in events if e["type"] in {"token", "status"}
        }
        assert "valuation" in agents_seen
        assert "fundamentals" in agents_seen
        assert "buffett" in agents_seen

        artifacts = [e for e in events if e["type"] == "artifact"]
        assert len(artifacts) == 1
        artifact = artifacts[0]["artifact"]
        assert artifact["kind"] == "memo"
        # Sell-side structure (Step 2).
        assert "Initiation" in artifact["content_md"]
        assert "**Rating:**" in artifact["content_md"]
        meta = artifact["content_json"]
        assert meta["rating"] == "BUY"
        assert meta["targets"]["base"] == 75.0
        assert meta["targets"]["bull"] == 90.0
        assert meta["targets"]["bear"] == 55.0
        assert meta["style"] == "classic"

        resp = client.get(f"/jobs/{job_id}/artifacts")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["kind"] == "memo"


def test_list_jobs_includes_ticker_and_persona(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "burry", "ticker": "TSLA"},
            },
        )
        job_id = resp.json()["job_id"]
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while ws.receive_json()["type"] != "job_done":
                pass

        resp = client.get("/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        mine = next(j for j in jobs if j["id"] == job_id)
        assert mine["ticker"] == "TSLA"
        assert mine["persona"] == "burry"


def test_research_fans_out_to_four_analysts(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "buffett", "ticker": "KO"},
                "budget_usd": 1.0,
            },
        )
        job_id = resp.json()["job_id"]
        agents_seen: set[str] = set()
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event = ws.receive_json()
                if event["type"] == "status" and event.get("agent"):
                    agents_seen.add(event["agent"])
                if event["type"] == "job_done":
                    break
        assert {"valuation", "fundamentals", "macro", "technicals"}.issubset(
            agents_seen
        )
        # Lead persona + both non-lead personas (as team-view contributors).
        assert {"buffett", "druckenmiller", "burry"}.issubset(agents_seen)


def test_research_memo_cites_team_views(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "buffett", "ticker": "KO"},
                "budget_usd": 1.0,
            },
        )
        job_id = resp.json()["job_id"]
        events: list[dict[str, Any]] = []
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event = ws.receive_json()
                events.append(event)
                if event["type"] == "job_done":
                    break

        # Each non-lead persona streams its view under its own agent name.
        views_by = {
            e["agent"]: e["text"]
            for e in events
            if e["type"] == "token"
            and e.get("agent") in {"druckenmiller", "burry"}
        }
        assert "druckenmiller" in views_by
        assert "burry" in views_by


def test_citrini_style_parses_basket(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {
                    "persona": "druckenmiller",
                    "ticker": "NVDA",
                    "style": "citrini",
                },
                "budget_usd": 1.0,
            },
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        events: list[dict[str, Any]] = []
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event = ws.receive_json()
                events.append(event)
                if event["type"] == "job_done":
                    break

        artifact = next(e for e in events if e["type"] == "artifact")["artifact"]
        assert artifact["kind"] == "memo"
        meta = artifact["content_json"]
        assert meta["style"] == "citrini"
        assert meta["rating"] == "BUY"
        basket = meta["basket"]
        assert basket is not None
        longs = {row["ticker"]: row["weight"] for row in basket["long"]}
        shorts = {row["ticker"]: row["weight"] for row in basket["short"]}
        assert longs["NVDA"] == 35.0
        assert "AVGO" in longs
        assert "DDOG" in shorts


def test_memo_injects_price_chart_and_financials_table(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Snapshot with weekly closes + fundamentals → memo gains a chart
    image and a markdown financials table."""

    async def fake_snapshot(ticker: str) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "as_of": "2024-04-01",
            "price": 100.0,
            "weekly_closes_52w": [
                {"date": f"2023-{((i % 12) + 1):02d}-01", "close": 90.0 + i * 0.8}
                for i in range(52)
            ],
            "fundamentals": {
                "report_period": "2023-12-31",
                "pe_ratio": 25.1,
                "gross_margin": 0.64,
                "revenue": 85_000_000_000,
                "free_cash_flow": 20_000_000_000,
            },
            "data_source": "fd.ai+yfinance",
        }

    from app.config import settings
    from app.tools import market_data

    # Chart writes land in tmp for this test.
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "fund.sqlite"))
    monkeypatch.setattr(market_data, "fetch_snapshot", fake_snapshot)

    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "buffett", "ticker": "NVDA"},
                "budget_usd": 1.0,
            },
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        events: list[dict[str, Any]] = []
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event = ws.receive_json()
                events.append(event)
                if event["type"] == "job_done":
                    break

        artifact = next(e for e in events if e["type"] == "artifact")["artifact"]
        md = artifact["content_md"]
        assert "Point-in-time financials" in md
        assert "| P/E (TTM) | 25.10 |" in md
        assert "Revenue (TTM)" in md
        assert f"/charts/{job_id}/price.png" in md
        # Chart URL also available in the JSON sidecar for downstream use.
        assert artifact["content_json"]["price_chart_url"].endswith(
            f"/charts/{job_id}/price.png"
        )


def test_budget_enforced_when_already_exceeded(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "buffett", "ticker": "NVDA"},
                "budget_usd": 0.0,
            },
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        statuses: list[str] = []
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event = ws.receive_json()
                if event["type"] == "status":
                    statuses.append(event["status"])
                if event["type"] == "job_done":
                    break

        assert "budget_exceeded" in statuses
