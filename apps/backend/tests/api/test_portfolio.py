"""Portfolio CRUD + daily spend. CLAUDE.md §5, §9."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_portfolio_lifecycle(client: TestClient) -> None:
    with client:
        resp = client.get("/portfolio")
        assert resp.status_code == 200
        assert resp.json() == []

        resp = client.put(
            "/portfolio/NVDA",
            json={"ticker": "NVDA", "qty": 10.0, "avg_price": 500.0},
        )
        assert resp.status_code == 200
        position = resp.json()
        assert position["ticker"] == "NVDA"
        assert position["qty"] == 10.0

        resp = client.put(
            "/portfolio/NVDA",
            json={"ticker": "NVDA", "qty": 15.0, "avg_price": 480.0},
        )
        assert resp.json()["qty"] == 15.0
        assert resp.json()["avg_price"] == 480.0

        resp = client.get("/portfolio")
        assert len(resp.json()) == 1

        resp = client.delete(f"/portfolio/{position['id']}")
        assert resp.status_code == 200
        resp = client.get("/portfolio")
        assert resp.json() == []


def test_portfolio_path_body_mismatch_rejected(client: TestClient) -> None:
    with client:
        resp = client.put(
            "/portfolio/NVDA",
            json={"ticker": "TSLA", "qty": 1.0, "avg_price": 200.0},
        )
        assert resp.status_code == 400


def test_portfolio_delete_missing_404s(client: TestClient) -> None:
    with client:
        resp = client.delete("/portfolio/999")
        assert resp.status_code == 404


def test_spend_today_empty(client: TestClient) -> None:
    with client:
        resp = client.get("/spend/today")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_usd"] == 0.0
        assert body["by_model"] == []
        assert body["daily_cap_usd"] > 0


@pytest.mark.usefixtures("patched_client", "patched_market_data")
def test_spend_today_reflects_research_run(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "buffett", "ticker": "NVDA"},
            },
        )
        job_id = resp.json()["job_id"]
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while ws.receive_json()["type"] != "job_done":
                pass

        resp = client.get("/spend/today")
        body = resp.json()
        # The fake Anthropic client reports 10 input + 20 output tokens per call.
        # Research runs 5 agents (valuation, fundamentals, macro, technicals,
        # persona) → 5 calls.
        assert body["total_usd"] > 0
        assert body["input_tokens"] == 50
        assert body["output_tokens"] == 100
        assert {m["model"] for m in body["by_model"]} == {"claude-sonnet-4-6"}
        assert sum(m["calls"] for m in body["by_model"]) == 5
