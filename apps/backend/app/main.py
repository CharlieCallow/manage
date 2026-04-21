"""FastAPI entrypoint. Runs migrations + persona seed on startup."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.personas.buffett import default_prompt_template
from app.api.jobs import router as jobs_router
from app.logging import configure_logging
from app.store import db

logger = logging.getLogger(__name__)


def _seed_personas() -> None:
    # Phase 0: only Buffett. Phase 1+ adds Druckenmiller, Burry, etc.
    db.upsert_persona(
        name="buffett",
        prompt_template=default_prompt_template(),
        model="claude-opus-4-7",
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    db.run_migrations()
    _seed_personas()
    logger.info("backend ready")
    yield


app = FastAPI(title="manage backend", version="0.0.0", lifespan=lifespan)
app.include_router(jobs_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
