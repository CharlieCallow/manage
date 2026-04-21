"""Risk analyst. In committee, interjects after the personas. CLAUDE.md §6."""
from __future__ import annotations

from pathlib import Path

from app.agents.base import AgentContext, LLMAgent
from app.agents.prompt import risk_user_message

PROMPT_PATH = Path(__file__).with_suffix(".md")


def default_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


class RiskAnalyst(LLMAgent):
    def __init__(self, model: str, prompt_template: str) -> None:
        super().__init__(name="risk", model=model, prompt_template=prompt_template)

    def build_user_message(self, ctx: AgentContext) -> str:
        turns = [(t.role, t.text) for t in ctx.transcript]
        return risk_user_message(
            ticker=ctx.ticker or "(unspecified)",
            snapshot=ctx.snapshot,
            turns=turns,
        )
