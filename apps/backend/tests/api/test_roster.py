"""Roster CRUD. CLAUDE.md §8 — per-persona model is editable; persists."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_list_personas_seeded(client: TestClient) -> None:
    with client:
        resp = client.get("/personas")
        assert resp.status_code == 200
        names = {r["name"] for r in resp.json()}
        assert {"buffett", "druckenmiller", "burry"}.issubset(names)


def test_list_analysts_seeded(client: TestClient) -> None:
    with client:
        resp = client.get("/analysts")
        assert resp.status_code == 200
        names = {r["name"] for r in resp.json()}
        assert {"valuation", "fundamentals"}.issubset(names)


def test_patch_persona_model_persists(client: TestClient) -> None:
    with client:
        resp = client.patch(
            "/personas/buffett", json={"model": "claude-haiku-4-5"}
        )
        assert resp.status_code == 200
        assert resp.json()["model"] == "claude-haiku-4-5"

        resp = client.get("/personas/buffett")
        assert resp.json()["model"] == "claude-haiku-4-5"


def test_patch_prompt_template_persists(client: TestClient) -> None:
    new_prompt = "You are a very concise value investor."
    with client:
        resp = client.patch(
            "/personas/buffett", json={"prompt_template": new_prompt}
        )
        assert resp.status_code == 200
        assert resp.json()["prompt_template"] == new_prompt


def test_patch_invalid_model_rejected(client: TestClient) -> None:
    with client:
        resp = client.patch("/personas/buffett", json={"model": "gpt-4"})
        assert resp.status_code == 422


def test_patch_unknown_persona_404s(client: TestClient) -> None:
    with client:
        resp = client.patch("/personas/does_not_exist", json={"enabled": False})
        assert resp.status_code == 404


def test_performance_empty_for_seeded_persona(client: TestClient) -> None:
    with client:
        resp = client.get("/personas/buffett/performance")
        assert resp.status_code == 200
        assert resp.json() == []
