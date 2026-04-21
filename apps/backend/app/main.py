"""FastAPI entrypoint. Runs migrations + persona/analyst seed on startup."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.analysts.fundamentals import (
    default_prompt_template as fundamentals_prompt,
)
from app.agents.analysts.valuation import default_prompt_template as valuation_prompt
from app.agents.personas.buffett import default_prompt_template as buffett_prompt
from app.agents.personas.burry import default_prompt_template as burry_prompt
from app.agents.personas.druckenmiller import (
    default_prompt_template as druckenmiller_prompt,
)
from app.api.jobs import router as jobs_router
from app.api.roster import router as roster_router
from app.logging import configure_logging
from app.store import db

logger = logging.getLogger(__name__)


# CLAUDE.md §8 — Sonnet is the default for personas and analysts. Users can
# bump individual rows to Opus from the Roster room.
_DEFAULT_MODEL = "claude-sonnet-4-6"


def _seed_agents() -> None:
    db.upsert_persona("buffett", buffett_prompt(), _DEFAULT_MODEL)
    db.upsert_persona("druckenmiller", druckenmiller_prompt(), _DEFAULT_MODEL)
    db.upsert_persona("burry", burry_prompt(), _DEFAULT_MODEL)
    db.upsert_analyst("valuation", valuation_prompt(), _DEFAULT_MODEL)
    db.upsert_analyst("fundamentals", fundamentals_prompt(), _DEFAULT_MODEL)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    db.run_migrations()
    _seed_agents()
    logger.info("backend ready")
    yield


app = FastAPI(title="manage backend", version="0.0.0", lifespan=lifespan)
app.include_router(jobs_router)
app.include_router(roster_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
