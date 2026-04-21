"""Anthropic tool-use definitions for agent-callable tools.

CLAUDE.md §13 — tools live in app/tools/<name>.py and are registered here
with their Anthropic-side definitions. Phase 1 ships the registry shell; no
agent invokes these via tool-use yet (the research graph fetches market data
up front and passes it as context). Tool-use wiring lands in a later phase.
"""
from __future__ import annotations

from typing import Any, TypedDict


class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]


TOOLS: list[ToolDefinition] = [
    {
        "name": "get_market_snapshot",
        "description": (
            "Return a compact snapshot of price, ratios, growth, margins, "
            "and balance-sheet figures for a single equity ticker."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Equity ticker symbol, e.g. 'NVDA'.",
                },
            },
            "required": ["ticker"],
        },
    },
]
