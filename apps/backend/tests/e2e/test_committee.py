"""End-to-end test for the committee job type. CLAUDE.md §6, §11."""
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


def test_committee_round_robin_through_to_pm_decision(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "committee",
                "inputs": {"ticker": "NVDA"},
                "budget_usd": 1.00,
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

        agents_seen = [
            e["agent"] for e in events if e["type"] == "status" and "agent" in e
        ]
        # Expect at least these speakers and in this order.
        expected_order = ["moderator", "buffett", "druckenmiller", "burry", "risk", "pm"]
        filtered = [a for a in agents_seen if a in expected_order]
        # First occurrence of each speaker must match the expected order.
        first_seen: list[str] = []
        for a in filtered:
            if a not in first_seen:
                first_seen.append(a)
        assert first_seen == expected_order

        artifacts = [e for e in events if e["type"] == "artifact"]
        assert len(artifacts) == 1
        art = artifacts[0]["artifact"]
        assert art["kind"] == "transcript"
        assert "Committee · NVDA" in art["content_md"]
        assert "PM decision" in art["content_md"]
        assert art["content_json"]["verdict"] == "buy"


def test_committee_artifact_queryable_via_http(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={"type": "committee", "inputs": {"ticker": "KO"}, "budget_usd": 1.00},
        )
        job_id = resp.json()["job_id"]
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while ws.receive_json()["type"] != "job_done":
                pass

        resp = client.get(f"/jobs/{job_id}/artifacts")
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["kind"] == "transcript"
        meta = json.loads(rows[0]["content_json"])
        assert meta["ticker"] == "KO"
        assert meta["participants"] == [
            "moderator",
            "buffett",
            "druckenmiller",
            "burry",
            "risk",
            "pm",
        ]


def test_committee_rejects_unknown_persona(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "committee",
                "inputs": {"ticker": "NVDA", "personas": ["not_a_persona"]},
                "budget_usd": 1.00,
            },
        )
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
