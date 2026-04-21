"""End-to-end test for the backtest job type. CLAUDE.md §6, §11."""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("patched_client", "patched_market_data")


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_backtest_runs_steps_and_writes_scoreboard(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "backtest",
                "inputs": {
                    "persona": "buffett",
                    "ticker": "NVDA",
                    "start_date": "2024-01-01",
                    "num_steps": 4,
                    "step_weeks": 1,
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

        statuses = [
            e for e in events if e["type"] == "status" and e.get("agent") == "backtester"
        ]
        status_texts = [s["status"] for s in statuses]
        assert status_texts[0] == "starting"
        assert any("step 1/4: fetching" in s for s in status_texts)
        assert any("step 1/4: scoring" in s for s in status_texts)
        assert any("step 4/4: scoring" in s for s in status_texts)
        assert "compiling report" in status_texts
        assert status_texts[-1] == "done"

        tokens = [
            e for e in events if e["type"] == "token" and e.get("agent") == "backtester"
        ]
        # one token event per step (single summary line each)
        assert len(tokens) == 4

        artifacts = [e for e in events if e["type"] == "artifact"]
        assert len(artifacts) == 1
        art = artifacts[0]["artifact"]
        assert art["kind"] == "backtest_report"
        assert "Backtest" in art["content_md"]

        resp = client.get(f"/jobs/{job_id}/artifacts")
        row = resp.json()[0]
        meta = json.loads(row["content_json"])
        assert meta["trades"] == 4          # all four steps are BUY in the fake
        assert meta["hit_rate"] == 1.0      # fake forward_return is positive
        assert meta["avg_return"] is not None


def test_backtest_populates_persona_performance(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "backtest",
                "inputs": {
                    "persona": "druckenmiller",
                    "ticker": "TSLA",
                    "start_date": "2024-03-01",
                    "num_steps": 3,
                },
                "budget_usd": 1.0,
            },
        )
        job_id = resp.json()["job_id"]
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while ws.receive_json()["type"] != "job_done":
                pass

        resp = client.get("/personas/druckenmiller/performance")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["period"] == "TSLA"
        assert row["trades"] == 3
        assert row["hit_rate"] == 1.0


def test_backtest_rejects_bad_start_date(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "backtest",
                "inputs": {
                    "persona": "burry",
                    "ticker": "KO",
                    "start_date": "not-a-date",
                    "num_steps": 2,
                },
                "budget_usd": 0.50,
            },
        )
        # start_date is validated inside the graph; the outer POST is OK but
        # the graph raises, so the WS eventually emits an error event.
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        saw_error = False
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event = ws.receive_json()
                if event["type"] == "error":
                    saw_error = True
                if event["type"] == "job_done":
                    break
        assert saw_error
