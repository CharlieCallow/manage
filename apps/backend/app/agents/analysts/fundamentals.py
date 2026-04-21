"""Fundamentals analyst. CLAUDE.md §5, §13."""
from __future__ import annotations

from pathlib import Path

from app.agents.base import AgentContext, LLMAgent
from app.agents.prompt import analyst_user_message

PROMPT_PATH = Path(__file__).with_suffix(".md")


def default_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


class FundamentalsAnalyst(LLMAgent):
    def __init__(self, model: str, prompt_template: str) -> None:
        super().__init__(
            name="fundamentals", model=model, prompt_template=prompt_template
        )

    def build_user_message(self, ctx: AgentContext) -> str:
        return analyst_user_message(
            kind="fundamentals",
            ticker=ctx.ticker or "(unspecified)",
            snapshot=ctx.snapshot,
        )
