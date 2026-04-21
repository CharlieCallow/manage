"""End-to-end test for the research job type. CLAUDE.md §11.

Uses a mocked Anthropic client (no network, no spend). Drives POST /jobs +
WebSocket stream, asserts tokens and a final job_done event.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("patched_client")


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_research_streams_tokens(client: TestClient) -> None:
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "buffett", "prompt": "Tell me about KO."},
            },
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]

        tokens: list[str] = []
        saw_job_done = False
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event: dict[str, Any] = ws.receive_json()
                if event["type"] == "token":
                    tokens.append(event["text"])
                if event["type"] == "job_done":
                    saw_job_done = True
                    break

        assert "".join(tokens) == "Hello from Buffett."
        assert saw_job_done


def test_budget_enforced_when_already_exceeded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A zero budget must produce budget_exceeded before streaming any tokens."""
    with client:
        resp = client.post(
            "/jobs",
            json={
                "type": "research",
                "inputs": {"persona": "buffett", "prompt": "hi"},
                "budget_usd": 0.0,
            },
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        statuses: list[str] = []
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            while True:
                event: dict[str, Any] = ws.receive_json()
                if event["type"] == "status":
                    statuses.append(event["status"])
                if event["type"] == "job_done":
                    break

        assert "budget_exceeded" in statuses
