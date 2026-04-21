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
        assert "buffett" in agents_seen


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
