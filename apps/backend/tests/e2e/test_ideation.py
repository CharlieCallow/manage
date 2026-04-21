"""End-to-end test for the ideation job type and idea approval flow."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("patched_client", "patched_market_data")


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def _run_ideation(client: TestClient) -> tuple[str, list[dict[str, Any]]]:
    resp = client.post(
        "/jobs",
        json={
            "type": "ideation",
            "inputs": {"framing": "AI infrastructure", "num_per_persona": 2},
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
    return job_id, events


def test_ideation_surfaces_candidates_per_persona(client: TestClient) -> None:
    with client:
        job_id, events = _run_ideation(client)

        agents_seen = {
            e.get("agent") for e in events if e["type"] == "status"
        }
        # Each of the three seeded personas should have spoken.
        assert {"buffett", "druckenmiller", "burry"}.issubset(agents_seen)

        resp = client.get("/ideas", params={"ideation_job_id": job_id})
        assert resp.status_code == 200
        ideas = resp.json()
        # Two per persona × three personas = six candidates.
        assert len(ideas) == 6
        tickers = {row["ticker"] for row in ideas}
        assert {"KO", "MCO", "NVDA", "GLD", "CVNA", "DKS"}.issubset(tickers)
        for row in ideas:
            assert row["status"] == "pending"
            assert row["thesis"]
            assert row["persona"] in {"buffett", "druckenmiller", "burry"}


def test_approve_spawns_research_job(client: TestClient) -> None:
    with client:
        _, _events = _run_ideation(client)
        pending = client.get("/ideas", params={"status": "pending"}).json()
        target = next(i for i in pending if i["ticker"] == "NVDA")

        resp = client.patch(
            f"/ideas/{target['id']}", json={"status": "approved"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["idea"]["status"] == "approved"
        research_job_id = body["research_job_id"]
        assert research_job_id

        # The spawned research job runs async; drive it to completion.
        with client.websocket_connect(f"/ws/jobs/{research_job_id}") as ws:
            while ws.receive_json()["type"] != "job_done":
                pass

        resp = client.get(f"/jobs/{research_job_id}/artifacts")
        assert resp.status_code == 200
        artifacts = resp.json()
        assert any(a["kind"] == "memo" for a in artifacts)


def test_dismiss_has_no_side_effects(client: TestClient) -> None:
    with client:
        _, _events = _run_ideation(client)
        pending = client.get("/ideas", params={"status": "pending"}).json()
        target = pending[0]

        resp = client.patch(
            f"/ideas/{target['id']}", json={"status": "dismissed"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["idea"]["status"] == "dismissed"
        assert body["research_job_id"] is None


def test_cannot_decide_twice(client: TestClient) -> None:
    with client:
        _, _events = _run_ideation(client)
        pending = client.get("/ideas", params={"status": "pending"}).json()
        target = pending[0]

        client.patch(f"/ideas/{target['id']}", json={"status": "dismissed"})
        resp = client.patch(
            f"/ideas/{target['id']}", json={"status": "approved"}
        )
        assert resp.status_code == 409
