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
    style: str = "classic",
) -> str:
    framing = (user_prompt or "").strip()
    context = (
        f"Research target: {ticker}\n\n"
        f"Market snapshot (from our data layer):\n{format_snapshot(snapshot)}\n\n"
        f"Analyst inputs:\n{format_analyst_block(analyst_outputs)}\n\n"
        f"PM framing: {framing or '(none)'}\n\n"
    )

    if style == "citrini":
        return context + _CITRINI_INSTRUCTIONS
    return context + _CLASSIC_INSTRUCTIONS


_CLASSIC_INSTRUCTIONS = """\
Write a full sell-side-style initiation memo, in your own voice. Markdown.
Paraphrase the investor's style — do NOT put direct quotes in their mouth.
Stay grounded in the snapshot and the analysts' numbers; say "unknown" if a
figure isn't there rather than inventing one.

Structure — use these exact section headings and machine-readable fields at
the top so the app can parse your call:

---

# {Persona} · {Ticker} — Initiation

**Rating:** <BUY | OVERWEIGHT | HOLD | NEUTRAL | UNDERWEIGHT | SELL>
**Base target:** $<number>
**Bull target:** $<number>
**Bear target:** $<number>
**Horizon:** 12 months

## Executive summary
Two to four sentences. Lead with your conclusion.

## Investment thesis
Three short pillars — each one sentence or two, ideally one concrete
number. Then:

### What the market is missing
One paragraph. The specific mispricing — why your view isn't already
consensus.

### Catalysts (12–18 months)
Bullet list of three to five dated catalysts.

## Bull / Base / Bear
### Bull — $<number>
What the world looks like if it works. Assign an approximate probability.

### Base — $<number>
Your central scenario. Approximate probability.

### Bear — $<number>
What goes wrong. Approximate probability.

## Business
What the company does, how it makes money, the moat, management quality.

## Industry & competitive position
Sector dynamics, where this name sits, the one or two rivals that matter.

## Valuation
Triangulate two ways: a quick DCF view (qualitative, with the key
assumptions you'd need to believe) and a comps view (trading multiples vs.
peers / history). Resolve to a target range.

## Risks
Three to five specific risks. Not boilerplate — what you'd actually worry
about.

## What would change my mind
One sentence. The single observable that flips the rating.

---

Aim for 600–900 words total. Keep paragraphs tight. No filler.
"""


_CITRINI_INSTRUCTIONS = """\
Write a thematic, narrative-driven research note in the house style of
Citrini Research. The ticker is your anchor, not your prison — start from
the mega-trend it lives inside and end with a concrete long/short basket.

House style notes:
- First-person voice, in your own investor persona. Paraphrase; never
  quote.
- Narrative spine. Open with a short story, an analogy, or an
  observation from the tape. Earn the reader's attention in the first
  paragraph.
- Chart-heavy tone even though you can't draw one — reference specific
  numbers from the snapshot so the reader can picture the move.
- Contrarian where warranted. Name the consensus view and why you think
  it's wrong. Be specific.
- No boilerplate. If a section has nothing distinctive to say, cut it.
- Construct a real basket at the end — long legs and short legs, with
  approximate weights. The primary ticker is one leg of the long side;
  the shorts are the companies that get run over if your thesis plays
  out. Use plausible real tickers from the same theme.

Structure — use these exact headings and put the machine-readable fields
at the very top so the app can parse your call:

---

# {Persona} · {Theme / basket name}

**Style:** citrini
**Anchor:** <PRIMARY_TICKER>
**Rating:** <BUY | OVERWEIGHT | HOLD | NEUTRAL | UNDERWEIGHT | SELL>
**Base target:** $<number>
**Bull target:** $<number>
**Bear target:** $<number>
**Horizon:** 12 months

## The trade
Two to four sentences. The thesis in plain language, the basket shape
(e.g. "long AI infra, short SaaS-below-the-line"), and why now.

## Why the consensus is wrong
One or two paragraphs. Name the consensus view specifically — what
everyone on FinTwit has decided — and lay out your evidence that it's
mispriced.

## The setup
The macro and tape context. Use the snapshot numbers. Reference the
moving-average structure, the drawdown, the factor regime, the
positioning data when you have it.

## Scenarios
### Bull ($<number>) — <probability>%
What unfolds if the theme works.

### Base ($<number>) — <probability>%
Your central path.

### Bear ($<number>) — <probability>%
The specific mechanism of failure.

## Basket

Emit EXACTLY this machine-readable block — one ticker per line, weights
in percentage points. Use real tickers.

```
BASKET
LONG: <TKR1> <weight>%
LONG: <TKR2> <weight>%
LONG: <TKR3> <weight>%
SHORT: <TKR1> <weight>%
SHORT: <TKR2> <weight>%
```

Then two or three sentences on *why these specific names*, not generic
"peers."

## Catalysts
Three to five dated events that move this trade.

## Risks
The specific ways this loses money. Crowding, factor reversal, macro
regime change, idiosyncratic blow-ups — whichever actually apply.

## What would change my mind
One sentence. The single observable that flips the trade.

---

Aim for 700–1000 words. Narrative paragraphs, short and punchy. No
hedging for the sake of hedging.
"""


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
