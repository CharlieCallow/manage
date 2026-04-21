"""Persona + analyst registry. CLAUDE.md §13.

A persona is looked up by name; the model comes from the DB row.
"""
from __future__ import annotations

from app.agents.base import Agent
from app.agents.personas.buffett import BuffettAgent
from app.store import db


def load_persona(name: str) -> Agent:
    row = db.get_persona_by_name(name)
    if row is None:
        raise KeyError(f"persona not found: {name}")

    # Phase 0 — only Buffett is implemented. Phase 1+ adds more.
    if name == "buffett":
        return BuffettAgent(model=row["model"], prompt_template=row["prompt_template"])

    raise NotImplementedError(f"persona not wired: {name}")
