"""FastAPI entrypoint. Runs migrations + persona/analyst seed on startup."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.analysts.fundamentals import (
    default_prompt_template as fundamentals_prompt,
)
from app.agents.analysts.macro import default_prompt_template as macro_prompt
from app.agents.analysts.moderator import (
    default_prompt_template as moderator_prompt,
)
from app.agents.analysts.pm import default_prompt_template as pm_prompt
from app.agents.analysts.risk import default_prompt_template as risk_prompt
from app.agents.analysts.technicals import (
    default_prompt_template as technicals_prompt,
)
from app.agents.analysts.valuation import default_prompt_template as valuation_prompt
from app.agents.personas.buffett import default_prompt_template as buffett_prompt
from app.agents.personas.burry import default_prompt_template as burry_prompt
from app.agents.personas.druckenmiller import (
    default_prompt_template as druckenmiller_prompt,
)
from app.api.ideas import router as ideas_router
from app.api.jobs import router as jobs_router
from app.api.portfolio import router as portfolio_router
from app.api.roster import router as roster_router
from app.logging import configure_logging
from app.store import db

logger = logging.getLogger(__name__)


# CLAUDE.md §8:
#   Sonnet 4.6 — default for personas and analysts (80%+ of calls).
#   Opus 4.7   — PM and committee synthesis.
#   Haiku 4.5  — moderator routing.
# _upsert only writes `model` on INSERT; existing rows keep whatever the
# Roster editor set, so these values only matter for fresh installs or
# when adding a brand-new row (e.g. moderator in Phase 3).
def _seed_agents() -> None:
    db.upsert_persona("buffett", buffett_prompt(), "claude-sonnet-4-6")
    db.upsert_persona("druckenmiller", druckenmiller_prompt(), "claude-sonnet-4-6")
    db.upsert_persona("burry", burry_prompt(), "claude-sonnet-4-6")
    db.upsert_analyst("valuation", valuation_prompt(), "claude-sonnet-4-6")
    db.upsert_analyst("fundamentals", fundamentals_prompt(), "claude-sonnet-4-6")
    db.upsert_analyst("macro", macro_prompt(), "claude-sonnet-4-6")
    db.upsert_analyst("technicals", technicals_prompt(), "claude-sonnet-4-6")
    db.upsert_analyst("moderator", moderator_prompt(), "claude-haiku-4-5")
    db.upsert_analyst("risk", risk_prompt(), "claude-sonnet-4-6")
    db.upsert_analyst("pm", pm_prompt(), "claude-opus-4-7")


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
app.include_router(portfolio_router)
app.include_router(ideas_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
