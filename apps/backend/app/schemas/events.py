"""Wire format for /ws/jobs/{job_id}. CLAUDE.md §7."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    agent: str
    text: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    agent: str
    name: str
    input: dict[str, Any]


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    agent: str
    name: str
    output: dict[str, Any]


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    agent: str
    status: str


class ArtifactPayload(BaseModel):
    id: int | None = None
    job_id: str
    kind: str
    content_md: str | None = None
    content_json: dict[str, Any] | None = None


class ArtifactEvent(BaseModel):
    type: Literal["artifact"] = "artifact"
    artifact: ArtifactPayload


class JobDoneEvent(BaseModel):
    type: Literal["job_done"] = "job_done"
    cost_usd: float


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


JobEvent = (
    TokenEvent
    | ToolCallEvent
    | ToolResultEvent
    | StatusEvent
    | ArtifactEvent
    | JobDoneEvent
    | ErrorEvent
)


class EventEnvelope(BaseModel):
    """Helper for parsing/serializing any event on the wire."""

    event: JobEvent = Field(discriminator="type")
