"""Shared user-message formatters for personas and analysts."""
from __future__ import annotations

import json
from typing import Any


def format_snapshot(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return "(no market snapshot available)"
    return json.dumps(snapshot, indent=2, default=str)


def format_analyst_block(analyst_outputs: dict[str, str]) -> str:
    if not analyst_outputs:
        return "(no analyst input yet)"
    parts = []
    for name, text in analyst_outputs.items():
        parts.append(f"[{name}]\n{text.strip()}")
    return "\n\n".join(parts)


def persona_user_message(
    ticker: str,
    snapshot: dict[str, Any] | None,
    analyst_outputs: dict[str, str],
    user_prompt: str | None,
) -> str:
    framing = (user_prompt or "").strip()
    return (
        f"Research target: {ticker}\n\n"
        f"Market snapshot (from our data layer):\n{format_snapshot(snapshot)}\n\n"
        f"Analyst inputs:\n{format_analyst_block(analyst_outputs)}\n\n"
        f"User framing: {framing or '(none)'}\n\n"
        "Write a concise investment memo as yourself. Use this structure:\n"
        "  - Thesis (two sentences)\n"
        "  - Business (what it does, moat, management)\n"
        "  - Numbers (the ratios that matter and what they say)\n"
        "  - Risks (the specific risks YOU worry about)\n"
        "  - Verdict (buy, watchlist, or pass — and the one condition that\n"
        "    would change your mind)\n\n"
        "Keep it under 500 words. Markdown is fine. Paraphrase your style; do\n"
        "not put direct quotes in the investor's mouth."
    )


def analyst_user_message(
    kind: str,
    ticker: str,
    snapshot: dict[str, Any] | None,
) -> str:
    return (
        f"Research target: {ticker}\n\n"
        f"Market snapshot:\n{format_snapshot(snapshot)}\n\n"
        f"Write a concise {kind} analysis (2–4 short paragraphs, markdown OK).\n"
        "Focus on the two or three things the downstream portfolio manager\n"
        "actually needs. If the data is missing, say so rather than inventing\n"
        "numbers."
    )


def format_transcript(turns: list[tuple[str, str]]) -> str:
    if not turns:
        return "(no turns yet)"
    return "\n\n".join(f"## {role}\n{text.strip()}" for role, text in turns)


def moderator_user_message(
    ticker: str,
    snapshot: dict[str, Any] | None,
    user_prompt: str | None,
) -> str:
    framing = (user_prompt or "").strip()
    return (
        f"Ticker: {ticker}\n\n"
        f"Market snapshot:\n{format_snapshot(snapshot)}\n\n"
        f"User framing: {framing or '(none)'}\n\n"
        "Open the committee meeting."
    )


def committee_persona_user_message(
    ticker: str,
    snapshot: dict[str, Any] | None,
    turns: list[tuple[str, str]],
    user_prompt: str | None,
) -> str:
    framing = (user_prompt or "").strip()
    return (
        f"Committee meeting on {ticker}.\n\n"
        f"Market snapshot:\n{format_snapshot(snapshot)}\n\n"
        f"User framing: {framing or '(none)'}\n\n"
        f"Transcript so far:\n{format_transcript(turns)}\n\n"
        "It is your turn. Respond as yourself in 120–180 words. Engage with\n"
        "the prior speakers' arguments where it sharpens your own. Do not\n"
        "restate the snapshot. Paraphrase; do not put direct quotes in the\n"
        "real investor's mouth."
    )


def risk_user_message(
    ticker: str,
    snapshot: dict[str, Any] | None,
    turns: list[tuple[str, str]],
) -> str:
    return (
        f"Committee meeting on {ticker}.\n\n"
        f"Market snapshot:\n{format_snapshot(snapshot)}\n\n"
        f"Transcript so far:\n{format_transcript(turns)}\n\n"
        "You are the risk officer. Interject."
    )


def pm_user_message(
    ticker: str,
    snapshot: dict[str, Any] | None,
    turns: list[tuple[str, str]],
    user_prompt: str | None,
) -> str:
    framing = (user_prompt or "").strip()
    return (
        f"Committee meeting on {ticker}.\n\n"
        f"Market snapshot:\n{format_snapshot(snapshot)}\n\n"
        f"User framing: {framing or '(none)'}\n\n"
        f"Transcript:\n{format_transcript(turns)}\n\n"
        "You are the PM. Close the meeting."
    )
